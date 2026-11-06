"""
萬星·词元 (Ciyuan) TTS helper for litellm-bridge.

Calls the ciyuan lane `POST /v1/audio/speech` (OpenAI audio shape) and writes
the returned audio stream to disk. Result dict mirrors the volcengine path:
{ok, provider, model, voice, text, local_path, file_size_bytes,
 audio_duration_seconds, api_latency_ms, captions_source?, captions_path?,
 segments?}

实测白名单（2026-10-16，VAAS 专用账号真调；2026-11-06 腾讯档复核）：
  可用: qwen3-tts-flash（voice 例 Cherry）、tencent-tts（数字音色 ID，如 101001）
  不可用: tts-1 → 502 lane_upstream_error(429)；
          gpt-4o-mini-audio-preview / speech-1.6 → 503 无上游账号
换模型前先实调——/v1/models 列的是「可识别」不是「可服务」。

出口层能力（add-tts-caption-fallback D2 的 python 腿回灌，deliver-hosted-surface W2；
与 node 腿 generators/tts.js 同算法同语义，spec ciyuan-lane-providers「语音车道」）：
  - 腾讯 TTS 单次请求长度墙 ~170 字（165 通/170 挂，超限 502 且触发上游熔断
    摘除约 5 分钟）→ 超长文本按句切段（≤150 字）逐段合成 + ffmpeg 拼接
    （段间 0.22s 静音），段级 ffprobe 实测时长锚定 captions 时间轴。
  - 段级重试 3 次（退避 1.5s/3s）；段间调用有间隔（防连环失败扩大熔断）；
    任一段最终失败 → 整体失败，MUST NOT 产出残缺音频。
  - 无官方逐字戳（词元档常态）→ 合成字幕兜底：token 均分 + 实测时长线性缩放，
    末帧钉实测总时长；captions_source=synthetic 随结果返回。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── 长度墙与分段纪律（实测钉死，勿凭感觉调参）─────────────────────────────
SEGMENT_MAX_CHARS = 150          # 165 通 / 170 挂；150 留安全余量
RETRY_MAX = 3
RETRY_BACKOFF_S = (1.5, 3.0)
INTER_SEG_GAP_SECONDS = 0.22     # 段间静音（自然句间停顿）
SEG_CALL_GAP_S = 0.3             # 段与段之间的调用间隔（熔断保护）
SYNTHETIC_BASE_SECONDS_PER_TOKEN = 0.22  # 缩放基准初值，实测时长线性覆盖

# 可透传给上游的音频容器（OpenAI audio 形状）
UPSTREAM_FORMATS = ("mp3", "wav", "opus", "aac", "flac", "pcm")


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def split_text_into_segments(text: str, max_chars: int = SEGMENT_MAX_CHARS) -> list[str]:
    """按句切（。！？；），过长的句按逗号/字数硬切；换行强制分段。与 node 腿同算法。"""
    sentences: list[str] = []
    buf = ""
    for ch in text:
        if ch in ("\n", "\r"):
            if buf.strip():
                sentences.append(buf.strip())
            buf = ""
            continue
        buf += ch
        if ch in "。！？；":
            if buf.strip():
                sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())

    def hard_split(s: str) -> list[str]:
        parts: list[str] = []
        cur = ""
        for ch in s:
            cur += ch
            if (len(cur) >= max_chars and ch in "，、：") or len(cur) >= max_chars:
                parts.append(cur)
                cur = ""
        if cur.strip():
            parts.append(cur)
        return parts

    segments: list[str] = []
    cur = ""
    for s in sentences:
        if len(s) > max_chars:
            if cur.strip():
                segments.append(cur.strip())
                cur = ""
            segments.extend(hard_split(s))
            continue
        if len(cur + s) > max_chars:
            if cur.strip():
                segments.append(cur.strip())
            cur = s
        else:
            cur += s
    if cur.strip():
        segments.append(cur.strip())
    return segments


def split_text_into_tokens(text: str) -> list[str]:
    """中文按字、标点并入前字、Latin 连续词元整体一个 token（node 腿同算法）。"""
    tokens: list[str] = []
    latin = ""
    for ch in text:
        if ch in ("\n", "\r"):
            if latin:
                tokens.append(latin)
                latin = ""
            continue
        if ch.isascii() and (ch.isalnum() or ch in "@._-/+"):
            latin += ch
            continue
        if latin:
            tokens.append(latin)
            latin = ""
        if ch in "，。！？；、：":
            if tokens:
                tokens[-1] += ch
            else:
                tokens.append(ch)
            continue
        if ch == " ":
            continue
        tokens.append(ch)
    if latin:
        tokens.append(latin)
    return tokens


def _probe_duration_seconds(path: str) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return None
        d = float(r.stdout.strip())
        return d if d > 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _build_segmented_captions(segments: list[str], seg_durations: list[float],
                              gap_seconds: float) -> list[dict]:
    """段级 token 均分于段实测时长；段间静音推进时间轴（node 腿同算法）。"""
    caps: list[dict] = []
    cursor = 0.0
    for i, seg in enumerate(segments):
        tokens = split_text_into_tokens(seg)
        if not tokens:
            continue
        seg_ms = (seg_durations[i] or 0) * 1000
        per = seg_ms / len(tokens)
        for tok in tokens:
            start = round(cursor)
            end = round(cursor + per)
            caps.append({
                "text": tok, "startMs": start, "endMs": end,
                "timestampMs": round((start + end) / 2), "confidence": None,
            })
            cursor += per
        if i < len(segments) - 1:
            cursor += gap_seconds * 1000
    return caps


def _synth_one_segment(*, text: str, model: str, voice: str, speed: float | None,
                       fmt: str, api_key: str, base_url: str, output_path: str) -> dict:
    """单次请求合成（≤150 字；调用方保证）。返回该段的字节/延迟信息。"""
    payload: dict = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": fmt if fmt in UPSTREAM_FORMATS else "wav",
    }
    if speed is not None:
        payload["speed"] = speed

    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=_headers(api_key),
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            audio_bytes = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"ciyuan TTS failed (HTTP {e.code}): {body}") from e

    # 200 ≠ 成功：上游网页缺陷会把 HTML 当 200 返回，必须校验内容类型。
    if "audio" not in content_type.lower():
        raise RuntimeError(
            f"ciyuan TTS returned non-audio response (Content-Type: {content_type}); "
            f"model '{model}' is likely not routable on the audio lane"
        )
    if not audio_bytes:
        raise RuntimeError("ciyuan TTS returned empty audio")

    with open(output_path, "wb") as f:
        f.write(audio_bytes)
    return {"file_size_bytes": len(audio_bytes),
            "api_latency_ms": round((time.time() - start) * 1000)}


def _concat_segments(seg_files: list[str], final_path: str, seg_dir: str) -> None:
    """mp3 段间垫静音拼接（node 腿同纪律：anullsrc gap + concat demuxer）。"""
    if len(seg_files) == 1:
        shutil.copyfile(seg_files[0], final_path)
        return
    gap = Path(seg_dir) / "gap.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", str(INTER_SEG_GAP_SECONDS), "-codec:a", "libmp3lame", "-q:a", "4", str(gap)],
        capture_output=True, timeout=60,
    )
    list_file = Path(seg_dir) / "concat.txt"
    lines: list[str] = []
    for i, f in enumerate(seg_files):
        lines.append(f"file '{f}'")
        if i < len(seg_files) - 1:
            lines.append(f"file '{gap}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cc = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-codec:a", "libmp3lame", "-q:a", "4", final_path],
        capture_output=True, text=True, timeout=300,
    )
    if cc.returncode != 0:
        raise RuntimeError(f"segment concat failed: {(cc.stderr or '')[-200:]}")


def synthesize(
    *,
    text: str,
    model: str,
    voice: str,
    speed: float | None,
    format: str,
    enable_subtitle: bool,
    api_key: str,
    base_url: str,
    output_path,
    captions_path=None,
) -> dict:
    """词元 TTS 出口层：长度墙分段 + 段级实测字幕兜底（D2 python 腿回灌）。

    短文本走单次请求（行为与历史一致）；超长文本自动分段，调用方零感知。
    captions：无官方逐字戳（词元档常态）→ 合成兜底，captions_source=synthetic。
    """
    if not api_key:
        raise ValueError("CIYUAN_API_KEY is required for ciyuan TTS")
    if not base_url:
        raise ValueError("CIYUAN_BASE_URL is required for ciyuan TTS")

    fmt = format if format in UPSTREAM_FORMATS else "wav"
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    start = time.time()

    segments = split_text_into_segments(text)
    multi = len(segments) > 1

    if multi:
        # 分段纪律：逐段重试退避 + 段间调用间隔；任一段最终失败 → 整体失败
        #（不产残缺音频，MUST NOT 伪装成功）。
        with tempfile.TemporaryDirectory(prefix="tts-seg-") as seg_dir:
            seg_files: list[str] = []
            for i, seg in enumerate(segments):
                seg_path = str(Path(seg_dir) / f"s{i:03d}.mp3")
                done = False
                last_err = ""
                for attempt in range(1, RETRY_MAX + 1):
                    try:
                        _synth_one_segment(text=seg, model=model, voice=voice, speed=speed,
                                           fmt="mp3", api_key=api_key, base_url=base_url,
                                           output_path=seg_path)
                        done = True
                        break
                    except RuntimeError as e:
                        last_err = str(e)[:300]
                        if attempt < RETRY_MAX:
                            time.sleep(RETRY_BACKOFF_S[min(attempt - 1, len(RETRY_BACKOFF_S) - 1)])
                if not done:
                    raise RuntimeError(
                        f"ciyuan TTS segment {i + 1}/{len(segments)} failed after "
                        f"{RETRY_MAX} attempts: {last_err}"
                    )
                seg_files.append(seg_path)
                if i < len(segments) - 1:
                    time.sleep(SEG_CALL_GAP_S)  # 熔断保护：段间调用有间隔

            _concat_segments(seg_files, output_path, seg_dir)
            seg_durations = [_probe_duration_seconds(f) or 0.0 for f in seg_files]
            caps = _build_segmented_captions(segments, seg_durations, INTER_SEG_GAP_SECONDS)
    else:
        _synth_one_segment(text=text, model=model, voice=voice, speed=speed,
                           fmt=fmt, api_key=api_key, base_url=base_url,
                           output_path=output_path)
        caps = None
        segments = [text]

    result = {
        "ok": True,
        "provider": "ciyuan",
        "model": model,
        "voice": voice,
        "text": text,
        "local_path": output_path,
        "file_size_bytes": Path(output_path).stat().st_size,
        "api_latency_ms": round((time.time() - start) * 1000),
        "segments": len(segments),
    }

    # 合成字幕兜底（无官方逐字戳，词元档常态）：段级实测锚定 + token 均分；
    # 短文本单段路径按总实测时长线性缩放，末帧钉实测总时长。
    real_sec = _probe_duration_seconds(output_path)
    if enable_subtitle or captions_path:
        if caps is None:
            caps = _build_segmented_captions([text], [real_sec or 0.0], 0.0)
        if caps and captions_path:
            cap_path = Path(captions_path)
            cap_path.parent.mkdir(parents=True, exist_ok=True)
            cap_path.write_text(json.dumps(caps, ensure_ascii=False, indent=2), encoding="utf-8")
            result["captions_path"] = str(cap_path)
            result["captions_count"] = len(caps)
        result["captions_source"] = "synthetic" if caps else "none"

    if real_sec:
        result["audio_duration_seconds"] = real_sec  # 实测值（契约：never upstream-claimed）
    return result

"""
Typed-scene 分段/对齐/字幕底座（add-typed-video-html-renderer W1.2）。

把口播稿变成带真实时长的 Segment 序列，供 builder 产出 seek 契约场景：

  Segment = {name, text, duration_s, sentences: [{text, start, end}]}
    name       — `## 段名`（无标记时整篇单段 "main"；结构数对照（1 hook +
                 N 要点 + 1 cta 等）由各 builder 按 type.json inputs.desc 校验）
    duration_s — 段时长（秒）。TTS 路径 = 逐段 synthesize 实测（口径与
                 generate_voice 一致，来自产物文件而非上游元数据）；voice_path
                 路径 = ffprobe 总时长按段字符数加权分摊（不发起 TTS、不解析
                 生成凭证）。
    sentences  — 段内句子切分（。！？!? 与换行为界），时长按字符数比例分摊，
                 start/end 相对段首（场景时长 == 段时长，句级字幕直接用场景
                 本地 t 查表）。

tailPad 帧垫沿用 type.json defaults（默认 15 frames @30fps = 0.5s），垫在
末场景之后（apply_tail_pad）：compose 的 -shortest 以较短一侧收尾，尾垫保证
最后一句不被吃掉。

TTS 底座：逐段调 generators/tts.synthesize（分段合成、manifest 语音硬校验、
idempotency_key 重放）——凭证链与 generate_voice 同源（prepare("tts") →
resolve("tts")，hosted 凭据经 subprocess_env 注入 bridge 子进程，本模块不做
任何额外接线）。
"""

import re
import subprocess
from pathlib import Path
from typing import Optional, TypedDict

from ...utils import DOWNLOADS_DIR, VAAS_ROOT

FPS_DEFAULT = 30
TAIL_PAD_FRAMES_DEFAULT = 15  # type.json defaults.tailPad 缺省值

_SENTENCE_END = "。！？!?"


class Sentence(TypedDict):
    text: str
    start: float
    end: float


class Segment(TypedDict):
    name: str
    text: str
    duration_s: float
    sentences: list


class TtsSegment(Segment, total=False):
    """align_tts 产物：额外携带逐段 TTS 资产（downloads 相对路径）。"""

    audio_path: str


# ─── 分段 ──────────────────────────────────────────────────────────────────

_SECTION_RE = re.compile(r"^##\s*(.*)$")


def split_script(script: str) -> list[dict]:
    """口播稿 → [{name, text}]：`## 段名` 分段；无段名整篇为单段（"main"）。

    空段（只有标题没有正文）丢弃；全空 → ValueError（结构校验交给各 builder
    按 type.json inputs.desc 报对照差异，这里只挡「无内容可渲」）。
    """
    if not script or not script.strip():
        raise ValueError("script is empty — render_video(type=...) requires 口播稿文本或路径")
    sections: list[dict] = []
    for line in script.splitlines():
        m = _SECTION_RE.match(line.strip())
        if m:
            sections.append({"name": m.group(1).strip() or "main", "lines": []})
        else:
            if not sections:
                sections.append({"name": "main", "lines": []})
            sections[-1]["lines"].append(line)
    out = [{"name": s["name"], "text": "\n".join(s["lines"]).strip()}
           for s in sections]
    out = [s for s in out if s["text"]]
    if not out:
        raise ValueError("script 分段结果为空（只有 `##` 标题没有正文）")
    return out


def skeleton_segments(raw: list[dict]) -> list[Segment]:
    """split_script 产物 → 骨架 Segment（duration 0、无句表）。

    builder.validate_inputs 的结构数对照不需要时长，在 TTS 花费之前以骨架
    调用即可完成「渲染前、零产物」校验。
    """
    return [{"name": s["name"], "text": s["text"],
             "duration_s": 0.0, "sentences": []} for s in raw]


# ─── 句子切分与比例分摊 ─────────────────────────────────────────────────────

def split_sentences(text: str) -> list[str]:
    """段内句子切分（。！？!? 与换行为界，标点归属前句；空句丢弃）。"""
    parts: list[str] = []
    buf = ""
    for ch in text:
        if ch == "\n":
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
        elif ch in _SENTENCE_END:
            buf += ch
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts or ([text.strip()] if text.strip() else [])


def _weighted(parts: list[str], total_s: float) -> list[float]:
    """按字符数把 total_s 分摊到各部分（累计取整，末项吃余量，总和恰等）。"""
    weights = [max(1, len(p)) for p in parts]
    total_w = float(sum(weights))
    ends = []
    acc = 0.0
    for w in weights:
        acc += w
        ends.append(round(total_s * acc / total_w, 4))
    spans = []
    prev = 0.0
    for i, e in enumerate(ends):
        spans.append(round(e - prev, 4) if i < len(ends) - 1
                     else round(total_s - prev, 4))
        prev = e
    return spans


def _sentences_with_timings(text: str, duration_s: float) -> list[Sentence]:
    parts = split_sentences(text)
    if not parts:
        return []
    spans = _weighted(parts, float(duration_s))
    out: list[Sentence] = []
    start = 0.0
    for p, d in zip(parts, spans):
        out.append({"text": p, "start": round(start, 4),
                    "end": round(start + d, 4)})
        start += d
    return out


# ─── 对齐路径一：voice_path（ffprobe 总时长按字符数加权分摊） ────────────────

def _resolve_file(p: str) -> Path:
    """与 render._resolve_input_file 同一信任级别：绝对直用，相对按序试
    （原样 → downloads/ 相对 → VAAS_ROOT 相对）。"""
    path = Path(p).expanduser()
    if path.is_absolute():
        return path
    for base in (None, DOWNLOADS_DIR, VAAS_ROOT):
        cand = path if base is None else base / path
        if cand.is_file():
            return cand
    return path


def _ffprobe_seconds(path: Path) -> Optional[float]:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        try:
            return float(r.stdout.strip())
        except ValueError:
            return None
    return None


def align_voice_path(voice_path: str, segments: list[dict]) -> list[Segment]:
    """voice_path 已有音频：ffprobe 总时长按段字符数加权分摊。

    不发起任何 TTS、不解析生成凭证（本地确定性重放路径）。
    """
    p = _resolve_file(voice_path)
    if not p.is_file():
        raise ValueError(f"voice file missing: {voice_path}")
    total_s = _ffprobe_seconds(p)
    if not total_s or total_s <= 0:
        raise RuntimeError(f"cannot measure voice duration: {voice_path}")
    spans = _weighted([s["text"] for s in segments], total_s)
    out: list[Segment] = []
    for seg, d in zip(segments, spans):
        out.append({"name": seg["name"], "text": seg["text"],
                    "duration_s": d,
                    "sentences": _sentences_with_timings(seg["text"], d)})
    return out


# ─── 对齐路径二：逐段 TTS（真实段时长） ─────────────────────────────────────

def align_tts(segments: list[dict], voice: Optional[str] = None,
              speed: Optional[float] = None, format: str = "mp3",
              idem_base: Optional[str] = None) -> list[TtsSegment]:
    """逐段调 generators/tts.synthesize 取真实段时长。

    idem_base（计划键）派生每段 idempotency_key（<base>-seg<i>）：同计划重跑
    返回既有资产，不重新合成、不重复计费。语音硬校验/idempotency 重放/凭证
    链全部沿用 synthesize 底座（与 generate_voice 同源）。
    """
    from ...generators.tts import synthesize, _probe_duration_seconds

    out: list[TtsSegment] = []
    for i, seg in enumerate(segments):
        idem = f"{idem_base}-seg{i}" if idem_base else None
        res = synthesize(text=seg["text"], voice=voice, speed=speed,
                         format=format, idempotency_key=idem)
        duration_ms = res.get("duration_ms")
        if not duration_ms:
            # 防御：历史资产行缺 duration_ms 时从产物文件实测（不信任上游）
            abs_p = _resolve_file(res["file_path"])
            duration_ms = round(_probe_duration_seconds(str(abs_p), format) * 1000)
        duration_s = round(duration_ms / 1000.0, 4)
        out.append({"name": seg["name"], "text": seg["text"],
                    "duration_s": duration_s,
                    "sentences": _sentences_with_timings(seg["text"], duration_s),
                    "audio_path": res["file_path"]})
    return out


# ─── 全轨拼接 + tailPad 帧垫 ────────────────────────────────────────────────

_REENCODE_BY_EXT = {
    ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    ".wav": ["-c:a", "pcm_s16le"],
}


def concat_audio(audio_paths: list[str], out_path: Path) -> Path:
    """按序拼接逐段音频 → 单一全轨（compose 的 -shortest 契约吃单文件）。

    ffmpeg concat demuxer；-c copy 失败（段间参数不一致等）回退按扩展名重
    编码。段路径可为 downloads 相对（TTS 产物口径）。
    """
    if not audio_paths:
        raise ValueError("concat_audio: no segment audio given")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_path.with_name(out_path.stem + ".concat.txt")
    lines = []
    for p in audio_paths:
        abs_p = _resolve_file(p)
        if not abs_p.is_file():
            raise ValueError(f"segment audio missing: {p}")
        lines.append("file '" + str(abs_p).replace("'", "'\\''") + "'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
               "-i", str(list_file), "-c", "copy", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not out_path.exists():
            fallback = _REENCODE_BY_EXT.get(out_path.suffix.lower(),
                                            _REENCODE_BY_EXT[".mp3"])
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                   "-i", str(list_file), *fallback, str(out_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0 or not out_path.exists():
                raise RuntimeError(f"ffmpeg concat failed: {proc.stderr[-400:]}")
    finally:
        list_file.unlink(missing_ok=True)
    return out_path


def apply_tail_pad(scenes: list[dict], frames: int,
                   fps: int = FPS_DEFAULT) -> list[dict]:
    """tailPad 帧垫（type.json defaults，默认 15 frames）：末场景时长追加
    frames/fps 秒。返回新 list（不动 builder 产物）；空场景原样返回。
    """
    if not scenes or frames <= 0:
        return scenes
    out = [dict(s) for s in scenes]
    out[-1]["duration_s"] = round(float(out[-1]["duration_s"]) + frames / fps, 4)
    return out

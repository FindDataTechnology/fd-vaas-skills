"""
萬星·词元 (Ciyuan) TTS helper for litellm-bridge.

Calls the ciyuan lane `POST /v1/audio/speech` (OpenAI audio shape) and writes
the returned audio stream to disk. Result dict mirrors the volcengine path:
{ok, provider, model, voice, text, local_path, file_size_bytes,
 audio_duration_seconds?, api_latency_ms}

实测白名单（2026-10-16，VAAS 专用账号 user94 真调）：
  可用: qwen3-tts-flash（voice 例 Cherry）→ 200，RIFF WAV
  不可用: tts-1 → 502 lane_upstream_error(429)；
          gpt-4o-mini-audio-preview / speech-1.6 → 503 无上游账号
换模型前先实调——/v1/models 列的是「可识别」不是「可服务」。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


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
) -> dict:
    if not api_key:
        raise ValueError("CIYUAN_API_KEY is required for ciyuan TTS")
    if not base_url:
        raise ValueError("CIYUAN_BASE_URL is required for ciyuan TTS (e.g. https://router.finddatatech.cloud)")

    start = time.time()
    payload: dict = {
        "model": model,
        "input": text,
        "voice": voice or "Cherry",
        "response_format": format if format in ("mp3", "wav", "opus", "aac", "flac", "pcm") else "wav",
    }
    if speed is not None:
        payload["speed"] = speed

    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
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

    output_path = str(output_path)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    result = {
        "ok": True,
        "provider": "ciyuan",
        "model": model,
        "voice": voice or "Cherry",
        "text": text,
        "local_path": output_path,
        "file_size_bytes": len(audio_bytes),
        "api_latency_ms": round((time.time() - start) * 1000),
    }
    # 字幕（逐字时间戳）是 volcengine 直连专属能力；ciyuan 车道无此契约，
    # enable_subtitle 在此档不可用（bridge 层负责向用户如实说明）。
    return result

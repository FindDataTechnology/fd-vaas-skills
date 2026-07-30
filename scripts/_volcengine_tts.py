"""
Volcengine ByteDance TTS helper for litellm-bridge.

Calls openspeech.bytedance.com Agent Plan TTS API directly,
matching the behavior of byted-ark-tts-skill/scripts/tts.js.

Returns a result dict with the same shape as the litellm path:
{ok, model, voice, text, local_path, file_size_bytes,
 audio_duration_seconds?, captions?, api_latency_ms}
"""

from __future__ import annotations

import base64
import json
import time
import urllib.request
import urllib.error


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
        raise ValueError("VOLC_AGENT_API_KEY or ARK_API_KEY is required for volcengine TTS")

    start = time.time()

    audio_params: dict = {
        "format": format,
        "sample_rate": 24000,
        "enable_subtitle": enable_subtitle,
    }
    if speed is not None:
        audio_params["speed_ratio"] = max(0.2, min(3.0, float(speed)))

    body = {
        "req_params": {
            "speaker": voice,
            "text": text,
            "audio_params": audio_params,
        }
    }

    url = base_url.rstrip("/") + "/unidirectional"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": model,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TTS HTTP {e.code}: {err_body[:500]}") from e

    # Parse chunked JSON response
    audio_b64_chunks: list[str] = []
    sentences: list[dict] = []
    for obj in _extract_json_objects(raw):
        if isinstance(obj, dict):
            if isinstance(obj.get("data"), str) and obj["data"]:
                audio_b64_chunks.append(obj["data"])
            if isinstance(obj.get("sentence"), dict):
                sentences.append(obj["sentence"])

    if not audio_b64_chunks:
        # fallback: regex capture
        import re

        for m in re.finditer(r'"data"\s*:\s*"([A-Za-z0-9+/=]+)"', raw):
            audio_b64_chunks.append(m.group(1))

    if not audio_b64_chunks:
        raise RuntimeError(f"No audio data in response. First 300 chars: {raw[:300]}")

    audio_bytes = base64.b64decode("".join(audio_b64_chunks))
    output_path.write_bytes(audio_bytes)

    # Build captions from sentence.words[] (same logic as tts.js)
    captions: list[dict] | None = None
    audio_duration_seconds: float | None = None
    if sentences:
        captions = []
        for s in sentences:
            words = s.get("words", []) if isinstance(s, dict) else []
            for w in words:
                start_ms = round((w.get("startTime", 0) or 0) * 1000)
                end_ms = round((w.get("endTime", w.get("startTime", 0)) or 0) * 1000)
                captions.append(
                    {
                        "text": w.get("word", ""),
                        "startMs": start_ms,
                        "endMs": end_ms,
                        "timestampMs": round((start_ms + end_ms) / 2),
                        "confidence": w.get("confidence"),
                    }
                )
        # Fix Latin token fake endMs (same rule as tts.js)
        for i in range(len(captions) - 1):
            dur = captions[i]["endMs"] - captions[i]["startMs"]
            gap = captions[i + 1]["startMs"] - captions[i]["endMs"]
            if dur < 100 and gap > 100:
                captions[i]["endMs"] = captions[i + 1]["startMs"]
                captions[i]["timestampMs"] = round(
                    (captions[i]["startMs"] + captions[i]["endMs"]) / 2
                )
        if captions:
            audio_duration_seconds = captions[-1]["endMs"] / 1000

    return {
        "ok": True,
        "provider": "volcengine",
        "model": model,
        "voice": voice,
        "text": text,
        "local_path": str(output_path),
        "file_size_bytes": len(audio_bytes),
        "audio_duration_seconds": audio_duration_seconds,
        "captions": captions,
        "api_latency_ms": round((time.time() - start) * 1000),
    }


def _extract_json_objects(text: str) -> list[dict]:
    """Extract top-level JSON objects from a string (chunked response)."""
    out: list[dict] = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                raw = text[start : i + 1]
                try:
                    out.append(json.loads(raw))
                except (json.JSONDecodeError, ValueError):
                    pass
                start = -1
    return out

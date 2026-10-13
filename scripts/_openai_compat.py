"""
OpenAI-compatible HTTP client for litellm-bridge (stdlib only).

Covers the relay caliber (萬星·词元 token.finddatatech.cloud) and any other
OpenAI-compatible endpoint: images (/images/generations) and speech
(/audio/speech). No SDK dependency on purpose — the hosted image stays slim
and the wire format is two POSTs.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def _post(url: str, api_key: str, payload: dict, timeout: int = 300) -> bytes:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from {url}: {body[:400]}") from e


def image_generate(
    *,
    prompt: str,
    model: str,
    api_key: str,
    base_url: str,
    size: str | None,
    output_format: str,
    n: int,
    output_path: Path,
) -> dict:
    """POST /images/generations; save b64/url results to disk."""
    if not api_key:
        raise ValueError("api_key is required for the OpenAI-compatible caliber")

    start = time.time()
    payload: dict = {"model": model, "prompt": prompt, "n": n}
    if size:
        payload["size"] = size
    # Most OpenAI-compatible image endpoints accept b64 output; ask for it so
    # no second fetch is needed.
    payload["response_format"] = "b64_json" if output_format != "url" else "url"

    raw = _post(base_url.rstrip("/") + "/images/generations", api_key, payload)
    data = json.loads(raw.decode("utf-8"))
    items = data.get("data") or []
    if not items:
        raise RuntimeError(f"No image data in response: {raw[:300]}")

    images = []
    for i, item in enumerate(items):
        img_path = output_path
        if len(items) > 1:
            img_path = output_path.with_name(f"{output_path.stem}_{i:02d}{output_path.suffix}")
        if item.get("b64_json"):
            img_path.write_bytes(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            with urllib.request.urlopen(item["url"], timeout=300) as resp:
                img_path.write_bytes(resp.read())
        else:
            continue
        images.append({"local_path": str(img_path), "url": item.get("url")})

    return {
        "ok": True,
        "provider": "openai",
        "model": model,
        "prompt": prompt,
        "size": size,
        "count": len(images),
        "images": images,
        "api_latency_ms": round((time.time() - start) * 1000),
    }


def speech_synthesize(
    *,
    text: str,
    model: str,
    api_key: str,
    base_url: str,
    voice: str,
    output_format: str,
    speed: float | None,
    output_path: Path,
) -> dict:
    """POST /audio/speech; write raw audio bytes."""
    if not api_key:
        raise ValueError("api_key is required for the OpenAI-compatible caliber")

    start = time.time()
    payload: dict = {"model": model, "input": text, "voice": voice}
    if output_format:
        payload["response_format"] = output_format
    if speed is not None:
        payload["speed"] = float(speed)

    raw = _post(base_url.rstrip("/") + "/audio/speech", api_key, payload, timeout=180)
    if raw.lstrip()[:1] == b"{":  # JSON error body with HTTP 200 (relay quirk)
        raise RuntimeError(f"speech endpoint returned JSON: {raw[:300]}")
    output_path.write_bytes(raw)

    return {
        "ok": True,
        "provider": "openai",
        "model": model,
        "voice": voice,
        "local_path": str(output_path),
        "bytes": len(raw),
        "api_latency_ms": round((time.time() - start) * 1000),
    }

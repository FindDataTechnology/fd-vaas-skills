"""
Volcengine ByteDance image generation helper for litellm-bridge.

Calls ark.cn-beijing.volces.com Agent Plan image API directly,
matching a subset of byted-ark-seedream-skill/scripts/seedream.js.

Supports: basic text-to-image, size, output_format.
(For reference images, web search, batch, use the Node skill directly.)
"""

from __future__ import annotations

import base64
import json
import time
import urllib.request
import urllib.error
from pathlib import Path


def generate(
    *,
    prompt: str,
    model: str,
    size: str,
    output_format: str,
    n: int,
    api_key: str,
    base_url: str,
    output_path: Path,
) -> dict:
    if not api_key:
        raise ValueError("VOLC_AGENT_API_KEY or ARK_API_KEY is required for volcengine image")

    start = time.time()

    body = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "output_format": output_format,
        "watermark": False,
    }

    url = base_url.rstrip("/") + "/images/generations"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Image gen HTTP {e.code}: {err_body[:500]}") from e

    images_data = data.get("data", [])
    if not isinstance(images_data, list) or not images_data:
        raise RuntimeError(f"No images in response: {json.dumps(data)[:300]}")

    ext = "png" if output_format.lower() == "png" else "jpg"
    images_out = []
    for i, img in enumerate(images_data):
        img_path = output_path
        if len(images_data) > 1:
            img_path = output_path.with_name(f"{output_path.stem}_{i:02d}.{ext}")

        if img.get("url"):
            _download(img["url"], img_path)
            images_out.append({"local_path": str(img_path), "url": img["url"]})
        elif img.get("b64_json"):
            img_path.write_bytes(base64.b64decode(img["b64_json"]))
            images_out.append({"local_path": str(img_path), "url": None})

    return {
        "ok": True,
        "provider": "volcengine",
        "model": model,
        "prompt": prompt,
        "size": size,
        "count": len(images_out),
        "images": images_out,
        "api_latency_ms": round((time.time() - start) * 1000),
    }


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as resp:
        dest.write_bytes(resp.read())

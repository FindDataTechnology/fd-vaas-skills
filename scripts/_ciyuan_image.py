"""
萬星·词元 (Ciyuan) image helper for litellm-bridge.

Calls the ciyuan lane `POST /v1/images/generations` (OpenAI images shape),
decodes data[].b64_json and writes the bytes to disk. Result dict mirrors the
volcengine path: {ok, provider, model, images:[{local_path, file_size_bytes}], ...}

实测白名单（2026-10-16，VAAS 专用账号 user94 真调）：
  可用: gemini-3-pro-image → 200 合规 JSON，data[].b64_json 解码得真 JPEG
  禁用: gpt-image-1 / gpt-image-2 → HTTP 200 但 Content-Type: text/html
        （openai-next 网页 UI；两个不同 prompt 返回同一 favicon URL——
        不是生成结果，是上游缺陷）；本客户端对非 JSON 应答一律报错，
        绝不从 HTML 里猜图片 URL 充当产物。
        doubao-seedream-* / flux-* / imagen-4 → 400 "requires an image model"
换模型前先实调——/v1/models 列的是「可识别」不是「可服务」。
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request


def generate(
    *,
    prompt: str,
    model: str,
    size: str | None,
    n: int,
    output_paths: list,  # one path per image
    api_key: str,
    base_url: str,
    extra: dict | None = None,
) -> dict:
    if not api_key:
        raise ValueError("CIYUAN_API_KEY is required for ciyuan image")
    if not base_url:
        raise ValueError("CIYUAN_BASE_URL is required for ciyuan image (e.g. https://router.finddatatech.cloud)")
    if not output_paths:
        raise ValueError("output_paths must contain at least one path")

    start = time.time()
    payload: dict = {"model": model, "prompt": prompt, "n": max(1, min(n, len(output_paths)))}
    if size:
        payload["size"] = size
    if extra:
        payload.update({k: v for k, v in extra.items() if v is not None})

    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # 明确要 JSON：上游网页缺陷会把 HTML 当 200 返回
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"ciyuan image failed (HTTP {e.code}): {err_body}") from e

    # 200 ≠ 成功：必须校验 Content-Type 与 JSON 可解析性，不能只看状态码。
    if "json" not in content_type.lower():
        raise RuntimeError(
            f"ciyuan image model '{model}' returned non-JSON response "
            f"(Content-Type: {content_type}) — 应答形状不合规，该模型不可用于图像车道"
        )
    try:
        doc = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise RuntimeError(f"ciyuan image response is not valid JSON: {e}") from e

    items = doc.get("data") or []
    if not items:
        raise RuntimeError(f"ciyuan image returned no data items: {json.dumps(doc)[:300]}")

    images = []
    for i, item in enumerate(items[: len(output_paths)]):
        b64 = item.get("b64_json")
        if not b64:
            # b64 形态缺失（如只有 url）不在本车道契约内，如实报错而非猜
            raise RuntimeError(
                "ciyuan image item has no b64_json (keys: "
                f"{sorted(item.keys())}) — 仅支持 b64_json 形态"
            )
        raw = base64.b64decode(b64)
        path = str(output_paths[i])
        with open(path, "wb") as f:
            f.write(raw)
        images.append({"local_path": path, "file_size_bytes": len(raw)})

    return {
        "ok": True,
        "provider": "ciyuan",
        "model": model,
        "prompt": prompt,
        "images": images,
        "usage": doc.get("usage"),
        "api_latency_ms": round((time.time() - start) * 1000),
    }

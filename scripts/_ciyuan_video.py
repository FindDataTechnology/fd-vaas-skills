"""
萬星·词元 (Ciyuan) video helper for litellm-bridge.

Async two-step flow (mirrors volcengine bridge semantics — resubmission-safe):
  submit(): POST /v1/contents/generations/tasks → task id (seconds, no waiting)
  poll():   GET  /v1/contents/generations/tasks/<id> → status; on `succeeded`
            downloads content.video_url to the output path.

实测白名单（2026-10-16，VAAS 专用账号 user94 真调）：
  可用: doubao-seedance-2-0-fast-260128 → queued→running→succeeded，真 MP4
  禁用: doubao-seedance-1-0-pro / doubao-seedance-2-5 → 503（上游不可达）；
        veo3.1-fast / sora-2 / kling-* → 404（模型目录挂名但上游无对应路径）
换模型前先实调——/v1/models 列的是「可识别」不是「可服务」。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def submit(
    *,
    prompt: str,
    model: str,
    duration: int | None,
    ratio: str | None,
    resolution: str | None,
    first_frame: str | None,
    last_frame: str | None,
    api_key: str,
    base_url: str,
) -> dict:
    """Create a generation task. Returns {task_id, model, status} — seconds, no polling."""
    if not api_key:
        raise ValueError("CIYUAN_API_KEY is required for ciyuan video")
    if not base_url:
        raise ValueError("CIYUAN_BASE_URL is required for ciyuan video (e.g. https://router.finddatatech.cloud)")

    content: list = [{"type": "text", "text": prompt}]
    if first_frame:
        content.append({"type": "image_url", "image_url": {"url": first_frame}, "role": "first_frame"})
    if last_frame:
        content.append({"type": "image_url", "image_url": {"url": last_frame}, "role": "last_frame"})

    payload: dict = {"model": model, "content": content}
    if duration is not None:
        payload["duration"] = duration
    if ratio:
        payload["ratio"] = ratio
    if resolution:
        payload["resolution"] = resolution

    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/contents/generations/tasks",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=_headers(api_key),
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            doc = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"ciyuan video submit failed (HTTP {e.code}): {body}") from e

    task_id = doc.get("id") or doc.get("task_id")
    if not task_id:
        raise RuntimeError(f"ciyuan video submit returned no task id: {json.dumps(doc)[:300]}")
    return {"task_id": task_id, "model": model, "status": doc.get("status") or "queued"}


def poll(
    *,
    task_id: str,
    api_key: str,
    base_url: str,
    timeout_seconds: int = 600,
    interval_seconds: int = 15,
) -> dict:
    """Poll until terminal. Returns the final task document (caller downloads video_url)."""
    base = base_url.rstrip("/") + "/v1/contents/generations/tasks/" + task_id
    deadline = time.time() + timeout_seconds
    last_doc: dict = {}
    while time.time() < deadline:
        req = urllib.request.Request(base, method="GET", headers=_headers(api_key))
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                last_doc = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"ciyuan video poll failed (HTTP {e.code}): {body}") from e
        status = last_doc.get("status")
        if status in ("succeeded", "failed", "cancelled"):
            return last_doc
        time.sleep(interval_seconds)
    raise RuntimeError(f"ciyuan video poll timed out after {timeout_seconds}s (last status: {last_doc.get('status')})")


def download(*, video_url: str, output_path, timeout_seconds: int = 300) -> dict:
    """Fetch content.video_url bytes to disk (the signed URL is self-authenticating)."""
    req = urllib.request.Request(video_url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        raw = resp.read()
    if not raw:
        raise RuntimeError("ciyuan video download returned empty body")
    path = str(output_path)
    with open(path, "wb") as f:
        f.write(raw)
    return {"local_path": path, "file_size_bytes": len(raw)}


def generate_and_wait(
    *,
    prompt: str,
    model: str,
    duration: int | None,
    ratio: str | None,
    resolution: str | None,
    first_frame: str | None,
    last_frame: str | None,
    api_key: str,
    base_url: str,
    output_path,
    timeout_seconds: int = 600,
) -> dict:
    """Synchronous convenience: submit + poll + download. Result mirrors volcengine shape."""
    start = time.time()
    sub = submit(prompt=prompt, model=model, duration=duration, ratio=ratio,
                 resolution=resolution, first_frame=first_frame, last_frame=last_frame,
                 api_key=api_key, base_url=base_url)
    final = poll(task_id=sub["task_id"], api_key=api_key, base_url=base_url,
                 timeout_seconds=timeout_seconds)
    if final.get("status") != "succeeded":
        raise RuntimeError(
            f"ciyuan video task {sub['task_id']} ended {final.get('status')}: "
            f"{json.dumps(final)[:400]}"
        )
    video_url = (final.get("content") or {}).get("video_url")
    if not video_url:
        raise RuntimeError(f"ciyuan video task succeeded but no video_url: {json.dumps(final)[:400]}")
    dl = download(video_url=video_url, output_path=output_path)
    return {
        "ok": True,
        "provider": "ciyuan",
        "model": model,
        "task_id": sub["task_id"],
        "status": "succeeded",
        **dl,
        "usage": final.get("usage"),
        "api_latency_ms": round((time.time() - start) * 1000),
    }

"""
Volcengine ByteDance video generation helper for litellm-bridge.

Calls ark.cn-beijing.volces.com Agent Plan video API directly.
Simplified version — submit task, optionally poll until done, download result.

For full features (reference media, draft, flex, etc.) use the Node seedance skill.
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from pathlib import Path


def generate(
    *,
    prompt: str,
    model: str,
    duration: int,
    ratio: str,
    resolution: str,
    api_key: str,
    base_url: str,
    output_path: Path,
    wait: bool,
    timeout: int,
) -> dict:
    if not api_key:
        raise ValueError("VOLC_AGENT_API_KEY or ARK_API_KEY is required for volcengine video")

    start = time.time()

    body = {
        "model": model,
        "prompt": prompt,
        "duration": duration,
        "ratio": ratio,
        "resolution": resolution,
    }

    url = base_url.rstrip("/") + "/contents/generations/tasks"
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            task = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Video task HTTP {e.code}: {err_body[:500]}") from e

    task_id = task.get("id") or task.get("task_id") or ""
    if not task_id:
        raise RuntimeError(f"No task id in response: {json.dumps(task)[:300]}")

    result: dict = {
        "ok": True,
        "provider": "volcengine",
        "model": model,
        "prompt": prompt,
        "task_id": task_id,
        "duration_seconds": duration,
        "ratio": ratio,
        "resolution": resolution,
    }

    if not wait:
        result["status"] = "submitted"
        result["api_latency_ms"] = round((time.time() - start) * 1000)
        return result

    # Poll until done or timeout
    deadline = time.time() + timeout
    status_url = base_url.rstrip("/") + f"/contents/generations/tasks/{task_id}"
    final_task = None
    while time.time() < deadline:
        time.sleep(5)
        req2 = urllib.request.Request(
            status_url,
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                final_task = json.loads(resp2.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # transient — keep trying
            if e.code >= 500:
                continue
            raise

        status = _get_task_status(final_task)
        if status in ("succeeded", "completed", "success", "done"):
            break
        if status in ("failed", "error", "cancelled"):
            result["status"] = status
            result["error"] = final_task.get("error", final_task)
            result["api_latency_ms"] = round((time.time() - start) * 1000)
            return result

    if final_task is None:
        result["status"] = "timeout"
        result["api_latency_ms"] = round((time.time() - start) * 1000)
        return result

    status = _get_task_status(final_task)
    result["status"] = status
    result["api_latency_ms"] = round((time.time() - start) * 1000)

    # Download first video output
    outputs = _extract_outputs(final_task)
    if outputs:
        first_url = outputs[0].get("url")
        if first_url:
            try:
                _download(first_url, output_path)
                result["local_path"] = str(output_path)
                result["download_url"] = first_url
            except Exception as e:
                result["download_error"] = str(e)
                result["download_url"] = first_url
        result["outputs"] = outputs

    return result


def _get_task_status(task: dict) -> str:
    # Try common status field names
    for key in ("status", "task_status", "state"):
        if key in task:
            return str(task[key]).lower()
    return "unknown"


def _extract_outputs(task: dict) -> list[dict]:
    """Extract output files from task response (flexible — API shape varies)."""
    # Common shapes
    candidates: list[dict] = []
    if isinstance(task.get("output"), list):
        candidates.extend(task["output"])
    if isinstance(task.get("outputs"), list):
        candidates.extend(task["outputs"])
    if isinstance(task.get("result"), dict):
        if isinstance(task["result"].get("output"), list):
            candidates.extend(task["result"]["output"])
        if isinstance(task["result"].get("outputs"), list):
            candidates.extend(task["result"]["outputs"])
    # Flatten and keep items with a url
    out = []
    for c in candidates:
        if isinstance(c, dict):
            if c.get("url") or c.get("video_url") or c.get("file_url"):
                out.append(
                    {
                        "url": c.get("url") or c.get("video_url") or c.get("file_url"),
                        "type": c.get("type") or c.get("mime_type"),
                    }
                )
    return out


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=300) as resp:
        dest.write_bytes(resp.read())

"""
Video generator wrapper.

Wraps litellm-bridge.py video command via subprocess. Two flows:
- generate(): synchronous submit+poll (local mode default; double-billing-safe
  because the caller already waited)
- submit()/poll(): async two-step for hosted mode — submit returns a job id in
  seconds, status polling completes the job; a client timeout then retries the
  *status* call, never the paid submission.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

from ..db import insert_content, insert_job, update_job, get_job, expire_stale_jobs, generate_id
from ..utils import generate_slug, ensure_directory_rel, get_relative_path, VAAS_ROOT
from .runtime import finish, prepare, run_bridge

# Path to litellm-bridge.py
SCRIPTS_DIR = VAAS_ROOT / "scripts"
LITELLM_BRIDGE = SCRIPTS_DIR / "litellm-bridge.py"


def _slug_for(prompt: Optional[str], slug: Optional[str], fallback: str) -> str:
    if slug:
        return slug
    prefix = (prompt or "")[:20].lower().replace(" ", "-")
    prefix = "".join(c for c in prefix if c.isalnum() or c == "-")
    return generate_slug(prefix or fallback)


def _build_cmd(prompt: Optional[str], output_path: Path, duration, ratio,
               resolution, first_frame, last_frame, wait, timeout) -> list[str]:
    cmd = ["python", str(LITELLM_BRIDGE), "video"]
    if prompt:
        cmd.extend(["--prompt", prompt])
    cmd.extend(["--output", str(output_path)])
    if duration is not None:
        cmd.extend(["--duration", str(duration)])
    if ratio:
        cmd.extend(["--ratio", ratio])
    if resolution:
        cmd.extend(["--resolution", resolution])
    if first_frame:
        cmd.extend(["--first-frame", first_frame])
    if last_frame:
        cmd.extend(["--last-frame", last_frame])
    if not wait:
        cmd.append("--async")
    if timeout:
        cmd.extend(["--timeout", str(timeout)])
    return cmd


def generate(
    prompt: str,
    duration: Optional[int] = None,
    ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    first_frame: Optional[str] = None,
    last_frame: Optional[str] = None,
    wait: bool = True,
    timeout: int = 600,
    slug: Optional[str] = None
) -> dict:
    """
    Generate video from text prompt (synchronous).

    Returns dict with id, slug, file_path, status (rendered|pending), model.
    """
    if not prompt:
        raise ValueError("prompt is required")

    ctx = prepare("video", {
        "prompt": prompt, "first_frame": first_frame, "last_frame": last_frame,
        "slug": slug,
    })
    owner = ctx["owner"]
    slug = _slug_for(prompt, slug, "video")

    output_dir = ensure_directory_rel("videos", slug)
    output_path = output_dir / f"{slug}.mp4"
    cmd = _build_cmd(prompt, output_path, duration, ratio, resolution,
                     first_frame, last_frame, wait, timeout)

    try:
        stdout = run_bridge(cmd, ctx)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Video generation failed: {e.stderr}")

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse video generation output: {e}")

    status = "rendered" if wait and output_path.exists() else "pending"
    content_id = generate_id()
    metadata = {
        "prompt": prompt,
        "duration": duration,
        "ratio": ratio,
        "resolution": resolution,
        "model": output.get("model"),
    }
    insert_content(
        id=content_id,
        type="video",
        slug=slug,
        file_path=get_relative_path("videos", slug, f"{slug}.mp4"),
        metadata=metadata,
        status=status,
        owner=owner,
    )

    seconds = float(duration or 5)
    result = {
        "id": content_id,
        "slug": slug,
        "file_path": get_relative_path("videos", slug, f"{slug}.mp4"),
        "status": status,
        "duration_sec": duration,
        "model": output.get("model"),
    }
    result.update(finish(ctx, "generate_video", "volcengine",
                         output.get("model"), seconds, "second", content_id))
    return result


def submit(
    prompt: str,
    duration: Optional[int] = None,
    ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    first_frame: Optional[str] = None,
    last_frame: Optional[str] = None,
    slug: Optional[str] = None,
) -> dict:
    """
    Submit an async video job: returns within seconds with a job id.

    No asset is created here — the asset appears when the job succeeds.
    """
    if not prompt:
        raise ValueError("prompt is required")

    ctx = prepare("video", {
        "prompt": prompt, "first_frame": first_frame, "last_frame": last_frame,
        "slug": slug,
    })
    owner = ctx["owner"]
    slug = _slug_for(prompt, slug, "video")
    output_dir = ensure_directory_rel("videos", slug)
    output_path = output_dir / f"{slug}.mp4"

    cmd = _build_cmd(prompt, output_path, duration, ratio, resolution,
                     first_frame, last_frame, wait=False, timeout=None)
    try:
        stdout = run_bridge(cmd, ctx)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Video submission failed: {e.stderr}")

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse video submission output: {e}")

    task_id = output.get("task_id") or ""
    if not task_id:
        raise RuntimeError(f"No task id in submission output: {stdout[:300]}")

    job_id = insert_job(owner=owner, kind="video", provider_task_id=task_id, slug=slug)
    return {
        "job_id": job_id,
        "status": "running",
        "provider_task_id": task_id,
        "slug": slug,
        "model": output.get("model"),
        "note": "poll video_job_status until succeeded/failed",
    }


def poll(job_id: str, owner: Optional[str] = None) -> dict:
    """
    Poll one video job; on success archive the asset and finish the job.

    owner=None means local/admin (any job); hosted callers pass their sub.
    Expired non-terminal jobs are flipped to 'expired' first.
    """
    expire_stale_jobs()
    job = get_job(job_id, owner=owner)
    if not job:
        raise ValueError(f"Job not found or not visible: {job_id}")
    if job["status"] in ("succeeded", "failed", "expired"):
        return _job_view(job)

    ctx = prepare("video", {})
    slug = job["slug"] or job_id
    output_path = ensure_directory_rel("videos", slug) / f"{slug}.mp4"

    cmd = [
        "python", str(LITELLM_BRIDGE), "video",
        "--status", job["provider_task_id"],
        "--output", str(output_path),
    ]
    try:
        stdout = run_bridge(cmd, ctx)
        output = json.loads(stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        update_job(job_id, status="failed", error=str(e)[:500])
        return _job_view(get_job(job_id, owner=owner))

    status = output.get("status")
    if status in ("succeeded", "completed", "success", "done"):
        asset_id = generate_id()
        insert_content(
            id=asset_id,
            type="video",
            slug=slug,
            file_path=get_relative_path("videos", slug, f"{slug}.mp4")
            if output.get("local_path") else "",
            metadata={"provider_task_id": job["provider_task_id"],
                      "video_url": output.get("video_url")},
            status="rendered",
            owner=job["owner"],
        )
        update_job(job_id, status="succeeded", asset_id=asset_id)
        extras = finish(ctx, "generate_video_submit", "volcengine",
                        None, float(5), "second", asset_id)
        view = _job_view(get_job(job_id, owner=owner))
        view.update({"asset_id": asset_id, **extras})
        return view
    if status in ("failed", "error", "cancelled"):
        update_job(job_id, status="failed",
                   error=str(output.get("error") or status)[:500])
    return _job_view(get_job(job_id, owner=owner))


def _job_view(job: dict) -> dict:
    return {
        "job_id": job["id"],
        "status": job["status"],
        "slug": job.get("slug"),
        "asset_id": job.get("asset_id"),
        "error": job.get("error"),
        "expires_at": job.get("expires_at"),
    }

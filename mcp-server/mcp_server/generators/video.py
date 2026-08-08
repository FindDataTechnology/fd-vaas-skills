"""
Video generator wrapper.

Wraps litellm-bridge.py video command via subprocess.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

from ..db import insert_content, generate_id
from ..utils import generate_slug, ensure_directory, get_relative_path, VAAS_ROOT

# Path to litellm-bridge.py
SCRIPTS_DIR = VAAS_ROOT / "scripts"
LITELLM_BRIDGE = SCRIPTS_DIR / "litellm-bridge.py"


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
    Generate video from text prompt.

    Args:
        prompt: Video description (required)
        duration: Video duration in seconds (default 5)
        ratio: Aspect ratio (16:9/9:16/1:1, default adaptive)
        resolution: Resolution (480p/720p/1080p/4k)
        first_frame: Path to first frame image
        last_frame: Path to last frame image
        wait: Wait for completion (default True)
        timeout: Max wait time in seconds (default 600)
        slug: Custom slug (auto-generated if not provided)

    Returns:
        Dict with:
            - id: Content UUID
            - slug: Human-readable identifier
            - file_path: Relative path from downloads/
            - status: rendered | pending
            - duration_sec: Video duration in seconds
            - model: Model name used

    Raises:
        ValueError: If prompt not provided
        RuntimeError: If video generation fails
    """
    if not prompt:
        raise ValueError("prompt is required")

    # Generate slug if not provided
    if not slug:
        prefix = prompt[:20].lower().replace(" ", "-")
        prefix = "".join(c for c in prefix if c.isalnum() or c == "-")
        slug = generate_slug(prefix or "video")

    # Create output directory
    output_dir = ensure_directory("videos", slug)
    output_path = output_dir / f"{slug}.mp4"

    # Build command
    cmd = [
        "python", str(LITELLM_BRIDGE), "video",
        "--prompt", prompt,
        "--output", str(output_path)
    ]

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

    # Execute subprocess
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(SCRIPTS_DIR)
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Video generation failed: {e.stderr}")

    # Parse output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse video generation output: {e}")

    # Determine status
    status = "rendered" if wait and output_path.exists() else "pending"

    # Insert into database
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
        status=status
    )

    return {
        "id": content_id,
        "slug": slug,
        "file_path": get_relative_path("videos", slug, f"{slug}.mp4"),
        "status": status,
        "duration_sec": duration,
        "model": output.get("model")
    }

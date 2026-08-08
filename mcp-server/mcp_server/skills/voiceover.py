"""
Voiceover video pipeline orchestrator.

Wraps task-render.mjs via subprocess to create complete voiceover videos.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

from ..db import insert_content, generate_id, update_content_status
from ..utils import generate_slug, ensure_directory, get_relative_path, VAAS_ROOT

# Path to video creator scripts
VIDEO_CREATOR_SCRIPTS = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-video-creator" / "scripts"
REMOTION_APP = VAAS_ROOT / "remotion-app"


def create_voiceover_video(
    script_path: str,
    visuals: Optional[dict] = None,
    voice: Optional[str] = None,
    composition: Optional[str] = None,
    slug: Optional[str] = None
) -> dict:
    """
    Create a complete voiceover video with TTS + captions + Remotion render.

    Args:
        script_path: Path to script text file (required)
        visuals: Optional visual assets dict with keys:
            - images: List of image paths for slideshow
            - video: Background video path
        voice: Voice ID for TTS (auto-detect if not provided)
        composition: Remotion composition name (default VoiceoverVideo)
        slug: Custom slug (auto-generated if not provided)

    Returns:
        Dict with:
            - id: Content UUID
            - slug: Human-readable identifier
            - file_path: Relative path from downloads/
            - duration_sec: Video duration in seconds
            - status: rendered

    Raises:
        ValueError: If script_path not provided or invalid
        RuntimeError: If video creation fails
    """
    if not script_path:
        raise ValueError("script_path is required")

    script_file = Path(script_path)
    if not script_file.exists():
        raise ValueError(f"Script file not found: {script_path}")

    # Generate slug if not provided
    if not slug:
        # Use script filename or first line
        if script_file.stem:
            prefix = script_file.stem.lower()[:20]
            prefix = "".join(c for c in prefix if c.isalnum() or c == "-")
            slug = generate_slug(prefix or "video")
        else:
            slug = generate_slug("video")

    # Create task directory
    task_dir = ensure_directory("videos", slug)

    # Copy script to task directory
    script_dest = task_dir / "script.txt"
    if not script_dest.exists():
        script_dest.write_text(script_file.read_text())

    # Step 1: Create task directory structure
    cmd1 = [
        "node", str(VIDEO_CREATOR_SCRIPTS / "new-task.mjs"),
        "--slug", slug,
        "--script", str(script_dest)
    ]

    if voice:
        cmd1.extend(["--voice", voice])

    try:
        subprocess.run(
            cmd1,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(REMOTION_APP)
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Task initialization failed: {e.stderr}")

    # Step 2: Run full pipeline (TTS → fix-timings → preflight → render)
    cmd2 = [
        "node", str(VIDEO_CREATOR_SCRIPTS / "task-render.mjs"),
        "--slug", slug
    ]

    if composition:
        cmd2.extend(["--composition", composition])

    # Build extra-props for visuals
    if visuals:
        extra_props = {}
        if visuals.get("video"):
            extra_props["videoSrc"] = visuals["video"]
        elif visuals.get("images"):
            extra_props["images"] = visuals["images"]

        if extra_props:
            cmd2.extend(["--extra-props", json.dumps(extra_props)])

    try:
        result = subprocess.run(
            cmd2,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(REMOTION_APP)
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Video rendering failed: {e.stderr}")

    # Step 3: Read task.json for metadata
    task_json_path = task_dir / "task.json"
    if task_json_path.exists():
        task_json = json.loads(task_json_path.read_text())
    else:
        task_json = {}

    # Extract duration
    duration_sec = task_json.get("render", {}).get("totalDurationSec")

    # Insert into database
    content_id = generate_id()
    metadata = {
        "script": "script.txt",
        "voice": voice,
        "composition": composition or "VoiceoverVideo",
        "visuals": visuals,
        "task_json": task_json,
    }

    insert_content(
        id=content_id,
        type="video",
        slug=slug,
        file_path=get_relative_path("videos", slug, f"{slug}.mp4"),
        metadata=metadata,
        status="rendered"
    )

    return {
        "id": content_id,
        "slug": slug,
        "file_path": get_relative_path("videos", slug, f"{slug}.mp4"),
        "duration_sec": duration_sec,
        "status": "rendered"
    }

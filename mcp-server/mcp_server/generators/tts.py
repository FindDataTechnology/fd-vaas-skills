"""
TTS (Text-to-Speech) generator wrapper.

Wraps litellm-bridge.py tts command via subprocess.
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


def synthesize(
    text: Optional[str] = None,
    file_path: Optional[str] = None,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    format: str = "mp3",
    slug: Optional[str] = None,
    enable_subtitles: bool = True
) -> dict:
    """
    Synthesize speech from text.

    Args:
        text: Text to synthesize (required if file_path not provided)
        file_path: Path to text file (required if text not provided)
        voice: Voice ID (auto-detect by language if not provided)
        speed: Speech speed multiplier (0.25-4.0, default 1.0)
        format: Output format (mp3/wav, default mp3)
        slug: Custom slug (auto-generated if not provided)
        enable_subtitles: Enable word-level timestamps (default True)

    Returns:
        Dict with:
            - id: Content UUID
            - slug: Human-readable identifier
            - file_path: Relative path from downloads/
            - duration_ms: Audio duration in milliseconds
            - captions_path: Path to captions JSON (if enabled)
            - voice: Voice ID used
            - model: Model name used

    Raises:
        ValueError: If neither text nor file_path provided
        RuntimeError: If TTS synthesis fails
    """
    if not text and not file_path:
        raise ValueError("Either text or file_path must be provided")

    # Generate slug if not provided
    if not slug:
        # Use first 20 chars of text or filename
        if text:
            prefix = text[:20].lower().replace(" ", "-")
            prefix = "".join(c for c in prefix if c.isalnum() or c == "-")
            slug = generate_slug(prefix or "audio")
        else:
            slug = generate_slug("audio")

    # Create output directory
    output_dir = ensure_directory("audio", slug)
    audio_path = output_dir / f"{slug}.{format}"
    captions_path = output_dir / "captions.json" if enable_subtitles else None

    # Build command
    cmd = [
        "python", str(LITELLM_BRIDGE), "tts",
        "--output", str(audio_path)
    ]

    if text:
        cmd.extend(["--text", text])
    elif file_path:
        cmd.extend(["--input", file_path])

    if voice:
        cmd.extend(["--voice", voice])

    if speed is not None:
        cmd.extend(["--speed", str(speed)])

    if format:
        cmd.extend(["--format", format])

    if captions_path:
        cmd.extend(["--captions", str(captions_path)])

    if not enable_subtitles:
        cmd.append("--no-subtitle")

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
        raise RuntimeError(f"TTS synthesis failed: {e.stderr}")

    # Parse output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse TTS output: {e}")

    # Insert into database
    content_id = generate_id()
    metadata = {
        "voice": output.get("voice"),
        "model": output.get("model"),
        "speed": speed,
        "format": format,
        "text_length": len(text) if text else None,
    }

    insert_content(
        id=content_id,
        type="audio",
        slug=slug,
        file_path=get_relative_path("audio", slug, f"{slug}.{format}"),
        metadata=metadata,
        status="rendered"
    )

    return {
        "id": content_id,
        "slug": slug,
        "file_path": get_relative_path("audio", slug, f"{slug}.{format}"),
        "duration_ms": output.get("api_latency_ms"),  # Note: actual duration not in output
        "captions_path": get_relative_path("audio", slug, "captions.json") if captions_path and captions_path.exists() else None,
        "voice": output.get("voice"),
        "model": output.get("model")
    }

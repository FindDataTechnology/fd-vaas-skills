"""
Image generator wrapper.

Wraps litellm-bridge.py image command via subprocess.
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
    size: Optional[str] = None,
    output_format: str = "jpeg",
    n: int = 1,
    reference_image: Optional[str] = None,
    slug: Optional[str] = None
) -> dict:
    """
    Generate images from text prompt.

    Args:
        prompt: Image description (required)
        size: Image size (2K/3K/4K or WxH, default 2K)
        output_format: Output format (png/jpeg, default jpeg)
        n: Number of images to generate (1-15, default 1)
        reference_image: Path to reference image for img2img
        slug: Custom slug (auto-generated if not provided)

    Returns:
        Dict with:
            - id: Content UUID
            - slug: Human-readable identifier
            - file_paths: List of relative paths from downloads/
            - count: Number of images generated
            - model: Model name used

    Raises:
        ValueError: If prompt not provided or n out of range
        RuntimeError: If image generation fails
    """
    if not prompt:
        raise ValueError("prompt is required")

    if n < 1 or n > 15:
        raise ValueError("n must be between 1 and 15")

    # Generate slug if not provided
    if not slug:
        prefix = prompt[:20].lower().replace(" ", "-")
        prefix = "".join(c for c in prefix if c.isalnum() or c == "-")
        slug = generate_slug(prefix or "image")

    # Create output directory
    output_dir = ensure_directory("images", slug)

    # Build command
    cmd = [
        "python", str(LITELLM_BRIDGE), "image",
        "--prompt", prompt,
        "--output-format", output_format,
        "-n", str(n)
    ]

    if size:
        cmd.extend(["--size", size])

    if reference_image:
        cmd.extend(["--image", reference_image])

    # For multiple images, we need to handle output path specially
    # litellm-bridge.py outputs to a single file, so we'll handle multiple files after
    output_path = output_dir / f"{slug}_00.{output_format}"
    cmd.extend(["--output", str(output_path)])

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
        raise RuntimeError(f"Image generation failed: {e.stderr}")

    # Parse output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse image generation output: {e}")

    # Collect generated image paths
    file_paths = []
    images = output.get("images", [])

    for i, img in enumerate(images):
        local_path = img.get("local_path")
        if local_path:
            # Rename to our naming convention
            src_path = Path(local_path)
            dst_name = f"{slug}_{i:02d}.{output_format}"
            dst_path = output_dir / dst_name

            if src_path != dst_path:
                src_path.rename(dst_path)

            file_paths.append(get_relative_path("images", slug, dst_name))

    # If no images in output, check if the output file exists
    if not file_paths and output_path.exists():
        file_paths.append(get_relative_path("images", slug, f"{slug}_00.{output_format}"))

    # Insert into database (one record per image)
    content_id = generate_id()
    metadata = {
        "prompt": prompt,
        "size": size,
        "format": output_format,
        "model": output.get("model"),
        "count": len(file_paths),
    }

    insert_content(
        id=content_id,
        type="image",
        slug=slug,
        file_path=file_paths[0] if file_paths else "",
        metadata=metadata,
        status="rendered"
    )

    return {
        "id": content_id,
        "slug": slug,
        "file_paths": file_paths,
        "count": len(file_paths),
        "model": output.get("model")
    }

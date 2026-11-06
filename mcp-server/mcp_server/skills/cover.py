"""
Cover image generator using Remotion.

Wraps generate-cover.mjs via subprocess.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from ..db import insert_content, generate_id, record_usage, scoped_asset_slug
from ..hosting import current_owner
from ..utils import generate_slug, ensure_directory_rel, get_relative_path, VAAS_ROOT

log = logging.getLogger("vaas.cover")

# Finite wall clock for the node render subprocess
# (fix-hosted-generation-correctness). Remotion cold starts are slow —
# generous but bounded.
RENDER_TIMEOUT_S = int(os.getenv("VAAS_COVER_TIMEOUT_S", "300"))

# Path to Remotion project and cover generation script
REMOTION_APP = VAAS_ROOT / "remotion-app"
COVER_SCRIPT = VAAS_ROOT / ".agents" / "skills" / "fd-cover-image" / "scripts" / "generate-cover.mjs"


def create_cover(
    title: str,
    subtitle: Optional[str] = None,
    tags: Optional[str] = None,
    orientation: str = "horizontal",
    size: Optional[str] = None,
    template: str = "brand",
    slug: Optional[str] = None
) -> dict:
    """
    Generate brand-consistent cover image using Remotion.

    Args:
        title: Main title (required)
        subtitle: Optional subtitle
        tags: Optional tags (comma-separated)
        orientation: horizontal/vertical/square (default horizontal)
        size: Custom size WxH (overrides orientation default)
        template: Template name (brand/title-only/gradient, default brand)
        slug: Custom slug (auto-generated if not provided)

    Returns:
        Dict with:
            - id: Content UUID
            - slug: Human-readable identifier
            - file_path: Relative path from downloads/
            - width: Image width in pixels
            - height: Image height in pixels

    Raises:
        ValueError: If title not provided
        RuntimeError: If cover generation fails
    """
    if not title:
        raise ValueError("title is required")

    # Generate slug if not provided
    if not slug:
        prefix = title[:20].lower().replace(" ", "-")
        prefix = "".join(c for c in prefix if c.isalnum() or c == "-")
        slug = generate_slug(prefix or "cover")

    # Create output directory
    output_dir = ensure_directory_rel("images", slug)

    # Determine output filename based on orientation
    if orientation == "vertical":
        filename = f"{slug}-vertical.jpg"
        default_size = "1080x1440"
    elif orientation == "square":
        filename = f"{slug}-square.jpg"
        default_size = "1080x1080"
    else:  # horizontal
        filename = f"{slug}-horizontal.jpg"
        default_size = "1920x1080"

    output_path = output_dir / filename

    # Build command
    cmd = [
        "node", str(COVER_SCRIPT),
        "--title", title,
        "--orientation", orientation,
        "--output", str(output_path)
    ]

    if subtitle:
        cmd.extend(["--subtitle", subtitle])

    if tags:
        cmd.extend(["--tags", tags])

    if size:
        cmd.extend(["--size", size])
    else:
        cmd.extend(["--size", default_size])

    # Execute subprocess
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(REMOTION_APP),
            timeout=RENDER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"timeout: cover render exceeded {RENDER_TIMEOUT_S}s wall clock "
            f"(raise VAAS_COVER_TIMEOUT_S only after checking the cold start)"
        )
    except subprocess.CalledProcessError as e:
        # Raw node stderr can carry /app layout paths — server log only.
        log.warning("cover render failed: %s", str(e.stderr or "")[-2000:])
        raise RuntimeError("render_error: cover generation failed (details in server log)") from e

    # Parse size to get width/height
    size_str = size or default_size
    try:
        width, height = map(int, size_str.split("x"))
    except (ValueError, AttributeError):
        width, height = 1920, 1080

    # Insert into database
    content_id = generate_id()
    metadata = {
        "title": title,
        "subtitle": subtitle,
        "tags": tags,
        "orientation": orientation,
        "template": template,
        "width": width,
        "height": height,
    }

    owner = current_owner()
    scoped = scoped_asset_slug(slug, owner)
    insert_content(
        id=content_id,
        type="image",
        slug=scoped,
        file_path=get_relative_path("images", slug, filename),
        metadata=metadata,
        status="rendered",
        owner=owner,
    )

    record_usage(owner, "generate_cover", "remotion", None, 1, "image", "env",
                 asset_id=content_id)

    return {
        "id": content_id,
        "slug": scoped,
        "file_path": get_relative_path("images", slug, filename),
        "width": width,
        "height": height
    }

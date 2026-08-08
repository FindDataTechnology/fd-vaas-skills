"""
File management utilities for VAAS MCP Server.

Handles slug generation, path resolution, and directory creation.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

# VAAS project root
VAAS_ROOT = Path(__file__).parent.parent.parent.parent

# Downloads directory
DOWNLOADS_DIR = VAAS_ROOT / "downloads"

# Valid content types
VALID_TYPES = {"video", "article", "image", "audio", "presentation"}

# Slug pattern: lowercase letters, numbers, hyphens
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def generate_slug(prefix: str) -> str:
    """
    Generate a unique slug with timestamp.

    Args:
        prefix: Slug prefix (e.g., "video", "article")

    Returns:
        Unique slug in format: prefix-YYYYMMDD-HHMMSS

    Example:
        >>> generate_slug("video")
        'video-20260804-143052'
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}"


def validate_slug(slug: str) -> bool:
    """
    Validate a slug string.

    Args:
        slug: Slug to validate

    Returns:
        True if valid, False otherwise

    Rules:
        - Must start with lowercase letter or number
        - Must end with lowercase letter or number
        - Can contain lowercase letters, numbers, hyphens
        - Minimum length: 2 characters
    """
    if len(slug) < 2:
        return False
    return bool(SLUG_PATTERN.match(slug))


def resolve_path(type: str, slug: str, filename: Optional[str] = None) -> Path:
    """
    Resolve absolute path under downloads/<type>/<slug>/.

    Args:
        type: Content type (video/article/image/audio/presentation)
        slug: Human-readable identifier
        filename: Optional filename within the slug directory

    Returns:
        Absolute Path object

    Raises:
        ValueError: If type is invalid or path traversal is attempted
    """
    if type not in VALID_TYPES:
        raise ValueError(f"Invalid content type: {type}. Must be one of {VALID_TYPES}")

    # Prevent path traversal
    if ".." in slug or "/" in slug or "\\" in slug:
        raise ValueError(f"Invalid slug: {slug}. Cannot contain '..' or path separators")

    base = DOWNLOADS_DIR / type / slug

    if filename:
        # Prevent path traversal in filename
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValueError(f"Invalid filename: {filename}. Cannot contain '..' or path separators")
        return base / filename

    return base


def ensure_directory(type: str, slug: str) -> Path:
    """
    Create directory if not exists, return path.

    Args:
        type: Content type (video/article/image/audio/presentation)
        slug: Human-readable identifier

    Returns:
        Absolute Path to the directory
    """
    path = resolve_path(type, slug)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_relative_path(type: str, slug: str, filename: str) -> str:
    """
    Get relative path from downloads/ directory.

    Args:
        type: Content type
        slug: Human-readable identifier
        filename: Filename within the slug directory

    Returns:
        Relative path string (e.g., "videos/my-video/my-video.mp4")
    """
    return f"{type}/{slug}/{filename}"


def create_downloads_structure() -> None:
    """
    Create the downloads/ directory structure.

    Creates:
        downloads/videos/
        downloads/articles/
        downloads/images/
        downloads/audio/
        downloads/presentations/
    """
    for type in VALID_TYPES:
        (DOWNLOADS_DIR / type).mkdir(parents=True, exist_ok=True)

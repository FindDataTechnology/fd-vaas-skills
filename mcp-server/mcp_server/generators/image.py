"""
Image generator wrapper.

Wraps litellm-bridge.py image command via subprocess.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

from ..db import insert_content, generate_id, scoped_asset_slug
from ..utils import generate_slug, ensure_directory_rel, get_relative_path, VAAS_ROOT
from .runtime import finish, prepare, provider_for, run_bridge
from .errors import classify_upstream_error

# Path to litellm-bridge.py
SCRIPTS_DIR = VAAS_ROOT / "scripts"
LITELLM_BRIDGE = SCRIPTS_DIR / "litellm-bridge.py"

# Output filename extension whitelist (path-traversal guard; same discipline
# as the render plane's still_chart).
IMAGE_FORMATS = {"png", "jpeg", "jpg", "webp"}

# Providers whose image request actually honors `n` (else the call must
# disclose the silent clamp, not fake multi-image support).
N_SUPPORTED_PROVIDERS = {"ciyuan"}


def generate(
    prompt: str,
    size: Optional[str] = None,
    output_format: str = "jpeg",
    n: int = 1,
    slug: Optional[str] = None
) -> dict:
    """
    Generate images from text prompt.

    Args:
        prompt: Image description (required)
        size: Image size (2K/3K/4K or WxH, default 2K)
        output_format: Output format (png/jpeg/jpg/webp, default jpeg)
        n: Number of images to generate (1-15, default 1). Providers that
           ignore n are reported via warnings (never silently one-for-many).
        slug: Custom slug (auto-generated if not provided)

    Returns:
        Dict with:
            - id: Content UUID
            - slug: Human-readable identifier
            - file_paths: List of relative paths from downloads/
            - count: Number of images generated
            - model: Model name used
            - warnings: disclosure list (provider count clamp etc.)

    Raises:
        ValueError: If prompt not provided or n out of range
        RuntimeError: If image generation fails (classified, upstream-safe)
    """
    if not prompt:
        raise ValueError("prompt is required")

    if n < 1 or n > 15:
        raise ValueError("n must be between 1 and 15")

    if output_format not in IMAGE_FORMATS:
        raise ValueError(
            f"invalid_input: output_format {output_format!r} not allowed "
            f"(supported: {sorted(IMAGE_FORMATS)})"
        )

    ctx = prepare("image", {
        "prompt": prompt, "slug": slug,
    })
    provider_actual = provider_for(ctx, "IMAGE_PROVIDER")

    # Generate slug if not provided
    if not slug:
        prefix = prompt[:20].lower().replace(" ", "-")
        prefix = "".join(c for c in prefix if c.isalnum() or c == "-")
        slug = generate_slug(prefix or "image")

    # Create output directory
    output_dir = ensure_directory_rel("images", slug)

    # Build command
    cmd = [
        "python", str(LITELLM_BRIDGE), "image",
        "--prompt", prompt,
        "--output-format", output_format,
        "-n", str(n)
    ]

    if size:
        cmd.extend(["--size", size])

    # reference_image (img2img) was never wired through the bridge (argparse
    # rejected --image → guaranteed failure advertised as support); removed
    # from the tool surface. Re-add only with an E2E proof per lane.
    output_path = output_dir / f"{slug}_00.{output_format}"
    cmd.extend(["--output", str(output_path)])

    # Execute subprocess
    try:
        stdout = run_bridge(cmd, ctx)
    except subprocess.CalledProcessError as e:
        raise classify_upstream_error("generate_image", e.stderr, provider_actual) from e

    # Parse output
    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"upstream_error: image lane returned unparsable output: {e}") from e

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

    # Parameter honesty: a zero-image "success" and a provider that ignored
    # n are both disclosed, never billed silently as if the request landed.
    warnings: list[str] = []
    if len(file_paths) < n:
        if provider_actual not in N_SUPPORTED_PROVIDERS:
            warnings.append(
                f"provider '{provider_actual}' ignores n: {len(file_paths)} image(s) "
                f"produced for a request of {n}"
            )
        else:
            warnings.append(
                f"upstream returned {len(file_paths)} of {n} requested images"
            )
    if not file_paths:
        raise RuntimeError(
            "upstream_error: image generation produced zero artifacts — nothing "
            "was written or billed"
        )

    # Ledger: the row's file_path is the primary image; every produced file
    # is registered in metadata.file_paths. GC reclaims the whole slug
    # directory when this row ages out, so no artifact leaks untracked.
    content_id = generate_id()
    metadata = {
        "prompt": prompt,
        "size": size,
        "format": output_format,
        "model": output.get("model"),
        "count": len(file_paths),
        "file_paths": file_paths,
        "warnings": warnings,
    }

    scoped = scoped_asset_slug(slug, ctx["owner"])
    insert_content(
        id=content_id,
        type="image",
        slug=scoped,
        file_path=file_paths[0],
        metadata=metadata,
        status="rendered",
        owner=ctx["owner"],
    )

    result = {
        "id": content_id,
        "slug": scoped,
        "file_paths": file_paths,
        "count": len(file_paths),
        "model": output.get("model"),
        "warnings": warnings,
    }
    result.update(finish(ctx, "generate_image", provider_actual,
                         output.get("model"), len(file_paths), "image", content_id))
    return result

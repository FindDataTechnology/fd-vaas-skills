"""
generate_* namespace: asset generation, dispatched through the generation registry.
"""

from typing import Optional

from ..registry import dispatch


def generate_voice(
    text: Optional[str] = None,
    file_path: Optional[str] = None,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    format: str = "mp3",
    slug: Optional[str] = None,
    enable_subtitles: bool = True,
    name: str = "tts",
) -> dict:
    """Generate speech from text using TTS (registry method: tts)."""
    return dispatch("voice", name, {
        "text": text, "file_path": file_path, "voice": voice, "speed": speed,
        "format": format, "slug": slug, "enable_subtitles": enable_subtitles,
    })


def generate_image(
    prompt: str,
    size: Optional[str] = None,
    output_format: str = "jpeg",
    n: int = 1,
    reference_image: Optional[str] = None,
    slug: Optional[str] = None,
    name: str = "seedream",
) -> dict:
    """Generate images from a text prompt (registry method: seedream)."""
    return dispatch("image", name, {
        "prompt": prompt, "size": size, "output_format": output_format,
        "n": n, "reference_image": reference_image, "slug": slug,
    })


def generate_video(
    prompt: str,
    duration: Optional[int] = None,
    ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    first_frame: Optional[str] = None,
    last_frame: Optional[str] = None,
    wait: bool = True,
    timeout: int = 600,
    slug: Optional[str] = None,
    name: str = "seedance",
) -> dict:
    """Generate video from a text prompt (registry method: seedance)."""
    return dispatch("video", name, {
        "prompt": prompt, "duration": duration, "ratio": ratio,
        "resolution": resolution, "first_frame": first_frame,
        "last_frame": last_frame, "wait": wait, "timeout": timeout, "slug": slug,
    })


def generate_cover(
    title: str,
    subtitle: Optional[str] = None,
    tags: Optional[str] = None,
    orientation: str = "horizontal",
    size: Optional[str] = None,
    template: str = "brand",
    slug: Optional[str] = None,
    name: str = "brand",
) -> dict:
    """Generate a brand-consistent cover image via Remotion (registry method: brand)."""
    return dispatch("cover", name, {
        "title": title, "subtitle": subtitle, "tags": tags,
        "orientation": orientation, "size": size, "template": template, "slug": slug,
    })

"""
orchestrate_* namespace: multi-step content pipelines (voiceover, brainstorm).
"""

from typing import Optional

from ..skills.brainstorm import brainstorm
from ..skills.voiceover import create_voiceover_video


def orchestrate_voiceover(
    script_path: str,
    visuals: Optional[dict] = None,
    voice: Optional[str] = None,
    composition: Optional[str] = None,
    slug: Optional[str] = None,
) -> dict:
    """Create a complete voiceover video: TTS + captions + Remotion render."""
    return create_voiceover_video(
        script_path=script_path, visuals=visuals,
        voice=voice, composition=composition, slug=slug,
    )


def orchestrate_brainstorm(
    mode: str,
    topic: str,
    audience: Optional[str] = None,
    brand_context: Optional[dict] = None,
) -> dict:
    """Generate a structured content plan for voiceover or article."""
    return brainstorm(
        mode=mode, topic=topic, audience=audience, brand_context=brand_context,
    )

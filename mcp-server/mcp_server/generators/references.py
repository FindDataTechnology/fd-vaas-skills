"""Reference clip library (vaas-media-pipeline W2.2).

Every ACTIVE (provider, model, voice) has one canonical short reference clip.
`reference_clips_check()` regenerates missing/recycled clips (or all when
asked), producing a per-voice diff report for upstream/vendor drift review.
"""

from typing import Optional

from ..db import delete_asset, get_asset_by_slug, insert_content, generate_id
from ..utils import DOWNLOADS_DIR, ensure_directory, get_relative_path
from .manifest import load_manifest
from .tts import synthesize

REFERENCE_TEXT = "百席共创计划，让 AI 成为你团队的一部分。"


def _ensure_ref(provider: str, model: dict, voice: dict, regenerate: bool) -> dict:
    vid = voice.get("id")
    slug = f"ref-{provider}-{vid}"
    existing = get_asset_by_slug(slug, owner=None)

    def _has_file(item: Optional[dict]) -> bool:
        if not item:
            return False
        fp = item.get("file_path") or ""
        return bool(fp) and (DOWNLOADS_DIR / fp).exists()

    if regenerate or not (existing and _has_file(existing)):
        if existing:
            delete_asset(existing["id"])
        probed = synthesize(
            text=REFERENCE_TEXT, voice=vid, slug=slug,
            idempotency_key=f"reference:{provider}:{vid}",
            enable_subtitles=False,
        )
        return {
            "provider": provider,
            "model": model.get("public_model"),
            "voice": vid,
            "voice_name": voice.get("name"),
            "slug": probed["slug"],
            "file_path": probed["file_path"],
            "duration_ms": probed["duration_ms"],
            "reused": False,
        }
    meta = (existing or {}).get("metadata") or {}
    return {
        "provider": provider,
        "model": model.get("public_model"),
        "voice": vid,
        "voice_name": voice.get("name"),
        "slug": slug,
        "file_path": existing["file_path"],
        "duration_ms": meta.get("duration_ms"),
        "reused": True,
    }


def reference_clips_check(regenerate_all: bool = False) -> dict:
    """Generate/review reference clips for every active voice; returns a report."""
    manifest = load_manifest()
    providers = (manifest.get("providers") or {})
    items = []
    for provider, prov in providers.items():
        for model in prov.get("models") or []:
            if not str(model.get("status", "")).startswith("active"):
                continue
            for voice in model.get("voices") or []:
                items.append(_ensure_ref(provider, model, voice, regenerate_all))
    reused = sum(1 for i in items if i["reused"])
    return {
        "count": len(items),
        "reused": reused,
        "regenerated": len(items) - reused,
        "items": items,
    }

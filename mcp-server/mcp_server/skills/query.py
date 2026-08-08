"""
Asset query tools: list / get / stats over the unified material store.
"""

from typing import Optional

from ..db import (
    list_assets as db_list_assets,
    get_asset as db_get_asset,
    get_asset_by_slug as db_get_asset_by_slug,
    get_asset_stats as db_get_asset_stats,
)


def list_assets(
    type: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """
    List asset summaries with optional filters.

    Args:
        type: Optional filter by asset type (video/article/image/audio/presentation/cover/copy)
        stage: Optional filter by stage (draft/rendered/published/failed)
        limit: Maximum number of records to return (default 100)

    Returns:
        Dict with items[] containing asset summaries
    """
    items = db_list_assets(type=type, stage=stage, limit=limit)
    simplified = [{
        "id": i["id"],
        "slug": i["slug"],
        "type": i["type"],
        "stage": i["stage"],
        "title": i.get("title"),
        "provider": i.get("provider"),
        "created_at": i["created_at"],
    } for i in items]
    return {"items": simplified, "count": len(simplified)}


def get_asset(id: Optional[str] = None, slug: Optional[str] = None) -> dict:
    """
    Get full asset details including lineage, variants, and distribution history.

    Args:
        id: Asset UUID (optional if slug provided)
        slug: Human-readable identifier (optional if id provided)

    Returns:
        Full asset dict with lineage tree, per-platform variants, distribution history

    Raises:
        ValueError: If neither id nor slug provided, or asset not found
    """
    if not id and not slug:
        raise ValueError("Either id or slug must be provided")

    asset = db_get_asset(id) if id else db_get_asset_by_slug(slug)
    if not asset:
        raise ValueError(f"Asset not found: {id or slug}")
    return asset


def get_asset_stats() -> dict:
    """Aggregate stats over all assets and distributions."""
    return db_get_asset_stats()


# ─── Backward-compat aliases (used by old tool names) ─────────────────────

def list_content(
    type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> dict:
    return list_assets(type=type, stage=status, limit=limit)


def get_content(id: Optional[str] = None, slug: Optional[str] = None) -> dict:
    return get_asset(id=id, slug=slug)

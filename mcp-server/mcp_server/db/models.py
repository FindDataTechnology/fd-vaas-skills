"""
Asset store CRUD helpers for the unified VAAS material database.

Asset-oriented API (insert_asset/get_asset/list_assets/update_asset_stage,
upsert_variant, insert_distribution, record_asset_history, get_lineage).
Legacy names (insert_content/get_content/list_content/update_content_status)
remain as thin aliases so existing generators/skills keep working.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from .database import get_connection


def generate_id() -> str:
    """Generate a UUID for asset records."""
    return str(uuid.uuid4())


# ─── Assets ────────────────────────────────────────────────────────────────

def insert_asset(
    type: str,
    slug: str,
    file_path: Optional[str] = None,
    metadata: Optional[dict] = None,
    stage: str = "draft",
    id: Optional[str] = None,
    title: Optional[str] = None,
    parent_id: Optional[str] = None,
    lineage_root: Optional[str] = None,
    provider: Optional[str] = None,
    video_id: Optional[int] = None,
) -> str:
    """
    Insert a new asset record.

    Args:
        type: Asset type (video/article/image/audio/presentation/cover/copy)
        slug: Human-readable identifier (unique)
        file_path: Relative path from downloads/ (optional)
        metadata: Structured metadata (JSON-serializable)
        stage: draft|rendered|published|failed
        id: Optional custom ID. Auto-generated if not provided.
        title: Optional human title
        parent_id: Parent asset id (lineage: demand -> master -> variant)
        lineage_root: Root id of the lineage tree (defaults to self id)
        provider: Which generator provider produced this asset
        video_id: Optional link to the video detail row

    Returns:
        The asset ID
    """
    asset_id = id or generate_id()
    if not lineage_root:
        lineage_root = asset_id
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO assets (id, slug, type, stage, title, parent_id, lineage_root,
                            provider, file_path, metadata, video_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (asset_id, slug, type, stage, title, parent_id, lineage_root,
         provider, file_path, json.dumps(metadata) if metadata else None, video_id)
    )
    conn.commit()
    conn.close()

    return asset_id


# Backward-compat alias: generators/skills call insert_content(..., status=...)
def insert_content(
    type: str,
    slug: str,
    file_path: str,
    metadata: Optional[dict] = None,
    status: str = "draft",
    id: Optional[str] = None,
) -> str:
    return insert_asset(
        type=type, slug=slug, file_path=file_path,
        metadata=metadata, stage=status, id=id, title=slug,
    )


def _parse(row) -> dict:
    asset = dict(row)
    if asset.get("metadata"):
        asset["metadata"] = json.loads(asset["metadata"])
    return asset


def _enrich(asset: dict) -> dict:
    """Attach variants, distribution, and lineage to an asset dict."""
    asset_id = asset["id"]
    conn = get_connection()
    asset["variants"] = [dict(r) for r in conn.execute(
        "SELECT platform, title, body, tags, cover_path, extra FROM variants "
        "WHERE asset_id = ? ORDER BY platform", (asset_id,))]
    asset["distribution"] = [dict(r) for r in conn.execute(
        "SELECT platform, url, status, error_message, published_at FROM distribution "
        "WHERE asset_id = ? ORDER BY published_at DESC", (asset_id,))]
    asset["lineage"] = _lineage_nodes(conn, asset_id)
    conn.close()
    return asset


def _lineage_nodes(conn, asset_id: str) -> list[dict]:
    """Collect the full lineage tree (root + all nodes sharing the root)."""
    row = conn.execute("SELECT lineage_root FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if not row:
        return []
    root = row["lineage_root"]
    return [dict(r) for r in conn.execute(
        "SELECT id, slug, type, stage, parent_id FROM assets "
        "WHERE lineage_root = ? ORDER BY created_at", (root,))]


def get_asset(asset_id: str) -> Optional[dict]:
    """Get a full asset record (with variants/distribution/lineage) by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich(_parse(row))


def get_asset_by_slug(slug: str) -> Optional[dict]:
    """Get a full asset record by slug."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM assets WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich(_parse(row))


# Backward-compat aliases used by skills/query.py and skills/publish.py
def get_content(content_id: str) -> Optional[dict]:
    return get_asset(content_id)


def get_content_by_slug(slug: str) -> Optional[dict]:
    return get_asset_by_slug(slug)


def list_assets(
    type: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """List asset summaries with optional filters."""
    conn = get_connection()
    query = "SELECT * FROM assets"
    params = []
    conditions = []
    if type:
        conditions.append("type = ?")
        params.append(type)
    if stage:
        conditions.append("stage = ?")
        params.append(stage)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = [_parse(r) for r in conn.execute(query, params).fetchall()]
    conn.close()
    return rows


def list_content(type: Optional[str] = None, status: Optional[str] = None, limit: int = 100) -> list[dict]:
    return list_assets(type=type, stage=status, limit=limit)


def update_asset_stage(asset_id: str, stage: str, action: Optional[str] = None) -> None:
    """Update the stage of an asset and record the transition in history."""
    conn = get_connection()
    conn.execute(
        "UPDATE assets SET stage = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (stage, asset_id)
    )
    conn.execute(
        "INSERT INTO asset_history (asset_id, timestamp, action, details) VALUES (?, ?, ?, ?)",
        (asset_id, datetime.now().isoformat(), action or f"stage:{stage}", None)
    )
    conn.commit()
    conn.close()


def update_content_status(content_id: str, status: str) -> None:
    update_asset_stage(content_id, status)


def record_asset_history(asset_id: str, action: str, details: Optional[str] = None) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO asset_history (asset_id, timestamp, action, details) VALUES (?, ?, ?, ?)",
        (asset_id, datetime.now().isoformat(), action, details)
    )
    conn.commit()
    conn.close()


# ─── Variants ──────────────────────────────────────────────────────────────

def upsert_variant(
    asset_id: str,
    platform: str,
    title: Optional[str] = None,
    body: Optional[str] = None,
    tags: Optional[list[str]] = None,
    cover_path: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """Upsert the platform-adapted version of an asset."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO variants (asset_id, platform, title, body, tags, cover_path, extra)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_id, platform) DO UPDATE SET
            title = COALESCE(excluded.title, variants.title),
            body = COALESCE(excluded.body, variants.body),
            tags = COALESCE(excluded.tags, variants.tags),
            cover_path = COALESCE(excluded.cover_path, variants.cover_path),
            extra = COALESCE(excluded.extra, variants.extra)
        """,
        (asset_id, platform, title, body,
         json.dumps(tags) if tags else None, cover_path,
         json.dumps(extra) if extra else None)
    )
    conn.commit()
    conn.close()


def get_variants(asset_id: str) -> list[dict]:
    conn = get_connection()
    rows = [dict(r) for r in conn.execute(
        "SELECT platform, title, body, tags, cover_path, extra FROM variants "
        "WHERE asset_id = ? ORDER BY platform", (asset_id,))]
    conn.close()
    for r in rows:
        if r.get("tags"):
            try:
                r["tags"] = json.loads(r["tags"])
            except json.JSONDecodeError:
                pass
        if r.get("extra"):
            try:
                r["extra"] = json.loads(r["extra"])
            except json.JSONDecodeError:
                pass
    return rows


# ─── Distribution ──────────────────────────────────────────────────────────

def insert_distribution(
    asset_id: str,
    platform: str,
    url: Optional[str] = None,
    status: str = "pending",
    error_message: Optional[str] = None,
    video_id: Optional[int] = None,
) -> int:
    """Insert/update a distribution record (one row per asset+platform, last write wins)."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO distribution (asset_id, video_id, platform, url, status, error_message, published_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_id, platform) DO UPDATE SET
            url = COALESCE(excluded.url, distribution.url),
            status = excluded.status,
            error_message = excluded.error_message,
            published_at = excluded.published_at
        """,
        (asset_id, video_id, platform, url, status, error_message, datetime.now().isoformat())
    )
    conn.commit()
    distribution_id = conn.execute(
        "SELECT id FROM distribution WHERE asset_id = ? AND platform = ?",
        (asset_id, platform)).fetchone()["id"]
    conn.close()
    return distribution_id


def get_distribution_by_asset(asset_id: str) -> list[dict]:
    conn = get_connection()
    rows = [dict(r) for r in conn.execute(
        "SELECT platform, url, status, error_message, published_at FROM distribution "
        "WHERE asset_id = ? ORDER BY published_at DESC", (asset_id,))]
    conn.close()
    return rows


def get_distribution_by_content(content_id: str) -> list[dict]:
    return get_distribution_by_asset(content_id)


def get_asset_stats() -> dict:
    """Aggregate stats: counts by type/stage and by platform."""
    conn = get_connection()
    by_type = [dict(r) for r in conn.execute(
        "SELECT type, COUNT(*) count FROM assets GROUP BY type ORDER BY count DESC")]
    by_stage = [dict(r) for r in conn.execute(
        "SELECT stage, COUNT(*) count FROM assets GROUP BY stage ORDER BY count DESC")]
    by_platform = [dict(r) for r in conn.execute(
        "SELECT platform, COUNT(*) count FROM distribution GROUP BY platform ORDER BY count DESC")]
    conn.close()
    return {
        "total_assets": sum(t["count"] for t in by_type),
        "total_distributions": sum(p["count"] for p in by_platform),
        "by_type": by_type,
        "by_stage": by_stage,
        "by_platform": by_platform,
    }

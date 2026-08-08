"""
publish_* namespace: multi-platform publishing + publish orchestration
(validate-ready / config / simulate / record).
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

from ..db import (
    get_asset_by_slug,
    insert_distribution,
    update_asset_stage,
    upsert_variant,
)
from ..skills.publish import publish_video as _skill_publish_video
from ..skills.publish import publish_article as _skill_publish_article
from ..utils import DOWNLOADS_DIR, VAAS_ROOT

PUBLISH_VIDEOS = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-publish-videos" / "scripts" / "publish.mjs"
PUBLISH_DOCS = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-publish-docs" / "scripts" / "publish.mjs"


def publish_video(
    slug: str,
    platforms: Optional[list[str]] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Publish a video asset to multiple platforms."""
    return _skill_publish_video(slug, platforms, title, description, tags)


def publish_article(
    slug: str,
    platforms: Optional[list[str]] = None,
    title: Optional[str] = None,
    body: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Publish an article asset to multiple platforms."""
    return _skill_publish_article(slug, platforms, title, body, tags)


def publish_validate_ready(slug: str, type: str = "video") -> dict:
    """
    Check whether an asset is ready to publish (exists, staged, files present).

    Returns:
        {ready, slug, type, stage, missing[]}
    """
    asset = get_asset_by_slug(slug)
    if not asset:
        return {"ready": False, "slug": slug, "type": type, "stage": None,
                "missing": [f"asset {slug} not found"]}

    missing = []
    if asset["type"] != type:
        missing.append(f"asset type {asset['type']} != {type}")
    if asset["stage"] not in ("rendered", "published"):
        missing.append(f"asset stage {asset['stage']} not rendered")
    if asset.get("file_path"):
        if not (DOWNLOADS_DIR / asset["file_path"]).exists():
            missing.append(f"file missing: {asset['file_path']}")

    return {"ready": not missing, "slug": slug, "type": asset["type"],
            "stage": asset["stage"], "missing": missing}


def publish_get_config(slug: str, type: str = "video") -> dict:
    """
    Read the publish configuration for an asset (title/tags/platforms).

    Reads the skill's task.json (video) or meta.json (article) when present.
    """
    cfg = {"slug": slug, "type": type}
    if type == "video":
        p = DOWNLOADS_DIR / "fd-videos" / slug / "task.json"
        if p.exists():
            task = json.loads(p.read_text(encoding="utf-8"))
            cfg.update({
                "title": task.get("title"),
                "description": task.get("desc") or task.get("description"),
                "tags": task.get("tags"),
                "platforms": task.get("platforms"),
                "has_covers": task.get("hasCovers", False),
            })
    else:
        p = DOWNLOADS_DIR / "fd-docs" / slug / "meta.json"
        if p.exists():
            meta = json.loads(p.read_text(encoding="utf-8"))
            cfg.update({
                "title": meta.get("title"),
                "summary": meta.get("summary"),
                "tags": meta.get("tags"),
                "platforms": meta.get("platforms"),
                "cover": meta.get("cover"),
            })
    return cfg


def publish_simulate(slug: str, type: str = "video", platforms: Optional[list[str]] = None,
                     title: Optional[str] = None, body: Optional[str] = None,
                     tags: Optional[list[str]] = None) -> dict:
    """
    Dry-run publish: preview the commands/platforms without uploading.

    Runs the skill's publish.mjs in dry-run/plan mode and returns the preview.
    """
    script = PUBLISH_VIDEOS if type == "video" else PUBLISH_DOCS
    flag = "--dry-run" if type == "video" else "--plan"
    cmd = ["node", str(script), "--slug", slug, flag]
    if platforms:
        cmd += ["--platforms", ",".join(platforms)]
    if title:
        cmd += ["--title", title]
    if body:
        cmd += (["--desc", body] if type == "video" else ["--body", body])
    if tags:
        cmd += ["--tags", ",".join(tags)]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(script.parent))
    return {
        "slug": slug, "type": type, "dry_run": True,
        "exit_code": result.returncode,
        "preview": (result.stdout + result.stderr)[-2000:],
    }


def publish_record(slug: str, platform: str, status: str = "uploaded",
                   url: Optional[str] = None, account: Optional[str] = None,
                   title: Optional[str] = None) -> dict:
    """
    Explicitly record a publish result for an asset+platform.

    Upserts the distribution row and per-platform variant, and advances the
    asset stage to published on success.
    """
    asset = get_asset_by_slug(slug)
    if not asset:
        raise ValueError(f"Asset not found: {slug}")

    insert_distribution(asset["id"], platform, url=url, status=status,
                        error_message=None if status == "uploaded" else status)
    if title:
        upsert_variant(asset["id"], platform, title=title,
                       extra={"account": account} if account else None)
    if status == "uploaded":
        update_asset_stage(asset["id"], "published", action=f"record:{platform}")
    return {"slug": slug, "platform": platform, "status": status, "url": url}

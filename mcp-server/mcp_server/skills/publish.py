"""
Publish orchestrator for multi-platform video and article distribution.

Runs fd-vaas-publish-videos / fd-vaas-publish-docs via subprocess, records
per-platform variants, then reads publish results from the unified database
(the skill's publish.mjs writes successes there via db_writer.py).
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from ..db import (
    get_asset_by_slug,
    insert_distribution,
    update_asset_stage,
    upsert_variant,
)
from ..utils import VAAS_ROOT

PUBLISH_VIDEOS_SCRIPTS = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-publish-videos" / "scripts"
PUBLISH_DOCS_SCRIPTS = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-publish-docs" / "scripts"


def _run_and_collect(
    slug: str,
    asset_type: str,
    script: Path,
    cmd_args: list,
    platforms: Optional[list[str]],
    variant_body_key: str,
) -> dict:
    """
    Run the publish script, then reflect its results from the unified DB.

    The skill records successful uploads to `distribution`/`variants` via
    db_writer.py. This wrapper records the platform-adapted variant upfront and
    reports per-platform status from the DB afterwards; platforms missing from
    the DB when the script failed are recorded as failed.
    """
    asset = get_asset_by_slug(slug)
    if not asset:
        raise ValueError(f"Asset not found: {slug}")
    if asset["type"] != asset_type:
        raise ValueError(f"Asset is not a {asset_type}: {slug}")
    if asset["stage"] not in ("rendered", "published"):
        raise ValueError(f"Asset not ready for publishing: {slug} (stage={asset['stage']})")

    asset_id = asset["id"]

    cmd = ["node", str(script), "--slug", slug] + cmd_args
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(script.parent)
    )

    # Refresh asset: db_writer may have added distribution/variants during the run
    asset = get_asset_by_slug(slug) or asset

    results = []
    requested = platforms or []
    if not requested:
        env_key = "PLATFORMS" if asset_type == "video" else "PLATFORMS_DOCS"
        requested = [p for p in (os.getenv(env_key, "") or "").split(",") if p]

    existing = {d["platform"]: d for d in asset["distribution"]}
    for p in requested:
        if p in existing:
            results.append({
                "platform": p,
                "status": existing[p]["status"],
                "url": existing[p]["url"],
                "published_at": existing[p]["published_at"],
            })
        elif result.returncode != 0:
            insert_distribution(asset_id, p, status="failed",
                                error_message=(result.stderr or "")[-300:])
            results.append({"platform": p, "status": "failed"})

    if result.returncode == 0:
        update_asset_stage(asset_id, "published", action=f"publish:{asset_type}")

    return {"results": results, "exit_code": result.returncode}


def publish_video(
    slug: str,
    platforms: Optional[list[str]] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Publish a video asset to multiple platforms."""
    args = []
    if platforms:
        args += ["--platforms", ",".join(platforms)]
    if title:
        args += ["--title", title]
    if description:
        args += ["--desc", description]
    if tags:
        args += ["--tags", ",".join(tags)]

    asset = get_asset_by_slug(slug)
    if asset and title:
        for p in (platforms or []):
            upsert_variant(asset["id"], p, title=title, body=description, tags=tags)

    return _run_and_collect(
        slug, "video", PUBLISH_VIDEOS_SCRIPTS / "publish.mjs",
        args, platforms, "desc"
    )


def publish_article(
    slug: str,
    platforms: Optional[list[str]] = None,
    title: Optional[str] = None,
    body: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Publish an article asset to multiple platforms."""
    args = []
    if platforms:
        args += ["--platforms", ",".join(platforms)]
    if title:
        args += ["--title", title]
    if body:
        args += ["--body", body]
    if tags:
        args += ["--tags", ",".join(tags)]

    asset = get_asset_by_slug(slug)
    if asset and title:
        for p in (platforms or []):
            upsert_variant(asset["id"], p, title=title, body=body, tags=tags)

    return _run_and_collect(
        slug, "article", PUBLISH_DOCS_SCRIPTS / "publish.mjs",
        args, platforms, "body"
    )

"""
VAAS MCP Server — unified material generation, management, and publishing.

Single MCP server exposing namespaced tools:
  generate_*    voice/image generation + async video submit/status (via registry)
  render_*      presentation render plane: video (storyboard/type),
                still (cover/chart/graphic), document (pdf/longimage)
  templates_*   presentation template discovery (video/cover/doc)
  models_voices / voiceover_assemble / reference_clips_check
                voice lane truth table + long-form assembly + ref clips
  publish_*     multi-platform publish + validate/config/simulate/record
  assets_*      material store queries (+ brand asset tree via assets_get kind)
  registry_*    generation method discovery

Wave1 (add-presentation-plane): orchestrate_*/generate_cover/generate_video(同步)/
Remotion discovery 工具与全部 legacy aliases 已退役；generate_cover 保留为
render_still(kind="cover") 的内部实现入口。

Transport:
  stdio (default) — full tool surface, local single-user mode.
  http  (VAAS_TRANSPORT=http, VAAS_HOSTED=1) — hosted tenant mode: publish
        plane excluded (workspace ADR-0004), owner-scoped assets, signed
        download + usage endpoints under the service bearer.
"""

import json
import logging
import os
import threading
import time

log = logging.getLogger("vaas.main")

from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.requests import Request

from .db import (
    ensure_db_exists, get_asset, usage_summary, expire_stale_jobs,
)
from .hosting import (
    current_owner, is_hosted, service_auth_ok, verify_download,
)
from .tools.generate import (
    generate_voice, generate_image, generate_video_submit, video_job_status,
    models_voices, voiceover_assemble, reference_clips_check,
)
from .tools.render import render_video, render_still, render_document
from .tools.templates import templates_list, templates_get
from .tools.publish import (
    publish_video, publish_article,
    publish_validate_ready, publish_get_config, publish_simulate, publish_record,
)
from .tools.assets import assets_list, assets_get, assets_stats
from .tools.registry_tools import registry_list_generators, registry_describe_generator

mcp = FastMCP("VAAS")

# ─── Canonical namespaced tools ────────────────────────────────────────────
# Hosted surface (ADR-0004): the publish plane never ships multi-tenant.
HOSTED_EXCLUDED = {
    publish_video, publish_article,
    publish_validate_ready, publish_get_config, publish_simulate, publish_record,
}

CANONICAL_TOOLS = [
    generate_voice, generate_image, generate_video_submit, video_job_status,
    models_voices, voiceover_assemble, reference_clips_check,
    render_video, render_still, render_document,
    templates_list, templates_get,
    assets_list, assets_get, assets_stats,
    registry_list_generators, registry_describe_generator,
    # publish plane: stdio-only (hosted surface excludes it, ADR-0004)
    publish_video, publish_article,
    publish_validate_ready, publish_get_config, publish_simulate, publish_record,
]
for fn in CANONICAL_TOOLS:
    if is_hosted() and fn in HOSTED_EXCLUDED:
        continue
    mcp.tool()(fn)


# ─── Artifact retention (task 4.5) ─────────────────────────────────────────

ARTIFACT_TTL_DAYS = int(os.getenv("VAAS_ARTIFACT_TTL_DAYS", "30"))


def gc_expired_artifacts(now: float | None = None, ttl_days: int = ARTIFACT_TTL_DAYS) -> int:
    """
    Delete rendered, unpublished assets older than the TTL along with their
    files; succeeded jobs and their assets survive until this TTL passes.
    Returns the number of assets removed.
    """
    import datetime
    import shutil

    from .db import get_connection, DB_PATH
    from .utils import DOWNLOADS_DIR

    cutoff = datetime.datetime.fromtimestamp(
        (now if now is not None else time.time()) - ttl_days * 86400,
        tz=datetime.timezone.utc,
    ).isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, file_path FROM assets WHERE stage = 'rendered' "
        "AND created_at < ? AND id NOT IN (SELECT asset_id FROM distribution)",
        (cutoff,),
    ).fetchall()
    removed = 0
    for row in rows:
        file_path = row["file_path"]
        if file_path:
            target = (DOWNLOADS_DIR / file_path).resolve()
            slug_dir = target.parent
            if slug_dir.is_dir():
                # containment by real path relation, not string prefix
                # (downloads vs downloads_evil prefix trap; fix-hosted-generation-correctness)
                if slug_dir.is_relative_to(DOWNLOADS_DIR.resolve()):
                    shutil.rmtree(slug_dir, ignore_errors=True)
                else:
                    log.warning("GC refused: path escapes downloads: %s", slug_dir)
        conn.execute("DELETE FROM assets WHERE id = ?", (row["id"],))
        removed += 1
    conn.commit()
    conn.close()
    return removed


def _load_pricing(strict: bool) -> dict:
    """Hosted pricing load refuses silent zero-rated metering.

    strict=True (hosted startup): a missing/empty/unreadable table is a
    config error, not a 0.0 default — usage totals would lie forever.
    strict=False (local stdio): {} is fine; local rows are informational.
    """
    pricing_path = os.getenv("VAAS_PRICING_FILE", "pricing.json")
    try:
        with open(pricing_path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        if strict:
            raise RuntimeError(
                f"pricing configuration missing or unreadable: {pricing_path} ({e}); "
                f"hosted mode refuses silent zero-rated metering — set VAAS_PRICING_FILE "
                f"to a valid pricing table"
            ) from e
        return {}
    if not isinstance(doc, dict) or not doc:
        if strict:
            raise RuntimeError(
                f"pricing table {pricing_path} is empty — fill real rates or unset hosted mode"
            )
        return {}
    return doc


def _start_gc_scheduler() -> None:
    """Daily opportunistic GC thread (hosted mode only)."""
    def _loop():
        while True:
            time.sleep(86400)
            try:
                expire_stale_jobs()
                removed = gc_expired_artifacts()
                if removed:
                    log.info("GC reclaimed %d aged assets", removed)
            except Exception as e:
                # A silent disk-leak was the old behavior; disk pressure on
                # deploy nodes is a known incident class — speak instead.
                log.warning("GC cycle failed: %s", e)
    thread = threading.Thread(target=_loop, name="vaas-gc", daemon=True)
    thread.start()


# ─── Custom HTTP routes (hosted mode; local stdio never serves them) ───────

@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "hosted": is_hosted()})


@mcp.custom_route("/download/{asset_id}", methods=["GET"])
async def download_asset(request: Request) -> JSONResponse:
    """Signed, expiring download for one owned asset.

    The HMAC signature (asset_id+owner+exp) IS the credential here — tenant
    agents never hold the service bearer (design D19), so no bearer check.
    """
    asset_id = request.path_params["asset_id"]
    q = request.query_params
    owner, exp, sig = q.get("owner"), q.get("exp"), q.get("signature")
    try:
        if not owner or not exp or not verify_download(asset_id, owner, int(exp), sig):
            return JSONResponse({"error": "invalid or expired link"}, status_code=403)
    except ValueError:
        return JSONResponse({"error": "invalid or expired link"}, status_code=403)

    asset = get_asset(asset_id, owner=owner)
    file_path = (asset or {}).get("file_path")
    if not asset or not file_path:
        return JSONResponse({"error": "asset not found"}, status_code=404)

    from .utils import DOWNLOADS_DIR
    from starlette.responses import FileResponse

    target = (DOWNLOADS_DIR / file_path).resolve()
    if not str(target).startswith(str(DOWNLOADS_DIR.resolve())) or not target.is_file():
        return JSONResponse({"error": "asset file missing"}, status_code=404)
    return FileResponse(target)


@mcp.custom_route("/usage/summary", methods=["GET"])
async def usage_report(request: Request) -> JSONResponse:
    """Read-only priced usage rollup (owner x tool), service credential required."""
    if not service_auth_ok(request):
        return JSONResponse({"error": "authentication required"}, status_code=401)

    try:
        pricing = _load_pricing(strict=is_hosted())
    except RuntimeError as e:
        return JSONResponse({"error": f"pricing_unconfigured: {e}"}, status_code=503)

    def _price(row: dict) -> float:
        rate = (pricing.get(row["tool"]) or {}).get(row["unit_type"], 0.0)
        return round(float(row.get("units") or 0) * float(rate), 6)

    rows = usage_summary(
        owner=None,
        since=request.query_params.get("since"),
        until=request.query_params.get("until"),
    )
    for row in rows:
        row["amount"] = _price(row)
    total = round(sum(r["amount"] for r in rows), 6)
    return JSONResponse({"items": rows, "total_amount": total, "currency": pricing.get("currency", "CNY")})


# ─── Entry point ───────────────────────────────────────────────────────────

def main():
    """Run the MCP server: stdio locally, streamable HTTP in hosted mode."""
    ensure_db_exists()
    from .tools.render import ensure_bgm_library
    ensure_bgm_library()  # W4.1: 首启注册种子 BGM 曲库为全局资产（幂等）
    if is_hosted():
        # Pricing is a startup dependency of the hosted plane: a missing/
        # empty table means every usage total would silently be ¥0 —
        # refuse boot loudly instead (fix-hosted-generation-correctness).
        _load_pricing(strict=True)
        expire_stale_jobs()
        gc_expired_artifacts()
        _start_gc_scheduler()
        mcp.run(transport="http", host=os.getenv("VAAS_BIND", "0.0.0.0"),
                port=int(os.getenv("VAAS_PORT", "30950")))
    else:
        mcp.run()


if __name__ == "__main__":
    main()

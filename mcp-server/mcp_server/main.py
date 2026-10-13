"""
VAAS MCP Server — unified material generation, management, and publishing.

Single MCP server exposing namespaced tools:
  generate_*    voice/image/video/cover generation (via registry)
  orchestrate_* voiceover / brainstorm pipelines
  publish_*     multi-platform publish + validate/config/simulate/record
  assets_*      material store queries + Remotion asset discovery
  registry_*    generation method discovery

Legacy tool names remain registered as deprecated aliases.

Transport:
  stdio (default) — full tool surface, local single-user mode.
  http  (VAAS_TRANSPORT=http, VAAS_HOSTED=1) — hosted tenant mode: publish
        plane excluded (workspace ADR-0004), owner-scoped assets, signed
        download + usage endpoints under the service bearer.
"""

import json
import os
import threading
import time

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
    generate_voice, generate_image, generate_video, generate_cover,
    generate_video_submit, video_job_status,
)
from .tools.orchestrate import orchestrate_voiceover, orchestrate_brainstorm
from .tools.publish import (
    publish_video, publish_article,
    publish_validate_ready, publish_get_config, publish_simulate, publish_record,
)
from .tools.assets import (
    assets_list, assets_get, assets_stats,
    assets_list_common, assets_find_logo, assets_list_compositions,
    assets_validate_paths, assets_get_scene_templates,
)
from .tools.registry_tools import registry_list_generators, registry_describe_generator

mcp = FastMCP("VAAS")

# ─── Canonical namespaced tools ────────────────────────────────────────────
# Hosted surface (ADR-0004): the publish plane never ships multi-tenant, and
# the synchronous video tool stays local-only (double-billing guard — hosted
# tenants use generate_video_submit / video_job_status).
HOSTED_EXCLUDED = {
    publish_video, publish_article,
    publish_validate_ready, publish_get_config, publish_simulate, publish_record,
    generate_video,
}

CANONICAL_TOOLS = [
    generate_voice, generate_image, generate_video, generate_cover,
    generate_video_submit, video_job_status,
    orchestrate_voiceover, orchestrate_brainstorm,
    publish_video, publish_article,
    publish_validate_ready, publish_get_config, publish_simulate, publish_record,
    assets_list, assets_get, assets_stats,
    assets_list_common, assets_find_logo, assets_list_compositions,
    assets_validate_paths, assets_get_scene_templates,
    registry_list_generators, registry_describe_generator,
]
for fn in CANONICAL_TOOLS:
    if is_hosted() and fn in HOSTED_EXCLUDED:
        continue
    mcp.tool()(fn)

# ─── Deprecated legacy aliases ─────────────────────────────────────────────
LEGACY_ALIASES = [
    ("create_cover_image", generate_cover, "Use generate_cover"),
    ("create_voiceover", orchestrate_voiceover, "Use orchestrate_voiceover"),
    ("brainstorm_content", orchestrate_brainstorm, "Use orchestrate_brainstorm"),
    ("publish_video_to_platforms", publish_video, "Use publish_video"),
    ("publish_article_to_platforms", publish_article, "Use publish_article"),
    ("list_all_content", assets_list, "Use assets_list"),
    ("get_content_details", assets_get, "Use assets_get"),
]
for name, fn, hint in LEGACY_ALIASES:
    if is_hosted() and fn in HOSTED_EXCLUDED:
        continue
    mcp.tool(name=name, description=f"{fn.__doc__ or ''} (deprecated: {hint})")(fn)


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
            if slug_dir.is_dir() and str(slug_dir).startswith(str(DOWNLOADS_DIR.resolve())):
                shutil.rmtree(slug_dir, ignore_errors=True)
        conn.execute("DELETE FROM assets WHERE id = ?", (row["id"],))
        removed += 1
    conn.commit()
    conn.close()
    return removed


def _start_gc_scheduler() -> None:
    """Daily opportunistic GC thread (hosted mode only)."""
    def _loop():
        while True:
            time.sleep(86400)
            try:
                expire_stale_jobs()
                gc_expired_artifacts()
            except Exception:
                pass
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

    pricing_path = os.getenv("VAAS_PRICING_FILE", "pricing.json")
    pricing = {}
    try:
        with open(pricing_path, encoding="utf-8") as f:
            pricing = json.load(f)
    except (OSError, ValueError):
        pricing = {}

    def _price(row: dict) -> float:
        key = f"{row['tool']}.{row['unit_type']}"
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
    if is_hosted():
        expire_stale_jobs()
        gc_expired_artifacts()
        _start_gc_scheduler()
        mcp.run(transport="http", host=os.getenv("VAAS_BIND", "0.0.0.0"),
                port=int(os.getenv("VAAS_PORT", "30950")))
    else:
        mcp.run()


if __name__ == "__main__":
    main()

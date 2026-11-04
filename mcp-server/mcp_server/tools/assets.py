"""
assets_* namespace: material store queries (内容库) + 品牌资产树查询.

原 assets_list_common / assets_find_logo 的查询逻辑折入 assets_get(kind=...)；
Remotion composition/scene 模板发现工具已随注册面退役（render 面由
render_video/render_still 承担）。
"""

from pathlib import Path
from typing import Optional

from ..db import get_asset_stats as _db_stats
from ..hosting import current_owner, download_url, is_hosted
from ..skills.query import list_assets as _skill_list_assets
from ..skills.query import get_asset as _skill_get_asset
from ..utils import VAAS_ROOT

COMMON_DIR = VAAS_ROOT / "downloads" / "common"
PUBLIC_DIR = VAAS_ROOT / "remotion-app" / "public"

ASSET_KINDS = ("common", "logo")  # assets_get(kind=...) 的资产树查询域


# ─── Asset store queries ───────────────────────────────────────────────────
# Content-store queries are owner-scoped in hosted mode; the brand-asset tree
# (kind=common/logo) is platform-level and stays unfiltered.

def assets_list(type: Optional[str] = None, stage: Optional[str] = None,
                limit: int = 100) -> dict:
    """List asset summaries with optional filters (own assets only in hosted mode)."""
    result = _skill_list_assets(type=type, stage=stage, limit=limit,
                                owner=current_owner())
    if is_hosted():
        for item in result.get("items", []):
            url = download_url(item["id"], current_owner())
            if url:
                item["download_url"] = url
    return result


def assets_get(id: Optional[str] = None, slug: Optional[str] = None,
               kind: Optional[str] = None) -> dict:
    """Get full asset details (lineage, variants, distribution); own assets only in hosted mode.

    In hosted mode the response carries a fresh signed download_url so remote
    tenants can pull the artifact without a generation call.

    资产树查询：kind="common" 列 downloads/common 与 remotion public 的公共
    资产（brand assets）；kind="logo" 只列 logo/icon 类。给定 kind 时忽略
    id/slug，走文件系统扫描（不分 owner）。
    """
    if kind is not None:
        if kind not in ASSET_KINDS:
            raise ValueError(
                f"unknown asset kind: {kind}. Available: {list(ASSET_KINDS)} "
                "(omit kind for a content-store lookup by id/slug)")
        want = "logo" if kind == "logo" else "all"
        assets = []
        assets.extend(_scan_dir(COMMON_DIR, 'common', want))
        assets.extend(_scan_dir(PUBLIC_DIR, 'public', want))
        if kind == "logo" and not assets:
            assets.extend(_scan_dir(COMMON_DIR, 'common', 'icon'))
            assets.extend(_scan_dir(PUBLIC_DIR, 'public', 'icon'))
        return {"kind": kind, "assets": assets, "total": len(assets)}

    asset = _skill_get_asset(id=id, slug=slug, owner=current_owner())
    if asset and is_hosted() and asset.get("file_path"):
        url = download_url(asset["id"], asset.get("owner") or current_owner())
        if url:
            asset["download_url"] = url
    return asset


def assets_stats() -> dict:
    """Aggregate stats by asset type/stage and platform (own assets in hosted mode)."""
    return _db_stats(owner=current_owner())


# ─── Brand asset tree scan (folded-in common/logo query) ───────────────────

def _classify_asset(filename: str) -> str:
    name = filename.lower()
    ext = Path(filename).suffix.lower()
    if 'logo' in name:
        return 'logo'
    if 'icon' in name or ext in ('.ico',):
        return 'icon'
    if 'bg' in name or 'background' in name or 'cover' in name:
        return 'background'
    if 'introduce' in name or 'company' in name:
        return 'company'
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'):
        return 'image'
    if ext in ('.mp4', '.mov', '.webm', '.avi'):
        return 'video'
    if ext in ('.mp3', '.wav', '.aac', '.m4a', '.flac'):
        return 'audio'
    if ext in ('.json',):
        return 'data'
    return 'other'


def _scan_dir(directory: Path, location: str, asset_type: str = 'all'):
    assets = []
    if not directory.exists():
        return assets
    for entry in sorted(directory.iterdir()):
        if entry.is_file() and not entry.name.startswith('.'):
            classified = _classify_asset(entry.name)
            if asset_type == 'all' or classified == asset_type:
                stat = entry.stat()
                assets.append({
                    'name': entry.name,
                    'type': classified,
                    'path': str(entry),
                    'size_kb': round(stat.st_size / 1024, 1),
                    'location': location,
                })
    return assets

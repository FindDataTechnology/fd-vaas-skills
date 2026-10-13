"""
assets_* namespace: material store queries + Remotion asset discovery.
(Merges the former vaas-video-assets discovery tools.)
"""

import json
import re
from pathlib import Path
from typing import Optional

from ..db import get_asset_stats as _db_stats
from ..hosting import current_owner, download_url, is_hosted
from ..skills.query import list_assets as _skill_list_assets
from ..skills.query import get_asset as _skill_get_asset
from ..utils import VAAS_ROOT

COMMON_DIR = VAAS_ROOT / "downloads" / "common"
PUBLIC_DIR = VAAS_ROOT / "remotion-app" / "public"
SRC_DIR = VAAS_ROOT / "remotion-app" / "src"


# ─── Asset store queries ───────────────────────────────────────────────────
# Content-store queries are owner-scoped in hosted mode; the Remotion
# discovery tools below are platform brand assets and stay unfiltered.

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


def assets_get(id: Optional[str] = None, slug: Optional[str] = None) -> dict:
    """Get full asset details (lineage, variants, distribution); own assets only in hosted mode.

    In hosted mode the response carries a fresh signed download_url so remote
    tenants can pull the artifact without a generation call.
    """
    asset = _skill_get_asset(id=id, slug=slug, owner=current_owner())
    if asset and is_hosted() and asset.get("file_path"):
        url = download_url(asset["id"], asset.get("owner") or current_owner())
        if url:
            asset["download_url"] = url
    return asset


def assets_stats() -> dict:
    """Aggregate stats by asset type/stage and platform (own assets in hosted mode)."""
    return _db_stats(owner=current_owner())


# ─── Remotion asset discovery (from former vaas-video-assets) ──────────────

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


def assets_list_common(asset_type: str = 'all') -> dict:
    """List common assets in downloads/common and remotion public."""
    assets = []
    assets.extend(_scan_dir(COMMON_DIR, 'common', asset_type))
    assets.extend(_scan_dir(PUBLIC_DIR, 'public', asset_type))
    return {'assets': assets, 'total': len(assets)}


def assets_find_logo() -> dict:
    """Find the company logo asset(s)."""
    assets = []
    assets.extend(_scan_dir(COMMON_DIR, 'common', 'logo'))
    assets.extend(_scan_dir(PUBLIC_DIR, 'public', 'logo'))
    if not assets:
        assets.extend(_scan_dir(COMMON_DIR, 'common', 'icon'))
        assets.extend(_scan_dir(PUBLIC_DIR, 'public', 'icon'))
    return {'logos': assets, 'total': len(assets)}


def assets_list_compositions() -> dict:
    """List registered Remotion compositions (id + duration)."""
    comp_file = SRC_DIR / 'Composition.tsx'
    if not comp_file.exists():
        return {'error': 'Composition.tsx not found'}
    content = comp_file.read_text(encoding="utf-8")
    compositions = []
    pattern = re.compile(r'id="([^"]+)"[\s\S]*?durationInFrames=\{(\d+)', re.MULTILINE)
    for match in pattern.finditer(content):
        compositions.append({
            'id': match.group(1),
            'durationInFrames': int(match.group(2)),
            'durationSeconds': round(int(match.group(2)) / 30, 1),
        })
    return {'compositions': compositions, 'total': len(compositions)}


def assets_validate_paths(composition_id: str = 'all') -> dict:
    """Validate staticFile() asset paths referenced in Remotion source."""
    issues = []
    valid = []
    for src_file in SRC_DIR.glob('*.tsx'):
        content = src_file.read_text(encoding="utf-8")
        for match in re.finditer(r'staticFile\(["\']([^"\']+)["\']', content):
            asset_path = match.group(1)
            if asset_path.startswith('http'):
                continue
            full_path = PUBLIC_DIR / asset_path
            entry = {
                'asset': asset_path,
                'referenced_in': src_file.name,
                'exists': full_path.exists(),
                'full_path': str(full_path),
            }
            if entry['exists']:
                valid.append(entry)
            else:
                issues.append(entry)
    return {
        'missing': issues,
        'valid_count': len(valid),
        'missing_count': len(issues),
        'all_valid': len(issues) == 0,
    }


def assets_get_scene_templates() -> dict:
    """List scene template components from scenes*.tsx files."""
    scenes = []
    for src_file in sorted(SRC_DIR.glob('scenes*.tsx')):
        content = src_file.read_text(encoding="utf-8")
        for match in re.finditer(r'export const (\w+)', content):
            scenes.append({'name': match.group(1), 'sourceFile': src_file.name})
    return {'scenes': scenes, 'total': len(scenes)}

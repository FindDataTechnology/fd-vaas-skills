"""
templates_* namespace: presentation template discovery (video / cover / doc).

三个域各自的模板真相源:
  video — .agents/skills/fd-vaas-video-creator/types/<id>/type.json
          （render_video(type=...) 的类型清单与输入契约）
  cover — CoverBrand（remotion 静帧，render_still(kind="cover") 的版式）
  doc   — mcp_server/templates/doc/<id>/（template.json + css，
          render_document 的版式；本波内置 default 占位版式）
"""

import json
from pathlib import Path
from typing import Optional

from ..utils import VAAS_ROOT

VIDEO_TYPES_DIR = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-video-creator" / "types"
DOC_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "doc"

TEMPLATES_DOMAINS = ("video", "cover", "doc")

# cover 域：CoverBrand 静帧版式（skills/cover.py 的 remotion 静帧路径）
COVER_TEMPLATES = [
    {
        "id": "brand",
        "name": "CoverBrand",
        "description": "品牌封面静帧（title/subtitle/tags，horizontal/vertical/square）。",
        "status": "active",
        "orientation": ["horizontal", "vertical", "square"],
        "default_size": "1920x1080",
    },
]

# doc 域 default 版式的契约说明（templates_get 用）
_DOC_TEMPLATE_CONTRACT = (
    "doc 版式目录 = template.json（元数据+参数契约）+ style.css（版式样式）。"
    "render_document(source, format, template) 用版式渲染 md/html 文本为 "
    "pdf/longimage。template.json: {id, name, description, formats, "
    "page:{size, margin}, fonts}。"
)


def _load_video_types() -> list[dict]:
    items = []
    if not VIDEO_TYPES_DIR.is_dir():
        return items
    for d in sorted(VIDEO_TYPES_DIR.iterdir()):
        type_json = d / "type.json"
        if not type_json.is_file():
            continue
        try:
            raw = json.loads(type_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append({
            "id": raw.get("id") or d.name,
            "name": raw.get("name"),
            "description": raw.get("description"),
            "status": raw.get("status"),
        })
    return items


def _load_doc_templates() -> list[dict]:
    items = []
    if not DOC_TEMPLATES_DIR.is_dir():
        return items
    for d in sorted(DOC_TEMPLATES_DIR.iterdir()):
        meta = d / "template.json"
        if not meta.is_file():
            continue
        try:
            raw = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append({
            "id": raw.get("id") or d.name,
            "name": raw.get("name"),
            "description": raw.get("description"),
            "status": raw.get("status", "active"),
            "formats": raw.get("formats") or ["pdf", "longimage"],
        })
    return items


def templates_list(domain: Optional[str] = None) -> dict:
    """List presentation templates by domain: video | cover | doc.

    video 版式即 render_video(type=...) 的类型清单；cover 为 CoverBrand 静帧；
    doc 为 render_document 的版式（default 内置）。domain=None 列全部三域。
    """
    if domain is not None and domain not in TEMPLATES_DOMAINS:
        raise ValueError(
            f"unknown template domain: {domain}. Available: {list(TEMPLATES_DOMAINS)}")
    domains = [domain] if domain else list(TEMPLATES_DOMAINS)
    out: dict = {}
    for d in domains:
        if d == "video":
            out["video"] = _load_video_types()
        elif d == "cover":
            out["cover"] = COVER_TEMPLATES
        elif d == "doc":
            out["doc"] = _load_doc_templates()
    total = sum(len(v) for v in out.values())
    return {"domains": domains, "templates": out, "total": total}


def templates_get(domain: str, id: str) -> dict:
    """Get one template's detail / input contract.

    video → types/<id>/type.json 原文（inputs 契约 + pipeline + composition）；
    cover/doc → 注册表条目 + 契约说明。
    """
    if domain not in TEMPLATES_DOMAINS:
        raise ValueError(
            f"unknown template domain: {domain}. Available: {list(TEMPLATES_DOMAINS)}")
    if domain == "video":
        type_json = VIDEO_TYPES_DIR / id / "type.json"
        if not type_json.is_file():
            known = [t["id"] for t in _load_video_types()]
            raise ValueError(f"unknown video template: {id}. Available: {known}")
        return {"domain": "video", **json.loads(type_json.read_text(encoding="utf-8"))}
    if domain == "cover":
        entry = next((t for t in COVER_TEMPLATES if t["id"] == id), None)
        if not entry:
            raise ValueError(
                f"unknown cover template: {id}. Available: {[t['id'] for t in COVER_TEMPLATES]}")
        return {
            "domain": "cover",
            **entry,
            "contract": "render_still(kind='cover', spec={title, subtitle?, tags?, "
                        "orientation?, size?})；底层为 remotion 静帧（generate-cover.mjs）。",
        }
    # doc
    entry = next((t for t in _load_doc_templates() if t["id"] == id), None)
    if not entry:
        raise ValueError(
            f"unknown doc template: {id}. Available: {[t['id'] for t in _load_doc_templates()]}")
    return {"domain": "doc", **entry, "contract": _DOC_TEMPLATE_CONTRACT}

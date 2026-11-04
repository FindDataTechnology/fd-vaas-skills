"""
Graphic still renderer (render_still(kind="graphic") 的 chromium 内核).

W2 (add-presentation-plane)：调用方 HTML + 品牌 CSS wrapper → chromium 单帧
截图 → 统一 assets 账本。

契约（render.py 分发以 spec dict 传入）:
  spec: {
    html: "...",                        # 必填；整页（含 <html>）或片段均可
    size:  {width, height} | [w, h],    # 可选，默认 1080x1920（VAAS 竖版）
    format: "png"(默认) | "svg" 位图截屏仅 png；svg 走整页 OUTER html 落盘,
  }

品牌 CSS wrapper：品牌变量从 echarts-theme.json 的 brand 块取（同一
theme.ts 单一来源），注入 :root 自定义属性（--vaas-bg/--vaas-text/
--vaas-accent/--vaas-font-sans…），字体栈覆盖部署镜像的 fonts-noto-cjk
（家族名 Noto Sans CJK SC，由生成器折入 fontSans）。
  - 片段 html → 包进 <div data-stage>（尺寸 = spec.size，品牌底色/字体基线）
  - 整页 html   → 只注入 <style id="vaas-brand">（:root 变量 + 字体基线），
    不改调用方结构，调用方 CSS 可直接消费变量

产物落 downloads/graphic/<slug>/，insert_content 落统一 assets 账本
（type=graphic）并附 download_url（hosted 模式），usage 记 tool="render_still"。
slug 缺省按 spec 规范化哈希派生，同一 spec 幂等重放既有资产。

playwright 交互集中在 _capture_graphic / _chromium（与 still_chart 共享），
测试 mock 即可全链不碰真浏览器；真实像素级渲染由部署探针兜底。
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

from ..db import (generate_id, insert_content, record_usage, scoped_asset_slug,
                  get_asset_by_slug, delete_asset)
from ..utils import (DOWNLOADS_DIR, ensure_directory_rel, get_relative_path,
                     validate_slug)
from ..hosting import current_owner, download_url, is_hosted
from ._scene_guard import assert_no_external_refs
from .render import _launch_kwargs
from .still_chart import (_chromium, _js_json, _load_theme_doc, _parse_size,
                          SETTLE_MS, VALID_FORMATS)

DEFAULT_SIZE = (1080, 1920)


def _brand_style(brand: dict) -> str:
    """theme.json brand 块 → :root 品牌变量（still_graphic 的取数边界）。"""
    return ":root{" + ";".join(
        f"--vaas-{key}:{value}" for key, value in brand.items()) + "}"


def _base_rules(w: int, h: int) -> str:
    return (
        "*{box-sizing:border-box}"
        f"[data-stage]{{position:relative;width:{w}px;height:{h}px;"
        "overflow:hidden}"
        "body{font-family:var(--vaas-font-sans);color:var(--vaas-text);"
        "background:var(--vaas-bg)}"
    )


def _wrap_graphic_html(html: str, theme_doc: dict, size: tuple) -> str:
    """调用方 HTML + 品牌 CSS wrapper（见模块 docstring 的两种形态）。"""
    w, h = size
    brand = theme_doc.get("brand") or {}
    style = f'<style id="vaas-brand">{_brand_style(brand)}{_base_rules(w, h)}</style>'
    if re.search(r"<html[\s>]", html, re.IGNORECASE):
        # 整页：只注入品牌 <style>，不动调用方结构
        if "</head>" in html.lower():
            idx = html.lower().index("</head>")
            return html[:idx] + style + html[idx:]
        return style + html
    # 片段：品牌底色 stage 盒 + 居中基线
    bg = brand.get("bg", "#0a0e14")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">{style}
<style>html,body{{margin:0;padding:0;background:{bg}}}</style></head>
<body><div data-stage>
{html}
</div></body></html>
"""


def _capture_graphic(html: str, size: tuple, out_path: Path) -> None:
    """One-frame chromium screenshot of the wrapped page (viewport-clipped)."""
    with _chromium(size) as page:
        page.goto("about:blank")
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(SETTLE_MS)
        page.screenshot(path=str(out_path),
                        clip={"x": 0, "y": 0, "width": size[0], "height": size[1]})


def _replay_or_none(scoped: str, owner: str) -> Optional[dict]:
    """同 slug 已有成功记录且文件在 → 幂等重放；failed/缺失 → 删除重建。"""
    replay = get_asset_by_slug(scoped, owner=owner)
    if replay is None:
        return None
    rel = replay.get("file_path") or ""
    if replay.get("stage") != "failed" and rel and (DOWNLOADS_DIR / rel).exists():
        meta = replay.get("metadata") or {}
        result = {
            "id": replay["id"], "slug": replay["slug"], "file_path": rel,
            "format": meta.get("format"), "width": meta.get("width"),
            "height": meta.get("height"), "type": replay.get("type"),
            "idempotent_replay": True,
        }
        if is_hosted():
            url = download_url(replay["id"], owner)
            if url:
                result["download_url"] = url
        return result
    delete_asset(replay["id"])
    return None


def render_graphic(spec: dict, slug: Optional[str] = None, format: str = "png") -> dict:
    """Render one generic graphic still from caller HTML (local chromium driver).

    render.py 分发以 spec dict 传入：spec = {html 必填,
    size?: {width, height} | [w, h]（默认 1080x1920）, format?: "png"}。
    返回 {id, slug, file_path, format, width, height[, download_url]}。
    """
    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")
    html = spec.get("html")
    if not html or not isinstance(html, str):
        raise ValueError("spec.html (caller HTML, full page or fragment) is required")
    # W6.1c: caller HTML 外链硬校验（外置场景无外链渲染，违规资源逐条点名）
    assert_no_external_refs(html, label="graphic caller html")
    fmt = spec.get("format") or format
    if fmt not in VALID_FORMATS:
        raise ValueError(f"format must be one of {VALID_FORMATS}, got: {fmt!r}")
    if fmt != "png":
        raise ValueError("render_graphic format: only 'png' is supported (svg "
                         "still is a chart-plane capability)")
    size = _parse_size(spec["size"]) if spec.get("size") is not None else DEFAULT_SIZE
    w, h = size
    if slug is not None and not validate_slug(slug):
        raise ValueError(f"invalid slug: {slug!r} (lowercase letters/numbers/"
                         "hyphens, min length 2)")

    theme_doc = _load_theme_doc()

    if not slug:
        canonical = json.dumps(
            {"html": html, "size": list(size)},
            ensure_ascii=False, sort_keys=True)
        slug = f"graphic-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"

    owner = current_owner()
    scoped = scoped_asset_slug(slug, owner)
    replayed = _replay_or_none(scoped, owner)
    if replayed is not None:
        return replayed

    out_dir = ensure_directory_rel("graphic", slug)
    out_path = out_dir / f"{slug}.png"
    rel_path = get_relative_path("graphic", slug, out_path.name)

    page_html = _wrap_graphic_html(html, theme_doc, size)
    _capture_graphic(page_html, size, out_path)
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise RuntimeError(f"graphic capture produced no output: {out_path}")

    content_id = generate_id()
    insert_content(
        id=content_id, type="graphic", slug=scoped, file_path=rel_path,
        metadata={"kind": "graphic_still", "format": "png", "width": w,
                  "height": h, "wrapper": "brand-css",
                  "generator": "playwright"},
        status="rendered", owner=owner,
    )
    record_usage(
        owner=owner, tool="render_still", provider="local", model="chromium",
        units=1, unit_type="render", credential_source="local",
        asset_id=content_id,
    )

    result = {
        "id": content_id, "slug": scoped, "file_path": rel_path,
        "format": "png", "width": w, "height": h, "type": "graphic",
    }
    if is_hosted():
        url = download_url(content_id, owner)
        if url:
            result["download_url"] = url
    return result

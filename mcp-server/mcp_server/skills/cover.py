"""封面图生成（chromium 静态出口，W6.5 起不再依赖 Remotion）。

品牌封面 = 品牌渐变底 + 强调色条 + 标题/副标题/标签，用 chromium 单帧截图
（与 still_graphic 同底座、同字体栈、同品牌令牌）。返回结构与账本口径
（type=image / tool=generate_cover）保持与旧实现一致。
"""

import logging
from typing import Optional

from ..db import insert_content, generate_id, record_usage, scoped_asset_slug
from ..hosting import current_owner
from ..utils import ensure_directory_rel, get_relative_path

log = logging.getLogger("vaas.cover")

_ORIENT_SIZES = {
    "horizontal": (1920, 1080),
    "vertical": (1080, 1440),
    "square": (1080, 1080),
}

_COVER_CSS = """
.cover{position:absolute;inset:0;display:flex;flex-direction:column;
  justify-content:flex-end;padding:8% 7%;
  background:linear-gradient(155deg,var(--vaas-bg) 0%,var(--vaas-bg1) 52%,
             var(--vaas-surface) 100%)}
.accent{position:absolute;left:7%;top:9%;width:12%;height:10px;
  border-radius:5px;background:var(--vaas-accent)}
.kicker{font-size:28px;letter-spacing:10px;color:var(--vaas-accent);
  font-weight:700;margin-bottom:26px}
.title{font-size:74px;line-height:1.22;font-weight:800;color:var(--vaas-text);
  letter-spacing:1px;word-break:break-word}
.sub{margin-top:26px;font-size:34px;line-height:1.5;color:var(--vaas-muted)}
.tags{margin-top:30px;display:flex;gap:16px;flex-wrap:wrap}
.tag{font-size:24px;padding:8px 18px;border-radius:999px;
  border:1px solid var(--vaas-border);color:var(--vaas-muted)}
"""


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _cover_html(title: str, subtitle: Optional[str], tags: Optional[str],
                w: int, h: int) -> str:
    tag_html = ""
    if tags:
        items = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
        tag_html = ('<div class="tags">'
                    + "".join(f'<span class="tag">{_esc(t)}</span>' for t in items)
                    + "</div>")
    return (
        f'<style>{_COVER_CSS}</style>'
        '<div class="cover"><div class="accent"></div>'
        '<div class="kicker">寻数科技</div>'
        f'<div class="title">{_esc(title)}</div>'
        + (f'<div class="sub">{_esc(subtitle)}</div>' if subtitle else "")
        + tag_html
        + "</div>"
    )


def create_cover(
    title: str,
    subtitle: Optional[str] = None,
    tags: Optional[str] = None,
    orientation: str = "horizontal",
    size: Optional[str] = None,
    template: str = "brand",
    slug: Optional[str] = None,
) -> dict:
    """渲染品牌封面（chromium 单帧），落账并返回账本行。

    orientation: horizontal / vertical / square；size: 自定义 "WxH"（覆盖 orientation）。
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("cover title must be a non-empty string")
    if template != "brand":
        raise ValueError(f"unknown cover template: {template!r} (only 'brand')")

    if size:
        try:
            width, height = (int(v) for v in size.lower().split("x", 1))
        except (ValueError, AttributeError):
            raise ValueError(f"invalid cover size: {size!r} (expect WxH)")
    else:
        if orientation not in _ORIENT_SIZES:
            raise ValueError(
                f"unknown orientation: {orientation!r} "
                f"(one of {sorted(_ORIENT_SIZES)})")
        width, height = _ORIENT_SIZES[orientation]

    # 复用 still_graphic 的品牌 wrapper + chromium 截图（同一渲染底座）
    from ..tools.still_graphic import (_capture_graphic, _wrap_graphic_html)
    from ..tools.typed_scenes.theme import load_theme

    html = _wrap_graphic_html(
        _cover_html(title, subtitle, tags, width, height),
        load_theme(), (width, height))

    out_dir = ensure_directory_rel("images", slug or title[:40])
    filename = f"{slug or 'cover'}.png"
    out_path = out_dir / filename
    _capture_graphic(html, (width, height), out_path)

    owner = current_owner()
    scoped = scoped_asset_slug(slug or f"cover-{title[:24]}", owner)
    content_id = generate_id()
    insert_content(
        id=content_id, type="image", slug=scoped,
        file_path=get_relative_path("images", slug or title[:40], filename),
        metadata={"title": title, "subtitle": subtitle, "tags": tags,
                  "orientation": orientation, "template": template,
                  "width": width, "height": height,
                  "generator": "chromium"},
        status="rendered", owner=owner,
    )
    record_usage(owner, "generate_cover", "chromium", None,
                 file_size_bytes(out_path) or 1, "image", "local",
                 asset_id=content_id)
    return {"id": content_id, "slug": scoped,
            "file_path": get_relative_path("images", slug or title[:40], filename),
            "width": width, "height": height, "format": "png"}


def file_size_bytes(path) -> Optional[int]:
    try:
        return path.stat().st_size
    except OSError:
        return None

"""封面图生成（chromium 静态出口，W6.5 起不再依赖 Remotion）。

品牌封面 = 品牌渐变底 + 强调色条 + 标题/副标题/标签，用 chromium 单帧截图
（与 still_graphic 同底座、同字体栈、同品牌令牌）。返回结构与账本口径
（type=image / tool=generate_cover）保持与旧实现一致。
"""

import logging
from typing import Optional

from ..db import insert_content, generate_id, record_usage, scoped_asset_slug
from ..hosting import current_owner, is_hosted
from ..utils import ensure_directory_rel, get_relative_path

log = logging.getLogger("vaas.cover")

_ORIENT_SIZES = {
    "horizontal": (1920, 1080),
    "vertical": (1080, 1440),
    "square": (1080, 1080),
}

# 底座与出片同源：品牌色双柔光 + 竖向 surface 提亮（与 builders/_stage.BASE_BG 同口径）。
# 单色 #0a0e14 铺满时整张封面 YAVG≈19，就是「一片黑」那一档；柔光把底子抬起来，
# 仍是品牌深色系、不引入新色值。

_COVER_CSS = (
    # 底色只用品牌变量（linear-gradient 三停），品牌的「亮」由下面两层柔光叠出来：
    # color-mix 在 still_graphic 的 chromium 里不一定可用，一旦不支持整条声明失效、
    # 画面反而更黑（实测 YAVG 20.7 → 16.6）。柔光层用 radial-gradient + opacity，
    # 只依赖 --vaas-accent / --vaas-palette-N（后者带 accent 回退）。
    ".cover{position:absolute;inset:0;display:flex;flex-direction:column;"
    "justify-content:flex-end;padding:8% 7%;overflow:hidden;"
    "background:linear-gradient(155deg,var(--vaas-bg) 0%,var(--vaas-bg1) 52%,"
    "var(--vaas-surface) 100%)}"
    ".glow-a{position:absolute;left:-12%;top:-18%;width:85%;height:62%;"
    "background:radial-gradient(closest-side,"
    "var(--vaas-accent),transparent 72%);opacity:.22}"
    ".glow-b{position:absolute;right:-15%;bottom:-20%;width:75%;height:55%;"
    "background:radial-gradient(closest-side,"
    "var(--vaas-palette-2,var(--vaas-accent)),transparent 72%);opacity:.13}"
    ".accent{position:absolute;left:7%;top:9%;width:12%;height:10px;"
    "border-radius:5px;background:var(--vaas-accent)}"
    ".kicker{font-size:28px;letter-spacing:10px;color:var(--vaas-accent);"
    "font-weight:700;margin-bottom:26px}"
    ".title{font-size:74px;line-height:1.22;font-weight:800;color:var(--vaas-text);"
    "letter-spacing:1px;word-break:break-word}"
    ".sub{margin-top:26px;font-size:34px;line-height:1.5;color:var(--vaas-muted)}"
    ".tags{margin-top:30px;display:flex;gap:16px;flex-wrap:wrap}"
    ".tag{font-size:24px;padding:8px 18px;border-radius:999px;"
    "border:1px solid var(--vaas-border);color:var(--vaas-muted)}"
)


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _tag_items(tags) -> list[str]:
    """tags → 标签列表。

    接受 list/tuple[str]（MCP 面 spec 是自由对象，传数组是最自然的写法）或
    逗号/顿号分隔的字符串（既有调用方）。此前只认字符串，传数组会直接
    `AttributeError: 'list' object has no attribute 'replace'`——对外表现为
    「封面工具崩了」，实为输入形状未归一。
    """
    if tags is None:
        return []
    if isinstance(tags, (list, tuple)):
        raw = [str(t) for t in tags]
    elif isinstance(tags, str):
        raw = tags.replace("，", ",").split(",")
    else:
        raise ValueError(
            f"cover tags 须为字符串数组或逗号分隔字符串，收到 {type(tags).__name__}")
    return [t.strip() for t in raw if t and t.strip()]


def _cover_html(title: str, subtitle: Optional[str], tags,
                w: int, h: int) -> str:
    tag_html = ""
    items = _tag_items(tags)
    if items:
        tag_html = ('<div class="tags">'
                    + "".join(f'<span class="tag">{_esc(t)}</span>' for t in items)
                    + "</div>")
    return (
        f'<style>{_COVER_CSS}</style>'
        '<div class="cover"><div class="glow-a"></div><div class="glow-b"></div>'
        '<div class="accent"></div>'
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
    # 计量口径对齐 still_graphic：1 张封面 = 1 render（2026-11-10 修——此前把
    # 文件字节数当 units 记（≈86 万），unit_type 还错标为 "image"；现网台账里
    # generate_cover units=861266 即该 bug 的产物）。当前价格表 cover 单价为 0.0，
    # 未造成金额污染，但作用量口径必须正确。
    record_usage(owner, "generate_cover", "chromium", None,
                 1, "render", "local",
                 asset_id=content_id)
    result = {"id": content_id, "slug": scoped,
              "file_path": get_relative_path("images", slug or title[:40], filename),
              "width": width, "height": height, "format": "png"}
    if is_hosted():
        from ..hosting import download_url
        url = download_url(content_id, owner)
        if url:
            result["download_url"] = url
    return result



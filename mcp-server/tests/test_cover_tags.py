"""封面 tags 输入归一（图片路径健壮性）。

MCP 面 render_still 的 spec 是自由对象，调用方按直觉传数组是最自然的写法；
此前只认逗号分隔字符串，传数组直接 AttributeError——对外表现为「封面工具崩了」。
这里锁住两种写法都对、非法类型给明确 ValueError。
"""

import pytest

from mcp_server.skills.cover import _cover_html, _tag_items


def test_tags_list_and_string_equivalent():
    assert _tag_items(["确定性", "托管直出"]) == ["确定性", "托管直出"]
    assert _tag_items("确定性，托管直出") == ["确定性", "托管直出"]
    assert _tag_items("  a , b ,, ") == ["a", "b"]


def test_tags_none_and_empty():
    assert _tag_items(None) == []
    assert _tag_items([]) == []
    assert _tag_items("") == []


@pytest.mark.parametrize("bad", [{"a": 1}, 42, object()])
def test_tags_reject_non_string_shapes(bad):
    with pytest.raises(ValueError):
        _tag_items(bad)


def test_cover_html_accepts_list_tags():
    html = _cover_html("标题", "副题", ["A", "B"], 1080, 1920)
    assert html.count('class="tag"') == 2
    assert ">A<" in html and ">B<" in html


def test_cover_html_escapes_tag_text():
    html = _cover_html("t", None, ["<script>"], 1080, 1920)
    assert "<script>" not in html


def test_brand_style_injects_palette_slots():
    """graphic/cover 的品牌变量必须带 palette 槽位。

    缺 --vaas-palette-N 时，引用它的 background/gradient 会整条失效（实测封面
    底色直接透明 → 整张图更黑，YAVG 20.7→16.6）。
    """
    from mcp_server.tools.still_graphic import _brand_style

    css = _brand_style({"bg": "#0a0e14", "accent": "#58a6ff"},
                       ["#58a6ff", "#3fb950"])
    assert "--vaas-bg:#0a0e14" in css
    assert "--vaas-palette-0:#58a6ff" in css
    assert "--vaas-palette-1:#3fb950" in css


def test_cover_css_avoids_color_mix():
    """封面 CSS 不依赖 color-mix（渲染器不一定支持，失效即整条声明作废）。"""
    from mcp_server.skills.cover import _COVER_CSS

    assert "color-mix" not in _COVER_CSS
    assert _COVER_CSS.count("glow-") == 2
    assert "var(--vaas-palette-2,var(--vaas-accent))" in _COVER_CSS

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

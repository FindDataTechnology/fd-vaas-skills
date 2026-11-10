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


def test_cover_css_uses_shared_base_bg():
    """封面底色必须复用视频卡片的同一份 BASE_BG（单一来源）。

    历史两坑：①封面自调 color-mix 底座，而 _brand_style 当时不注入 palette 变量
    → 整条 background 失效、比原来更黑（YAVG 20.7→16.6）；②改用自造柔光层，
    44% 面积只抬 1.4 点（23.1→24.5）。复用 BASE_BG 后 23.1→30.5。
    """
    from mcp_server.skills.cover import _COVER_CSS
    from mcp_server.tools.typed_scenes.builders._stage import BASE_BG

    assert BASE_BG in _COVER_CSS, "封面底色须与视频卡片同源"
    # palette 缺变量会让整条声明失效 → 用色处必须带回退
    assert "var(--vaas-palette-2,var(--vaas-accent))" in _COVER_CSS


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """把 DB 指到临时库（与 tests/test_builders_data_viz.py 同款做法）。"""
    from mcp_server.db import database
    from mcp_server.db.database import init_schema

    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


def test_list_assets_sees_seed_bgm_but_not_other_tenants(isolated_db):
    """list_assets 的可见性必须与 _owner_visible 同口径。

    种子曲库（owner=service, type=bgm）对每个租户可见——技能文档教调用方用
    `bgm={"asset_id": "<种子曲库 asset_id>"}`，若 list 查不到这些 id，
    种子曲库就是「不可发现」；其他租户与 service 的其他行仍必须隔离。
    """
    from mcp_server.db import models

    models.insert_asset(type="bgm", slug="bgm-seed-a", file_path="a.dat",
                        owner="service", stage="rendered")
    models.insert_asset(type="video", slug="svc-video", file_path="v.dat",
                        owner="service", stage="rendered")
    models.insert_asset(type="video", slug="alice-video", file_path="x.dat",
                        owner="alice", stage="rendered")
    models.insert_asset(type="video", slug="bob-video", file_path="y.dat",
                        owner="bob", stage="rendered")

    alice = {i["slug"] for i in models.list_assets(owner="alice")}
    assert "bgm-seed-a" in alice, "平台种子曲库应对租户可见"
    assert "alice-video" in alice
    assert "bob-video" not in alice, "他人资产必须隔离"
    assert "svc-video" not in alice, "service 的非 bgm 行仍不可见"

    bgm = {i["slug"] for i in models.list_assets(type="bgm", owner="alice")}
    assert bgm == {"bgm-seed-a"}

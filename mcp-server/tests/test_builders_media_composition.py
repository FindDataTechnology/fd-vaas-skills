"""契约 v2 媒体族 builder（carousel / kinetic-quote）测试（W3.3 / W3.5）。

覆盖：结构、时间轴连续性、字幕对齐、seek_js 纯函数、零外链（data: 放行）、
carousel 图少时循环复用且相邻不同图、kinetic 零图片依赖与关键词语义。
"""

import base64

import pytest

from mcp_server.tools.composition import validate_no_external_refs
from mcp_server.tools.typed_scenes import BUILDER_REGISTRY, load_type_json
from mcp_server.tools.typed_scenes.theme import load_theme

SIZE = [1080, 1920]

# 1x1 PNG（测试用素材，data: URI）
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _seg(name, text, dur, sents):
    return {"name": name, "text": text, "duration_s": float(dur),
            "sentences": [{"text": s, "start": a, "end": b} for s, a, b in sents]}


@pytest.fixture(scope="module")
def theme():
    return load_theme()


@pytest.fixture()
def images(tmp_path, monkeypatch):
    """把两张图落到临时 downloads 根，并让解析器指过去。"""
    from mcp_server.tools.typed_scenes import alignment as align
    root = tmp_path / "downloads"
    (root / "img").mkdir(parents=True)
    p1, p2 = root / "img" / "a.png", root / "img" / "b.png"
    p1.write_bytes(TINY_PNG)
    p2.write_bytes(TINY_PNG)
    monkeypatch.setattr(align, "DOWNLOADS_DIR", root, raising=False)
    monkeypatch.setattr(align, "VAAS_ROOT", tmp_path, raising=False)
    return ["img/a.png", "img/b.png"]


def _carousel_segments():
    return [
        _seg("第一帧", "品牌轮播开始。", 2.0, [("品牌轮播开始。", 0.0, 2.0)]),
        _seg("第二帧", "托管同底座。", 3.0, [("托管同底座。", 0.0, 3.0)]),
        _seg("第三帧", "交叉淡入。", 2.5, [("交叉淡入。", 0.0, 2.5)]),
    ]


def _kinetic_segments():
    return [
        _seg("金句", "**确定性**是展示层的底座。", 2.0,
             [("**确定性**是展示层的底座。", 0.0, 2.0)]),
        _seg("尾声", "托管直出，一步到位。", 1.5,
             [("托管直出，一步到位。", 0.0, 1.5)]),
    ]


def test_carousel_structure_and_reuse(theme, images):
    b = BUILDER_REGISTRY["carousel"]
    out = b.build_composition(_carousel_segments(), {"images": images}, SIZE, theme)
    visual = out["visual"]
    assert len(visual) == 3
    starts = [c["start"] for c in visual]
    assert starts == [0.0, 2.0, 5.0]
    assert abs(sum(c["duration"] for c in visual) - 7.5) < 1e-6
    for c in visual:
        assert c["seek_js"].startswith("function")
        for banned in ("Date.now", "Math.random", "setInterval"):
            assert banned not in c["seek_js"]
    html = "".join(c["html"] for c in visual)
    assert "data:image/png;base64," in html, "图片必须 data: 内联（零外链）"
    validate_no_external_refs(html)
    # 字幕轨按段给出
    assert out["subtitle"] and len(out["subtitle"]) == 3


def test_carousel_single_image_no_prev_layer(theme, images):
    b = BUILDER_REGISTRY["carousel"]
    out = b.build_composition(_carousel_segments(), {"images": images[:1]}, SIZE, theme)
    html = "".join(c["html"] for c in out["visual"])
    # 单图复用：没有上一图淡入层（不出 prev 图层 id）
    assert "-prev-" not in html


def test_carousel_missing_file_rejected(theme, tmp_path):
    b = BUILDER_REGISTRY["carousel"]
    with pytest.raises(ValueError):
        b.build_composition(_carousel_segments(),
                            {"images": ["img/not-there.png"]}, SIZE, theme)


def test_kinetic_structure_zero_img(theme):
    b = BUILDER_REGISTRY["kinetic-quote"]
    out = b.build_composition(_kinetic_segments(), {}, SIZE, theme)
    visual = out["visual"]
    assert len(visual) == 2
    assert [c["start"] for c in visual] == [0.0, 2.0]
    html = "".join(c["html"] for c in visual)
    assert "<img" not in html, "kinetic-quote 零图片依赖"
    # 关键词强调样式必须是 .kw（与渲染标记一致）且取品牌强调色
    assert ".kw{" in html and "var(--vaas-accent)" in html
    assert 'class="kw"' in html
    validate_no_external_refs(html)
    assert out["subtitle"] and len(out["subtitle"]) == 2


def test_kinetic_rejects_images(theme):
    b = BUILDER_REGISTRY["kinetic-quote"]
    with pytest.raises(ValueError):
        b.validate_inputs({"images": ["x.png"]}, _kinetic_segments())


@pytest.mark.parametrize("type_id", ["carousel", "kinetic-quote"])
def test_media_type_json_renderer(type_id):
    assert load_type_json(type_id).get("renderer") == "hyperframes"


@pytest.mark.parametrize("type_id", ["carousel", "kinetic-quote"])
def test_media_legacy_build_works(theme, images, type_id):
    b = BUILDER_REGISTRY[type_id]
    segs = _carousel_segments() if type_id == "carousel" else _kinetic_segments()
    inputs = {"images": images} if type_id == "carousel" else {}
    scenes = b.build(segs, inputs, SIZE, theme)
    assert isinstance(scenes, list) and scenes

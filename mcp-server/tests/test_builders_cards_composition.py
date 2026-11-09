"""契约 v2 卡族 builder（news-flash / listicle）测试（W3.2 / W3.6）。

验证 `build_composition` 的结构、时间轴连续性、字幕对齐、seek_js 纯函数、
零外链，以及 type.json 的 renderer 声明；全程不依赖 chromium。
"""

import pytest

from mcp_server.tools.composition import validate_no_external_refs
from mcp_server.tools.typed_scenes import BUILDER_REGISTRY
from mcp_server.tools.typed_scenes.theme import load_theme

SIZE = [1080, 1920]


def _segs(*specs):
    """specs: (name, text, duration, [(sentence, start, end), ...])"""
    out = []
    for name, text, dur, sents in specs:
        out.append({
            "name": name,
            "text": text,
            "duration_s": float(dur),
            "sentences": [{"text": s, "start": s0, "end": s1}
                          for s, s0, s1 in sents],
        })
    return out


def _news_flash_segments():
    return _segs(
        ("开场", "今日三大看点。", 2.0, [("今日三大看点。", 0.0, 2.0)]),
        ("要点一", "第一，确定性。", 2.5, [("第一，", 0.0, 0.8), ("确定性。", 0.8, 2.5)]),
        ("要点二", "第二，托管直出。", 2.5, [("第二，", 0.0, 0.9), ("托管直出。", 0.9, 2.5)]),
        ("订阅", "关注寻数。", 1.5, [("关注寻数。", 0.0, 1.5)]),
    )


def _listicle_segments():
    return _segs(
        ("开场", "三大看点。", 2.0, [("三大看点。", 0.0, 2.0)]),
        ("第三", "确定性帧级一致。", 2.0, [("确定性帧级一致。", 0.0, 2.0)]),
        ("第二", "托管同底座。", 2.0, [("托管同底座。", 0.0, 2.0)]),
        ("第一", "五类型全链。", 2.0, [("五类型全链。", 0.0, 2.0)]),
        ("结尾", "关注寻数。", 1.5, [("关注寻数。", 0.0, 1.5)]),
    )


@pytest.fixture(scope="module")
def theme():
    return load_theme()


def _assert_clip_shape(clips, label):
    assert isinstance(clips, list) and clips, f"{label}: 需非空 clip 列表"
    starts = [c["start"] for c in clips]
    assert starts == sorted(starts), f"{label}: clip 必须按 start 升序"
    for i, c in enumerate(clips):
        assert isinstance(c["start"], (int, float)) and c["start"] >= 0
        assert isinstance(c["duration"], (int, float)) and c["duration"] > 0
        assert isinstance(c.get("html"), str) and c["html"].strip()
        if i:
            prev = clips[i - 1]
            assert abs(c["start"] - (prev["start"] + prev["duration"])) < 1e-6, (
                f"{label}: clip {i} 起点必须紧接前一个（时间轴连续）")


def test_news_flash_composition_structure(theme):
    b = BUILDER_REGISTRY["news-flash"]
    segs = _news_flash_segments()
    out = b.build_composition(segs, {"meta": {
        "headline": "五类型验收", "points": ["确定性", "托管直出"],
        "source": "FindData"}}, SIZE, theme)

    assert set(out) >= {"visual", "subtitle"}
    _assert_clip_shape(out["visual"], "news-flash.visual")
    # 标题卡 + 2 要点卡 + CTA = 4
    assert len(out["visual"]) == 4
    total = sum(c["duration"] for c in out["visual"])
    assert abs(total - sum(s["duration_s"] for s in segs)) < 1e-6

    # 每个视觉 clip 自带 seek_js，且是纯函数（无随机/时间源）
    for c in out["visual"]:
        js = c.get("seek_js") or ""
        assert js.startswith("function"), "seek_js 必须是 function(lt){…}"
        for banned in ("Date.now", "Math.random", "setTimeout", "setInterval",
                       "requestAnimationFrame"):
            assert banned not in js, f"seek_js 不得含 {banned}"

    # 品牌变量与零外链
    html = "".join(c["html"] for c in out["visual"])
    assert "--vaas-" in html
    validate_no_external_refs(html)


def test_news_flash_structure_mismatch_rejected(theme):
    b = BUILDER_REGISTRY["news-flash"]
    segs = _news_flash_segments()
    with pytest.raises(ValueError) as ei:
        b.validate_inputs({"meta": {"headline": "x", "points": ["只有一个"]}}, segs)
    msg = str(ei.value)
    assert "结构数对照" in msg and "2" in msg and "1" in msg


def test_listicle_composition_structure(theme):
    b = BUILDER_REGISTRY["listicle"]
    segs = _listicle_segments()
    items = [
        {"rank": 3, "title": "确定性", "desc": "帧级一致"},
        {"rank": 2, "title": "托管直出", "desc": "同底座"},
        {"rank": 1, "title": "全链验收", "desc": "voice_path"},
    ]
    out = b.build_composition(segs, {"items": items}, SIZE, theme)

    _assert_clip_shape(out["visual"], "listicle.visual")
    # hook + 3 条目 + CTA = 5
    assert len(out["visual"]) == 5
    total = sum(c["duration"] for c in out["visual"])
    assert abs(total - sum(s["duration_s"] for s in segs)) < 1e-6

    for c in out["visual"]:
        js = c.get("seek_js") or ""
        assert js.startswith("function")
        for banned in ("Date.now", "Math.random", "setTimeout", "setInterval"):
            assert banned not in js
    validate_no_external_refs("".join(c["html"] for c in out["visual"]))


def test_listicle_item_mismatch_rejected(theme):
    b = BUILDER_REGISTRY["listicle"]
    segs = _listicle_segments()
    with pytest.raises(ValueError) as ei:
        b.validate_inputs({"items": [{"rank": 1, "title": "只有一个", "desc": "x"}]}, segs)
    assert "结构数对照" in str(ei.value)


@pytest.mark.parametrize("type_id", ["news-flash", "listicle"])
def test_type_json_renderer_declares_hyperframes(type_id):
    tj = BUILDER_REGISTRY  # 仅为触发注册
    from mcp_server.tools.typed_scenes import load_type_json
    assert load_type_json(type_id).get("renderer") == "hyperframes"


@pytest.mark.parametrize("type_id", ["news-flash", "listicle"])
def test_legacy_build_still_works(theme, type_id):
    """旧 build() 保留到 W4 切流后删除；此处守护兼容面。"""
    b = BUILDER_REGISTRY[type_id]
    segs = _news_flash_segments() if type_id == "news-flash" else _listicle_segments()
    inputs = ({"meta": {"headline": "x", "points": ["a", "b"]}}
              if type_id == "news-flash"
              else {"items": [{"rank": 3, "title": "a", "desc": "x"},
                              {"rank": 2, "title": "b", "desc": "y"},
                              {"rank": 1, "title": "c", "desc": "z"}]})
    scenes = b.build(segs, inputs, SIZE, theme)
    assert isinstance(scenes, list) and scenes
    assert all(s.get("html") for s in scenes)

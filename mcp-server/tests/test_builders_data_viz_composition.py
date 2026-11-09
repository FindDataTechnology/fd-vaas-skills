"""契约 v2 data-viz builder 测试（W3.4）。

覆盖：结构（hook/图表×N/CTA）、时间轴连续、字幕对齐、图表数量对照报错、
seek_js 纯函数（无 Date.now/Math.random/定时器）、零外链、数据岛与
echarts 内联、惰性初始化（seek_js 内 echarts.init，非顶层）、type.json
renderer=hyperframes、旧 build() 仍可用。
"""

import pytest

from mcp_server.tools.composition import validate_no_external_refs
from mcp_server.tools.typed_scenes import BUILDER_REGISTRY, load_type_json
from mcp_server.tools.typed_scenes.builders.data_viz import BUILDER
from mcp_server.tools.typed_scenes.theme import load_theme

SIZE = [1080, 1920]


def _seg(name, text, dur, sents=None):
    return {"name": name, "text": text, "duration_s": float(dur),
            "sentences": sents or [{"text": text, "start": 0.0, "end": float(dur)}]}


def _segments(n_charts=2):
    segs = [_seg("开场", "数据动画验收。", 2.0)]
    for i in range(n_charts):
        segs.append(_seg(f"图表{i+1}", f"第{i+1}张图。", 3.0))
    segs.append(_seg("结束", "验收完毕。", 1.5))
    return segs


def _inputs(n_charts=2):
    charts = []
    kinds = ["bar", "line", "pie"]
    for i in range(n_charts):
        k = kinds[i % 3]
        charts.append({"type": k, "title": f"图表{i+1}",
                       "labels": ["甲", "乙", "丙"], "values": [3, 5, 4]})
    return {"data": {"title": "验收看板", "charts": charts}}


@pytest.fixture(scope="module")
def theme():
    return load_theme()


def test_structure_and_timeline(theme):
    out = BUILDER.build_composition(_segments(2), _inputs(2), SIZE, theme)
    v = out["visual"]
    assert len(v) == 4  # hook + 2 图表 + CTA
    assert [c["start"] for c in v] == [0.0, 2.0, 5.0, 8.0]
    assert abs(sum(c["duration"] for c in v) - 9.5) < 1e-6
    for i in range(1, len(v)):
        prev = v[i - 1]
        assert abs(v[i]["start"] - (prev["start"] + prev["duration"])) < 1e-6
    assert out["subtitle"] == []  # 卡内自绘（.dv-sub）


def test_seek_js_purity_and_lazy_init(theme):
    out = BUILDER.build_composition(_segments(2), _inputs(2), SIZE, theme)
    for c in out["visual"]:
        js = c["seek_js"]
        assert js.startswith("function (lt)")
        for banned in ("Date.now", "Math.random", "setTimeout", "setInterval",
                       "requestAnimationFrame"):
            assert banned not in js, f"seek_js 不得含 {banned}"
    chart_js = out["visual"][1]["seek_js"]
    # 惰性：echarts.init 在 seek 内（出现），但不在顶层（不在 html 的顶层脚本里）
    assert "echarts.init" in chart_js
    assert "if (!D.seekFn)" in chart_js


def test_zero_external_refs_and_inline_echarts(theme):
    out = BUILDER.build_composition(_segments(2), _inputs(2), SIZE, theme)
    html = "".join(c["html"] for c in out["visual"])
    validate_no_external_refs(html)
    assert "echarts" in out["visual"][1]["html"]
    assert "window.__dvD0" in out["visual"][1]["html"]
    assert "@font-face" not in html or "data:" in html


def test_chart_count_mismatch_rejected(theme):
    segs = _segments(2)          # 2 个图表段
    inputs = _inputs(3)          # 3 张图
    with pytest.raises(ValueError) as ei:
        BUILDER.build_composition(segs, inputs, SIZE, theme)
    assert "结构数对照" in str(ei.value)


def test_missing_data_rejected(theme):
    with pytest.raises(ValueError):
        BUILDER.build_composition(_segments(2), {}, SIZE, theme)


def test_renderer_declares_hyperframes():
    assert load_type_json("data-viz").get("renderer") == "hyperframes"


def test_registry_points_to_v2_builder():
    b = BUILDER_REGISTRY["data-viz"]
    # 同一实例，且 v2 方法覆写自模块实现（不是 AbstractBuilder 默认抛错）
    from mcp_server.tools.typed_scenes import AbstractBuilder
    assert type(b).build_composition is not AbstractBuilder.build_composition


def test_legacy_build_still_works(theme):
    scenes = BUILDER.build(_segments(2), _inputs(2), SIZE, theme)
    assert isinstance(scenes, list) and scenes
    assert all(s.get("html") for s in scenes)

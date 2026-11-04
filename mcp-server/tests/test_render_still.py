"""
W2 (add-presentation-plane) still-plane unit tests.

覆盖 render_still 的 chart / graphic 内核（tools/still_chart.py、
tools/still_graphic.py）与 chart 产物→kenburns 场景的两用验收：
  - spec 校验（echarts_option 必填 / size 形态 / format 白名单 / slug 合法性）
  - 品牌主题注入的 HTML 契约（registerTheme + 色板 + caller 显式色优先 +
    animation 强制关 + </script> 转义）
  - 落账与幂等重放（type=chart / type=graphic，usage tool=render_still）
  - W2.4：render_chart 产物路径直接作为 storyboard kenburns 场景的视觉输入
  - 真实渲染探针（playwright+chromium 可用时才跑；镜像内置 chromium 即部署探针）

playwright / chromium 交互全部 mock（除标注 probe 的用例）；DB/downloads 全部
重定向到 tmp_path。
"""

import base64
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import init_schema, get_asset_by_slug, usage_summary
from mcp_server.tools import render as render_mod
from mcp_server.tools import still_chart as chart_mod
from mcp_server.tools import still_graphic as graphic_mod
from mcp_server.tools.still_chart import _chart_html

FAKE_PNG = b"\x89PNG-fake-still-bytes"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


def _ensure_rel_factory(downloads):
    def _ensure_rel(*parts):
        path = downloads.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return _ensure_rel


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
    """Redirect downloads/ writes for both still modules."""
    downloads = tmp_path / "downloads"
    _ensure_rel = _ensure_rel_factory(downloads)
    for mod in (chart_mod, graphic_mod):
        monkeypatch.setattr(mod, "DOWNLOADS_DIR", downloads)
        monkeypatch.setattr(mod, "ensure_directory_rel", _ensure_rel)
    return {"downloads": downloads}


def _fake_capture_ctor(monkeypatch, module, attr, *, fmt_aware, payload=FAKE_PNG):
    """Mock 截图缝：写假字节并记录 (html, size, fmt, out_path)。"""
    calls = []

    def _capture(html, size, *rest):
        out_path = rest[-1]
        fmt = rest[0] if fmt_aware else "png"
        Path(out_path).write_bytes(payload)
        calls.append({"html": html, "size": tuple(size), "format": fmt,
                      "out_path": Path(out_path)})
    _capture.calls = calls
    monkeypatch.setattr(module, attr, _capture)
    return _capture


BAR_SPEC = {"echarts_option": {
    "xAxis": {"type": "category", "data": ["一月", "二月", "三月"]},
    "yAxis": {"type": "value"},
    "series": [{"type": "bar", "data": [120, 200, 150]}],
}}


class TestChartSpecValidation:
    def test_echarts_option_required(self):
        with pytest.raises(ValueError, match="echarts_option"):
            chart_mod.render_chart({"size": {"width": 100, "height": 100}})
        with pytest.raises(ValueError, match="echarts_option"):
            chart_mod.render_chart({**BAR_SPEC, "echarts_option": "not-a-dict"})

    def test_spec_must_be_dict(self):
        with pytest.raises(ValueError, match="spec must be a dict"):
            chart_mod.render_chart("bar")

    def test_format_whitelist(self):
        with pytest.raises(ValueError, match="format must be one of"):
            chart_mod.render_chart({**BAR_SPEC, "format": "gif"})

    def test_size_shapes(self):
        with pytest.raises(ValueError, match="size must be"):
            chart_mod.render_chart({**BAR_SPEC, "size": "big"})
        with pytest.raises(ValueError, match="size must be integers"):
            chart_mod.render_chart({**BAR_SPEC, "size": {"width": "wide", "height": 100}})
        with pytest.raises(ValueError, match="out of range"):
            chart_mod.render_chart({**BAR_SPEC, "size": {"width": -1, "height": 100}})
        with pytest.raises(ValueError, match="out of range"):
            chart_mod.render_chart({**BAR_SPEC, "size": [99999, 100]})
        # 合法形态：dict 与 [w, h]，浮点整数值接受
        assert chart_mod._parse_size({"width": 1920.0, "height": 1080.0}) == (1920, 1080)
        assert chart_mod._parse_size([720, 1280]) == (720, 1280)
        assert chart_mod._parse_size(None) == chart_mod.DEFAULT_SIZE

    def test_caller_slug_validated(self, hermetic_fs):
        with pytest.raises(ValueError, match="invalid slug"):
            chart_mod.render_chart(BAR_SPEC, slug="../escape")


class TestChartRender:
    def test_png_happy_path_ledger_and_usage(self, hermetic_fs, monkeypatch):
        capture = _fake_capture_ctor(monkeypatch, chart_mod, "_capture_chart", fmt_aware=True)
        out = chart_mod.render_chart({**BAR_SPEC, "size": {"width": 800, "height": 600}})
        assert out["format"] == "png" and out["width"] == 800 and out["height"] == 600
        assert out["type"] == "chart"
        assert out["file_path"] == f"chart/{out['slug']}/{out['slug']}.png"
        f = hermetic_fs["downloads"] / out["file_path"]
        assert f.is_file() and f.read_bytes() == FAKE_PNG

        row = get_asset_by_slug(out["slug"])
        assert row["type"] == "chart" and row["stage"] == "rendered"
        meta = row["metadata"]
        assert meta["kind"] == "chart_still" and meta["width"] == 800
        assert meta["echarts"] == "5.5.1" and meta["theme"] == "vaas"
        assert any(r["tool"] == "render_still" for r in usage_summary())

        assert len(capture.calls) == 1
        assert capture.calls[0]["size"] == (800, 600)
        assert capture.calls[0]["out_path"] == f

    def test_svg_format(self, hermetic_fs, monkeypatch):
        _fake_capture_ctor(monkeypatch, chart_mod, "_capture_chart", fmt_aware=True)
        out = chart_mod.render_chart({**BAR_SPEC, "format": "svg"})
        assert out["file_path"].endswith(".svg")
        assert get_asset_by_slug(out["slug"])["metadata"]["renderer"] == "svg"

    def test_spec_format_overrides_kwarg(self, hermetic_fs, monkeypatch):
        _fake_capture_ctor(monkeypatch, chart_mod, "_capture_chart", fmt_aware=True)
        out = chart_mod.render_chart({**BAR_SPEC, "format": "svg"}, format="png")
        assert out["format"] == "svg"

    def test_idempotent_replay_same_spec(self, hermetic_fs, monkeypatch):
        capture = _fake_capture_ctor(monkeypatch, chart_mod, "_capture_chart", fmt_aware=True)
        first = chart_mod.render_chart(BAR_SPEC)
        second = chart_mod.render_chart(BAR_SPEC)
        assert second["id"] == first["id"]
        assert second["idempotent_replay"] is True
        assert len(capture.calls) == 1  # 第二次未再截图

    def test_failed_or_missing_output_is_rebuilt(self, hermetic_fs, monkeypatch):
        _fake_capture_ctor(monkeypatch, chart_mod, "_capture_chart", fmt_aware=True)
        first = chart_mod.render_chart(BAR_SPEC, slug="chart-rebuild")
        (hermetic_fs["downloads"] / first["file_path"]).unlink()  # 产物丢失
        second = chart_mod.render_chart(BAR_SPEC, slug="chart-rebuild")
        assert second["id"] != first["id"]
        assert "idempotent_replay" not in second

    def test_hosted_mode_returns_download_url(self, hermetic_fs, monkeypatch):
        _fake_capture_ctor(monkeypatch, chart_mod, "_capture_chart", fmt_aware=True)
        monkeypatch.setattr(chart_mod, "is_hosted", lambda: True)
        monkeypatch.setattr(chart_mod, "download_url",
                            lambda asset_id, owner: f"https://cdn.test/{asset_id}")
        out = chart_mod.render_chart(BAR_SPEC, slug="chart-hosted")
        assert out["download_url"] == f"https://cdn.test/{out['id']}"


class TestChartHtmlContract:
    """品牌主题注入的实现契约（HTML 层断言，echarts 运行时语义由探针验证）。"""

    def test_vendored_echarts_inlined_with_theme_registration(self):
        html = _chart_html(BAR_SPEC["echarts_option"], (800, 600),
                           chart_mod._load_theme_doc(), "png")
        # vendor 内联（1MB 级脚本 + 版本指纹）
        assert 'version="5.5.1"' in html and len(html) > 900_000
        # 主题经 registerTheme + init(theme) 接入
        assert "echarts.registerTheme('vaas'" in html
        assert "echarts.init(document.getElementById('chart'), 'vaas'" in html

    def test_theme_palette_present_for_unspecified_slots(self):
        doc = chart_mod._load_theme_doc()
        html = _chart_html(BAR_SPEC["echarts_option"], (800, 600), doc, "png")
        theme_blob = html[html.index("var THEME ="):html.index("var OPTION")]
        # 主题色板在 THEME 注入体里（未显式指定颜色的槽位由 echarts 取用）
        for color in doc["palette"][:3]:
            assert color in theme_blob
        # caller option 未写 color → OPTION 体不带 color 槽
        option_blob = html[html.index("var OPTION"):]
        assert '"color"' not in option_blob

    def test_caller_explicit_color_wins_over_palette(self):
        doc = chart_mod._load_theme_doc()
        option = {**BAR_SPEC["echarts_option"], "color": ["#ff8800"]}
        html = _chart_html(option, (800, 600), doc, "png")
        option_blob = html[html.index("var OPTION"):]
        assert "#ff8800" in option_blob  # caller 显式色原样保留
        # 主题色板仍在 THEME 体（合并语义 = option-over-theme，由 echarts 保证）

    def test_animation_forced_off_unless_caller_sets_it(self):
        doc = chart_mod._load_theme_doc()
        html = _chart_html(BAR_SPEC["echarts_option"], (800, 600), doc, "png")
        assert '"animation":false' in html
        html2 = _chart_html({**BAR_SPEC["echarts_option"], "animation": True},
                            (800, 600), doc, "png")
        assert '"animation":true' in html2

    def test_option_script_injection_escaped(self):
        doc = chart_mod._load_theme_doc()
        option = {**BAR_SPEC["echarts_option"],
                  "title": {"text": "</script><script>alert(1)</script>"}}
        html = _chart_html(option, (800, 600), doc, "png")
        assert "</script><script>alert(1)" not in html[html.index("var OPTION"):]

    def test_size_painted_into_stage(self):
        html = _chart_html(BAR_SPEC["echarts_option"], (1920, 1080),
                           chart_mod._load_theme_doc(), "png")
        assert "#chart{width:1920px;height:1080px" in html


class TestGraphicRender:
    def test_png_happy_path_ledger(self, hermetic_fs, monkeypatch):
        capture = _fake_capture_ctor(monkeypatch, graphic_mod, "_capture_graphic", fmt_aware=False)
        out = graphic_mod.render_graphic(
            {"html": "<p>你好 VAAS</p>", "size": [720, 1280]})
        assert out["type"] == "graphic" and out["width"] == 720 and out["height"] == 1280
        assert out["file_path"] == f"graphic/{out['slug']}/{out['slug']}.png"
        assert (hermetic_fs["downloads"] / out["file_path"]).read_bytes() == FAKE_PNG
        row = get_asset_by_slug(out["slug"])
        assert row["type"] == "graphic" and row["metadata"]["kind"] == "graphic_still"
        assert any(r["tool"] == "render_still" for r in usage_summary())
        assert len(capture.calls) == 1

    def test_fragment_html_gets_brand_wrapper(self, hermetic_fs, monkeypatch):
        capture = _fake_capture_ctor(monkeypatch, graphic_mod, "_capture_graphic", fmt_aware=False)
        doc = graphic_mod._load_theme_doc()
        graphic_mod.render_graphic({"html": "<p>你好</p>", "size": [720, 1280]})
        html = capture.calls[0]["html"]
        # 品牌变量从 theme.json brand 块取（同一 theme.ts 单一来源）
        assert f"--vaas-bg:{doc['brand']['bg']}" in html
        assert f"--vaas-accent:{doc['brand']['accent']}" in html
        # 字体栈覆盖部署镜像 fonts-noto-cjk 家族名
        assert "Noto Sans CJK SC" in html
        assert "--vaas-font-sans" in html
        # 片段被包进品牌 stage 盒（尺寸 = spec.size）
        assert "[data-stage]{position:relative;width:720px;height:1280px" in html
        assert "<div data-stage>" in html and "你好" in html

    def test_full_page_html_gets_style_injected_not_wrapped(self, hermetic_fs, monkeypatch):
        capture = _fake_capture_ctor(monkeypatch, graphic_mod, "_capture_graphic", fmt_aware=False)
        page = ("<!DOCTYPE html><html><head><title>x</title>"
                "<style>p{color:red}</style></head><body><p>整页</p></body></html>")
        graphic_mod.render_graphic({"html": page, "size": [800, 600]})
        html = capture.calls[0]["html"]
        assert html.startswith("<!DOCTYPE html><html><head>")  # 结构未改
        assert html.count("<html") == 1
        assert '<style id="vaas-brand">' in html  # 品牌变量注入在 </head> 前
        # 注入点在调用方样式之后 → 同特异性下调用方样式优先（与 option-over-theme 同构）
        assert html.index("<style>p{color:red}") < html.index('<style id="vaas-brand">')

    def test_html_required_and_replay(self, hermetic_fs, monkeypatch):
        _fake_capture_ctor(monkeypatch, graphic_mod, "_capture_graphic", fmt_aware=False)
        with pytest.raises(ValueError, match="html"):
            graphic_mod.render_graphic({"size": [100, 100]})
        spec = {"html": "<p>同页</p>"}
        first = graphic_mod.render_graphic(spec)
        second = graphic_mod.render_graphic(spec)
        assert second["id"] == first["id"] and second["idempotent_replay"] is True

    def test_caller_slug_validated(self, hermetic_fs):
        with pytest.raises(ValueError, match="invalid slug"):
            graphic_mod.render_graphic({"html": "<p>x</p>"}, slug="a/b")


# ─── W2.4: chart 产物 → kenburns 场景两用验收（代码层）────────────────────────

class TestChartFeedsKenburns:
    def test_render_chart_output_referenced_by_storyboard_scene(self, tmp_path,
                                                                hermetic_fs,
                                                                monkeypatch):
        """同一 chart spec 的产物路径可直接作为 render_video kenburns 视觉输入。

        渲染 mock 层面验证路径/规格对齐（chart 产物绝对路径 → kenburns
        images[] → data URI 内联进场景 HTML）；真实像素级验证在部署探针
        （镜像内置 chromium 跑 probe 用例）。
        """
        chart_png = FAKE_PNG + b"-chart"  # 可辨识的假 chart 字节
        _fake_capture_ctor(monkeypatch, chart_mod, "_capture_chart", fmt_aware=False,
                           payload=chart_png)
        chart = chart_mod.render_chart(
            {**BAR_SPEC, "size": {"width": 1920, "height": 1080}})
        chart_abs = hermetic_fs["downloads"] / chart["file_path"]
        assert chart_abs.is_file()

        # render_mod 的渲染/封装全部 mock（同 test_render_recut 约定）
        frame_calls = []

        def _fake_frames(html, duration_s, size, out_dir, fps, start_index=0):
            out_dir.mkdir(parents=True, exist_ok=True)
            produced = []
            for i in range(2):
                f = out_dir / f"frame_{start_index + i:05d}.png"
                f.write_bytes(FAKE_PNG)
                produced.append(f)
            frame_calls.append({"html": html, "size": tuple(size)})
            return produced

        monkeypatch.setattr(render_mod, "_render_html_frames", _fake_frames)
        monkeypatch.setattr(render_mod, "_ffmpeg",
                            lambda frames_dir, audio, out, fps:
                            out.write_bytes(b"fake-mp4-bytes"))

        class _Probe:
            returncode = 0
            stdout = "2.000\n"
            stderr = ""

        monkeypatch.setattr(render_mod.subprocess, "run",
                            lambda cmd, **kw: _Probe())  # 唯一到达的是 ffprobe

        def _ensure_dir(type, slug):
            path = hermetic_fs["downloads"] / type / slug
            path.mkdir(parents=True, exist_ok=True)
            return path

        monkeypatch.setattr(render_mod, "VAAS_ROOT", hermetic_fs["downloads"].parent)
        monkeypatch.setattr(render_mod, "ensure_directory", _ensure_dir)

        storyboard = {
            "size": [1080, 1920],
            "scenes": [{"kind": "kenburns", "duration_s": 2,
                        "images": [str(chart_abs)], "caption": "图表解说"}],
        }
        video = render_mod.compose_storyboard(storyboard, slug="vid-kb")

        assert video["scenes"] == 1 and video["frames"] == 2
        # kenburns 场景把 chart 产物按 data URI 内联（路径 + 字节对齐）
        inlined = base64.b64encode(chart_png).decode("ascii")
        assert inlined in frame_calls[0]["html"]
        assert chart_abs.read_bytes() == chart_png


# ─── 部署探针：playwright + chromium 可用时做真实像素渲染 ─────────────────────

def _chromium_available() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    pinned = __import__("os").getenv("VAAS_CHROMIUM_EXECUTABLE")
    if pinned and Path(pinned).is_file():
        return True
    if Path("/usr/bin/chromium").is_file():
        return True
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


@pytest.mark.skipif(not _chromium_available(), reason="chromium unavailable "
                    "(deploy probe: runs where the image ships chromium)")
class TestRealRenderProbe:
    def test_real_chart_png_and_svg(self, hermetic_fs):
        png = chart_mod.render_chart({**BAR_SPEC, "size": [320, 240]})
        f = hermetic_fs["downloads"] / png["file_path"]
        data = f.read_bytes()
        assert data[:4] == b"\x89PNG" and len(data) > 1000
        svg = chart_mod.render_chart({**BAR_SPEC, "size": [320, 240], "format": "svg"})
        s = (hermetic_fs["downloads"] / svg["file_path"]).read_text()
        assert s.lstrip().startswith("<svg") and "xmlns" in s

    def test_real_chart_theme_palette_painted(self, hermetic_fs):
        """真实像素验证：未显式指定颜色时系列取主题色板首色 #58a6ff。"""
        svg = chart_mod.render_chart({**BAR_SPEC, "size": [320, 240], "format": "svg"})
        s = (hermetic_fs["downloads"] / svg["file_path"]).read_text()
        assert "#58a6ff" in s

    def test_real_graphic_png(self, hermetic_fs):
        out = graphic_mod.render_graphic({"html": "<p>品牌图形</p>", "size": [320, 240]})
        data = (hermetic_fs["downloads"] / out["file_path"]).read_bytes()
        assert data[:4] == b"\x89PNG" and len(data) > 500

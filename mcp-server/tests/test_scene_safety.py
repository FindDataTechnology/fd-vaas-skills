"""
W6 (add-presentation-plane) 外置场景安全边界单测 + 真拦截冒烟.

覆盖 tools/_scene_guard.py 与四条出 HTML 渲染路径的接线（W6.1）：
  - W6.1a storyboard 场景 HTML 硬校验：html_full 外链（http/https/file）被拒
    且逐条列出违规资源；违规渲染零部分产物（帧目录不建、账本行不写、
    storyboard.json 不落）；html_intro 提升 html 与场景 caller css 的 url()
    同被扫；data: URI / 相对内联样式放行
  - W6.1c caller HTML 同源校验：render_graphic 的 spec.html、render_document
    的 html source 外链拒绝；markdown 来源不硬拦——外链图片经 result.warnings
    注释报告（普通超链不算）
  - W3 移交接线修复：render_document 分发面 format 接受 str 或 list（每元素
    ∈ {pdf, longimage}），非法值报错不变
  - _scene_guard 单元行为（srcset 多候选 / 去重 / include_links=False /
    data:·相对·#锚点·协议相对放行）
  - W6.1b chromium 请求拦截兜底（probe，chromium 可用时）：静态扫描不可见的
    JS 动态外链渲染期被 abort——本地回环 HTTP 服务零命中、渲染仍成功；
    无守卫对照请求可达（证明不是服务不可达）；data: 内联图仍正常出帧

playwright 交互全部 mock（除标注 probe 的用例）；DB/downloads 全部重定向
tmp_path。
"""

import base64
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import init_schema, get_asset_by_slug
from mcp_server.tools import render as render_mod
from mcp_server.tools import doc_render as doc_mod
from mcp_server.tools import still_graphic as graphic_mod
from mcp_server.tools import _scene_guard as guard


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
    """Redirect downloads/ writes for all four render modules."""
    downloads = tmp_path / "downloads"
    downloads.mkdir(parents=True)

    def _ensure_rel(*parts):
        return _mkdir(downloads.joinpath(*parts))

    for mod in (render_mod, doc_mod, graphic_mod):
        if hasattr(mod, "DOWNLOADS_DIR"):  # render.py 已不再绑定（重放/校验走 VAAS_ROOT）
            monkeypatch.setattr(mod, "DOWNLOADS_DIR", downloads)
        monkeypatch.setattr(mod, "ensure_directory_rel", _ensure_rel)
    monkeypatch.setattr(render_mod, "VAAS_ROOT", tmp_path)
    monkeypatch.setattr(render_mod, "ensure_directory",
                        lambda type, slug: _mkdir(downloads / type / slug))
    return {"downloads": downloads}


def _fake_frame_renderer(frames_per_scene: int = 2):
    """Fake playwright 逐帧渲染（同 test_render_recut 约定）。"""
    calls = []

    def _render(html, duration_s, size, out_dir, fps, start_index=0):
        produced = []
        for i in range(frames_per_scene):
            f = out_dir / f"frame_{start_index + i:05d}.png"
            f.write_bytes(b"\x89PNG-fake")
            produced.append(f)
        calls.append({"html": html, "start_index": start_index})
        return produced

    _render.calls = calls
    return _render


@pytest.fixture
def fake_render_pipeline(monkeypatch):
    """Mock 逐帧渲染 + ffmpeg + ffprobe，compose 全链不碰真实二进制。"""
    renderer = _fake_frame_renderer()
    monkeypatch.setattr(render_mod, "_render_html_frames", renderer)
    monkeypatch.setattr(render_mod, "_ffmpeg",
                        lambda frames_dir, audio, out, fps: out.write_bytes(b"fake-mp4"))

    class _Probe:
        returncode = 0
        stdout = "2.000\n"
        stderr = ""

    monkeypatch.setattr(render_mod.subprocess, "run", lambda cmd, **kw: _Probe())
    return renderer


FAKE_PDF = b"%PDF-1.4\n%fake\n"


def _fake_captures(monkeypatch):
    """Mock doc 截图缝（_print_pdf/_shot_longimage）：写假产物并记录调用。"""
    pdf_calls, shot_calls = [], []

    def _print_pdf(html, template, out_path):
        Path(out_path).write_bytes(FAKE_PDF)
        pdf_calls.append({"html": html})

    def _shot_longimage(html, width, out_path):
        Path(out_path).write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)
        shot_calls.append({"html": html})

    monkeypatch.setattr(doc_mod, "_print_pdf", _print_pdf)
    monkeypatch.setattr(doc_mod, "_shot_longimage", _shot_longimage)
    return pdf_calls, shot_calls


EXTERNAL_SB = {"size": [320, 240], "scenes": [
    {"kind": "html_full", "duration_s": 1,
     "html": '<div data-stage><img src="https://cdn.example.com/hero.png"></div>'},
]}


# ─── W6.1a: storyboard 场景 HTML 硬校验 ─────────────────────────────────────

class TestStoryboardSceneGate:
    def test_external_ref_rejected_and_listed(self, hermetic_fs, fake_render_pipeline):
        """外链被拒：错误点名违规资源 URL 与所在场景；渲染从未启动。"""
        with pytest.raises(ValueError) as ei:
            render_mod.compose_storyboard(EXTERNAL_SB, slug="sb-ext")
        msg = str(ei.value)
        assert "https://cdn.example.com/hero.png" in msg
        assert "scene 0 (html_full)" in msg
        assert "data: URI" in msg  # 指明修法（内联为 data: URI）
        assert fake_render_pipeline.calls == []  # 逐帧渲染未启动

    def test_all_violations_listed_in_one_error(self, hermetic_fs, fake_render_pipeline):
        """多场景多违规：一次报错逐条列全（先全量建 HTML 再校验）。"""
        sb = {"size": [320, 240], "scenes": [
            {"kind": "html_full", "duration_s": 1,
             "html": '<img src="https://a.example.com/1.png">'},
            {"kind": "html_full", "duration_s": 1,
             "html": '<img src="http://b.example.com/2.png"><img src="https://a.example.com/1.png">'},
        ]}
        with pytest.raises(ValueError) as ei:
            render_mod.compose_storyboard(sb, slug="sb-multi")
        msg = str(ei.value)
        assert "https://a.example.com/1.png" in msg
        assert "http://b.example.com/2.png" in msg
        assert "scene 0" in msg and "scene 1" in msg

    def test_file_scheme_rejected(self, hermetic_fs, fake_render_pipeline):
        """file:// 引用被拒（外置场景不得访问宿主文件系统）。"""
        sb = {"size": [320, 240], "scenes": [
            {"kind": "html_full", "duration_s": 1, "html":
                '<img src="file:///etc/vaas/secret.png">'
                '<style>i{background:url(file:///etc/vaas/bg.png)}</style>'},
        ]}
        with pytest.raises(ValueError) as ei:
            render_mod.compose_storyboard(sb, slug="sb-file")
        msg = str(ei.value)
        assert "file:///etc/vaas/secret.png" in msg
        assert "file:///etc/vaas/bg.png" in msg

    def test_html_intro_promoted_field_scanned(self, hermetic_fs, fake_render_pipeline):
        """storyboard.html_intro（提升为 html_full 场景）同被硬校验。"""
        sb = {"size": [320, 240],
              "html_intro": '<img src="https://cdn.example.com/intro.png">',
              "scenes": [{"kind": "html_outro", "duration_s": 1, "title": "尾"}]}
        with pytest.raises(ValueError, match="https://cdn.example.com/intro.png"):
            render_mod.compose_storyboard(sb, slug="sb-intro")

    def test_scene_css_url_flagged(self, hermetic_fs, fake_render_pipeline):
        """html_intro/outro 场景的 caller css 经模板生成后同被扫（url() 面）。"""
        sb = {"size": [320, 240], "scenes": [
            {"kind": "html_intro", "duration_s": 1, "title": "开场",
             "css": "background:url(https://cdn.example.com/bg.png)"},
        ]}
        with pytest.raises(ValueError, match="https://cdn.example.com/bg.png"):
            render_mod.compose_storyboard(sb, slug="sb-css")

    def test_no_partial_artifacts(self, hermetic_fs):
        """违规渲染零部分产物：帧目录不存在、无账本行、storyboard.json 不落。"""
        with pytest.raises(ValueError):
            render_mod.compose_storyboard(EXTERNAL_SB, slug="sb-partial")
        out_dir = hermetic_fs["downloads"] / "video" / "sb-partial"
        assert not (out_dir / "frames").exists()       # 帧目录未创建
        assert not (out_dir / "storyboard.json").exists()  # 成片元数据未落
        assert not list(out_dir.glob("sb-partial.*"))  # 无半成品成片
        assert get_asset_by_slug("sb-partial") is None  # 无账本行

    def test_data_uri_and_relative_allowed(self, hermetic_fs, fake_render_pipeline):
        """data: URI 与相对内联样式放行，正常出帧入账。"""
        html = ('<div data-stage><img src="data:image/png;base64,AAA"></div>'
                '<style>[data-stage]{background:url("data:image/png;base64,BBB")}'
                ".cap{background:url(cap-bg.png)}</style>")
        sb = {"size": [320, 240], "scenes": [
            {"kind": "html_full", "duration_s": 1, "html": html}]}
        result = render_mod.compose_storyboard(sb, slug="sb-inline")
        assert result["frames"] == 2
        row = get_asset_by_slug("sb-inline")
        assert row and row["stage"] == "rendered"

    def test_video_dispatcher_reports_violations_too(self, hermetic_fs, fake_render_pipeline):
        """render_video 分发路径同样被拦（校验在 compose 内核前置）。"""
        with pytest.raises(ValueError, match="https://cdn.example.com/hero.png"):
            render_mod.render_video(storyboard=EXTERNAL_SB, slug="sb-dispatch")


# ─── W6.1c: graphic caller HTML 硬校验 ──────────────────────────────────────

class TestGraphicCallerGate:
    def test_external_img_rejected_before_capture(self, hermetic_fs, monkeypatch):
        """graphic caller HTML 外链拒绝：不截图、不落账。"""
        calls = []
        monkeypatch.setattr(graphic_mod, "_capture_graphic",
                            lambda html, size, out_path: calls.append(html))
        with pytest.raises(ValueError) as ei:
            graphic_mod.render_graphic(
                {"html": '<p>x</p><img src="http://cdn.example.com/a.png">'},
                slug="g-ext")
        assert "http://cdn.example.com/a.png" in str(ei.value)
        assert calls == []
        assert get_asset_by_slug("g-ext") is None

    def test_data_uri_caller_html_allowed(self, hermetic_fs, monkeypatch):
        """data: URI 的 caller HTML 放行，正常截图入账。"""
        monkeypatch.setattr(graphic_mod, "_capture_graphic",
                            lambda html, size, out_path:
                            Path(out_path).write_bytes(b"\x89PNG-fake"))
        out = graphic_mod.render_graphic(
            {"html": '<img src="data:image/png;base64,AAA">'}, slug="g-inline")
        assert get_asset_by_slug(out["slug"])["type"] == "graphic"


# ─── W6.1c: doc_render html source 硬校验 + markdown 注释报告 ────────────────

class TestDocumentCallerGate:
    def test_html_source_external_rejected(self, hermetic_fs, monkeypatch):
        """html source 外链拒绝：不截图、不落账。"""
        pdf_calls, shot_calls = _fake_captures(monkeypatch)
        with pytest.raises(ValueError) as ei:
            doc_mod.render_document(
                '<p>hi</p><img src="https://cdn.example.com/x.png">',
                format="pdf", slug="doc-ext")
        assert "https://cdn.example.com/x.png" in str(ei.value)
        assert pdf_calls == [] and shot_calls == []
        assert get_asset_by_slug("doc-ext") is None

    def test_html_source_file_scheme_rejected(self, hermetic_fs, monkeypatch):
        _fake_captures(monkeypatch)
        with pytest.raises(ValueError, match="file:///etc/secret.png"):
            doc_mod.render_document('<img src="file:///etc/secret.png">',
                                    format="longimage", slug="doc-file")

    def test_md_external_image_reported_not_blocked(self, hermetic_fs, monkeypatch):
        """md 来源不硬拦：外链图片经 result.warnings 注释报告，渲染照常。"""
        _fake_captures(monkeypatch)
        out = doc_mod.render_document(
            "# 标题\n\n![logo](https://cdn.example.com/pic.png)\n",
            format="pdf", slug="doc-mdext")
        assert out["source_kind"] == "markdown"
        assert get_asset_by_slug("doc-mdext") is not None  # 渲染未被拦截
        warnings = out.get("warnings") or []
        assert any("https://cdn.example.com/pic.png" in w for w in warnings)
        assert any("data: URI" in w for w in warnings)  # 报告里给出修法

    def test_md_plain_link_not_flagged(self, hermetic_fs, monkeypatch):
        """md 普通超链不是渲染期取数：不产生 warnings。"""
        _fake_captures(monkeypatch)
        out = doc_mod.render_document(
            "详见 [文档](https://example.com/doc)。\n",
            format="pdf", slug="doc-mdlink")
        assert "warnings" not in out


# ─── W3 移交修复: render_document 分发面 format str/list ─────────────────────

class TestDispatcherFormatList:
    def _mock_kernel(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(doc_mod, "render_document",
                            lambda **kw: captured.update(kw) or {"type": "doc"})
        return captured

    def test_list_format_reaches_kernel(self, monkeypatch):
        captured = self._mock_kernel(monkeypatch)
        out = render_mod.render_document("# hi", format=["pdf", "longimage"])
        assert out == {"type": "doc"}
        assert captured["format"] == ["pdf", "longimage"]

    def test_string_format_unchanged(self, monkeypatch):
        captured = self._mock_kernel(monkeypatch)
        render_mod.render_document("# hi", format="pdf")
        assert captured["format"] == "pdf"

    def test_unknown_string_rejected(self):
        with pytest.raises(ValueError, match="unknown document format: docx"):
            render_mod.render_document("# hi", format="docx")

    def test_unknown_list_element_rejected(self):
        with pytest.raises(ValueError, match="unknown document format: gif"):
            render_mod.render_document("# hi", format=["pdf", "gif"])

    def test_wrong_type_rejected(self):
        with pytest.raises(ValueError, match="format must be"):
            render_mod.render_document("# hi", format=None)
        with pytest.raises(ValueError, match="format must be"):
            render_mod.render_document("# hi", format=[])
        with pytest.raises(ValueError, match="format must be"):
            render_mod.render_document("# hi", format=7)


# ─── _scene_guard 单元行为 ──────────────────────────────────────────────────

class TestSceneGuardUnit:
    def test_collects_from_all_surfaces_and_dedupes(self):
        html = ('<img src="https://a/x.png"><img src="https://a/x.png">'
                "<video poster=\"https://b/p.jpg\"></video>"
                '<style>@import "https://c/s.css";'
                "body{background:url('https://d/bg.png')}</style>")
        assert guard.find_external_refs(html) == [
            "https://a/x.png", "https://b/p.jpg", "https://c/s.css",
            "https://d/bg.png"]

    def test_srcset_multi_candidate(self):
        html = '<img srcset="https://a/1.png 1x, https://a/2.png 2x, /local.png 3x">'
        assert guard.find_external_refs(html) == ["https://a/1.png", "https://a/2.png"]

    def test_allowed_values_pass(self):
        """data:/相对/#锚点/about: 放行；协议相对（//host/x）交由 chromium
        请求拦截兜底断网（静态面不误报 JS 字符串等非资源引用）。"""
        html = ('<img src="data:image/png;base64,AAA">'
                '<img src="images/local.png">'
                '<link href="css/style.css">'
                '<a href="#anchor">#</a>'
                '<a href="about:blank">b</a>'
                '<img src="//cdn.example.com/x.png">'
                '<style>a{background:url(theme/bg.png)}</style>')
        assert guard.find_external_refs(html) == []

    def test_include_links_false_ignores_href(self):
        html = '<a href="https://example.com">text</a><img src="https://a/x.png">'
        assert guard.find_external_refs(html, include_links=False) == ["https://a/x.png"]

    def test_assert_message_lists_each_ref(self):
        with pytest.raises(ValueError) as ei:
            guard.assert_no_external_refs(
                '<img src="https://a/1.png"><img src="file:///x">',
                label="caller html")
        msg = str(ei.value)
        assert "caller html" in msg
        assert "- https://a/1.png" in msg and "- file:///x" in msg


# ─── W6.1b: chromium 请求拦截兜底（真渲染探针）────────────────────────────────

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGA"
    "hKmMIQAAAABJRU5ErkJggg==")


class _HitHandler(BaseHTTPRequestHandler):
    hits: list[str] = []

    def do_GET(self):
        type(self).hits.append(self.path)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):  # 静默 access log
        pass


@pytest.fixture
def loopback_server():
    """127.0.0.1 随机端口 HTTP 服务，记录全部命中（探测「零外发请求」）。"""
    _HitHandler.hits = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HitHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server.server_address[1]  # port
    finally:
        server.shutdown()
        server.server_close()


def _chromium_available() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    import os
    pinned = os.getenv("VAAS_CHROMIUM_EXECUTABLE")
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
                    "(probe: needs playwright + chromium)")
class TestRouteGuardProbe:
    def test_loopback_server_reachable_by_chromium(self, hermetic_fs, loopback_server):
        """对照：主框架导航可达回环服务（服务本身工作，零命中断言才有意义）。"""
        from playwright.sync_api import sync_playwright
        from mcp_server.tools.render import _launch_kwargs
        with sync_playwright() as p:
            browser = p.chromium.launch(**_launch_kwargs())
            page = browser.new_page(viewport={"width": 320, "height": 240})
            resp = page.goto(f"http://127.0.0.1:{loopback_server}/control-nav",
                             wait_until="domcontentloaded")
            browser.close()
        assert resp.status == 200
        assert _HitHandler.hits == ["/control-nav"]

    def test_dynamic_external_request_aborted_in_storyboard(self, hermetic_fs,
                                                            loopback_server,
                                                            monkeypatch):
        """静态扫描不可见的 JS 动态外链 → 渲染期被 route guard abort。

        场景 JS 用字符串拼接构造外链（静态扫描面不可见）请求回环服务；经
        on_abort 审计回调证明请求由页面发起且被守卫拦截 abort，回环服务零
        命中，渲染照常出帧。（部分新版 chromium 对 about:blank 载体页自身
        也会拦子资源请求——本探针断言的是「守卫拦截」而非「浏览器放行」，
        两代 chromium 行为下语义一致。）
        """
        port = loopback_server
        aborted = []
        real = render_mod.install_route_guard
        monkeypatch.setattr(render_mod, "install_route_guard",
                            lambda page: real(page, on_abort=aborted.append))

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script>window.__DURATION__=1;window.__SIZE__=[320,240];</script>
<style>html,body{{margin:0}}</style></head>
<body><div data-stage>probe</div>
<script>
  var u = 'ht' + 'tp://127.0.0.1:{port}/js-hit';
  var im = new Image(); im.src = u;
  fetch(u).catch(function(){{}});
</script></body></html>"""
        sb = {"size": [320, 240], "scenes": [
            {"kind": "html_full", "duration_s": 1, "html": html}]}
        result = render_mod.compose_storyboard(sb, slug="sb-probe", fps=2)
        assert result["frames"] == 2  # 渲染照常完成（abort 不致命）
        assert f"http://127.0.0.1:{port}/js-hit" in aborted  # 守卫拦到了该请求
        assert "/js-hit" not in _HitHandler.hits  # 网络请求零外发
        assert _HitHandler.hits == []  # 主框架对照之外零命中

    def test_data_uri_subresources_still_render(self, hermetic_fs):
        """守卫不误伤 data: 内联子资源：kenburns 场景真实出帧。"""
        img = hermetic_fs["downloads"] / "probe-img" / "a.png"
        _mkdir(img.parent)
        img.write_bytes(PNG_1PX)
        sb = {"size": [320, 240], "scenes": [
            {"kind": "kenburns", "duration_s": 1, "images": [str(img)],
             "caption": "内联图"}]}
        result = render_mod.compose_storyboard(sb, slug="sb-probe-data", fps=2)
        assert result["frames"] == 2
        out_dir = hermetic_fs["downloads"] / "video" / "sb-probe-data"
        for f in sorted(out_dir.glob("frame_*.png")):
            assert f.read_bytes()[:4] == b"\x89PNG"

    def test_graphic_dynamic_external_request_aborted(self, hermetic_fs,
                                                      loopback_server,
                                                      monkeypatch):
        """graphic 路径（still_chart._chromium 共享缝，chart/doc 同享）同享断网兜底。"""
        from mcp_server.tools import still_chart as chart_mod
        port = loopback_server
        aborted = []
        real = chart_mod.install_route_guard
        monkeypatch.setattr(chart_mod, "install_route_guard",
                            lambda page: real(page, on_abort=aborted.append))

        html = f"""<p>probe</p><script>
  var im = new Image();
  im.src = 'ht' + 'tp://127.0.0.1:{port}/graphic-js-hit';
</script>"""
        out = graphic_mod.render_graphic({"html": html, "size": [320, 240]},
                                         slug="g-probe")
        f = hermetic_fs["downloads"] / out["file_path"]
        assert f.is_file() and f.read_bytes()[:4] == b"\x89PNG"  # 渲染成功
        assert f"http://127.0.0.1:{port}/graphic-js-hit" in aborted  # 守卫拦截
        assert "/graphic-js-hit" not in _HitHandler.hits  # 零外发


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

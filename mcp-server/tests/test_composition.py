"""
中性 composition spec 编译器单测（adopt-hyperframes-video-renderer W2.2）。

覆盖 tools/composition.py：
  - 根 div 六属性（data-composition-id/start/duration/width/height/fps）
  - visual/subtitle clip 的 data-start/duration/track-index 与字幕品牌条
    （底部、line-clamp 2 行）、文本转义
  - audio clip 的 src/volume 与 fade_out 音量包络（seek 内逐帧线性收尾）
  - seek 汇总：多个带 seek_js 的 clip 合成单一 window.__hf，按窗口命中并以
    localT 调各自 seek_js——用 node 实跑生成的运行时断言窗口语义与音量包络
    （node 不可用时 skip，结构断言仍在）
  - 品牌变量注入（:root --vaas-*）与舞台 CSS（全幅、overflow hidden）
  - 零外链：http(s)/协议相对 //host 拒绝并列出资源；data:/相对放行；编译
    入口自动校验
  - spec 校验：duration/fps/size/轨 index 重复与负值/clip 越界/kind 非法/
    各 kind 必填字段/一次列全

node 仅用于执行生成的 seek 运行时（不依赖浏览器/网络）；playwright 不参与。
"""

import json
import re
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.tools import composition as comp
from mcp_server.tools import render_client
from mcp_server.tools._scene_guard import find_external_refs

THEME = {
    "brand": {
        "bg": "#0a0e14",
        "text": "#e6edf3",
        "accent": "#58a6ff",
        "fontSans": "'PingFang SC','Noto Sans CJK SC',sans-serif",
    },
    "palette": ["#58a6ff", "#3fb950"],
}


def _spec(**overrides):
    spec = {
        "size": [1080, 1920],
        "duration_s": 10.0,
        "fps": 10,
        "tracks": [
            {"index": 0, "kind": "visual", "clips": [
                {"start": 0.0, "duration": 3.0,
                 "html": '<div class="card" id="a">A</div>'},
                {"start": 3.0, "duration": 3.0,
                 "html": '<div class="card" id="b">B</div>'},
            ]},
            {"index": 1, "kind": "subtitle", "clips": [
                {"start": 0.0, "duration": 1.2, "text": "第一句"},
            ]},
            {"index": 2, "kind": "audio", "clips": [
                {"start": 0.0, "duration": 10.0, "src": "assets/voice.mp3",
                 "volume": 0.8, "fade_out": True},
            ]},
        ],
    }
    spec.update(overrides)
    return spec


def _build(spec=None, theme=None):
    return comp.build_composition_html(spec or _spec(), theme or THEME)


def _script_of(html: str) -> str:
    m = re.search(r"<script>\n(.*?)\n</script>", html, re.S)
    assert m, "composition html 缺少内联 <script>"
    return m.group(1)


def _node():
    return shutil.which("node")


needs_node = pytest.mark.skipif(_node() is None, reason="node 不在 PATH（结构断言仍覆盖）")


def _run_seek(html: str, prelude: str, body: str) -> list[str]:
    """在 node 里执行生成的 seek 运行时（window/document 用最小桩）。"""
    program = "global.window = {};\n" + prelude + "\n" + _script_of(html) + "\n" + body
    proc = subprocess.run([_node(), "-e", program], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip().splitlines()


# ─── 结构 ──────────────────────────────────────────────────────────────────

class TestCompileStructure:
    def test_root_attributes(self):
        html = _build()
        assert 'data-composition-id="main"' in html
        assert 'data-start="0"' in html
        assert 'data-duration="10"' in html
        assert 'data-width="1080"' in html
        assert 'data-height="1920"' in html
        assert 'data-fps="10"' in html
        # 根 div 只出现一次（composition 根，不是嵌套）
        assert html.count('data-composition-id="main"') == 1

    def test_visual_clip_attributes(self):
        html = _build()
        assert ('<div class="clip" data-start="0" data-duration="3" '
                'data-track-index="0"><div class="card" id="a">A</div></div>') in html
        assert ('<div class="clip" data-start="3" data-duration="3" '
                'data-track-index="0">') in html
        assert html.count('data-track-index="0"') == 2

    def test_subtitle_track_brand_band(self):
        html = _build()
        assert ('<div class="clip subtitle" data-start="0" data-duration="1.2" '
                'data-track-index="1">第一句</div>') in html
        # 内置品牌字幕条：底部、半透明底、最多 2 行
        assert ".clip.subtitle{inset:auto 6% 7% 6%" in html
        assert "background:rgba(0,0,0,.62)" in html
        assert "-webkit-line-clamp:2" in html
        assert "color:var(--vaas-text)" in html

    def test_subtitle_text_escaped(self):
        spec = _spec(tracks=[
            {"index": 0, "kind": "subtitle", "clips": [
                {"start": 0.0, "duration": 1.0, "text": "<b>加粗</b> & 符号"}]},
        ])
        html = _build(spec)
        assert "<b>加粗</b>" not in html
        assert "&lt;b&gt;加粗&lt;/b&gt; &amp; 符号" in html

    def test_audio_clip_attributes(self):
        html = _build()
        assert ('<audio id="hf-audio-2-0" data-start="0" data-duration="10" '
                'data-track-index="2" src="assets/voice.mp3" volume="0.8">') in html
        assert html.count("<audio") == 1

    def test_audio_defaults_volume_one_no_fade(self):
        spec = _spec(tracks=[
            {"index": 2, "kind": "audio", "clips": [
                {"start": 0.0, "duration": 10.0, "src": "assets/voice.mp3"}]},
        ])
        html = _build(spec)
        assert 'volume="1"' in html
        assert "var AUDIO = [];" in html  # 无 fade_out 不需要音量包络

    def test_brand_variables_and_stage(self):
        html = _build()
        assert ":root{--vaas-bg:#0a0e14" in html
        assert "--vaas-font-sans:'PingFang SC'" in html
        assert "--vaas-palette-1:#3fb950" in html
        assert "html,body{margin:0;width:1080px;height:1920px;" in html
        assert "overflow:hidden" in html
        assert "background:var(--vaas-bg)" in html
        assert "font-family:var(--vaas-font-sans)" in html

    def test_script_emits_hf_runtime_once(self):
        html = _build()
        assert html.count("window.__hf") >= 1
        assert "window.__hf = {" in html
        # 逐帧驱动的真正入口：运行时按帧调 timeline.seek(t)（只注册 __hf 时动画静止，
        # 见 0.9.26 实测）——两者缺一不可
        assert "window.__timelines['main'] = TL;" in html
        assert "seek: function (t) { seek(t); return TL; }" in html
        # 首帧落位（否则第 0 帧停在 CSS 初值）
        assert "  seek(0);\n" in html
        assert html.count("<script>") == 1


# ─── seek 汇总（node 实跑） ────────────────────────────────────────────────

class TestSeekAggregation:
    def _two_seek_spec(self):
        return _spec(tracks=[
            {"index": 0, "kind": "visual", "clips": [
                {"start": 0.0, "duration": 3.0, "html": "<div>A</div>",
                 "seek_js": "function(lt){(window.__hits=window.__hits||[])"
                            ".push(['a',lt]);}"},
                {"start": 3.0, "duration": 3.0, "html": "<div>B</div>",
                 "seek_js": "function(lt){(window.__hits=window.__hits||[])"
                            ".push(['b',lt]);}"},
                {"start": 6.0, "duration": 2.0, "html": "<div>C</div>"},  # 无 seek
            ]},
        ])

    def test_windows_and_functions_aligned(self):
        html = _build(self._two_seek_spec())
        assert "var WINDOWS = [[0.0, 3.0], [3.0, 6.0]];" in html
        assert html.count(".push(['a',lt])") == 1
        assert html.count(".push(['b',lt])") == 1
        assert "window.__hits" in html

    def test_no_seek_js_no_functions(self):
        html = _build(_spec(tracks=[
            {"index": 0, "kind": "visual", "clips": [
                {"start": 0.0, "duration": 3.0, "html": "<div>A</div>"}]},
        ]))
        assert "var WINDOWS = [];" in html
        assert "var SEEKS = [];" in html

    @needs_node
    def test_window_hit_localT(self):
        html = _build(self._two_seek_spec())
        out = _run_seek(
            html, "global.__hits = [];\n",
            "\n".join([
                "window.__hf.seek(0.5);",
                "window.__hf.seek(4.25);",
                "window.__hf.seek(6.5);",   # 无 seek_js 的 clip → 不调用
                "window.__hf.seek(-1);",    # 负值夹到 0
                "window.__hf.seek(99);",    # 越过 duration 夹到末尾（半开区间）
                "console.log(JSON.stringify(window.__hits || []));",
            ]))
        # 脚本体末尾自带 seek(0)（首帧落位）→ 首条 ['a', 0]
        assert json.loads(out[-1]) == [["a", 0], ["a", 0.5], ["b", 1.25], ["a", 0]]

    @needs_node
    def test_audio_fade_envelope(self):
        html = _build(_spec(tracks=[
            {"index": 2, "kind": "audio", "clips": [
                {"start": 0.0, "duration": 10.0, "src": "assets/voice.mp3",
                 "volume": 0.8, "fade_out": True}]},
        ]))
        out = _run_seek(
            html,
            "global.__els = {};\n"
            "global.document = {getElementById: function (id) {"
            " return __els[id] || (__els[id] = {volume: 1}); }};\n",
            "\n".join([
                "window.__hf.seek(0);",
                "console.log(String(__els['hf-audio-2-0'].volume));",
                "window.__hf.seek(8.5);",
                "console.log(String(__els['hf-audio-2-0'].volume));",
                "window.__hf.seek(9.9);",
                "console.log(String(__els['hf-audio-2-0'].volume));",
            ]))
        v0, v85, v99 = (float(x) for x in out[-3:])
        assert v0 == pytest.approx(0.8)
        assert v85 == pytest.approx(0.4)             # left 1.5s / fade 3s
        assert v99 == pytest.approx(0.8 * 0.1 / 3)


# ─── 零外链 ────────────────────────────────────────────────────────────────

class TestZeroExternalRefs:
    def test_http_src_rejected_and_listed(self):
        spec = _spec(tracks=[
            {"index": 0, "kind": "visual", "clips": [
                {"start": 0.0, "duration": 3.0,
                 "html": '<img src="https://cdn.example.com/a.png">'}]},
        ])
        with pytest.raises(ValueError) as exc:
            _build(spec)
        msg = str(exc.value)
        assert "https://cdn.example.com/a.png" in msg
        assert "零外链" in msg

    def test_protocol_relative_rejected(self):
        spec = _spec(tracks=[
            {"index": 0, "kind": "visual", "clips": [
                {"start": 0.0, "duration": 3.0,
                 "html": '<img src="//cdn.example.com/a.png">'}]},
        ])
        with pytest.raises(ValueError, match="//cdn.example.com/a.png"):
            _build(spec)

    def test_css_url_and_href_rejected(self):
        spec = _spec(tracks=[
            {"index": 0, "kind": "visual", "clips": [
                {"start": 0.0, "duration": 3.0,
                 "html": '<div style="background:url(https://x/y.png)">'
                         '<a href="http://x/z">z</a></div>'}]},
        ])
        with pytest.raises(ValueError) as exc:
            _build(spec)
        msg = str(exc.value)
        assert "https://x/y.png" in msg and "http://x/z" in msg

    def test_data_and_relative_pass(self):
        spec = _spec(tracks=[
            {"index": 0, "kind": "visual", "clips": [
                {"start": 0.0, "duration": 3.0,
                 "html": '<img src="data:image/png;base64,AAAA">'
                         '<img src="assets/x.png"><a href="#t">t</a>'}]},
        ])
        html = _build(spec)
        assert "data:image/png;base64,AAAA" in html
        assert "assets/x.png" in html
        assert find_external_refs(html) == []

    def test_validate_function_direct(self):
        comp.validate_no_external_refs("<img src='assets/x.png'>")  # 不抛
        with pytest.raises(ValueError, match="http://x/y.png"):
            comp.validate_no_external_refs("<img src='http://x/y.png'>")

    def test_srcset_candidates_scanned(self):
        with pytest.raises(ValueError, match="https://x/b.png"):
            comp.validate_no_external_refs(
                '<img srcset="assets/a.png 1x, https://x/b.png 2x">')


# ─── spec 校验 ─────────────────────────────────────────────────────────────

class TestSpecValidation:
    def test_duration_must_be_positive(self):
        with pytest.raises(ValueError, match="duration_s 必须"):
            _build(_spec(duration_s=0))

    def test_fps_must_be_positive_int(self):
        with pytest.raises(ValueError, match="fps 必须是正整数"):
            _build(_spec(fps=0))
        with pytest.raises(ValueError, match="fps 必须是正整数"):
            _build(_spec(fps=True))

    def test_size_must_be_two_positive_ints(self):
        with pytest.raises(ValueError, match="size 必须是"):
            _build(_spec(size=[1080]))
        with pytest.raises(ValueError, match="size 必须是"):
            _build(_spec(size=[-1, 1920]))

    def test_track_index_negative_and_duplicate(self):
        with pytest.raises(ValueError, match="index 必须是非负整数"):
            _build(_spec(tracks=[{"index": -1, "kind": "visual", "clips": []}]))
        with pytest.raises(ValueError, match="index 重复"):
            _build(_spec(tracks=[
                {"index": 0, "kind": "visual", "clips": []},
                {"index": 0, "kind": "subtitle", "clips": []},
            ]))

    def test_clip_overflow(self):
        spec = _spec(tracks=[
            {"index": 0, "kind": "visual", "clips": [
                {"start": 9.0, "duration": 2.0, "html": "<div>x</div>"}]},
        ])
        with pytest.raises(ValueError) as exc:
            _build(spec)
        msg = str(exc.value)
        assert "tracks[0].clips[0] 越界" in msg and "11 > spec.duration_s=10" in msg

    def test_clip_overflow_tolerance(self):
        spec = _spec(tracks=[
            {"index": 1, "kind": "subtitle", "clips": [
                {"start": 9.9999995, "duration": 0.0000005, "text": "尾"}]},
        ])
        _build(spec)  # EPS 容差内放行

    def test_unknown_kind_and_missing_fields(self):
        with pytest.raises(ValueError) as exc:
            _build(_spec(tracks=[
                {"index": 0, "kind": "overlay", "clips": []},
                {"index": 1, "kind": "visual", "clips": [{"start": 0, "duration": 1}]},
                {"index": 2, "kind": "subtitle", "clips": [{"start": 0, "duration": 1}]},
                {"index": 3, "kind": "audio", "clips": [{"start": 0, "duration": 1}]},
            ]))
        msg = str(exc.value)
        assert "kind 必须是" in msg
        assert "clips[0].html 必须" in msg
        assert "clips[0].text 必须" in msg
        assert "clips[0].src 必须" in msg  # 一次列全

    def test_audio_volume_and_fade_types(self):
        with pytest.raises(ValueError, match="volume 必须是"):
            _build(_spec(tracks=[
                {"index": 2, "kind": "audio", "clips": [
                    {"start": 0, "duration": 1, "src": "a.mp3", "volume": 0}]}]))
        with pytest.raises(ValueError, match="fade_out 必须是 boolean"):
            _build(_spec(tracks=[
                {"index": 2, "kind": "audio", "clips": [
                    {"start": 0, "duration": 1, "src": "a.mp3",
                     "fade_out": "yes"}]}]))

    def test_seek_js_cannot_close_script(self):
        with pytest.raises(ValueError, match="</script"):
            _build(_spec(tracks=[
                {"index": 0, "kind": "visual", "clips": [
                    {"start": 0, "duration": 1, "html": "<div>x</div>",
                     "seek_js": "function(lt){var s='</script>';}"}]}]))

    def test_negative_start_and_zero_duration(self):
        with pytest.raises(ValueError, match="start 必须是"):
            _build(_spec(tracks=[
                {"index": 0, "kind": "visual", "clips": [
                    {"start": -1, "duration": 1, "html": "<div>x</div>"}]}]))
        with pytest.raises(ValueError, match="duration 必须是"):
            _build(_spec(tracks=[
                {"index": 0, "kind": "visual", "clips": [
                    {"start": 0, "duration": 0, "html": "<div>x</div>"}]}]))

    def test_normalize_fills_defaults(self):
        normalized = comp.normalize_composition_spec({
            "size": [640, 360], "duration_s": 3, "fps": 10,
            "tracks": [{"index": 2, "kind": "audio", "clips": [
                {"start": 0, "duration": 3, "src": "assets/v.mp3"}]}],
        })
        clip = normalized["tracks"][0]["clips"][0]
        assert clip["volume"] == 1.0 and clip["fade_out"] is False


# ─── render_client（W4 预埋） ──────────────────────────────────────────────

class _Plane:
    """最小渲染面桩：记录 PUT/POST，按 state['status'] 返回成片或错误体。"""

    def __init__(self):
        self.puts = []
        self.posts = []
        self.status = 200
        plane = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _read(self):
                length = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(length)

            def do_PUT(self):
                plane.puts.append({"path": self.path, "body": self._read()})
                payload = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):
                body = self._read()
                plane.posts.append({"path": self.path,
                                    "json": json.loads(body.decode("utf-8"))})
                if plane.status == 200:
                    payload = b"fake-mp4-bytes"
                    self.send_response(200)
                    self.send_header("X-Engine", "hyperframes@0.9.26")
                    self.send_header("X-Job-Id", plane.posts[-1]["json"]["job_id"])
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                else:
                    payload = json.dumps({
                        "error": "boom", "phase": "render",
                        "log_tail": "last lines"}).encode("utf-8")
                    self.send_response(plane.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class TestRenderClient:
    def test_uploads_assets_then_renders(self):
        with _Plane() as plane:
            data, headers = render_client.submit_render(
                "<html><body>hi</body></html>",
                {"assets/voice.mp3": b"voice-bytes"},
                fps=10, quality="looks", format="mp4", job_id="typed-abc",
                base_url=plane.base_url)
        assert data == b"fake-mp4-bytes"
        assert headers["X-Engine"] == "hyperframes@0.9.26"
        assert headers["X-Job-Id"] == "typed-abc"
        import hashlib
        digest = hashlib.sha256(b"voice-bytes").hexdigest()
        assert [p["path"] for p in plane.puts] == [f"/v1/assets/{digest}"]
        assert plane.puts[0]["body"] == b"voice-bytes"
        posted = plane.posts[0]["json"]
        assert posted["job_id"] == "typed-abc"
        assert posted["fps"] == 10 and posted["quality"] == "looks"
        assert posted["format"] == "mp4"
        assert posted["composition"]["html"] == "<html><body>hi</body></html>"
        assert posted["composition"]["assets"] == [
            {"sha256": digest, "name": "assets/voice.mp3",
             "path": "assets/voice.mp3"}]

    def test_env_base_url_used_when_argument_absent(self, monkeypatch):
        with _Plane() as plane:
            monkeypatch.setenv("VAAS_RENDER_URL", plane.base_url)
            data, _ = render_client.submit_render(
                "<html>x</html>", None, fps=10, quality="draft",
                format="mp4", job_id="job-1")
        assert data == b"fake-mp4-bytes"
        assert plane.posts[0]["json"]["composition"]["assets"] == []

    def test_http_error_surfaces_phase_and_log(self):
        with _Plane() as plane:
            plane.status = 500
            with pytest.raises(render_client.RenderPlaneError) as exc:
                render_client.submit_render(
                    "<html>x</html>", None, job_id="job-2",
                    base_url=plane.base_url)
        msg = str(exc.value)
        assert "500" in msg and "boom" in msg and "phase=render" in msg
        assert "log_tail=" in msg and "last lines" in msg

    def test_unreachable_names_url_and_fix(self):
        with pytest.raises(render_client.RenderPlaneError) as exc:
            render_client.submit_render(
                "<html>x</html>", None, job_id="job-3",
                base_url="http://127.0.0.1:1", timeout=2)
        msg = str(exc.value)
        assert "unreachable" in msg and "VAAS_RENDER_URL" in msg

    def test_input_validation(self):
        with pytest.raises(ValueError, match="html 必须"):
            render_client.submit_render("", None, job_id="j")
        with pytest.raises(ValueError, match="job_id 必须"):
            render_client.submit_render("<html>x</html>", None, job_id="")
        with pytest.raises(ValueError, match="fps 必须是正整数"):
            render_client.submit_render("<html>x</html>", None, fps=0, job_id="j")
        with pytest.raises(ValueError, match="相对路径"):
            render_client.submit_render(
                "<html>x</html>", [{"path": "/abs/v.mp3", "bytes": b"x"}],
                job_id="j")
        with pytest.raises(ValueError, match="bytes 必须是 bytes"):
            render_client.submit_render(
                "<html>x</html>", [{"path": "assets/v.mp3", "bytes": "x"}],
                job_id="j")

    def test_duplicate_asset_paths_rejected(self):
        with pytest.raises(ValueError, match="路径重复"):
            render_client.submit_render(
                "<html>x</html>",
                [{"path": "assets/v.mp3", "bytes": b"a"},
                 {"path": "assets/v.mp3", "bytes": b"b"}],
                job_id="j")

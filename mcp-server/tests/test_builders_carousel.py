"""
add-typed-video-html-renderer W2.2 carousel builder 测试。


覆盖:
  - validate_inputs：图片清单形状（string / {"path"} / {"prompt"}）一次列全
  - build：每段一图 html_full 场景（Ken Burns motion 轮换 pan_down/zoom_in/
    pan_right）、图片循环复用且相邻不同图、交叉淡入（场景内上一层冻结上一
    场景末态 transform，前 FADE 秒淡出）、句级字幕带（查表纯函数）、seek 契约、
    品牌 CSS wrapper、零外链（图片 data: URI 内联）
  - 补图 pending 对接：render_video 层提示词项未确认零产物返回，确认后补图
    回填路径再渲染（清单入账）；纯字符串 + generate:true → prompt 语义
  - build_typed_storyboard 集成：type.json gate（renderer=html）、orientation
  - 真渲染冒烟：ffmpeg 合成 3s 音频（voice_path 口径，不发起 TTS）→ mp4，
    双跑 mp4 容器字节 md5 一致 + 帧级 framemd5 交叉验证（chromium/ffmpeg
    可用才跑，缺则 skip 并注明）

playwright / ffmpeg / TTS / generate_image 除冒烟组外全部 mock（口径同
test_typed_scenes / test_determinism）。
"""

import json
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest
def _render_plane_available() -> bool:
    """渲染面可达性（W4 起真实出片必须经渲染面）。"""
    import os, socket
    from urllib.parse import urlparse
    url = os.getenv("VAAS_RENDER_URL", "http://127.0.0.1:8099")
    u = urlparse(url)
    try:
        with socket.create_connection((u.hostname or "127.0.0.1", u.port or 80), 1):
            return True
    except OSError:
        return False


sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import get_asset_by_slug
from mcp_server.tools import render as render_mod
from mcp_server.tools import typed_scenes as ts
from mcp_server.tools.typed_scenes import alignment as align_mod
from mcp_server.tools.typed_scenes.builders import carousel as car_mod
from mcp_server.tools._scene_guard import find_external_refs


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    from mcp_server.db import init_schema
    init_schema(db)
    return db


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
    """Redirect downloads/ 与 typed_scenes 的目录绑定到 tmp_path。"""
    root = tmp_path / "hermetic"
    downloads = root / "downloads"
    downloads.mkdir(parents=True)
    monkeypatch.setattr(render_mod, "VAAS_ROOT", root)
    monkeypatch.setattr(render_mod, "ensure_directory",
                        lambda type, slug: _mkdir(downloads / type / slug))
    monkeypatch.setattr(ts, "DOWNLOADS_DIR", downloads)
    monkeypatch.setattr(ts, "VAAS_ROOT", root)
    monkeypatch.setattr(ts, "ensure_directory_rel",
                        lambda *parts: _mkdir(downloads.joinpath(*parts)))
    monkeypatch.setattr(align_mod, "DOWNLOADS_DIR", downloads)
    monkeypatch.setattr(align_mod, "VAAS_ROOT", root)
    return {"root": root, "downloads": downloads}


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fake_frame_renderer(frames_per_scene: int = 2):
    """Fake playwright 逐帧渲染：按调用序写帧文件，记录每次调用。"""
    calls = []

    def _render(html, duration_s, size, out_dir, fps, start_index=0):
        produced = []
        for i in range(frames_per_scene):
            f = out_dir / f"frame_{start_index + i:05d}.png"
            f.write_bytes(b"\x89PNG-fake")
            produced.append(f)
        calls.append({"html": html, "duration_s": duration_s,
                      "start_index": start_index})
        return produced

    _render.calls = calls
    return _render


@pytest.fixture
def fake_render_pipeline(monkeypatch):
    """Mock 逐帧渲染 + ffmpeg + ffprobe，compose 全链不碰真实二进制。"""
    renderer = _fake_frame_renderer()
    monkeypatch.setattr(render_mod, "_render_html_frames", renderer)

    def _fake_ffmpeg(frames_dir, audio, out, fps):
        out.write_bytes(b"fake-mp4-bytes")

    monkeypatch.setattr(render_mod, "_ffmpeg", _fake_ffmpeg)

    class _Probe:
        returncode = 0
        stdout = "3.500\n"
        stderr = ""

    monkeypatch.setattr(render_mod.subprocess, "run",
                        lambda cmd, **kw: _Probe())  # 唯一到达的是 ffprobe
    return renderer


# ─── 共用料 ─────────────────────────────────────────────────────────────────

SCRIPT = ("## 开场\n大家好，先看第一张图。\n"
          "## 第一张\n这是第一张图的解说！内容很充实。\n"
          "## 第二张\n第二张图，讲趋势。\n"
          "## 第三张\n第三张图，讲结论。\n"
          "## 结尾\n关注我们，下期再见。")

SMOKE_SCRIPT = "## 一\n第一段解说。\n## 二\n第二段解说。\n## 三\n第三段解说。"


def _gradient_png(width: int, height: int) -> bytes:
    """确定性渐变 PNG（纯 zlib/struct，无 PIL）——与 test_determinism 同款。"""
    rows = b"".join(
        b"\x00" + bytes(v for x in range(width) for v in (
            (x * 255) // width,
            ((x + y) * 200) // (width + height),
            (y * 255) // height))
        for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        piece = struct.pack(">I", len(data)) + tag + data
        return piece + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def _three_images(tmp_path: Path) -> tuple[list[str], list[str]]:
    """3 张互不相同的本地 PNG → (路径清单, data URI 清单)。"""
    paths, uris = [], []
    for i, w in enumerate((64, 65, 66)):
        p = tmp_path / f"img{i}.png"
        p.write_bytes(_gradient_png(w, 64))
        paths.append(str(p))
        uris.append(car_mod._data_uri(p))
    return paths, uris


def _aligned_segments(raw, durations):
    out = []
    for seg, d in zip(raw, durations):
        out.append({"name": seg["name"], "text": seg["text"],
                    "duration_s": d,
                    "sentences": align_mod._sentences_with_timings(
                        seg["text"], d)})
    return out


# ─── validate_inputs：清单形状一次列全 ──────────────────────────────────────

class TestCarouselValidate:
    def setup_method(self):
        self.builder = ts.BUILDER_REGISTRY["carousel"]
        self.raw = align_mod.split_script(SCRIPT)

    def test_valid_image_lists_pass(self):
        self.builder.validate_inputs(
            {"images": ["a.png", {"path": "b.png"}, {"prompt": "城市夜景"}]},
            align_mod.skeleton_segments(self.raw))

    def test_missing_or_empty_images_rejected(self):
        with pytest.raises(ValueError, match="inputs.images"):
            self.builder.validate_inputs({}, align_mod.skeleton_segments(self.raw))
        with pytest.raises(ValueError, match="inputs.images"):
            self.builder.validate_inputs(
                {"images": []}, align_mod.skeleton_segments(self.raw))

    def test_bad_item_shapes_listed_by_index(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"images": [123, {}, {"prompt": ""}, {"path": "   "}, "ok.png"]},
                align_mod.skeleton_segments(self.raw))
        msg = str(exc.value)
        for i in range(4):
            assert f"images[{i}]" in msg
        assert "images[4]" not in msg  # 合法项不点名

    def test_all_violations_listed_at_once(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs({}, [])
        msg = str(exc.value)
        assert "inputs.images" in msg
        assert "分段结果为空" in msg

    def test_registry_and_contract_surface(self):
        assert self.builder.type_id == "carousel"
        import inspect
        assert list(inspect.signature(self.builder.validate_inputs).parameters) \
            == ["inputs", "segments"]
        assert list(inspect.signature(self.builder.build).parameters) \
            == ["segments", "inputs", "size", "theme"]


# ─── build：场景结构 / 循环复用 / 交叉淡入 / 字幕带 / 契约面 ─────────────────

class TestCarouselBuild:
    @pytest.fixture
    def built(self, tmp_path):
        paths, uris = _three_images(tmp_path)
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [2.0, 3.0, 2.5, 2.0, 1.5])
        theme = ts.load_theme()
        scenes = ts.BUILDER_REGISTRY["carousel"].build(
            segs, {"images": paths}, [1080, 1920], theme)
        return {"scenes": scenes, "segs": segs, "paths": paths, "uris": uris}

    def test_scene_structure(self, built):
        scenes, segs = built["scenes"], built["segs"]
        assert len(scenes) == 5
        assert [s["kind"] for s in scenes] == ["html_full"] * 5
        assert [s["name"] for s in scenes] == [g["name"] for g in segs]
        assert [s["duration_s"] for s in scenes] == [2.0, 3.0, 2.5, 2.0, 1.5]

    def test_image_reuse_and_adjacent_different(self, built):
        """3 图 5 段：场景 i 用 images[i % 3]；相邻场景不同图（spec 验收条目）。"""
        scenes, uris = built["scenes"], built["uris"]

        def cur_uri(html):
            # 当前图层（prev 顶层同场景共存，须按 id 精确取 cur 层）
            return re.search(r'<img class="kb" id="kb-cur" src="([^"]+)"',
                             html).group(1)

        for i, s in enumerate(scenes):
            assert cur_uri(s["html"]) == uris[i % 3], f"scene {i} image index"
        for i, (a, b) in enumerate(zip(scenes, scenes[1:])):
            assert cur_uri(a["html"]) != cur_uri(b["html"]), f"junction {i}"
        # 复用计数（cur+prev 全场景）：img0×4（场景0 cur、场景1/4 prev、场景3 cur）、
        # img1×3（场景1/4 cur、场景2 prev）、img2×2（场景2 cur、场景3 prev）
        counts = [sum(f'src="{u}"' in s["html"] for s in scenes) for u in uris]
        assert counts == [4, 3, 2]

    def test_motion_rotation(self, built):
        """Ken Burns motion 按 pan_down/zoom_in/pan_right 轮换（场景 i 取 i%3）。"""
        scenes = built["scenes"]
        for i, s in enumerate(scenes):
            assert car_mod._MOTION_JS[
                car_mod._MOTION_ORDER[i % 3]] in s["html"], f"scene {i} motion"

    def test_crossfade_prev_layer_freezes_prev_end_state(self, built):
        """交叉淡入（场景内口径）：场景 i>0 顶层带上一场景的图，transform 冻结在
        上一场景 motion 的 rel=1 末态，seek 期前 FADE 秒淡出；场景 0 无顶层。"""
        scenes, uris = built["scenes"], built["uris"]
        assert 'id="kb-prev"' not in scenes[0]["html"]
        for i in range(1, len(scenes)):
            html = scenes[i]["html"]
            assert 'id="kb-prev"' in html
            # 顶层图 = 上一场景的图（3 图轮换下相邻必不同）
            assert f'src="{uris[(i - 1) % 3]}"' in html
            # 冻结末态 = 上一场景 motion 的 rel=1 transform
            prev_motion = car_mod._MOTION_ORDER[(i - 1) % 3]
            assert f'style="transform:{car_mod._MOTION_END[prev_motion]}"' in html
            assert "1 - clamp(t / FADE, 0, 1)" in html
        assert "const FADE = 0.6;" in scenes[1]["html"]

    def test_single_image_reuse_has_no_fade_layer(self, tmp_path):
        """1 图全程复用：无上一层、无淡入淡出（相邻不重复在 M=1 无解，放行）。"""
        p = tmp_path / "only.png"
        p.write_bytes(_gradient_png(64, 64))
        raw = align_mod.split_script(SMOKE_SCRIPT)
        segs = _aligned_segments(raw, [1.0, 1.0, 1.0])
        scenes = ts.BUILDER_REGISTRY["carousel"].build(
            segs, {"images": [str(p)]}, [1080, 1920], ts.load_theme())
        assert len(scenes) == 3
        for s in scenes:
            assert 'id="kb-prev"' not in s["html"]
            assert f'src="{car_mod._data_uri(p)}"' in s["html"]

    def test_sentence_subtitle_band(self, built):
        scenes, segs = built["scenes"], built["segs"]
        html = scenes[1]["html"]
        sents = segs[1]["sentences"]
        assert json.dumps(sents[0]["text"], ensure_ascii=False) in html
        assert "SENTS[i].start" in html
        assert "subband" in html and 'id="sub"' in html
        # 句表缺失的段回退整段文本单句（防御口径，同 news-flash CTA）
        seg = {"name": "x", "text": "整段。", "duration_s": 1.0, "sentences": []}
        (scene,) = ts.BUILDER_REGISTRY["carousel"].build(
            [seg], {"images": built["paths"]}, [1080, 1920], ts.load_theme())
        assert json.dumps("整段。", ensure_ascii=False) in scene["html"]

    def test_seek_contract_and_zero_external_refs(self, built):
        scenes = built["scenes"]
        for s in scenes:
            html = s["html"]
            assert "data-stage" in html
            assert "window.__DURATION__" in html
            assert "window.__SIZE__=[1080,1920]" in html
            assert "window.seek = function (t)" in html
            assert "window.seek(0)" in html
            # 图片全部 data: URI 内联——零外链硬校验同源放行 data:
            assert html.count('src="data:image/png;base64,') >= 1
            assert find_external_refs(html) == []

    def test_brand_wrapper_from_theme(self, built):
        html = built["scenes"][0]["html"]
        assert "--vaas-accent:" in html and "--vaas-font-sans:" in html
        assert "--vaas-palette-0:" in html
        assert "var(--vaas-font-sans)" in html
        assert "var(--vaas-surface)" in html  # 字幕带底色取 theme
        # 颜色取 theme，不硬编码色值（base64 串不含 '#'，直比安全）
        assert "#070a20" not in html

    def test_unresolvable_image_named_in_error(self, tmp_path):
        raw = align_mod.split_script(SMOKE_SCRIPT)
        segs = _aligned_segments(raw, [1.0, 1.0, 1.0])
        with pytest.raises(ValueError, match="carousel image not found: nope.png"):
            ts.BUILDER_REGISTRY["carousel"].build(
                segs, {"images": ["nope.png"]}, [1080, 1920], ts.load_theme())

    def test_pending_prompt_at_build_named(self):
        """提示词项到 build 仍未回填（绕过 confirm 协议）→ 指路报错。"""
        raw = align_mod.split_script(SMOKE_SCRIPT)
        segs = _aligned_segments(raw, [1.0, 1.0, 1.0])
        with pytest.raises(ValueError, match="confirm"):
            ts.BUILDER_REGISTRY["carousel"].build(
                segs, {"images": [{"prompt": "城市夜景"}]},
                [1080, 1920], ts.load_theme())


# ─── 补图 pending 对接（render_video 层） ───────────────────────────────────

class TestCarouselPendingProtocol:
    @pytest.fixture
    def voice_wav(self, hermetic_fs):
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        return str(wav)

    @pytest.fixture(autouse=True)
    def probe_voice(self, monkeypatch):
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 3.0)

    def test_prompt_image_blocks_render_until_confirmed(
            self, hermetic_fs, fake_render_pipeline, voice_wav, monkeypatch):
        gen_calls = []
        ready = hermetic_fs["downloads"] / "ready.png"
        ready.write_bytes(b"png")

        def fake_generate_image(prompt, size=None):
            gen_calls.append(prompt)
            rel = "images/gen/a.jpeg"
            target = hermetic_fs["downloads"] / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"jpeg-fake")
            return {"id": "img-1", "file_paths": [rel]}

        monkeypatch.setattr("mcp_server.tools.generate.generate_image",
                            fake_generate_image)
        inputs = {"images": [{"prompt": "城市夜景 数据大屏"}, str(ready)],
                  "generate": True}

        pending = render_mod.render_video(
            type="carousel", script=SMOKE_SCRIPT, inputs=inputs,
            voice_path=voice_wav)
        assert pending["pending_images"] == [{"index": 0,
                                              "prompt": "城市夜景 数据大屏"}]
        assert "confirm_images" in pending["message"]
        assert gen_calls == []  # 未确认：不补图
        assert fake_render_pipeline.calls == []  # 未确认：不渲染（零产物）

        confirmed = render_mod.render_video(
            type="carousel", script=SMOKE_SCRIPT,
            inputs={**inputs, "confirm_images": True}, voice_path=voice_wav)
        assert gen_calls == ["城市夜景 数据大屏"]  # 先补图（清单入账）
        assert confirmed["type"] == "carousel"
        assert confirmed["scenes"] == 3
        asset = get_asset_by_slug(confirmed["slug"])
        typed = asset["metadata"]["typed"]
        assert typed["type"] == "carousel"
        assert typed["renderer"] in ("html", "hyperframes")
        assert typed["generated_images"][0]["file_path"] == "images/gen/a.jpeg"
        assert typed["generated_images"][0]["asset_id"] == "img-1"

    def test_plain_string_prompt_semantics(self, tmp_path):
        """公共层语义（carousel inputs 形状）：纯字符串非文件 + generate:true
        → prompt；无开关不视为待补；就绪文件跳过。"""
        ready = tmp_path / "ready.png"
        ready.write_bytes(b"png")
        inputs = {"images": ["a photo of charts", str(ready), {"path": str(ready)}],
                  "generate": "true"}
        assert ts.collect_pending_images(inputs) == [
            {"index": 0, "prompt": "a photo of charts"}]
        assert ts.collect_pending_images(
            {"images": ["a photo of charts"], "generate": "false"}) == []


# ─── build_typed_storyboard 集成（type.json gate + orientation） ─────────────

class TestCarouselStoryboard:
    @pytest.fixture
    def voice_wav(self, hermetic_fs):
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        return str(wav)

    @pytest.fixture(autouse=True)
    def probe_voice(self, monkeypatch):
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 3.0)

    def test_type_gate_passes_voice_path_mode(self, hermetic_fs, voice_wav,
                                              tmp_path):
        paths, _ = _three_images(tmp_path)
        storyboard, meta = ts.build_typed_storyboard(
            "carousel", SCRIPT, {"images": paths}, voice_path=voice_wav)
        assert storyboard["size"] == [1080, 1920]
        assert len(storyboard["scenes"]) == 5
        assert meta["type"] == "carousel" and meta["renderer"] == "html"
        assert meta["voice_mode"] == "voice_path"
        assert meta["plan_slug"].startswith("typed-")
        assert meta["tail_pad_frames"] == 15

    def test_orientation_landscape(self, hermetic_fs, voice_wav, tmp_path):
        paths, _ = _three_images(tmp_path)
        storyboard, _ = ts.build_typed_storyboard(
            "carousel", SMOKE_SCRIPT, {"images": paths,
                                       "orientation": "1920x1080"},
            voice_path=voice_wav)
        assert storyboard["size"] == [1920, 1080]
        assert "__SIZE__=[1920,1080]" in storyboard["scenes"][0]["html"]


# ─── 真渲染冒烟（chromium + ffmpeg 可用才跑；同 test_determinism 口径） ──────

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


def _ffmpeg_synth_voice(out: Path, seconds: int = 3) -> Path:
    """ffmpeg 合成旁白音频（sine 3s，确定字节；voice_path 口径不发起 TTS）。"""
    proc = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}",
         "-c:a", "pcm_s16le", str(out)],
        capture_output=True, text=True)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"ffmpeg voice synth failed: {proc.stderr[-300:]}")
    return out


def _md5(path: Path) -> str:
    import hashlib
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def _framemd5_hashes(path: Path) -> list:
    """ffmpeg 解码帧级 md5（容器时间戳无关的帧内容口径）。"""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "framemd5", "-"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"framemd5 failed: {proc.stderr[-300:]}")
    return [line.split(",")[-1].strip().lower()
            for line in proc.stdout.splitlines()
            if line and not line.startswith("#")]


@pytest.mark.real_render
@pytest.mark.skipif(not _render_plane_available(), reason="渲染面不可达（VAAS_RENDER_URL），真实出片冒烟跳过")
@pytest.mark.skipif(not _chromium_available(), reason="chromium unavailable "
                    "(carousel real-render smoke needs real playwright+chromium)")
class TestCarouselRealRenderSmoke:
    def test_double_run_md5_identical(self, hermetic_fs, tmp_path):
        """voice_path 真渲染冒烟：ffmpeg 合成 3s 音频 + 3 图 3 段 → mp4；双跑
        （不同 slug）帧级 framemd5 与容器字节 md5 逐一致（重放确定性契约）。"""
        if shutil.which("ffmpeg") is None:
            pytest.skip("ffmpeg unavailable (carousel real-render smoke)")
        voice = _ffmpeg_synth_voice(tmp_path / "voice.wav", 3)
        paths, _ = _three_images(tmp_path)

        def render(slug):
            return render_mod.render_video(
                type="carousel", script=SMOKE_SCRIPT,
                inputs={"images": paths}, voice_path=str(voice),
                fps=8, slug=slug)

        ra, rb = render("csmoke-a"), render("csmoke-b")
        assert ra["slug"] != rb["slug"] and ra["id"] != rb["id"]
        assert ra["type"] == "carousel"
        assert ra["frames"] == rb["frames"] and 24 <= ra["frames"] <= 32
        assert ra["duration_ms"] and 2500 <= ra["duration_ms"] <= 4000

        fa = hermetic_fs["downloads"] / ra["file_path"]
        fb = hermetic_fs["downloads"] / rb["file_path"]
        # 帧级口径（解码内容，与容器时间戳无关）——确定性契约本体
        assert _framemd5_hashes(fa) == _framemd5_hashes(fb), \
            "decoded frames differ between double runs"
        # 容器字节口径（最强；本机 ffmpeg mov muxer 无时间戳，实测可比）
        assert _md5(fa) == _md5(fb), "mp4 container bytes differ between double runs"

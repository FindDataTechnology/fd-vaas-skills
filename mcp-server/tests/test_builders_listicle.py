"""
listicle builder 测试（add-typed-video-html-renderer W2.1 card 族）。

覆盖:
  - validate_inputs：结构数对照（1 hook + N 条目 + 1 cta == items 数，一次
    列全对照面）、items 形状（rank 整数/整数字符串、title/desc 非空、image
    可选且文件必须已就绪——_resolve_file 相对 downloads 解析）
  - build：hook 卡（TOP N + 钩子首句 + REST 句级字幕带）→ 条目卡×N（rank
    大数字弹入 = seek 纯函数阶跃、title/desc、配图 data: URI 内联、句级字幕
    带、进度条、palette 轮转）→ CTA（逐句阶跃显现）；seek 契约面、品牌 CSS
    wrapper、零外链（find_external_refs 同源）
  - build_typed_storyboard：listicle 过三道 gate（renderer=html + builder
    注册）、items 不匹配在 TTS 花费之前报错（渲染前零产物）、计划键折入
    items、orientation 画幅
  - 真渲染冒烟探针（chromium 可用才跑）：voice_path（ffmpeg 合成 3s 音频）
    → mp4，双跑（不同 slug）容器字节 md5 一致 + 解码帧级 framemd5 交叉验证
    （口径与 test_determinism 同源）

playwright / ffmpeg / TTS / generate_image 在单测面全部 mock（冒烟探针除外）。
"""

import base64
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import init_schema
from mcp_server.tools import render as render_mod
from mcp_server.tools import typed_scenes as ts
from mcp_server.tools.typed_scenes import alignment as align_mod
from mcp_server.tools._scene_guard import find_external_refs


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
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


SCRIPT = ("## 开场\n这是一份今日行业榜单，一共三条。先来看看第三名。\n"
          "## 第三名\n第三名！短视频工具集大成者。\n"
          "## 第二名\n第二名，数据平台异军突起。\n"
          "## 第一名\n第一名非他莫属，生态王者。\n"
          "## 结尾\n关注我们，下期榜单再见。")
ITEMS = [
    {"rank": 3, "title": "短视频工具集", "desc": "一站式剪辑与分发工具箱"},
    {"rank": 2, "title": "数据平台", "desc": "面向增长的实时分析平台"},
    {"rank": 1, "title": "生态王者", "desc": "开放生态连接一切"},
]

# 1x1 PNG（内联 data: URI 用；字节确定性）
TINY_PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
                "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def _aligned_segments(raw, durations):
    out = []
    for seg, d in zip(raw, durations):
        out.append({"name": seg["name"], "text": seg["text"],
                    "duration_s": d,
                    "sentences": align_mod._sentences_with_timings(
                        seg["text"], d)})
    return out


def _md5(path: Path) -> str:
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


# ─── validate_inputs：结构数对照（一次列全） ────────────────────────────────

class TestListicleValidate:
    def setup_method(self):
        self.builder = ts.BUILDER_REGISTRY["listicle"]
        self.raw = align_mod.split_script(SCRIPT)

    def test_valid_structure_passes(self):
        self.builder.validate_inputs(
            {"items": ITEMS}, align_mod.skeleton_segments(self.raw))

    def test_rank_integer_string_accepted(self):
        items = [{**it, "rank": str(it["rank"])} for it in ITEMS]
        self.builder.validate_inputs(
            {"items": items}, align_mod.skeleton_segments(self.raw))

    def test_count_mismatch_lists_both_sides(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"items": ITEMS[:2]}, align_mod.skeleton_segments(self.raw))
        msg = str(exc.value)
        assert "口播条目段数 3" in msg and "items 数 2" in msg  # 3 vs 2 对照
        assert "hook" in msg and "cta" in msg  # 对照面点名
        assert "第三名" in msg and "第一名" in msg  # 条目段名入对照

    def test_short_script_points_to_segmentation(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"items": ITEMS},
                align_mod.skeleton_segments(self.raw[:1]))
        msg = str(exc.value)
        assert "1 hook + N 条目 + 1 cta" in msg
        assert "当前 1 段" in msg

    def test_all_violations_listed_at_once(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"items": [{"rank": True, "title": "", "desc": 3,
                            "image": "missing.png"},
                           "not-an-object"]},
                align_mod.skeleton_segments(self.raw))
        msg = str(exc.value)
        assert "items[0].rank" in msg
        assert "items[0].title" in msg
        assert "items[0].desc" in msg
        assert "items[0].image" in msg and "missing.png" in msg
        assert "items[1]" in msg

    def test_image_resolved_via_downloads_relative(self, hermetic_fs):
        img = hermetic_fs["downloads"] / "top1.png"
        img.write_bytes(b"\x89PNG-fake")
        items = [{**ITEMS[0], "image": "top1.png"}, *ITEMS[1:]]
        self.builder.validate_inputs(
            {"items": items}, align_mod.skeleton_segments(self.raw))

    def test_missing_items_key(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {}, align_mod.skeleton_segments(self.raw))
        assert "inputs.items 必须是非空 JSON 数组" in str(exc.value)


# ─── build：场景结构 / seek 契约 / rank 弹入 / data URI / 字幕带 ─────────────

class TestListicleBuild:
    @pytest.fixture
    def built(self, tmp_path):
        builder = ts.BUILDER_REGISTRY["listicle"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [2.0, 3.0, 2.5, 2.0, 1.5])
        img = tmp_path / "top1.png"
        img.write_bytes(b"\x89PNG-fake-bytes")
        items = [{**ITEMS[0]}, {**ITEMS[1]}, {**ITEMS[2], "image": str(img)}]
        theme = ts.load_theme()
        return builder.build(segs, {"items": items}, [1080, 1920], theme), segs

    def test_scene_structure(self, built):
        scenes, segs = built
        assert len(scenes) == 5
        assert [s["kind"] for s in scenes] == ["html_full"] * 5
        assert [s["name"] for s in scenes] == [g["name"] for g in segs]
        assert [s["duration_s"] for s in scenes] == [2.0, 3.0, 2.5, 2.0, 1.5]

    def test_seek_contract_and_zero_external_refs(self, built):
        scenes, _ = built
        for s in scenes:
            html = s["html"]
            assert "data-stage" in html
            assert "window.__DURATION__" in html
            assert "window.__SIZE__=[1080,1920]" in html
            assert "window.seek = function (t)" in html
            assert "window.seek(0)" in html
            assert find_external_refs(html) == []  # 零外链硬校验同源

    def test_brand_wrapper_from_theme(self, built):
        scenes, _ = built
        html = scenes[0]["html"]
        assert "--vaas-accent:" in html and "--vaas-font-sans:" in html
        assert "--vaas-palette-0:" in html
        assert "var(--vaas-font-sans)" in html
        assert "var(--vaas-accent)" in html

    def test_palette_cycles_across_item_cards(self, built):
        scenes, _ = built
        assert "color:#58a6ff" in scenes[1]["html"]  # palette[0] 槽位上色
        assert "color:#3fb950" in scenes[2]["html"]  # palette[1]

    def test_hook_card_top_n_and_first_sentence(self, built):
        scenes, segs = built
        hook = scenes[0]["html"]
        assert '"top":3' in hook
        assert "'TOP ' + DATA.top" in hook  # JS 运行时拼 TOP N
        # 钩子首句做大字标题，其余句子进字幕带（REST 查表）
        first, rest = segs[0]["sentences"][0], segs[0]["sentences"][1:]
        assert json.dumps(first["text"], ensure_ascii=False) in hook
        assert json.dumps(rest[0]["text"], ensure_ascii=False) in hook
        assert "REST[i].start" in hook
        assert "slice(1)" in hook

    def test_rank_pop_is_seek_pure_step(self, built):
        scenes, _ = built
        item = scenes[1]["html"]
        # rank 大数字：data 岛 + 延迟起步（卡片落位后）3 步阶跃 scale 弹入
        assert '"rank":3' in item
        assert "stepIn(t, 0.16, 3, 0.14)" in item
        assert "scale(" in item
        assert "rank.style.transform" in item
        assert "rank.style.opacity" in item

    def test_item_card_content_and_subtitle_band(self, built):
        scenes, segs = built
        item = scenes[1]["html"]
        assert json.dumps(ITEMS[0]["title"], ensure_ascii=False) in item
        assert json.dumps(ITEMS[0]["desc"], ensure_ascii=False) in item
        sents = segs[1]["sentences"]
        assert json.dumps(sents[0]["text"], ensure_ascii=False) in item
        assert "SENTS[i].start" in item  # 句级字幕查表
        assert "bar.style.width" in item  # 进度条随 t

    def test_image_inlined_as_data_uri(self, built):
        scenes, _ = built
        with_img = scenes[3]["html"]  # items[2] 带 image
        assert "data:image/png;base64," in with_img
        assert "top1.png" not in with_img  # 路径引用不落场景（零外链面）
        assert '<figure class="fig"' in with_img
        without_img = scenes[1]["html"]
        assert "data:image" not in without_img
        assert '<figure' not in without_img

    def test_cta_reveals_sentences_stepwise(self, built):
        scenes, segs = built
        cta = scenes[4]["html"]
        assert cta.count('class="line"') == len(segs[4]["sentences"])
        assert "DATA.sentences[i].start" in cta
        assert '"top":3' in cta


# ─── build_typed_storyboard：gate / 渲染前零产物 / 计划键 / 画幅 ─────────────

class TestBuildTypedStoryboardListicle:
    def test_gate_passes_end_to_end(self, hermetic_fs, monkeypatch):
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        storyboard, meta = ts.build_typed_storyboard(
            "listicle", SCRIPT, {"items": ITEMS}, voice_path=str(wav))
        assert storyboard["size"] == [1080, 1920]
        assert len(storyboard["scenes"]) == 5
        assert meta["type"] == "listicle" and meta["renderer"] == "html"
        assert meta["composition"] == "ListicleVideo"
        assert meta["voice_mode"] == "voice_path"
        assert len(meta["segments"]) == 5

    def test_mismatch_rejected_before_tts_zero_artifacts(
            self, hermetic_fs, monkeypatch):
        def explode(*a, **kw):
            raise AssertionError("TTS must not run when counts mismatch")

        monkeypatch.setattr("mcp_server.generators.tts.synthesize", explode)
        with pytest.raises(ValueError) as exc:
            ts.build_typed_storyboard("listicle", SCRIPT, {"items": ITEMS[:2]})
        msg = str(exc.value)
        assert "口播条目段数 3" in msg and "items 数 2" in msg
        assert not (hermetic_fs["downloads"] / "audio").exists()  # 零产物

    def test_plan_slug_folds_items(self, hermetic_fs, monkeypatch):
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        _, meta1 = ts.build_typed_storyboard(
            "listicle", SCRIPT, {"items": ITEMS}, voice_path=str(wav))
        _, meta2 = ts.build_typed_storyboard(
            "listicle", SCRIPT, {"items": ITEMS}, voice_path=str(wav))
        assert meta1["plan_slug"] == meta2["plan_slug"]  # 同输入同键
        changed = [{**ITEMS[0], "rank": 99}, *ITEMS[1:]]
        _, meta3 = ts.build_typed_storyboard(
            "listicle", SCRIPT, {"items": changed}, voice_path=str(wav))
        assert meta3["plan_slug"] != meta1["plan_slug"]  # items 折入计划键

    def test_orientation_landscape(self, hermetic_fs, monkeypatch):
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        storyboard, _ = ts.build_typed_storyboard(
            "listicle", SCRIPT,
            {"items": ITEMS, "orientation": "1920x1080"},
            voice_path=str(wav))
        assert storyboard["size"] == [1920, 1080]
        assert "__SIZE__=[1920,1080]" in storyboard["scenes"][0]["html"]


# ─── 真渲染冒烟探针（chromium 可用才跑；口径与 test_determinism 同源） ────────

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
                    "(listicle smoke probe: needs playwright + chromium)")
class TestListicleRenderSmoke:
    def test_voice_path_double_run_md5(self, hermetic_fs, tmp_path):
        """voice_path（ffmpeg 合成 3s 音频）→ mp4；双跑 md5 一致（容器口径 +
        帧级 framemd5 交叉验证）。"""
        if shutil.which("ffmpeg") is None:
            pytest.skip("ffmpeg unavailable (listicle smoke needs ffmpeg)")
        voice = tmp_path / "voice.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "sine=frequency=440:duration=3", "-c:a", "libmp3lame",
             str(voice)],
            capture_output=True, check=True)
        img = tmp_path / "top1.png"
        img.write_bytes(base64.b64decode(TINY_PNG_B64))
        items = [{**ITEMS[0]}, {**ITEMS[1]}, {**ITEMS[2], "image": str(img)}]

        def run(slug):
            return render_mod.render_video(
                type="listicle", script=SCRIPT, inputs={"items": items},
                voice_path=str(voice), slug=slug, fps=8)

        ra, rb = run("listicle-smoke-a"), run("listicle-smoke-b")
        assert ra["slug"] != rb["slug"] and ra["id"] != rb["id"]
        assert ra["frames"] == rb["frames"] and ra["frames"] >= 20
        assert ra["duration_ms"] and 2000 <= ra["duration_ms"] <= 5000
        fa = hermetic_fs["root"] / "downloads" / ra["file_path"]
        fb = hermetic_fs["root"] / "downloads" / rb["file_path"]
        # 帧级口径（解码内容）——确定性契约本体
        assert _framemd5_hashes(fa) == _framemd5_hashes(fb), \
            "decoded frames differ between double runs"
        # 容器字节口径（最强）
        assert _md5(fa) == _md5(fb), \
            f"mp4 container bytes differ: {_md5(fa)} vs {_md5(fb)}"


def test_read_script_long_inline_text_is_not_treated_as_path():
    """CI 首跑实证：含换行/长 UTF-8 的内联稿在 Linux 上 Path(...).is_file()
    抛 ENAMETOOLONG；_read_script 必须原样返回，不得触文件系统。"""
    from mcp_server.tools.typed_scenes import _read_script
    assert _read_script(SCRIPT) == SCRIPT
    long_single_line = "行业观察" * 100  # 1200 bytes, no newline
    assert _read_script(long_single_line) == long_single_line

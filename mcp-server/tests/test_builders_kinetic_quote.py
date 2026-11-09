"""
add-typed-video-html-renderer W2.4：kinetic-quote builder 测试。

覆盖:
  - validate_inputs：零图片依赖（inputs.images 非空拒绝，spec MUST NOT 依赖
    图片素材）、`**` 标记成对校验（不成对指路段名）、违规一次列全
  - build：每段一场景 html_full（零 <img>/零外链）、句块数 = 句数、
    `**词**` 强调（kw span + 品牌强调色 + em 放大）、无标记段 fallback 取
    段内最长 CJK 连续片段（与 Remotion 管线 extract-keywords steps.mjs 同
    口径）、seek 阶跃契约（stepIn 相对句 start，opacity+translateY）、句级
    字幕与句切换对齐（同一张句表 + `**` 标记不进字幕）、品牌 CSS wrapper
  - type 模式注册链：renderer=html 三道 gate 通过、build_typed_storyboard
    voice_path 口径端到端（ffprobe mock，不发起 TTS）、图片输入在 TTS 前
    被拒（零产物）

playwright/ffmpeg/TTS 全部不真跑（真渲染冒烟由本 change 手工冒烟兜底）。
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import init_schema
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


# seg0 两个带 `**复利**` 标记的句；seg1 无标记（fallback 最长 CJK 片段）
KQ_SCRIPT = ("## 开场\n真正的增长来自**复利**，而不是运气。\n"
             "坚持记录，时间会给你答案。\n"
             "## 结尾\n数据不会说谎，长期主义永远有效。")


def _aligned_segments(raw, durations):
    out = []
    for seg, d in zip(raw, durations):
        out.append({"name": seg["name"], "text": seg["text"],
                    "duration_s": d,
                    "sentences": align_mod._sentences_with_timings(
                        seg["text"], d)})
    return out


# ─── validate_inputs：零图片依赖 + 标记成对 ────────────────────────────────

class TestKineticQuoteValidate:
    def setup_method(self):
        self.builder = ts.BUILDER_REGISTRY["kinetic-quote"]
        self.raw = align_mod.split_script(KQ_SCRIPT)

    def test_valid_passes(self):
        self.builder.validate_inputs({}, self.raw)

    def test_empty_images_list_passes(self):
        self.builder.validate_inputs({"images": []},
                                     align_mod.skeleton_segments(self.raw))

    def test_images_rejected_named(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"images": [{"prompt": "配图"}, "x.png"]},
                align_mod.skeleton_segments(self.raw))
        msg = str(exc.value)
        assert "images" in msg and "纯文字" in msg
        assert "2 项" in msg  # 点名收到几张
        assert "MUST NOT" in msg  # spec 口径指路

    def test_unbalanced_marker_named_with_segment(self):
        raw = align_mod.split_script("## 段一\n好的开始是**成功的一半。\n"
                                     "## 段二\n正常。")
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs({}, raw)
        msg = str(exc.value)
        assert "段一" in msg and "不成对" in msg
        assert "段二" not in msg  # 只点名违规段

    def test_all_violations_listed_at_once(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"images": ["a.png"]},
                [{"name": "空段", "text": "", "duration_s": 0.0,
                  "sentences": []},
                 {"name": "坏段", "text": "只有**一半标记。", "duration_s": 0.0,
                  "sentences": []}])
        msg = str(exc.value)
        assert "images" in msg
        assert "空段" in msg
        assert "坏段" in msg and "不成对" in msg


# ─── build：场景结构 / 强调 / seek 契约 / 品牌 wrapper ──────────────────────

class TestKineticQuoteBuild:
    @pytest.fixture
    def built(self):
        builder = ts.BUILDER_REGISTRY["kinetic-quote"]
        raw = align_mod.split_script(KQ_SCRIPT)
        segs = _aligned_segments(raw, [4.0, 3.0])
        theme = ts.load_theme()
        return builder.build(segs, {}, [1080, 1920], theme), segs

    def test_scene_structure(self, built):
        scenes, segs = built
        assert len(scenes) == 2
        assert [s["kind"] for s in scenes] == ["html_full"] * 2
        assert [s["name"] for s in scenes] == [g["name"] for g in segs]
        assert [s["duration_s"] for s in scenes] == [4.0, 3.0]
        assert "__DURATION__=4.0" in scenes[0]["html"]
        assert "__DURATION__=3.0" in scenes[1]["html"]

    def test_zero_images_and_offline(self, built):
        scenes, _ = built
        for s in scenes:
            html = s["html"]
            assert "<img" not in html          # 零图片素材
            assert "background-image" not in html
            assert find_external_refs(html) == []  # 零外链硬校验同源

    def test_sblock_count_equals_sentences(self, built):
        scenes, segs = built
        for scene, seg in zip(scenes, segs):
            assert scene["html"].count('class="sblock"') == \
                len(seg["sentences"])

    def test_marked_keyword_emphasized(self, built):
        scenes, _ = built
        html = scenes[0]["html"]
        assert '<span class="kw">复利</span>' in html
        # 强调样式走品牌强调色 + em 放大（CSS 承担，不内联色值）；
        # keep-all 保证关键词整体换行不在词内断开（对齐 Remotion kwScale=1.12）
        assert ".kw{color:var(--vaas-accent)" in html
        assert "font-size:1.12em" in html
        assert "word-break:keep-all" in html

    def test_fallback_keyword_longest_cjk_run(self, built):
        scenes, _ = built
        # 与 Remotion 管线 extract-keywords（steps.mjs）同口径：无标记段取
        # 段内最长 CJK 连续片段（>=2 字）
        assert '<span class="kw">长期主义永远有效</span>' in scenes[1]["html"]

    def test_seek_step_contract(self, built):
        scenes, _ = built
        for s in scenes:
            html = s["html"]
            assert "data-stage" in html
            assert "window.__SIZE__=[1080,1920]" in html
            assert "window.seek = function (t)" in html
            assert "window.seek(0)" in html
            # 句内 3 步阶跃（相对句 start）：opacity/位移全由 t 决定
            assert "stepIn(t, SENTS[i].start, 3, 0.15)" in html
            assert "el.style.opacity = String(k / 3)" in html
            assert "el.style.transform = 'translateY('" in html
            assert "transition" not in html  # 无 CSS 过渡（逐帧重放确定性）

    def test_caption_aligned_and_markers_stripped(self, built):
        scenes, segs = built
        html = scenes[0]["html"]
        # 句级字幕与句块同一张句表 → 句切换严格对齐
        assert "SENTS[cur].text" in html
        sents = segs[0]["sentences"]
        assert json.dumps(sents[0]["text"], ensure_ascii=False) in html
        assert "SENTS[i].start" in html
        # `**` 标记不进字幕（标记是排版指令不是内容）
        assert ".replace(/\\*\\*/g, '')" in html

    def test_brand_wrapper_from_theme(self, built):
        scenes, _ = built
        html = scenes[0]["html"]
        assert "--vaas-accent:" in html and "--vaas-font-sans:" in html
        assert "--vaas-palette-0:" in html
        assert "var(--vaas-font-sans)" in html
        # 颜色全部取 theme 变量，不硬编码色值
        assert "#070a20" not in html

    def test_landscape_orientation(self, built):
        builder = ts.BUILDER_REGISTRY["kinetic-quote"]
        raw = align_mod.split_script(KQ_SCRIPT)
        segs = _aligned_segments(raw, [4.0, 3.0])
        scenes = builder.build(segs, {}, [1920, 1080], ts.load_theme())
        assert "__SIZE__=[1920,1080]" in scenes[0]["html"]


# ─── type 模式注册链：gate / storyboard / 渲染前零产物 ──────────────────────

class TestKineticQuoteTypeMode:
    def test_registry_gate_passes(self):
        # type.json renderer=html + builder 已注册 → 三道 gate 全过
        assert "kinetic-quote" in ts.list_video_types()
        assert ts.load_type_json("kinetic-quote").get("renderer") in ("html", "hyperframes")
        assert ts.BUILDER_REGISTRY["kinetic-quote"].type_id == "kinetic-quote"

    def test_storyboard_voice_path_mode(self, hermetic_fs, monkeypatch):
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        raw = align_mod.split_script(KQ_SCRIPT)
        storyboard, meta = ts.build_typed_storyboard(
            "kinetic-quote", KQ_SCRIPT, {}, voice_path=str(wav))
        assert meta["type"] == "kinetic-quote"
        assert meta["renderer"] == "html"
        assert meta["composition"] == "KineticQuoteVideo"
        assert storyboard["size"] == [1080, 1920]
        assert [s["name"] for s in storyboard["scenes"]] == \
            [g["name"] for g in raw]
        assert meta["voice_mode"] == "voice_path"
        assert meta["plan_slug"].startswith("typed-")
        # tailPad 帧垫沿用 type.json defaults（kinetic-quote: 15 @30fps）
        assert meta["tail_pad_frames"] == 15
        total_chars = sum(len(g["text"]) for g in raw)
        assert storyboard["scenes"][-1]["duration_s"] == pytest.approx(
            8.0 * len(raw[-1]["text"]) / total_chars + 0.5, abs=1e-3)

    def test_images_rejected_before_tts_zero_artifacts(self, hermetic_fs,
                                                       monkeypatch):
        def _no_tts(*a, **kw):
            raise AssertionError("TTS must not run before validate_inputs")

        monkeypatch.setattr("mcp_server.generators.tts.synthesize", _no_tts)
        with pytest.raises(ValueError, match="images"):
            ts.build_typed_storyboard(
                "kinetic-quote", KQ_SCRIPT,
                {"images": [{"prompt": "配图"}]})

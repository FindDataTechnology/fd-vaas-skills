"""
builder 契约 v2 + build_typed_composition 单测（adopt-hyperframes-video-renderer
W3.1）。

覆盖 typed_scenes.build_typed_composition：
  - gate：renderer 同时接受 "html" 与 "hyperframes"；未注册 builder 列清单；
    未实现契约 v2 的 builder 在 TTS 花费之前就 NotImplementedError（不白烧）
  - voice_path 模式：ffprobe 比例分摊 → visual/subtitle 片段 → composition
    HTML（根属性、每 clip data-*、旁白整轨、字幕后品牌条）；meta 结构
    （engine/scene_seconds/fps/duration_s/segments/billing/assets）
  - TTS 模式：逐段 synthesize + concat 全轨 → assets/voice.mp3，billing
    tts_segments 全量；时长 = 段和 + tailPad
  - BGM：独立轨（index 3）、volume/fade_out 进 audio clip 与音量包络
  - 结构校验先于 TTS（骨架 Segment 的 duration=0/无句表）
  - 片段契约早报错（build_composition 非 dict / 片段缺 start/duration）
  - 计划键稳定与折入（同输入同 slug；bgm 变化换 slug）
  - 零外链（编译入口硬校验；_scene_guard 复核）

TTS / ffprobe / ffmpeg concat 全部 mock；DB 与 downloads 重定向 tmp_path。
"""

import inspect
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

SCRIPT = ("## 开场\n大家好，今天是三条行业热点。\n"
          "## 要点一\n第一点！数据很关键。\n"
          "## 要点二\n第二点，值得关注。\n"
          "## 结尾\n关注我们，下期再见。")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
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


def _write_type(types_dir: Path, type_id: str, *, renderer="hyperframes",
                tail_pad=15) -> None:
    d = types_dir / type_id
    d.mkdir(parents=True)
    (d / "type.json").write_text(json.dumps({
        "id": type_id,
        "renderer": renderer,
        "inputs": {
            "orientation": {
                "enum": ["1080x1920", "1920x1080"],
                "default": "1080x1920",
            },
        },
        "defaults": {"tailPad": tail_pad},
        "composition": "FakeComposition",
    }), encoding="utf-8")


@pytest.fixture
def fake_types(tmp_path, monkeypatch):
    d = tmp_path / "types"
    d.mkdir()
    monkeypatch.setattr(ts, "VIDEO_TYPES_DIR", d)
    return d


@pytest.fixture
def register(monkeypatch):
    """注册测试 builder 到 registry 副本（不污染全局注册表）。"""
    reg = dict(ts.BUILDER_REGISTRY)
    monkeypatch.setattr(ts, "BUILDER_REGISTRY", reg)

    def _add(builder):
        reg[builder.type_id] = builder
        return builder

    return _add


class _FakeCompositionBuilder(ts.AbstractBuilder):
    """契约 v2 测试 builder：每段一卡 + 句级字幕。"""

    type_id = "fake-cards"

    def __init__(self):
        self.validations = []
        self.builds = []

    def validate_inputs(self, inputs, segments):
        self.validations.append([
            {"name": s["name"], "duration_s": s["duration_s"],
             "sentences": s["sentences"]} for s in segments])
        if inputs.get("fail_structure"):
            raise ValueError("fake-cards 结构数对照失败: fail_structure")

    def build_composition(self, segments, inputs, size, theme):
        self.builds.append({"segments": [dict(s) for s in segments],
                            "size": list(size), "theme": theme})
        visual, subtitle = [], []
        start = 0.0
        for i, seg in enumerate(segments):
            dur = float(seg["duration_s"])
            visual.append({
                "start": start, "duration": dur,
                "html": f'<div class="card" id="card-{i}">'
                        f'<h1>{seg["name"]}</h1></div>',
                "seek_js": "function(lt){(window.__hits=window.__hits||[])"
                           f".push(['v{i}',lt]);}}",
            })
            for s in seg["sentences"] or []:
                subtitle.append({"start": round(start + s["start"], 4),
                                 "duration": round(s["end"] - s["start"], 4),
                                 "text": s["text"]})
            start = round(start + dur, 4)
        return {"visual": visual, "subtitle": subtitle}


class _BrokenClipBuilder(_FakeCompositionBuilder):
    type_id = "broken-cards"

    def build_composition(self, segments, inputs, size, theme):
        return {"visual": [{"start": 0, "html": "<div>x</div>"}],
                "subtitle": []}


class _NotDictBuilder(_FakeCompositionBuilder):
    type_id = "notdict-cards"

    def build_composition(self, segments, inputs, size, theme):
        return [{"html": "<div>x</div>"}]


class _LegacyBuilder(ts.AbstractBuilder):
    """旧契约 builder（只有 build()，尚未迁移 v2）。"""

    type_id = "legacy-cards"

    def validate_inputs(self, inputs, segments):
        pass

    def build(self, segments, inputs, size, theme):
        return []


def _voice_path(hermetic_fs, monkeypatch, total_s=8.0) -> Path:
    monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: total_s)
    wav = hermetic_fs["downloads"] / "voice.wav"
    wav.write_bytes(b"fake-audio")
    return wav


# ─── gate ──────────────────────────────────────────────────────────────────

class TestGate:
    def test_hyperframes_renderer_accepted(self, hermetic_fs, fake_types,
                                           register, monkeypatch):
        _write_type(fake_types, "fake-cards", renderer="hyperframes")
        register(_FakeCompositionBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        html, meta = ts.build_typed_composition(
            "fake-cards", SCRIPT, {}, voice_path=str(wav))
        assert 'data-composition-id="main"' in html
        assert meta["renderer"] == "hyperframes"

    def test_html_renderer_accepted_in_parallel_wave(self, hermetic_fs,
                                                     fake_types, register,
                                                     monkeypatch):
        """并行波次：renderer 仍是 html 的 type 也能走 v2（不撞车）。"""
        _write_type(fake_types, "fake-cards", renderer="html")
        register(_FakeCompositionBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        html, meta = ts.build_typed_composition(
            "fake-cards", SCRIPT, {}, voice_path=str(wav))
        assert "window.__hf" in html
        assert meta["renderer"] == "html"
        assert meta["engine"] == "hyperframes"

    def test_other_renderer_rejected(self, fake_types, register):
        _write_type(fake_types, "fake-cards", renderer="screen-recording")
        register(_FakeCompositionBuilder())
        with pytest.raises(ValueError, match="not an html-renderer type"):
            ts.build_typed_composition("fake-cards", SCRIPT, {})

    def test_unregistered_builder_lists_available(self, fake_types, monkeypatch):
        _write_type(fake_types, "fake-cards")
        monkeypatch.setattr(ts, "BUILDER_REGISTRY", {})
        with pytest.raises(ValueError, match="Available builders"):
            ts.build_typed_composition("fake-cards", SCRIPT, {})

    def test_legacy_builder_rejected_before_tts(self, fake_types, register,
                                                hermetic_fs, monkeypatch):
        _write_type(fake_types, "legacy-cards")
        register(_LegacyBuilder())
        calls = []
        monkeypatch.setattr("mcp_server.generators.tts.synthesize",
                            lambda *a, **kw: calls.append(1) or {})
        with pytest.raises(NotImplementedError, match="build_composition"):
            ts.build_typed_composition("legacy-cards", SCRIPT, {})
        assert calls == []  # TTS 零花费

    def test_contract_signatures_stable(self):
        vp = list(inspect.signature(
            ts.AbstractBuilder.build_composition).parameters)
        assert vp == ["self", "segments", "inputs", "size", "theme"]
        fp = list(inspect.signature(ts.build_typed_composition).parameters)
        assert fp == ["type_id", "script", "inputs", "voice_path", "bgm", "owner"]


# ─── voice_path 模式 ───────────────────────────────────────────────────────

@pytest.fixture
def built_voice(hermetic_fs, fake_types, register, monkeypatch):
    _write_type(fake_types, "fake-cards")
    builder = register(_FakeCompositionBuilder())
    wav = _voice_path(hermetic_fs, monkeypatch)
    html, meta = ts.build_typed_composition(
        "fake-cards", SCRIPT, {}, voice_path=str(wav))
    return {"html": html, "meta": meta, "builder": builder, "wav": wav}


class TestVoicePathComposition:
    def test_root_and_tracks(self, built_voice):
        html = built_voice["html"]
        assert 'data-composition-id="main"' in html
        assert 'data-start="0"' in html
        # 尾垫并入末片段（末帧保持可见，不再追加空白黑段）→ 时长仍 8.5
        assert 'data-duration="8.5"' in html
        assert 'data-width="1080"' in html
        assert 'data-height="1920"' in html
        assert 'data-fps="30"' in html
        # 4 段 → 4 张视觉卡（track 0）
        assert html.count('data-track-index="0"') == 4
        assert 'class="clip" data-start="0" data-duration="2.6047"' in html
        # 句级字幕（track 1）：开场 1 + 要点一 2 + 要点二 1 + 结尾 1
        assert html.count('class="clip subtitle"') == 5
        assert html.count('data-track-index="1"') == 5
        assert "第一点！" in html and "数据很关键。" in html
        # 旁白整轨（track 2）：start=0、时长 8、素材相对路径
        assert ('<audio id="hf-audio-2-0" data-start="0" data-duration="8" '
                'data-track-index="2" src="assets/voice.wav" volume="1">') in html

    def test_seek_runtime_from_builder_clips(self, built_voice):
        html = built_voice["html"]
        assert "window.__hf = {" in html
        assert "var DURATION = 8.5;" in html
        # 4 个带 seek_js 的 visual clip → 4 个窗口 + 4 个函数
        assert html.count(".push(['v") == 4
        assert "var WINDOWS = [[0.0, 2.6047]" in html

    def test_meta_structure(self, built_voice):
        meta = built_voice["meta"]
        assert meta["type"] == "fake-cards"
        assert meta["engine"] == "hyperframes"
        assert meta["renderer"] == "hyperframes"
        assert meta["composition"] == "FakeComposition"
        assert meta["plan_slug"].startswith("typed-")
        assert meta["size"] == [1080, 1920]
        assert meta["fps"] == 30
        # 尾垫延长最后画面片段（末帧可见），总时长 = 画面末点 8.5
        assert meta["duration_s"] == 8.5
        assert meta["scene_seconds"] == 8.0
        assert meta["tail_pad_frames"] == 15
        assert meta["voice_mode"] == "voice_path"
        assert meta["voice_path"] == str(built_voice["wav"])
        assert len(meta["segments"]) == 4
        assert sum(len(s["sentences"]) for s in meta["segments"]) == 5
        assert meta["billing"]["mode"] == "voice_path"
        assert meta["billing"]["tts_segments"] is None
        assert meta["billing"]["scene_seconds"] == 8.0
        assert meta["billing"]["unit_type"] == "second"
        assert meta["bgm"] is None
        assert meta["assets"] == [{
            "role": "voice", "path": "assets/voice.wav",
            "source": str(built_voice["wav"])}]

    def test_structure_checked_on_skeleton_before_tts(self, built_voice):
        first = built_voice["builder"].validations[0]
        assert [s["name"] for s in first] == ["开场", "要点一", "要点二", "结尾"]
        assert all(s["duration_s"] == 0.0 for s in first)
        assert all(s["sentences"] == [] for s in first)

    def test_builder_receives_aligned_segments(self, built_voice):
        call = built_voice["builder"].builds[0]
        segs = call["segments"]
        assert [s["name"] for s in segs] == ["开场", "要点一", "要点二", "结尾"]
        assert sum(s["duration_s"] for s in segs) == pytest.approx(8.0)
        assert all(s["sentences"] for s in segs)  # 句表供字幕轨
        assert call["size"] == [1080, 1920]
        assert (call["theme"].get("brand") or {}).get("fontSans")

    def test_zero_external_refs(self, built_voice):
        html = built_voice["html"]
        assert find_external_refs(html) == []
        assert 'src="assets/' in html

    def test_landscape_orientation(self, hermetic_fs, fake_types, register,
                                   monkeypatch):
        _write_type(fake_types, "fake-cards")
        register(_FakeCompositionBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        html, meta = ts.build_typed_composition(
            "fake-cards", SCRIPT, {"orientation": "1920x1080"},
            voice_path=str(wav))
        assert meta["size"] == [1920, 1080]
        assert 'data-width="1920"' in html and 'data-height="1080"' in html

    def test_bad_orientation_lists_allowed(self, hermetic_fs, fake_types,
                                           register, monkeypatch):
        _write_type(fake_types, "fake-cards")
        register(_FakeCompositionBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        with pytest.raises(ValueError, match="orientation must be one of"):
            ts.build_typed_composition(
                "fake-cards", SCRIPT, {"orientation": "400x400"},
                voice_path=str(wav))

    def test_tail_pad_zero_uses_audio_length(self, hermetic_fs, fake_types,
                                             register, monkeypatch):
        _write_type(fake_types, "fake-cards", tail_pad=0)
        register(_FakeCompositionBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        html, meta = ts.build_typed_composition(
            "fake-cards", SCRIPT, {}, voice_path=str(wav))
        assert meta["duration_s"] == 8.0
        assert 'data-duration="8"' in html


# ─── TTS 模式 ──────────────────────────────────────────────────────────────

class TestTtsComposition:
    def test_concat_full_track_and_meta(self, hermetic_fs, fake_types,
                                        register, monkeypatch):
        _write_type(fake_types, "fake-cards")
        register(_FakeCompositionBuilder())

        def fake_synthesize(text, voice=None, speed=None, format="mp3",
                            idempotency_key=None):
            return {"file_path": f"audio/fake-{len(text)}.mp3",
                    "duration_ms": 500 * len(text)}

        monkeypatch.setattr("mcp_server.generators.tts.synthesize", fake_synthesize)
        concated = {}

        def fake_concat(paths, out_path):
            concated["paths"] = list(paths)
            concated["out"] = Path(out_path)
            out_path.write_bytes(b"fake-mp3")
            return Path(out_path)

        monkeypatch.setattr(ts, "concat_audio", fake_concat)

        html, meta = ts.build_typed_composition(
            "fake-cards", SCRIPT, {})

        assert meta["voice_mode"] == "tts"
        assert meta["voice_path"] == (f"audio/{meta['plan_slug']}/"
                                      f"{meta['plan_slug']}.voice.mp3")
        assert len(concated["paths"]) == 4
        assert concated["out"].parent.name == meta["plan_slug"]
        # 段时长和 21.5s + tailPad 0.5s
        assert meta["duration_s"] == 22.0
        assert 'data-duration="22"' in html
        assert 'data-duration="21.5"' in html  # 旁白整轨
        assert 'src="assets/voice.mp3"' in html
        assert meta["assets"] == [{
            "role": "voice", "path": "assets/voice.mp3",
            "source": meta["voice_path"]}]
        assert meta["billing"]["mode"] == "tts"
        assert len(meta["billing"]["tts_segments"]) == 4
        assert meta["billing"]["tts_segments"][0]["chars"] == 14
        assert meta["billing"]["chars"] == 43

    def test_structure_validation_blocks_tts(self, hermetic_fs, fake_types,
                                             register, monkeypatch):
        _write_type(fake_types, "fake-cards")
        register(_FakeCompositionBuilder())
        calls = []
        monkeypatch.setattr(
            "mcp_server.generators.tts.synthesize",
            lambda *a, **kw: calls.append(1) or {"file_path": "x", "duration_ms": 1})
        with pytest.raises(ValueError, match="结构数对照失败"):
            ts.build_typed_composition(
                "fake-cards", SCRIPT, {"fail_structure": True})
        assert calls == []


# ─── BGM 轨 ────────────────────────────────────────────────────────────────

class TestBgmTrack:
    def test_bgm_separate_track_with_volume_and_fade(self, hermetic_fs,
                                                     fake_types, register,
                                                     monkeypatch):
        _write_type(fake_types, "fake-cards")
        register(_FakeCompositionBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        bgm_file = hermetic_fs["downloads"] / "track.mp3"
        bgm_file.write_bytes(b"fake-bgm")

        html, meta = ts.build_typed_composition(
            "fake-cards", SCRIPT, {}, voice_path=str(wav),
            bgm={"path": str(bgm_file), "volume": 0.15})

        assert ('<audio id="hf-audio-3-0" data-start="0" data-duration="8.5" '
                'data-track-index="3" src="assets/bgm.mp3" '
                'volume="0.15">') in html
        # fade_out 默认 True → 音量包络窗口 3s
        assert '"id": "hf-audio-3-0"' in html
        assert '"fade": 3.0' in html
        assert meta["bgm"]["volume"] == 0.15
        assert meta["bgm"]["fade_out"] is True
        assert meta["bgm"]["ref"] == f"path:{bgm_file}"
        assert [a["role"] for a in meta["assets"]] == ["voice", "bgm"]
        assert meta["assets"][1]["path"] == "assets/bgm.mp3"
        assert meta["assets"][1]["source"] == str(bgm_file)

    def test_pre_resolved_bgm_passes_through(self, hermetic_fs, fake_types,
                                             register, monkeypatch):
        _write_type(fake_types, "fake-cards")
        register(_FakeCompositionBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        bgm_file = hermetic_fs["downloads"] / "resolved.m4a"
        bgm_file.write_bytes(b"x")
        _, meta = ts.build_typed_composition(
            "fake-cards", SCRIPT, {}, voice_path=str(wav),
            bgm={"file": str(bgm_file), "volume": 0.4, "fade_out": False,
                 "asset_id": "bgm-1", "path": None})
        assert meta["bgm"]["ref"] == "asset:bgm-1"
        assert meta["bgm"]["fade_out"] is False


# ─── 片段契约与计划键 ──────────────────────────────────────────────────────

class TestClipContract:
    def test_missing_duration_named(self, fake_types, register, hermetic_fs,
                                    monkeypatch):
        _write_type(fake_types, "broken-cards")
        register(_BrokenClipBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        with pytest.raises(ValueError) as exc:
            ts.build_typed_composition(
                "broken-cards", SCRIPT, {}, voice_path=str(wav))
        msg = str(exc.value)
        assert "broken-cards.build_composition visual[0]" in msg
        assert "duration" in msg

    def test_non_dict_return_named(self, fake_types, register, hermetic_fs,
                                   monkeypatch):
        _write_type(fake_types, "notdict-cards")
        register(_NotDictBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)
        with pytest.raises(ValueError, match="必须返回"):
            ts.build_typed_composition(
                "notdict-cards", SCRIPT, {}, voice_path=str(wav))


class TestPlanSlug:
    def test_same_input_same_slug_and_bgm_changes_it(self, hermetic_fs,
                                                     fake_types, register,
                                                     monkeypatch):
        _write_type(fake_types, "fake-cards")
        register(_FakeCompositionBuilder())
        wav = _voice_path(hermetic_fs, monkeypatch)

        _, meta1 = ts.build_typed_composition(
            "fake-cards", SCRIPT, {}, voice_path=str(wav))
        _, meta2 = ts.build_typed_composition(
            "fake-cards", SCRIPT, {}, voice_path=str(wav))
        assert meta1["plan_slug"] == meta2["plan_slug"]

        bgm_file = hermetic_fs["downloads"] / "t.mp3"
        bgm_file.write_bytes(b"x")
        _, meta3 = ts.build_typed_composition(
            "fake-cards", SCRIPT, {}, voice_path=str(wav),
            bgm={"path": str(bgm_file)})
        assert meta3["plan_slug"] != meta1["plan_slug"]

        _, meta4 = ts.build_typed_composition(
            "fake-cards", SCRIPT, {"orientation": "1920x1080"},
            voice_path=str(wav))
        assert meta4["plan_slug"] != meta1["plan_slug"]  # inputs 折入

    def test_missing_script_named(self):
        with pytest.raises(ValueError, match="requires script"):
            ts.build_typed_composition("fake-cards", "", {})

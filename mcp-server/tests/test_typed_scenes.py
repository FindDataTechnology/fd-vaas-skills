"""
add-typed-video-html-renderer W1/W3 脊柱测试。

覆盖:
  - split_script 分段（## 段名 / 无段名单段 / 空稿）与句子切分、比例分摊
  - 对齐：align_voice_path（ffprobe mock，字符数加权，不发起 TTS）/
    align_tts（mock synthesize，idempotency_key 派生、实测时长、句表）
  - news-flash builder：validate_inputs 结构数对照（一次列全）、场景结构断言
    （标题卡/要点卡×N/CTA、句级字幕 data 岛、seek 契约、品牌 CSS wrapper、
    零外链、meta.source 署名位、palette 槽位）
  - build_typed_storyboard：type.json 三道 gate（未注册 type 列清单 /
    renderer 必须 html / 未注册 builder 列清单）、tailPad 帧垫、计划键稳定、
    TTS 全轨拼接与 voice_path 两口径的 meta 计费面
  - 补图 confirm 协议（公共层）：pending_images 返回零产物 / confirm 先补图
    （清单入账）再渲染
  - render_video type 模式重接：builder → compose_storyboard 同一实现路径
    （mock 帧/ffmpeg/ffprobe 的本地全链）、计划级重放免费、bgm 复用混流链、
    hosted 行为一致（ADR-0004 carve-out 已移除）

playwright / ffmpeg / TTS / generate_image 全部 mock（真渲染冒烟由
test_determinism 同款探针与本 change 的手工冒烟兜底）。
"""

import json
import subprocess as _subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import init_schema, get_asset_by_slug, usage_summary
from mcp_server.tools import render as render_mod
from mcp_server.tools import typed_scenes as ts
from mcp_server.tools.typed_scenes import alignment as align_mod
from mcp_server.tools.typed_scenes.builders import news_flash as nf_mod
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

    # W4：视频渲染已委托渲染面——用确定性假实现替换 HTTP 调用
    from mcp_server.tools import render_client

    renderer.submits = []

    def _fake_submit(html, assets=None, fps=30, quality="looks",
                     format="mp4", job_id="", base_url=None, timeout=None):
        rec = {"html": html, "assets": list(assets or []), "fps": fps,
               "job_id": job_id, "format": format, "quality": quality}
        renderer.submits.append(rec)
        _fake_submit.last = rec
        return b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64, \
               {"x-engine": "hyperframes@0.9.26"}

    monkeypatch.setattr(render_client, "submit_render", _fake_submit)
    return renderer


SCRIPT = ("## 开场\n大家好，今天是三条行业热点。\n"
          "## 要点一\n第一点！数据很关键。\n"
          "## 要点二\n第二点，值得关注。\n"
          "## 结尾\n关注我们，下期再见。")
META = {"headline": "今日热点速览", "points": ["要点一的内容", "要点二的内容"],
        "source": "FindData"}


def _aligned_segments(raw, durations):
    out = []
    for seg, d in zip(raw, durations):
        out.append({"name": seg["name"], "text": seg["text"],
                    "duration_s": d,
                    "sentences": align_mod._sentences_with_timings(
                        seg["text"], d)})
    return out


# ─── 分段与句子切分 ─────────────────────────────────────────────────────────

class TestSplitScript:
    def test_section_headings_split(self):
        raw = align_mod.split_script(SCRIPT)
        assert [s["name"] for s in raw] == ["开场", "要点一", "要点二", "结尾"]
        assert raw[1]["text"] == "第一点！数据很关键。"

    def test_no_heading_single_segment(self):
        raw = align_mod.split_script("整篇没有分段标记的口播稿。")
        assert len(raw) == 1 and raw[0]["name"] == "main"
        assert "口播稿" in raw[0]["text"]

    def test_empty_script_rejected(self):
        with pytest.raises(ValueError, match="script is empty"):
            align_mod.split_script("   \n  ")
        with pytest.raises(ValueError, match="分段结果为空"):
            align_mod.split_script("## 只有标题")

    def test_leading_text_before_first_heading(self):
        raw = align_mod.split_script("开头白。\n## 段一\n正文。")
        assert [s["name"] for s in raw] == ["main", "段一"]


class TestSentences:
    def test_sentence_boundaries(self):
        parts = align_mod.split_sentences("第一句。第二句！第三句？\n第四句\n还有一行")
        assert parts == ["第一句。", "第二句！", "第三句？", "第四句", "还有一行"]

    def test_weighting_sums_to_segment_duration(self):
        sents = align_mod._sentences_with_timings("短句。这是一个长很多很多的长句！", 3.0)
        assert abs(sum(s["end"] - s["start"] for s in sents) - 3.0) < 1e-6
        # 字符多的句占比更大
        assert sents[1]["end"] - sents[1]["start"] > sents[0]["end"] - sents[0]["start"]
        assert sents[0]["start"] == 0.0 and sents[-1]["end"] == pytest.approx(3.0)

    def test_contiguous_starts(self):
        sents = align_mod._sentences_with_timings("一。二。三。四。五。", 5.0)
        for a, b in zip(sents, sents[1:]):
            assert b["start"] == pytest.approx(a["end"])


# ─── 对齐：voice_path / TTS ─────────────────────────────────────────────────

class TestAlignVoicePath:
    def test_char_weighted_allocation_no_tts(self, tmp_path, monkeypatch):
        wav = tmp_path / "voice.wav"
        wav.write_bytes(b"fake-audio")
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 10.0)
        raw = align_mod.split_script(SCRIPT)
        segs = align_mod.align_voice_path(str(wav), raw)
        assert [s["name"] for s in segs] == ["开场", "要点一", "要点二", "结尾"]
        assert abs(sum(s["duration_s"] for s in segs) - 10.0) < 1e-6
        # 文本最长的段分到最多时长（开场 14 字 > 其余段）
        longest = max(range(len(segs)), key=lambda i: len(segs[i]["text"]))
        assert segs[longest]["duration_s"] == max(s["duration_s"] for s in segs)
        assert segs[0]["duration_s"] > segs[2]["duration_s"]
        # 句表齐全（句级字幕的数据面）
        assert all(s["sentences"] for s in segs)

    def test_missing_voice_named_in_error(self, tmp_path):
        with pytest.raises(ValueError, match="voice file missing"):
            align_mod.align_voice_path(str(tmp_path / "nope.wav"),
                                       align_mod.split_script(SCRIPT))

    def test_unmeasurable_duration_raises(self, tmp_path, monkeypatch):
        wav = tmp_path / "voice.wav"
        wav.write_bytes(b"fake-audio")
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: None)
        with pytest.raises(RuntimeError, match="cannot measure voice duration"):
            align_mod.align_voice_path(str(wav), align_mod.split_script(SCRIPT))


class TestAlignTts:
    def test_per_segment_synthesize_with_idem_keys(self, monkeypatch):
        calls = []

        def fake_synthesize(text, voice=None, speed=None, format="mp3",
                            idempotency_key=None):
            calls.append({"text": text, "idem": idempotency_key, "format": format})
            return {"file_path": f"audio/seg-{len(calls)}.mp3",
                    "duration_ms": 1000 * len(text)}

        monkeypatch.setattr("mcp_server.generators.tts.synthesize", fake_synthesize)
        raw = align_mod.split_script(SCRIPT)
        segs = align_mod.align_tts(raw, idem_base="typed-abc123")

        assert len(calls) == 4
        assert calls[0]["idem"] == "typed-abc123-seg0"
        assert calls[3]["idem"] == "typed-abc123-seg3"
        assert [s["duration_s"] for s in segs] == [14.0, 10.0, 9.0, 10.0]
        assert segs[0]["audio_path"] == "audio/seg-1.mp3"
        assert all(s["sentences"] for s in segs)


# ─── news-flash builder ────────────────────────────────────────────────────

class TestNewsFlashValidate:
    def setup_method(self):
        self.builder = ts.BUILDER_REGISTRY["news-flash"]
        self.raw = align_mod.split_script(SCRIPT)

    def test_valid_structure_passes(self):
        self.builder.validate_inputs(
            {"meta": META}, align_mod.skeleton_segments(self.raw))

    def test_points_dict_form_accepted(self):
        self.builder.validate_inputs(
            {"meta": {"headline": "H", "points": [{"text": "a"}, {"text": "b"}]}},
            align_mod.skeleton_segments(self.raw))

    def test_count_mismatch_lists_everything(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"meta": {"headline": "H", "points": ["只有一条"]}},
                align_mod.skeleton_segments(self.raw))
        msg = str(exc.value)
        assert "口播要点段数 2" in msg and "meta.points 数 1" in msg
        assert "hook" in msg and "cta" in msg  # 对照面点名

    def test_all_violations_listed_at_once(self):
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"meta": {"points": ["ok", 123]}},
                align_mod.skeleton_segments([self.raw[0]]))
        msg = str(exc.value)
        assert "meta.headline" in msg
        assert "meta.points[1]" in msg
        assert "1 hook + N 要点 + 1 cta" in msg  # 无段名/段数不足指路


class TestNewsFlashBuild:
    @pytest.fixture
    def built(self):
        builder = ts.BUILDER_REGISTRY["news-flash"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [2.0, 3.0, 2.5, 2.0])
        theme = ts.load_theme()
        return builder.build(segs, {"meta": META}, [1080, 1920], theme), segs

    def test_scene_structure(self, built):
        scenes, segs = built
        assert len(scenes) == 4
        assert [s["kind"] for s in scenes] == ["html_full"] * 4
        assert [s["name"] for s in scenes] == [g["name"] for g in segs]
        assert [s["duration_s"] for s in scenes] == [2.0, 3.0, 2.5, 2.0]

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
        # 颜色取 theme，不硬编码色值（gradient 全部走变量）
        assert "#070a20" not in html

    def test_sentence_subtitle_data_island(self, built):
        scenes, segs = built
        # 要点卡：句级字幕表进 data 岛，seek 查表驱动
        point_html = scenes[1]["html"]
        sents = segs[1]["sentences"]
        assert json.dumps(sents[0]["text"], ensure_ascii=False) in point_html
        assert "SENTS[i].start" in point_html
        # 标题卡无句表（headline 驱动）
        assert "__DURATION__=2.0" in scenes[0]["html"]
        assert "__DURATION__=3.0" in point_html

    def test_source_attribution_and_palette(self, built):
        scenes, _ = built
        # 署名位：source 进 data 岛（紧凑 JSON）+ seek 期 textContent('来源：' + source)
        assert '"source":"FindData"' in scenes[0]["html"]  # 标题卡 data 岛
        assert "'来源：' + DATA.source" in scenes[0]["html"]
        assert '"source":"FindData"' in scenes[3]["html"]  # CTA 署名位
        assert scenes[1]["html"].count("来源：") == 0  # 要点卡不重复署名
        assert scenes[1]["html"].count('"source"') == 0
        assert "color:#58a6ff" in scenes[1]["html"]  # palette[0] 槽位上色
        assert "color:#3fb950" in scenes[2]["html"]  # palette[1]

    def test_cta_reveals_sentences_stepwise(self, built):
        scenes, segs = built
        cta = scenes[3]["html"]
        assert cta.count('class="line"') == len(segs[3]["sentences"])
        assert "DATA.sentences[i].start" in cta


# ─── build_typed_storyboard：gate / 计划键 / tailPad / meta ─────────────────

class TestBuildTypedStoryboard:
    def test_unknown_type_lists_registry(self):
        with pytest.raises(ValueError, match="unknown video type: nope"):
            ts.build_typed_storyboard("nope", script="x", inputs={})

    def test_non_html_renderer_rejected(self):
        # screen-recording 未声明 renderer: html（card 族 W2.1/W2.2 已全部
        # 接入 html renderer，未接入类型剩 screen-recording/voiceover）
        with pytest.raises(ValueError, match="not an html-renderer type"):
            ts.build_typed_storyboard("screen-recording", script="## a\nb",
                                      inputs={})

    def test_unregistered_builder_lists_available(self, monkeypatch):
        monkeypatch.setattr(ts, "BUILDER_REGISTRY", {})
        with pytest.raises(ValueError) as exc:
            ts.build_typed_storyboard("news-flash", script="## a\nb", inputs={})
        assert "Available builders" in str(exc.value)

    def test_voice_path_mode_end_to_end(self, hermetic_fs, monkeypatch):
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        storyboard, meta = ts.build_typed_storyboard(
            "news-flash", SCRIPT, {"meta": META}, voice_path=str(wav))
        assert storyboard["size"] == [1080, 1920]
        assert len(storyboard["scenes"]) == 4
        assert storyboard["voice_path"] == str(wav)  # voice_path 优先
        assert meta["voice_mode"] == "voice_path"
        assert meta["plan_slug"].startswith("typed-")
        assert meta["billing"]["mode"] == "voice_path"
        assert meta["billing"]["tts_segments"] is None
        assert len(meta["segments"]) == 4
        # tailPad 帧垫（type.json defaults.tailPad=15 @30fps）：末段字符权重
        # 分摊（8.0*10/43，4 位舍入）+ 0.5s
        assert meta["tail_pad_frames"] == 15
        assert storyboard["scenes"][-1]["duration_s"] == pytest.approx(
            8.0 * 10 / 43 + 0.5, abs=1e-3)

    def test_tts_mode_concat_full_track(self, hermetic_fs, monkeypatch):
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
        storyboard, meta = ts.build_typed_storyboard(
            "news-flash", SCRIPT, {"meta": META})
        assert meta["voice_mode"] == "tts"
        assert meta["voice_path"] == f"audio/{meta['plan_slug']}/{meta['plan_slug']}.voice.mp3"
        assert storyboard["voice_path"] == meta["voice_path"]
        assert len(concated["paths"]) == 4
        assert concated["out"].parent.name == meta["plan_slug"]
        assert meta["billing"]["mode"] == "tts"
        assert meta["billing"]["tts_segments"][0]["chars"] > 0

    def test_plan_slug_folds_all_inputs(self, hermetic_fs, monkeypatch):
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        _, meta1 = ts.build_typed_storyboard(
            "news-flash", SCRIPT, {"meta": META}, voice_path=str(wav))
        _, meta2 = ts.build_typed_storyboard(
            "news-flash", SCRIPT, {"meta": META}, voice_path=str(wav))
        assert meta1["plan_slug"] == meta2["plan_slug"]  # 同输入同键
        _, meta3 = ts.build_typed_storyboard(
            "news-flash", SCRIPT, {"meta": META}, voice_path=str(wav),
            bgm={"path": "/x.mp3"})
        assert meta3["plan_slug"] != meta1["plan_slug"]  # bgm 折入
        _, meta4 = ts.build_typed_storyboard(
            "news-flash", SCRIPT, {"meta": {**META, "headline": "另一些"}},
            voice_path=str(wav))
        assert meta4["plan_slug"] != meta1["plan_slug"]  # inputs 折入

    def test_orientation_landscape(self, hermetic_fs, monkeypatch):
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        storyboard, _ = ts.build_typed_storyboard(
            "news-flash", SCRIPT, {"meta": META, "orientation": "1920x1080"},
            voice_path=str(wav))
        assert storyboard["size"] == [1920, 1080]
        assert "__SIZE__=[1920,1080]" in storyboard["scenes"][0]["html"]

    def test_bad_orientation_lists_allowed(self, hermetic_fs, monkeypatch):
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        with pytest.raises(ValueError, match="orientation must be one of"):
            ts.build_typed_storyboard(
                "news-flash", SCRIPT, {"meta": META, "orientation": "400x400"},
                voice_path=str(wav))


# ─── 补图 confirm 协议（公共层） ────────────────────────────────────────────

class TestPendingImagesProtocol:
    def test_prompt_entries_detected(self, tmp_path):
        img = tmp_path / "ready.png"
        img.write_bytes(b"png")
        inputs = {"images": [
            {"prompt": "城市夜景 数据大屏"},
            {"path": str(img)},
            str(img),
            " street photo ",  # 无 generate 开关：不视为待补
            "",
        ]}
        pending = ts.collect_pending_images(inputs)
        assert pending == [{"index": 0, "prompt": "城市夜景 数据大屏"}]

    def test_plain_string_becomes_prompt_with_generate_flag(self, tmp_path):
        missing = "a photo of charts"
        inputs = {"images": [missing], "generate": "true"}
        pending = ts.collect_pending_images(inputs)
        assert pending == [{"index": 0, "prompt": missing}]
        assert ts.collect_pending_images({"images": [missing], "generate": False}) == []

    def test_resolve_backfills_generated_paths(self, tmp_path, monkeypatch):
        generated_calls = []

        def fake_generate_image(prompt, size=None):
            generated_calls.append({"prompt": prompt, "size": size})
            return {"id": f"img-{len(generated_calls)}",
                    "file_paths": [f"images/gen-{len(generated_calls)}/a.jpeg"]}

        monkeypatch.setattr("mcp_server.tools.generate.generate_image",
                            fake_generate_image)
        inputs = {"images": [{"prompt": "p1"}, {"prompt": "p2", "size": "2K"}],
                  "confirm_images": True}
        out, generated = ts.resolve_pending_images(inputs)
        assert len(generated_calls) == 2
        assert generated_calls[1]["size"] == "2K"
        assert out["images"] == ["images/gen-1/a.jpeg", "images/gen-2/a.jpeg"]
        assert generated[0]["asset_id"] == "img-1"
        # 无待补项时不发起任何生成
        out2, generated2 = ts.resolve_pending_images(
            {"images": ["ready.png"]}, owner="service")
        assert generated2 == [] and out2["images"] == ["ready.png"]


# ─── render_video type 模式重接（本地 mock 全链） ───────────────────────────

class TestRenderVideoTypedMode:
    @pytest.fixture
    def voice_wav(self, hermetic_fs):
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        return str(wav)

    @pytest.fixture(autouse=True)
    def probe_voice(self, monkeypatch):
        # ffprobe mock：voice 对齐与成片时长探测共用
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)

    def test_full_chain_through_compose(self, hermetic_fs, fake_render_pipeline,
                                        voice_wav):
        result = render_mod.render_video(
            type="news-flash", script=SCRIPT, inputs={"meta": META},
            voice_path=voice_wav, slug="nf-full")
        assert result["type"] == "news-flash"
        assert result["slug"] == "nf-full"
        assert result["format"] == "mp4"
        # W4：提交一次 composition 到渲染面（不再是逐帧本地渲染）
        assert len(fake_render_pipeline.submits) == 1
        comp = fake_render_pipeline.submits[0]["html"]
        assert comp.count('class="clip"') == 4
        assert "window.__timelines['main'] = TL;" in comp
        # 账本：metadata.typed 带 segments 对齐表与计费口径
        asset = get_asset_by_slug("nf-full")
        assert asset and asset["type"] == "video"
        typed = asset["metadata"]["typed"]
        assert typed["type"] == "news-flash"
        assert typed["renderer"] in ("html", "hyperframes")
        assert asset["metadata"]["engine"].startswith("hyperframes@")
        assert [s["name"] for s in typed["segments"]] == ["开场", "要点一", "要点二", "结尾"]
        assert typed["billing"]["mode"] == "voice_path"
        assert typed["tail_pad_frames"] == 15
        rows = usage_summary(owner="service")
        assert any(r["tool"] == "render_video" and r["unit_type"] == "second"
                   for r in rows)

    def test_plan_slug_replay_is_free(self, hermetic_fs, fake_render_pipeline,
                                      voice_wav):
        first = render_mod.render_video(
            type="news-flash", script=SCRIPT, inputs={"meta": META},
            voice_path=voice_wav)
        assert first["slug"].startswith("typed-")
        n_calls = len(fake_render_pipeline.calls)
        second = render_mod.render_video(
            type="news-flash", script=SCRIPT, inputs={"meta": META},
            voice_path=voice_wav)
        assert second["idempotent_replay"] is True
        assert second["id"] == first["id"]
        assert len(fake_render_pipeline.calls) == n_calls  # 不重渲染
        # 计划键折入 voice_path：换音轨 → 新键重渲
        other = hermetic_fs["downloads"] / "voice2.wav"
        other.write_bytes(b"fake-audio-2")
        third = render_mod.render_video(
            type="news-flash", script=SCRIPT, inputs={"meta": META},
            voice_path=str(other))
        assert third["slug"] != first["slug"]
        assert "idempotent_replay" not in third

    def test_explicit_slug_wins_over_plan_hash(self, hermetic_fs,
                                               fake_render_pipeline, voice_wav):
        result = render_mod.render_video(
            type="news-flash", script=SCRIPT, inputs={"meta": META},
            voice_path=voice_wav, slug="my-nf")
        assert result["slug"] == "my-nf"

    def test_bgm_wired_for_type_mode(self, hermetic_fs, fake_render_pipeline,
                                     voice_wav):
        """W4：BGM 作为 composition 音频轨随作业上传（不再成片后混流）。"""
        bgm_file = hermetic_fs["downloads"] / "bgm.mp3"
        bgm_file.write_bytes(b"fake-bgm")
        result = render_mod.render_video(
            type="news-flash", script=SCRIPT, inputs={"meta": META},
            voice_path=voice_wav, bgm={"path": str(bgm_file), "volume": 0.3})
        assert result["type"] == "news-flash"
        sub = fake_render_pipeline.submits[0]
        paths = [p for p, _ in sub["assets"]]
        assert any(p.startswith("assets/bgm") for p in paths), paths
        asset = get_asset_by_slug(result["slug"])
        assert asset["metadata"]["bgm"]["volume"] == 0.3

    def test_confirm_protocol_blocks_render_until_confirmed(
            self, hermetic_fs, fake_render_pipeline, voice_wav, monkeypatch):
        gen_calls = []
        ready = hermetic_fs["downloads"] / "ready.png"
        ready.write_bytes(b"png")

        def fake_generate_image(prompt, size=None):
            gen_calls.append(prompt)
            return {"id": "img-1", "file_paths": ["images/gen/a.jpeg"]}

        monkeypatch.setattr("mcp_server.tools.generate.generate_image",
                            fake_generate_image)
        inputs = {"meta": META,
                  "images": [{"prompt": "图表插画"}, str(ready)],
                  "generate": True}

        pending = render_mod.render_video(
            type="news-flash", script=SCRIPT, inputs=inputs,
            voice_path=voice_wav)
        assert pending["pending_images"] == [
            {"index": 0, "prompt": "图表插画"}]
        assert "confirm_images" in pending["message"]
        assert gen_calls == []  # 未确认：不补图
        assert fake_render_pipeline.calls == []  # 未确认：不渲染（零产物）

        confirmed = render_mod.render_video(
            type="news-flash", script=SCRIPT,
            inputs={**inputs, "confirm_images": True}, voice_path=voice_wav)
        assert gen_calls == ["图表插画"]  # 先补图（清单入账）
        assert confirmed["type"] == "news-flash"
        asset = get_asset_by_slug(confirmed["slug"])
        typed = asset["metadata"]["typed"]
        assert typed["generated_images"][0]["file_path"] == "images/gen/a.jpeg"
        assert typed["generated_images"][0]["asset_id"] == "img-1"

    def test_hosted_behaves_like_local(self, hermetic_fs, fake_render_pipeline,
                                       voice_wav, monkeypatch):
        """ADR-0004 carve-out 已移除：hosted 面 type 模式照常出片 + 签名 URL。"""
        monkeypatch.setattr(render_mod, "is_hosted", lambda: True)
        monkeypatch.setattr(render_mod, "download_url",
                            lambda asset_id, owner: f"https://cdn/{asset_id}")
        result = render_mod.render_video(
            type="news-flash", script=SCRIPT, inputs={"meta": META},
            voice_path=voice_wav)
        assert result["type"] == "news-flash"
        assert result["download_url"].startswith("https://cdn/")

    def test_unknown_type_and_missing_script(self, voice_wav):
        with pytest.raises(ValueError, match="unknown video type: nope"):
            render_mod.render_video(type="nope", script="文本")
        with pytest.raises(ValueError, match="requires script"):
            render_mod.render_video(type="news-flash", inputs={"meta": META})

    def test_builder_contract_surface(self):
        """契约面稳定：validate_inputs/build 签名 + registry 键。"""
        builder = ts.BUILDER_REGISTRY["news-flash"]
        assert builder.type_id == "news-flash"
        import inspect
        vp = list(inspect.signature(builder.validate_inputs).parameters)
        bp = list(inspect.signature(builder.build).parameters)
        assert vp == ["inputs", "segments"]
        assert bp == ["segments", "inputs", "size", "theme"]

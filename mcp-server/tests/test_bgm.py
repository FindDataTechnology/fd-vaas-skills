"""
Wave4 (add-presentation-plane) BGM unit tests.

覆盖 W4.1–W4.3：
  - bgm 参数解析（normalize_bgm：默认值 / 互斥 / 未知键 / 音量边界）
  - 混流命令构造（render_video storyboard 与 voiceover_assemble，ffmpeg mock：
    -stream_loop 补长、amix、-t covered_s 收尾、afade 出、-c:v copy）
  - bgm asset_id 跨租户引用拒绝 + 种子曲库全局可见
  - 种子曲库幂等注册（ensure_bgm_library）+ 随包 licenses.json 完整性

playwright / ffmpeg / TTS 全部 mock（真实混流冒烟由部署探针兜底）。
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
import mcp_server.utils as utils_pkg
import mcp_server.generators.voiceover as voiceover_mod
from mcp_server.db import (init_schema, insert_asset, get_asset,
                           get_asset_by_slug, list_assets, get_connection)
from mcp_server.tools import render as render_mod
from mcp_server.tools import generate as gen_mod


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
    """Redirect downloads/ writes and VAAS_ROOT resolution to tmp_path."""
    downloads = tmp_path / "downloads"
    monkeypatch.setattr(utils_pkg, "VAAS_ROOT", tmp_path)
    monkeypatch.setattr(render_mod, "VAAS_ROOT", tmp_path)
    monkeypatch.setattr(voiceover_mod, "VAAS_ROOT", tmp_path)
    monkeypatch.setattr(render_mod, "ensure_directory",
                        lambda type, slug: _mkdir(downloads / type / slug))
    monkeypatch.setattr(render_mod, "ensure_directory_rel",
                        lambda *parts: _mkdir(downloads.joinpath(*parts)))
    return {"downloads": downloads}


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def bgm_seed_dir(tmp_path, monkeypatch):
    """随包曲库替身：两支假 mp3 + licenses.json（第三条文件缺失应被跳过）。"""
    tdir = _mkdir(tmp_path / "templates" / "bgm")
    (tdir / "alpha.mp3").write_bytes(b"fake-mp3-alpha")
    (tdir / "beta.mp3").write_bytes(b"fake-mp3-beta")
    (tdir / "licenses.json").write_text(json.dumps({"tracks": [
        {"file": "alpha.mp3", "title": "Alpha", "duration_seconds": 15.9,
         "artist": "A", "source": "https://example.com/alpha.mp3",
         "license": "CC-BY-4.0",
         "license_url": "https://creativecommons.org/licenses/by/4.0/",
         "attribution": "Alpha by A"},
        {"file": "beta.mp3", "title": "Beta", "duration_seconds": 36.2,
         "artist": "B", "source": "https://example.com/beta.mp3",
         "license": "CC0", "attribution": "Beta by B"},
        {"file": "missing.mp3", "title": "Ghost", "duration_seconds": 1.0,
         "source": "https://example.com/missing.mp3", "license": "X"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(render_mod, "BGM_TEMPLATE_DIR", tdir)
    return tdir


class _FakeProc:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def _fake_frames(frames_per_scene: int = 2):
    calls = []

    def _render(html, duration_s, size, out_dir, fps, start_index=0):
        produced = []
        for i in range(frames_per_scene):
            f = out_dir / f"frame_{start_index + i:05d}.png"
            f.write_bytes(b"\x89PNG-fake")
            produced.append(f)
        calls.append({"start_index": start_index})
        return produced

    _render.calls = calls
    return _render


@pytest.fixture
def fake_video_pipeline(monkeypatch, hermetic_fs):
    """逐帧渲染 + 首道 ffmpeg mock；subprocess.run 按命令形态分派（ffprobe/mix）。"""
    renderer = _fake_frames()
    monkeypatch.setattr(render_mod, "_render_html_frames", renderer)
    monkeypatch.setattr(render_mod, "_ffmpeg",
                        lambda frames_dir, audio, out, fps: out.write_bytes(b"pre-mix-bytes"))
    state = {"mix_cmds": [], "has_audio": True, "duration": "12.0"}

    def fake_run(cmd, **kw):
        cmd = [str(c) for c in cmd]
        if cmd[0] == "ffprobe":
            if "stream=index" in cmd:
                return _FakeProc(stdout="1\n" if state["has_audio"] else "")
            return _FakeProc(stdout=state["duration"])
        # ffmpeg bgm mix：落产物文件再返回成功
        state["mix_cmds"].append(cmd)
        Path(cmd[-1]).write_bytes(b"mixed-bytes")
        return _FakeProc()

    monkeypatch.setattr(render_mod.subprocess, "run", fake_run)
    return state


@pytest.fixture
def fake_voiceover(monkeypatch, hermetic_fs, tmp_path):
    """TTS + 时长探测 + ffmpeg（assemble 与 bgm mix 共用分派器）mock。"""
    downloads = hermetic_fs["downloads"]
    monkeypatch.setattr(voiceover_mod, "ensure_directory",
                        lambda type, slug: _mkdir(downloads / type / slug))
    monkeypatch.setattr(voiceover_mod, "_probe_duration_seconds",
                        lambda path, fmt: 2.5)
    calls = {"tts": [], "ffmpeg": []}

    def fake_synthesize(**kw):
        slug = kw["slug"]
        seg_dir = _mkdir(downloads / "audio" / slug)
        f = seg_dir / f"{slug}.mp3"
        f.write_bytes(b"seg")
        calls["tts"].append(slug)
        return {"file_path": f"audio/{slug}/{slug}.mp3", "duration_ms": 2000}

    def fake_run(cmd, **kw):
        cmd = [str(c) for c in cmd]
        calls["ffmpeg"].append(cmd)
        Path(cmd[-1]).write_bytes(b"audio-bytes")
        return _FakeProc()

    monkeypatch.setattr(voiceover_mod, "synthesize", fake_synthesize)
    monkeypatch.setattr(voiceover_mod.subprocess, "run", fake_run)
    return calls


def _mix_cmds(cmds):
    """bgm 混流命令（duration=first）区别于 assemble 混流（duration=longest）。"""
    return [c for c in cmds
            if any("duration=first" in part for part in c)]


SB = {"size": [720, 1280],
      "scenes": [{"kind": "html_intro", "duration_s": 2, "title": "开场"}]}


# ─── W4.2/W4.3 参数解析 ────────────────────────────────────────────────────

class TestBgmParamParsing:
    def test_none_passthrough(self):
        assert render_mod.normalize_bgm(None) is None
        assert render_mod.resolve_bgm(None) is None

    def test_defaults(self):
        spec = render_mod.normalize_bgm({"asset_id": "a1"})
        assert spec["ref"] == {"asset_id": "a1"}
        assert spec["volume"] == 0.2
        assert spec["fade_out"] is True

    def test_custom_volume_and_fade(self):
        spec = render_mod.normalize_bgm({"path": "/x.mp3", "volume": 0.5,
                                         "fade_out": False})
        assert spec["ref"] == {"path": "/x.mp3"}
        assert spec["volume"] == 0.5 and spec["fade_out"] is False

    def test_non_dict_rejected(self):
        with pytest.raises(ValueError, match="bgm must be a dict"):
            render_mod.normalize_bgm("/x.mp3")

    def test_unknown_keys_rejected(self):
        with pytest.raises(ValueError, match="unknown keys"):
            render_mod.normalize_bgm({"asset_id": "a", "loop": True})

    def test_both_refs_rejected(self):
        with pytest.raises(ValueError, match="not both"):
            render_mod.normalize_bgm({"asset_id": "a", "path": "/x.mp3"})

    def test_no_ref_rejected(self):
        with pytest.raises(ValueError, match="requires asset_id"):
            render_mod.normalize_bgm({"volume": 0.5})

    @pytest.mark.parametrize("volume", [0, -0.5, 1.01, 2, "loud", True])
    def test_volume_bounds(self, volume):
        with pytest.raises(ValueError, match="volume"):
            render_mod.normalize_bgm({"asset_id": "a", "volume": volume})

    def test_volume_upper_bound_allowed(self):
        assert render_mod.normalize_bgm({"asset_id": "a", "volume": 1})["volume"] == 1.0

    def test_fade_out_must_be_bool(self):
        with pytest.raises(ValueError, match="fade_out"):
            render_mod.normalize_bgm({"asset_id": "a", "fade_out": "yes"})


# ─── W4.2 render_video storyboard bgm 混流 ─────────────────────────────────

class TestVideoBgmMix:
    @pytest.mark.skip(reason="W4：视频 BGM 改为 composition 音频轨（随作业上传），不再走成片后 ffmpeg 混流；_mix_bgm_onto_video 保留实现但不再被 render_video 调用")
    def test_mix_command_shape_with_voice(self, hermetic_fs, fake_video_pipeline,
                                          tmp_path):
        voice = tmp_path / "voice.mp3"
        voice.write_bytes(b"v")
        bgm = tmp_path / "loop.mp3"
        bgm.write_bytes(b"b")
        result = render_mod.render_video(
            storyboard=SB, voice_path=str(voice),
            bgm={"path": str(bgm), "volume": 0.5, "fade_out": True},
            slug="sb-bgm1")

        assert len(fake_video_pipeline["mix_cmds"]) == 1
        cmd = fake_video_pipeline["mix_cmds"][0]
        assert cmd[cmd.index("-stream_loop") + 1] == "-1"      # BGM 循环补长
        assert str(bgm) in cmd
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "volume=0.5" in fc
        assert "afade=t=out:st=9.000:d=3.000" in fc            # 12s - 3s fade
        assert "[0:a][bgm]amix=inputs=2:duration=first:normalize=0[aout]" in fc
        assert cmd[cmd.index("-t") + 1] == "12.000"            # -t covered_s 纪律
        assert cmd[cmd.index("-c:v") + 1] == "copy"            # 视频流不重编码
        assert "0:v" in cmd and "[aout]" in cmd
        # 产物 + 账本 metadata
        assert result["duration_ms"] == 12000
        asset = get_asset_by_slug("sb-bgm1")
        assert asset["metadata"]["bgm"]["ref"] == f"path:{bgm}"
        assert asset["metadata"]["bgm"]["volume"] == 0.5
        # prebgm 中间体不残留
        out_dir = hermetic_fs["downloads"] / "video" / "sb-bgm1"
        assert not list(out_dir.glob("*.prebgm.*"))

    @pytest.mark.skip(reason="W4：BGM 改为 composition 音频轨（submit 时随作业上传），"
                             "不再走成片后 ffmpeg 混流；音频轨断言见 "
                             "test_typed_scenes.py::test_bgm_wired_for_type_mode")
    def test_mix_command_without_voice_maps_bgm_only(self, hermetic_fs,
                                                     fake_video_pipeline,
                                                     tmp_path):
        fake_video_pipeline["has_audio"] = False
        bgm = tmp_path / "loop.mp3"
        bgm.write_bytes(b"b")
        render_mod.render_video(storyboard=SB, bgm={"path": str(bgm)},
                                slug="sb-bgm2")
        cmd = fake_video_pipeline["mix_cmds"][0]
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "amix" not in fc and fc.endswith("[bgm]")
        assert "[bgm]" in cmd and "[aout]" not in cmd

    @pytest.mark.skip(reason="W4：视频 BGM 改为 composition 音频轨（随作业上传），不再走成片后 ffmpeg 混流；_mix_bgm_onto_video 保留实现但不再被 render_video 调用")
    def test_fade_out_disabled_drops_afade(self, hermetic_fs,
                                           fake_video_pipeline, tmp_path):
        bgm = tmp_path / "loop.mp3"
        bgm.write_bytes(b"b")
        render_mod.render_video(storyboard=SB,
                                bgm={"path": str(bgm), "fade_out": False},
                                slug="sb-bgm3")
        fc = fake_video_pipeline["mix_cmds"][0][
            fake_video_pipeline["mix_cmds"][0].index("-filter_complex") + 1]
        assert "afade" not in fc and "volume=0.2" in fc

    @pytest.mark.skip(reason="W4：视频 BGM 改为 composition 音频轨（随作业上传），不再走成片后 ffmpeg 混流；_mix_bgm_onto_video 保留实现但不再被 render_video 调用")
    def test_fade_clamped_on_short_video(self, hermetic_fs,
                                         fake_video_pipeline, tmp_path):
        fake_video_pipeline["duration"] = "1.0"
        bgm = tmp_path / "loop.mp3"
        bgm.write_bytes(b"b")
        render_mod.render_video(storyboard=SB, bgm={"path": str(bgm)},
                                slug="sb-bgm4")
        fc = fake_video_pipeline["mix_cmds"][0][
            fake_video_pipeline["mix_cmds"][0].index("-filter_complex") + 1]
        assert "afade=t=out:st=0.000:d=1.000" in fc

    @pytest.mark.skip(reason="W4：视频 BGM 改为 composition 音频轨（随作业上传），不再走成片后 ffmpeg 混流；_mix_bgm_onto_video 保留实现但不再被 render_video 调用")
    def test_bgm_folded_into_replay_key(self, hermetic_fs, fake_video_pipeline,
                                        tmp_path):
        """同 storyboard 不同 BGM = 不同重放键；同 BGM 重跑命中重放不重混。"""
        b1 = tmp_path / "b1.mp3"
        b1.write_bytes(b"1")
        b2 = tmp_path / "b2.mp3"
        b2.write_bytes(b"2")
        r1 = render_mod.render_video(storyboard=SB, bgm={"path": str(b1)})
        r2 = render_mod.render_video(storyboard=SB, bgm={"path": str(b1)})
        assert r2["idempotent_replay"] is True
        assert r2["slug"] == r1["slug"]
        assert len(fake_video_pipeline["mix_cmds"]) == 1  # 重放未重混
        r3 = render_mod.render_video(storyboard=SB, bgm={"path": str(b2)})
        assert r3["slug"] != r1["slug"]                   # 换 BGM → 新计划
        assert len(fake_video_pipeline["mix_cmds"]) == 2

    def test_missing_bgm_path_in_one_shot_validation(self, hermetic_fs):
        with pytest.raises(ValueError) as exc:
            render_mod.render_video(storyboard=SB, bgm={"path": "/no/bgm.mp3"})
        assert "bgm path: /no/bgm.mp3" in str(exc.value)

    def test_type_mode_bgm_accepted_at_mode_gate(self):
        """add-typed-video-html-renderer W3.2：type 模式接入 bgm（与 storyboard
        同参数语义，复用 normalize_bgm/resolve_bgm/混流链）——模式级不再拒绝；
        此处只验模式 gate 放行（未注册 builder 的 type 撞的是类型 gate）。
        完整混流链覆盖见 test_typed_scenes.py::test_bgm_wired_for_type_mode。"""
        with pytest.raises(ValueError, match="html-renderer"):
            render_mod.render_video(type="screen-recording", script="口播稿",
                                    bgm={"path": "/x.mp3"})

    @pytest.mark.skip(reason="W4：视频 BGM 改为 composition 音频轨（随作业上传），不再走成片后 ffmpeg 混流；_mix_bgm_onto_video 保留实现但不再被 render_video 调用")
    def test_seed_asset_id_resolution_propagates_license(
            self, hermetic_fs, bgm_seed_dir, fake_video_pipeline):
        """asset_id 引用种子曲库：混流输入是 downloads/bgm 拷贝，授权字段入账本。"""
        seeded = render_mod.ensure_bgm_library()
        aid = next(t["id"] for t in seeded if t["slug"] == "bgm-seed-alpha")
        render_mod.render_video(storyboard=SB, bgm={"asset_id": aid},
                                slug="sb-seedbgm")
        cmd = fake_video_pipeline["mix_cmds"][0]
        assert str(hermetic_fs["downloads"] / "bgm" / "alpha.mp3") in cmd
        asset = get_asset_by_slug("sb-seedbgm")
        assert asset["metadata"]["bgm"]["ref"] == f"asset:{aid}"
        assert asset["metadata"]["bgm"]["license"] == "CC-BY-4.0"
        assert asset["metadata"]["bgm"]["attribution"] == "Alpha by A"


# ─── W4.1 bgm 资产解析与租户规则 ───────────────────────────────────────────

class TestBgmAssetResolution:
    def test_cross_tenant_ref_rejected_as_not_found(self, hermetic_fs):
        """租户 A 的 bgm 资产对租户 B 不可见 → 提示资产不存在（不泄露存在性）。"""
        f = _mkdir(hermetic_fs["downloads"] / "bgm") / "alice.mp3"
        f.write_bytes(b"x")
        aid = insert_asset(type="bgm", slug="alice-track",
                           file_path="bgm/alice.mp3", stage="rendered",
                           owner="alice")
        with pytest.raises(ValueError, match="bgm asset not found"):
            render_mod.resolve_bgm({"asset_id": aid}, owner="bob")
        with pytest.raises(ValueError, match="bgm asset not found"):
            render_mod.render_video(storyboard=SB, bgm={"asset_id": aid},
                                    slug="sb-ct")

    def test_service_seed_visible_to_every_tenant(self, hermetic_fs):
        f = _mkdir(hermetic_fs["downloads"] / "bgm") / "seed.mp3"
        f.write_bytes(b"x")
        aid = insert_asset(type="bgm", slug="bgm-seed-seed",
                           file_path="bgm/seed.mp3", stage="rendered",
                           owner="service",
                           metadata={"license": "CC0", "source": "s"})
        spec = render_mod.resolve_bgm({"asset_id": aid}, owner="tenant-b")
        assert spec["asset_id"] == aid and spec["file"].is_file()
        assert spec["license"] == "CC0"

    def test_own_non_bgm_asset_rejected(self, hermetic_fs):
        f = _mkdir(hermetic_fs["downloads"] / "audio" / "plain")
        (f / "plain.mp3").write_bytes(b"x")
        aid = insert_asset(type="audio", slug="plain-audio",
                           file_path="audio/plain/plain.mp3",
                           stage="rendered", owner="alice")
        with pytest.raises(ValueError, match="not a bgm asset"):
            render_mod.resolve_bgm({"asset_id": aid}, owner="alice")

    def test_missing_asset_file_rejected(self, hermetic_fs):
        aid = insert_asset(type="bgm", slug="ghost-bgm",
                           file_path="bgm/ghost.mp3", stage="rendered",
                           owner="service")
        with pytest.raises(ValueError, match="file missing"):
            render_mod.resolve_bgm({"asset_id": aid}, owner="service")

    def test_missing_path_rejected(self):
        with pytest.raises(ValueError, match="bgm path not found"):
            render_mod.resolve_bgm({"path": "/no/bgm.mp3"})


# ─── W4.1 种子曲库注册 ─────────────────────────────────────────────────────

class TestSeedLibrary:
    def test_seed_registers_idempotent(self, hermetic_fs, bgm_seed_dir):
        """首启注册 + 重启幂等：slug 确定性、不重复插、metadata 字段齐、文件落 downloads。"""
        first = render_mod.ensure_bgm_library()
        assert [(t["slug"], t["inserted"]) for t in first] == [
            ("bgm-seed-alpha", True), ("bgm-seed-beta", True)]
        second = render_mod.ensure_bgm_library()
        assert [t["inserted"] for t in second] == [False, False]
        assert {t["id"] for t in second} == {t["id"] for t in first}
        rows = list_assets(type="bgm")
        assert len(rows) == 2  # 缺文件的 missing.mp3 被跳过，无重复行
        row = get_asset_by_slug("bgm-seed-alpha")
        assert row["owner"] == "service" and row["type"] == "bgm"
        assert row["stage"] == "rendered"
        meta = row["metadata"]
        assert meta["duration_seconds"] == 15.9
        assert meta["license"] == "CC-BY-4.0"
        assert meta["source"] == "https://example.com/alpha.mp3"
        assert meta["attribution"] == "Alpha by A"
        # 文件复制到 downloads/bgm/ 以走签名下载
        assert (hermetic_fs["downloads"] / "bgm" / "alpha.mp3").is_file()

    def test_seed_global_but_service_rows_stay_isolated(self, hermetic_fs,
                                                        bgm_seed_dir):
        """种子 bgm 对任意租户可见；service 名下其他类型资产不豁免。"""
        seeded = render_mod.ensure_bgm_library()
        assert get_asset(seeded[0]["id"], owner="tenant-a") is not None
        other = insert_asset(type="video", slug="svc-video", owner="service",
                             stage="rendered")
        assert get_asset(other, owner="tenant-a") is None

    def test_seed_reuses_preexisting_row(self, hermetic_fs, bgm_seed_dir):
        pre = insert_asset(type="bgm", slug="bgm-seed-alpha",
                           file_path="bgm/alpha.mp3", stage="rendered",
                           owner="service")
        out = render_mod.ensure_bgm_library()
        assert {t["id"] for t in out} == {pre, *(t["id"] for t in out
                                                if t["slug"] == "bgm-seed-beta")}
        assert list_assets(type="bgm", limit=10)[0]["slug"] in (
            "bgm-seed-alpha", "bgm-seed-beta")
        assert len(list_assets(type="bgm", limit=10)) == 2

    def test_seed_without_manifest_is_noop(self, hermetic_fs, tmp_path,
                                           monkeypatch):
        monkeypatch.setattr(render_mod, "BGM_TEMPLATE_DIR",
                            _mkdir(tmp_path / "empty-bgm"))
        assert render_mod.ensure_bgm_library() == []
        assert list_assets(type="bgm") == []

    def test_packaged_library_is_licensed(self):
        """随包真曲库完整性：3–5 条、每条授权来源+时长齐、音频文件在包内。"""
        manifest = json.loads((render_mod.BGM_TEMPLATE_DIR / "licenses.json")
                              .read_text(encoding="utf-8"))
        tracks = manifest["tracks"]
        assert 3 <= len(tracks) <= 5
        for t in tracks:
            assert t.get("license"), t["file"]
            assert t.get("source"), t["file"]
            assert t.get("duration_seconds"), t["file"]
            assert t.get("attribution"), t["file"]
            assert (render_mod.BGM_TEMPLATE_DIR / t["file"]).is_file(), t["file"]


# ─── W4.3 voiceover_assemble bgm ───────────────────────────────────────────

SEG = [{"text": "第一句", "window_s": 2.5}, {"text": "第二句"}]


class TestVoiceoverBgm:
    def test_no_bgm_untouched(self, fake_voiceover):
        out = gen_mod.voiceover_assemble(segments=SEG, slug="vo-plain")
        assert "bgm" not in out
        assert _mix_cmds(fake_voiceover["ffmpeg"]) == []
        assert out["slug"] == "vo-plain"

    def test_bgm_mix_command_and_ledger(self, fake_voiceover, tmp_path):
        bgm = tmp_path / "loop.mp3"
        bgm.write_bytes(b"b")
        out = gen_mod.voiceover_assemble(
            segments=SEG, bgm={"path": str(bgm), "volume": 0.3, "fade_out": True})

        # bgm 签名折入确定性 slug
        plan_key = json.dumps(
            {"segs": SEG, "voice": None, "format": "mp3", "idem": "",
             "bgm": {"ref": f"path:{bgm}", "volume": 0.3, "fade_out": True}},
            ensure_ascii=False, sort_keys=True)
        assert out["slug"] == "assemble-" + hashlib.sha256(
            plan_key.encode()).hexdigest()[:12]

        assert len(_mix_cmds(fake_voiceover["ffmpeg"])) == 1
        cmd = _mix_cmds(fake_voiceover["ffmpeg"])[0]
        assert cmd[cmd.index("-stream_loop") + 1] == "-1"
        assert str(bgm) in cmd
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "volume=0.3" in fc and "afade=t=out" in fc
        assert "[0:a][bgm]amix=inputs=2:duration=first:normalize=0[aout]" in fc
        assert cmd[cmd.index("-t") + 1] == "2.500"     # -t covered_s 纪律
        assert cmd[cmd.index("-b:a") + 1] == "128k"    # mp3 格式沿用
        # 账本 metadata 补丁 + history + 响应 + 干声备份
        asset = get_asset_by_slug(out["slug"])
        assert asset["metadata"]["bgm"]["ref"] == f"path:{bgm}"
        hist = get_connection().execute(
            "SELECT action FROM asset_history WHERE asset_id=? "
            "AND action='bgm:mixed'", (asset["id"],)).fetchall()
        assert len(hist) == 1
        assert out["bgm"]["ref"] == f"path:{bgm}"
        voiceonly = (tmp_path / "downloads" / "audio" / out["slug"]
                     / f"{out['slug']}.voiceonly.mp3")
        assert voiceonly.is_file()
        assert (tmp_path / "downloads" / "audio" / out["slug"]
                / f"{out['slug']}.mp3").is_file()

    def test_same_bgm_replay_skips_remix(self, fake_voiceover, tmp_path):
        """幂等重放：同计划同 BGM 重跑不再 TTS、不再混流（不叠混）。"""
        bgm = tmp_path / "loop.mp3"
        bgm.write_bytes(b"b")
        r1 = gen_mod.voiceover_assemble(segments=SEG, bgm={"path": str(bgm)})
        assert len(fake_voiceover["tts"]) == 2
        n_mix = len(_mix_cmds(fake_voiceover["ffmpeg"]))
        r2 = gen_mod.voiceover_assemble(segments=SEG, bgm={"path": str(bgm)})
        assert r2["slug"] == r1["slug"]
        assert len(fake_voiceover["tts"]) == 2          # 重放不重烧 TTS
        assert len(_mix_cmds(fake_voiceover["ffmpeg"])) == n_mix
        assert r2["bgm"]["ref"] == f"path:{bgm}"

    def test_explicit_slug_bgm_change_remixes_from_voiceonly(
            self, fake_voiceover, tmp_path):
        """显式 slug + 换 BGM：从干声备份重混（不叠混旧 BGM），账本更新。"""
        b1 = tmp_path / "b1.mp3"
        b1.write_bytes(b"1")
        b2 = tmp_path / "b2.mp3"
        b2.write_bytes(b"2")
        gen_mod.voiceover_assemble(segments=SEG, slug="vo-fixed",
                                   bgm={"path": str(b1), "volume": 0.2})
        out2 = gen_mod.voiceover_assemble(segments=SEG, slug="vo-fixed",
                                          bgm={"path": str(b2), "volume": 0.4})
        assert out2["bgm"]["ref"] == f"path:{b2}"
        asset = get_asset_by_slug("vo-fixed")
        assert asset["metadata"]["bgm"]["volume"] == 0.4
        assert len(fake_voiceover["tts"]) == 2          # 重放不重烧 TTS
        mix_cmds = _mix_cmds(fake_voiceover["ffmpeg"])
        assert len(mix_cmds) == 2
        for c in mix_cmds:                              # 两次都从干声出发
            assert "voiceonly" in c[3]

    def test_voiceover_bgm_missing_path_rejected(self, fake_voiceover):
        with pytest.raises(ValueError, match="bgm path not found"):
            gen_mod.voiceover_assemble(segments=SEG,
                                       bgm={"path": "/no/bgm.mp3"})
        assert fake_voiceover["tts"] == []              # 渲染前即拒绝

    def test_voiceover_bgm_cross_tenant_rejected(self, fake_voiceover,
                                                 hermetic_fs):
        f = _mkdir(hermetic_fs["downloads"] / "bgm") / "alice.mp3"
        f.write_bytes(b"x")
        aid = insert_asset(type="bgm", slug="alice-track",
                           file_path="bgm/alice.mp3", stage="rendered",
                           owner="alice")
        with pytest.raises(ValueError, match="bgm asset not found"):
            gen_mod.voiceover_assemble(segments=SEG, bgm={"asset_id": aid})
        assert fake_voiceover["tts"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Wave1 (add-presentation-plane) render-plane unit tests.

覆盖 compose_video 移植（tools/render.py）的可单元化逻辑：
  - storyboard 解析（空场景/未知 kind/html_intro 提升/kenburns 契约）
  - 计划级重放键（scoped_asset_slug + 幂等重放 / failed 记录重建）
  - render_video 两模式互斥 + 输入文件缺失一次性列全
  - type 模式的 subprocess 契约（mock，不依赖 node）
  - render_still / render_document 分发（chart/graphic W2 起为实现内核，
    本文件只验分发；内核单测见 test_render_still.py / test_echarts_theme.py）
  - templates_list / templates_get

playwright / ffmpeg / node 全部 mock（渲染路径冒烟由部署探针兜底）。
"""

import hashlib
import json
import subprocess as _subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import init_schema, get_asset_by_slug, insert_asset, usage_summary
from mcp_server.tools import render as render_mod
from mcp_server.tools import assets as assets_mod
from mcp_server.tools.templates import templates_list, templates_get


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
    """Redirect downloads/ writes and the replay existence check to tmp_path."""
    downloads = tmp_path / "downloads"
    monkeypatch.setattr(render_mod, "VAAS_ROOT", tmp_path)
    monkeypatch.setattr(render_mod, "ensure_directory",
                        lambda type, slug: _mkdir(downloads / type / slug))
    img = _mkdir(downloads / "imgs") / "a.png"
    img.write_bytes(b"\x89PNG-fake")
    return {"downloads": downloads, "image": str(img)}


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
        calls.append({"html": html, "duration_s": duration_s, "size": tuple(size),
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


SB = {"size": [720, 1280], "scenes": [
    {"kind": "html_intro", "duration_s": 2, "title": "开场", "sub": "副题"},
    {"kind": "html_outro", "duration_s": 3, "title": "收尾"},
]}


class TestStoryboardParsing:
    def test_empty_scenes_rejected(self, hermetic_fs):
        with pytest.raises(ValueError, match="scenes must not be empty"):
            render_mod.compose_storyboard({"scenes": []}, slug="sb-empty")

    def test_unknown_scene_kind_rejected(self, hermetic_fs):
        sb = {"scenes": [{"kind": "hologram", "duration_s": 1}]}
        with pytest.raises(ValueError, match="unknown scene kind: hologram"):
            render_mod.compose_storyboard(sb, slug="sb-badkind")

    def test_html_intro_promoted_to_first_full_scene(self, hermetic_fs, fake_render_pipeline):
        """storyboard.html_intro → 前置一个 html_full 场景（seek 契约同源）。"""
        sb = {"html_intro": "<div data-stage>custom</div>", "intro_duration_s": 5,
              "scenes": [{"kind": "html_outro", "duration_s": 1, "title": "尾"}]}
        result = render_mod.compose_storyboard(sb, slug="sb-promote", format="mp4")
        assert len(fake_render_pipeline.calls) == 2
        assert result["scenes"] == 2
        assert "custom" in fake_render_pipeline.calls[0]["html"]

    def test_frame_numbering_is_continuous_across_scenes(self, hermetic_fs, fake_render_pipeline):
        """共享帧序号：第二段场景的 start_index 接在第一段之后。"""
        render_mod.compose_storyboard(SB, slug="sb-frames", format="mp4")
        starts = [c["start_index"] for c in fake_render_pipeline.calls]
        assert starts == [0, 2]  # 每个假场景产 2 帧

    def test_kenburns_images_inlined_as_data_uri(self, hermetic_fs, fake_render_pipeline):
        """kenburns 图片以 data: URI 内联（set_content 无法取 file:// 子资源）。"""
        sb = {"scenes": [{"kind": "kenburns", "duration_s": 2,
                          "images": [hermetic_fs["image"]], "caption": "注"}]}
        result = render_mod.compose_storyboard(sb, slug="sb-kb", format="mp4")
        html = fake_render_pipeline.calls[0]["html"]
        assert "data:image/png;base64," in html
        assert result["frames"] == 2

    def test_storyboard_json_kept_and_frames_dropped(self, hermetic_fs, fake_render_pipeline):
        out_dir = hermetic_fs["downloads"] / "video" / "sb-keep"
        render_mod.compose_storyboard(SB, slug="sb-keep", format="mp4")
        assert (out_dir / "storyboard.json").exists()
        assert not (out_dir / "frames").exists()
        assert (out_dir / "sb-keep.mp4").exists()

    def test_kenburns_missing_image_named_in_error(self, hermetic_fs, fake_render_pipeline):
        """kenburns 图片缺失 → 报错点名具体文件（assets_validate_paths 逻辑折入）。"""
        sb = {"scenes": [{"kind": "kenburns", "duration_s": 2,
                          "images": ["/nonexistent/a.png", "/nonexistent/b.png"]}]}
        with pytest.raises(ValueError) as exc:
            render_mod.render_video(storyboard=sb, slug="sb-missing")
        assert "/nonexistent/a.png" in str(exc.value)
        assert "/nonexistent/b.png" in str(exc.value)

    def test_voice_path_missing_named_in_error(self, hermetic_fs):
        with pytest.raises(ValueError, match="voice_path: /no/such.mp3"):
            render_mod.render_video(
                storyboard={"scenes": [{"kind": "html_intro", "duration_s": 1}]},
                voice_path="/no/such.mp3", slug="sb-voice")


class TestDeterministicSlug:
    def test_slug_derivation_is_plan_hash(self, hermetic_fs, fake_render_pipeline):
        """未给 slug 时 = compose-<sha256(plan)[:12]>，同计划同键。"""
        plan = json.dumps(SB, ensure_ascii=False, sort_keys=True)
        expected = f"compose-{hashlib.sha256(plan.encode()).hexdigest()[:12]}"
        result = render_mod.compose_storyboard(SB, format="mp4")
        assert result["slug"] == expected

    def test_same_plan_replays_idempotent(self, hermetic_fs, fake_render_pipeline):
        """计划级重放：同 storyboard 第二次调用 → idempotent_replay，不重渲染。"""
        first = render_mod.compose_storyboard(SB, format="mp4")
        calls_before = len(fake_render_pipeline.calls)
        second = render_mod.compose_storyboard(SB, format="mp4")
        assert second["idempotent_replay"] is True
        assert second["id"] == first["id"]
        assert second["slug"] == first["slug"]
        # 渲染器未被再次调用（mock 若被调用会追加 calls）
        assert len(fake_render_pipeline.calls) == calls_before

    def test_failed_replay_record_is_replaced(self, hermetic_fs, fake_render_pipeline):
        """failed/残缺记录 → 删除重建（不吞错误返回假成功）。"""
        first = render_mod.compose_storyboard(SB, format="mp4")
        from mcp_server.db import update_asset_stage, get_connection
        update_asset_stage(first["id"], "failed")
        conn = get_connection()
        rel = conn.execute("SELECT file_path FROM assets WHERE id=?",
                           (first["id"],)).fetchone()["file_path"]
        conn.close()
        (hermetic_fs["downloads"] / rel).unlink()
        second = render_mod.compose_storyboard(SB, format="mp4")
        assert "idempotent_replay" not in second
        assert second["id"] != first["id"]

    def test_scoped_asset_slug_keys(self, hermetic_fs, fake_render_pipeline):
        """重放键按 owner 命名空间隔离：service 原样、租户前缀化。"""
        from mcp_server.db import scoped_asset_slug
        assert scoped_asset_slug("abc", "service") == "abc"
        assert scoped_asset_slug("abc", None) == "abc"
        assert scoped_asset_slug("abc", "alice") == "alice--abc"
        # 本地（service）渲染落原样 slug
        local = render_mod.compose_storyboard(
            {"scenes": [{"kind": "html_intro", "duration_s": 1}]},
            slug="keycheck", format="mp4")
        assert local["slug"] == "keycheck"
        assert get_asset_by_slug("alice--keycheck") is None


class TestRenderVideoModes:
    def test_storyboard_and_type_mutually_exclusive(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            render_mod.render_video(storyboard=SB, type="carousel")

    def test_no_mode_given_rejected(self):
        with pytest.raises(ValueError, match="no mode given"):
            render_mod.render_video()

    def test_unknown_type_rejected_with_known_list(self):
        with pytest.raises(ValueError, match="unknown video type: nope"):
            render_mod.render_video(type="nope", script="文本")

    def test_type_mode_requires_script(self):
        with pytest.raises(ValueError, match="requires script"):
            render_mod.render_video(type="carousel", slug="t1")

    def test_type_mode_task_dir_must_be_fresh(self, tmp_path, monkeypatch):
        monkeypatch.setattr(render_mod, "FD_VIDEOS_DIR", tmp_path / "fd-videos")
        _mkdir(tmp_path / "fd-videos" / "stale")
        with pytest.raises(ValueError, match="task dir already exists"):
            render_mod.render_video(type="carousel", script="文本", slug="stale")

    def test_type_mode_subprocess_contract_and_ledger(self, tmp_path, monkeypatch):
        """type 模式：new-task.mjs + task-render.mjs 按序调用，cwd=remotion-app，入账本。"""
        fd = tmp_path / "fd-videos"
        monkeypatch.setattr(render_mod, "FD_VIDEOS_DIR", fd)
        monkeypatch.setattr(render_mod, "REMOTION_APP", tmp_path)
        monkeypatch.setattr(render_mod, "VIDEO_CREATOR_SCRIPTS", tmp_path / "scripts")

        cmds = []

        def fake_run(cmd, capture_output=True, text=True, check=True,
                     cwd=None, env=None):
            cmds.append((cmd, cwd, env))
            # new-task.mjs 建目录；task-render.mjs 收尾时补 task.json + 成片
            if "new-task.mjs" in str(cmd[1]):
                _mkdir(fd / "my-list")
            else:
                task_dir = fd / "my-list"
                (task_dir / "task.json").write_text(json.dumps({
                    "composition": "CarouselVideo",
                    "render": {"totalDurationSec": 42.5},
                }), encoding="utf-8")
                (task_dir / "my-list.mp4").write_bytes(b"vv")
            return _subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(render_mod.subprocess, "run", fake_run)

        result = render_mod.render_video(
            type="carousel", script="第一段\n第二段",
            inputs={"images": ["/x/a.png"], "orientation": "1080x1920"},
            slug="my-list")

        assert len(cmds) == 2
        new_task, cwd1, env1 = cmds[0]
        task_render, cwd2, env2 = cmds[1]
        assert "new-task.mjs" in new_task[1]
        assert "--type" in new_task and "carousel" in new_task
        assert "--script" in new_task
        # json inputs 以内联 JSON 传递，enum 原值传递
        assert "--images" in new_task
        inline = new_task[new_task.index("--images") + 1]
        assert json.loads(inline) == ["/x/a.png"]
        assert new_task[new_task.index("--orientation") + 1] == "1080x1920"
        assert "task-render.mjs" in task_render[1] and "--slug" in task_render
        assert cwd1 == cwd2  # 两步都在 remotion-app 下执行
        # 入账本
        assert result["status"] == "rendered" and result["type"] == "carousel"
        assert result["duration_sec"] == 42.5
        asset = get_asset_by_slug("my-list")
        assert asset and asset["type"] == "video"
        assert asset["metadata"]["composition"] == "CarouselVideo"
        rows = usage_summary(owner="service")
        assert any(r["tool"] == "render_video" and r["unit_type"] == "render" for r in rows)

    def test_type_mode_missing_output_raises_with_stdout_tail(self, tmp_path, monkeypatch):
        """管线跑完但成片缺失 → RuntimeError 带诊断（不静默成功）。"""
        monkeypatch.setattr(render_mod, "FD_VIDEOS_DIR", tmp_path / "fd-videos")
        monkeypatch.setattr(render_mod, "REMOTION_APP", tmp_path)
        monkeypatch.setattr(render_mod, "VIDEO_CREATOR_SCRIPTS", tmp_path / "scripts")
        monkeypatch.setattr(render_mod.subprocess, "run",
                            lambda cmd, **kw: _subprocess.CompletedProcess(cmd, 0, "pipeline done", ""))
        with pytest.raises(RuntimeError, match="output missing"):
            render_mod.render_video(type="listicle", script="文本", slug="ghost")


class TestRenderStillAndDocumentSkeletons:
    def test_unknown_still_kind_rejected(self):
        with pytest.raises(ValueError, match="unknown still kind: sticker"):
            render_mod.render_still(kind="sticker", spec={})

    def test_chart_dispatch_reaches_kernel(self):
        """kind=chart → still_chart.render_chart（W2 起为实现内核，规格先行校验）。"""
        with pytest.raises(ValueError, match="echarts_option"):
            render_mod.render_still(kind="chart", spec={"type": "bar", "data": {}})

    def test_graphic_dispatch_reaches_kernel(self):
        """kind=graphic → still_graphic.render_graphic（W2 起为实现内核）。"""
        with pytest.raises(ValueError, match="html"):
            render_mod.render_still(kind="graphic", spec={})

    def test_cover_dispatch_reaches_registry_driver(self, monkeypatch):
        """kind=cover 走原 generate_cover 实现（registry cover/brand）。"""
        import mcp_server.tools.generate as gen_mod
        captured = {}
        monkeypatch.setattr(gen_mod, "dispatch",
                            lambda domain, name, params: captured.update(
                                domain=domain, name=name, **params) or {"ok": True})
        out = render_mod.render_still(kind="cover", spec={"title": "标题"}, slug="cov")
        assert out == {"ok": True}
        assert captured["domain"] == "cover" and captured["name"] == "brand"
        assert captured["title"] == "标题" and captured["template"] == "brand"

    def test_cover_spec_validated(self):
        with pytest.raises(ValueError, match="requires title"):
            render_mod.render_still(kind="cover", spec={})
        with pytest.raises(ValueError, match="unknown keys"):
            render_mod.render_still(kind="cover", spec={"title": "t", "bogus": 1})

    def test_document_format_validated(self):
        with pytest.raises(ValueError, match="unknown document format: docx"):
            render_mod.render_document("# hi", format="docx")
        with pytest.raises(ValueError, match="source is required"):
            render_mod.render_document("", format="pdf")

    def test_document_template_defaults_to_default(self, monkeypatch):
        """template 未指定 → 'default' 传入内核（W3 起为实现内核，同 chart/graphic 先例）。"""
        import mcp_server.tools.doc_render as doc_mod
        captured = {}
        monkeypatch.setattr(doc_mod, "render_document",
                            lambda **kw: captured.update(kw) or {"type": "doc"})
        out = render_mod.render_document("# hi", format="longimage")
        assert out == {"type": "doc"}
        assert captured == {"source": "# hi", "format": "longimage",
                            "template": "default", "slug": None}


class TestTemplates:
    def test_list_video_domain_reads_type_registry(self):
        out = templates_list(domain="video")
        ids = [t["id"] for t in out["templates"]["video"]]
        assert {"carousel", "listicle", "data-viz", "kinetic-quote",
                "news-flash"} <= set(ids)
        assert all({"id", "name", "description", "status"} <= set(t)
                   for t in out["templates"]["video"])

    def test_list_all_domains(self):
        out = templates_list()
        assert set(out["templates"]) == {"video", "cover", "doc"}
        assert out["templates"]["cover"][0]["id"] == "brand"
        doc_ids = [t["id"] for t in out["templates"]["doc"]]
        assert "default" in doc_ids

    def test_unknown_domain_rejected(self):
        with pytest.raises(ValueError, match="unknown template domain"):
            templates_list(domain="sticker")
        with pytest.raises(ValueError, match="unknown template domain"):
            templates_get("sticker", "x")

    def test_get_doc_default_contract(self):
        got = templates_get("doc", "default")
        assert got["id"] == "default"
        assert "pdf" in got["formats"]
        assert "contract" in got

    def test_get_video_type_contract(self):
        got = templates_get("video", "carousel")
        assert got["composition"] == "CarouselVideo"
        assert "script" in got["inputs"]

    def test_get_unknown_id_rejected_with_available(self):
        with pytest.raises(ValueError, match="unknown doc template: nope"):
            templates_get("doc", "nope")


class TestAssetsGetKind:
    def test_kind_logo_scans_brand_tree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(assets_mod, "COMMON_DIR", _mkdir(tmp_path / "common"))
        monkeypatch.setattr(assets_mod, "PUBLIC_DIR", _mkdir(tmp_path / "public"))
        (tmp_path / "common" / "logo.png").write_bytes(b"l")
        (tmp_path / "common" / "notes.txt").write_text("x")
        out = assets_mod.assets_get(kind="logo")
        assert [a["name"] for a in out["assets"]] == ["logo.png"]
        common = assets_mod.assets_get(kind="common")
        assert {a["name"] for a in common["assets"]} == {"logo.png", "notes.txt"}

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError, match="unknown asset kind"):
            assets_mod.assets_get(kind="everything")

    def test_plain_lookup_untouched(self):
        insert_asset(type="image", slug="kind-normal", stage="rendered")
        out = assets_mod.assets_get(slug="kind-normal")
        assert out["slug"] == "kind-normal"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

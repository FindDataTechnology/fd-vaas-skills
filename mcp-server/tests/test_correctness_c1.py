"""
fix-hosted-generation-correctness regression tests.

Covers the tenant-visible contracts added/hardened by the change:
- text source contract (file_path reads content, mutual exclusion)
- output format whitelist (traversal refused before anything is created)
- idempotent replay in the owner-scoped slug domain (no double generate/bill)
- video job polling: transient failures never terminally fail a paid job;
  success bills measured seconds
- image surface honesty (no dead reference_image; count warnings; zero-artifact
  failure; scoped slug ledger rows)
- upstream error scrubbing/classification
- hosted download URL base from explicit config only
- pricing fail-loud + real rates
- GC containment by real path relation + no silent failure loop
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import init_schema, insert_job, get_job, record_usage


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


@pytest.fixture
def isolated_downloads(tmp_path, monkeypatch):
    import mcp_server.utils.file_manager as fm
    dl = tmp_path / "downloads"
    dl.mkdir()
    monkeypatch.setattr(fm, "DOWNLOADS_DIR", dl)
    return dl


class TestTextSourceContract:
    def _synth(self, monkeypatch, isolated_downloads, **kwargs):
        from mcp_server.generators import tts as tmod
        monkeypatch.setattr(tmod, "DOWNLOADS_DIR", isolated_downloads)
        monkeypatch.setattr(tmod, "_probe_duration_seconds", lambda p, f: 1.5)
        calls = []

        def fake_run_bridge(cmd, ctx, timeout_s=None):
            calls.append(list(cmd))
            # bridge always lands the artifact at --output; replay existence
            # checks depend on it
            Path(cmd[cmd.index("--output") + 1]).parent.mkdir(parents=True, exist_ok=True)
            Path(cmd[cmd.index("--output") + 1]).write_bytes(b"ID3fake")
            return json.dumps({"ok": True, "voice": kwargs.get("voice") or "101001",
                               "model": "tencent-tts", "api_latency_ms": 5})
        monkeypatch.setattr(tmod, "run_bridge", fake_run_bridge)
        monkeypatch.setattr(tmod, "_validate_voice", lambda p, v: v or "101001")
        return tmod, calls

    def test_file_path_content_is_synthesized(self, monkeypatch, isolated_downloads, tmp_path):
        src = tmp_path / "script.txt"
        content = "这是台词正文内容"
        src.write_text(content, encoding="utf-8")
        tmod, calls = self._synth(monkeypatch, isolated_downloads)
        result = tmod.synthesize(file_path=str(src), format="mp3")
        cmd = calls[0]
        assert cmd[cmd.index("--text") + 1] == content
        assert "--input" not in cmd
        assert str(src) not in cmd  # the path string itself never lands as text
        from mcp_server.db import usage_summary
        rows = usage_summary(owner=None)
        voice_rows = [r for r in rows if r["tool"] == "generate_voice"]
        assert voice_rows and voice_rows[0]["units"] == float(len(content))

    def test_both_sources_rejected(self, monkeypatch, isolated_downloads):
        tmod, calls = self._synth(monkeypatch, isolated_downloads)
        with pytest.raises(ValueError, match="not both"):
            tmod.synthesize(text="a", file_path="b.txt")
        assert not calls

    def test_empty_file_rejected(self, monkeypatch, isolated_downloads, tmp_path):
        src = tmp_path / "blank.txt"
        src.write_text("   \n", encoding="utf-8")
        tmod, calls = self._synth(monkeypatch, isolated_downloads)
        with pytest.raises(ValueError, match="empty"):
            tmod.synthesize(file_path=str(src))
        assert not calls

    def test_unreadable_file_reports_clearly(self, monkeypatch, isolated_downloads):
        tmod, calls = self._synth(monkeypatch, isolated_downloads)
        with pytest.raises(ValueError, match="cannot read"):
            tmod.synthesize(file_path="/nonexistent/dir/x.txt")
        assert not calls

    def test_format_traversal_refused_before_write(self, monkeypatch, isolated_downloads):
        tmod, calls = self._synth(monkeypatch, isolated_downloads)
        with pytest.raises(ValueError, match="not allowed"):
            tmod.synthesize(text="hello", format="mp3/../../../../evil")
        assert not calls
        assert not list(isolated_downloads.rglob("*evil*"))

    def test_speed_honesty_on_local_volcengine_lane(self, monkeypatch, isolated_downloads):
        # provider was literally "env" locally → false warnings + skipped
        # voice validation; must resolve TTS_PROVIDER now.
        monkeypatch.setenv("TTS_PROVIDER", "volcengine")
        tmod, calls = self._synth(monkeypatch, isolated_downloads)
        result = tmod.synthesize(text="测试台词", speed=1.2, format="mp3")
        assert result["warnings"] == []  # volcengine honors speed

    def test_speed_warning_on_ciyuan_local_lane(self, monkeypatch, isolated_downloads):
        monkeypatch.setenv("TTS_PROVIDER", "ciyuan")
        tmod, calls = self._synth(monkeypatch, isolated_downloads)
        result = tmod.synthesize(text="测试台词", speed=1.2, format="mp3")
        assert any("speed" in w for w in result["warnings"])


class TestIdempotentReplayScoped:
    def test_hosted_tenant_replay_hits_scoped_domain(self, monkeypatch, isolated_downloads):
        from mcp_server.generators import tts as tmod
        from mcp_server.generators import runtime as rt
        monkeypatch.setattr(rt, "current_owner", lambda: "tenant-a")
        monkeypatch.setattr(tmod, "DOWNLOADS_DIR", isolated_downloads)
        monkeypatch.setattr(tmod, "_probe_duration_seconds", lambda p, f: 1.0)
        monkeypatch.setattr(tmod, "_validate_voice", lambda p, v: v or "101001")
        n = {"calls": 0}

        def fake_run_bridge(cmd, ctx, timeout_s=None):
            n["calls"] += 1
            out = Path(cmd[cmd.index("--output") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"ID3fake")
            return json.dumps({"ok": True, "voice": "101001", "model": "m", "api_latency_ms": 1})
        monkeypatch.setattr(tmod, "run_bridge", fake_run_bridge)

        first = tmod.synthesize(text="同内容", idempotency_key="k-77", format="mp3")
        assert n["calls"] == 1 and first["slug"].startswith("tenant-a--idem-")
        second = tmod.synthesize(text="同内容", idempotency_key="k-77", format="mp3")
        assert second.get("idempotent_replay") is True
        assert n["calls"] == 1  # NOT regenerated (was: raw-slug lookup missed → re-billed)
        from mcp_server.db import usage_summary
        rows = usage_summary(owner=None)
        voice_rows = [r for r in rows if r["tool"] == "generate_voice"]
        assert len(voice_rows) == 1  # single usage row, no double billing

    def test_cross_tenant_same_slug_independent(self, monkeypatch, isolated_downloads):
        from mcp_server.generators import tts as tmod
        from mcp_server.generators import runtime as rt
        monkeypatch.setattr(tmod, "DOWNLOADS_DIR", isolated_downloads)
        monkeypatch.setattr(tmod, "_probe_duration_seconds", lambda p, f: 1.0)
        monkeypatch.setattr(tmod, "_validate_voice", lambda p, v: v or "101001")

        def fake_run_bridge(cmd, ctx, timeout_s=None):
            return json.dumps({"ok": True, "voice": "101001", "model": "m", "api_latency_ms": 1})
        monkeypatch.setattr(tmod, "run_bridge", fake_run_bridge)

        monkeypatch.setattr(rt, "current_owner", lambda: "tenant-a")
        r1 = tmod.synthesize(text="内容甲", slug="shared-name", format="mp3")
        monkeypatch.setattr(rt, "current_owner", lambda: "tenant-b")
        r2 = tmod.synthesize(text="内容乙", slug="shared-name", format="mp3")
        assert r1["slug"] != r2["slug"]  # no UNIQUE collision (was IntegrityError)


class TestVideoPollSemantics:
    def _patch_dirs(self, monkeypatch, tmp_path):
        from mcp_server.generators import video as vmod
        monkeypatch.setattr(vmod, "ensure_directory_rel", lambda *a, **k: tmp_path)
        return vmod

    def test_transient_503_keeps_job_running(self, monkeypatch, tmp_path):
        vmod = self._patch_dirs(monkeypatch, tmp_path)
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-t1", slug="t1")

        def raiser(cmd, ctx, timeout_s=None):
            raise subprocess.CalledProcessError(
                1, cmd, stderr='HTTP 503: {"error": "No available compatible accounts"}')
        monkeypatch.setattr(vmod, "run_bridge", raiser)
        view = vmod.poll(job_id, owner="alice")
        assert view["status"] == "running"  # NOT terminally failed (was: permanent failed)
        assert "last_poll_error" in view
        assert get_job(job_id)["status"] == "running"

    def test_timeout_poll_keeps_job_running(self, monkeypatch, tmp_path):
        vmod = self._patch_dirs(monkeypatch, tmp_path)
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-t2", slug="t2")

        def raiser(cmd, ctx, timeout_s=None):
            raise subprocess.TimeoutExpired(cmd, 900)
        monkeypatch.setattr(vmod, "run_bridge", raiser)
        view = vmod.poll(job_id, owner="alice")
        assert view["status"] == "running"
        assert get_job(job_id)["status"] == "running"

    def test_terminal_failure_marks_failed(self, monkeypatch, tmp_path):
        vmod = self._patch_dirs(monkeypatch, tmp_path)
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-t3", slug="t3")

        def fake(cmd, ctx, timeout_s=None):
            return json.dumps({"ok": False, "status": "failed",
                               "error": {"code": "content_policy"}})
        monkeypatch.setattr(vmod, "run_bridge", fake)
        view = vmod.poll(job_id, owner="alice")
        assert view["status"] == "failed"
        assert get_job(job_id)["status"] == "failed"

    def test_success_bills_measured_seconds(self, monkeypatch, tmp_path):
        vmod = self._patch_dirs(monkeypatch, tmp_path)
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-m1", slug="m1")
        fake_file = tmp_path / "m1.mp4"

        def fake(cmd, ctx, timeout_s=None):
            fake_file.write_bytes(b"v")
            return json.dumps({"ok": True, "status": "succeeded",
                               "local_path": str(fake_file),
                               "video_url": "https://cdn/v.mp4"})
        monkeypatch.setattr(vmod, "run_bridge", fake)
        monkeypatch.setattr(vmod, "_probe_video_seconds", lambda p: 7.4)
        view = vmod.poll(job_id, owner="alice")
        assert view["status"] == "succeeded" and abs(view["duration_sec"] - 7.4) < 1e-9
        from mcp_server.db import usage_summary
        rows = [r for r in usage_summary(owner=None) if r["tool"] == "generate_video_submit"]
        assert rows[0]["units"] == 7.4  # measured, not the old hard-coded 5
        from mcp_server.db import get_asset
        meta = get_asset(view["asset_id"], owner="alice")["metadata"]
        assert meta["duration_source"] == "measured"
        # row is in the owner-scoped slug domain
        assert get_asset(view["asset_id"], owner="alice")["slug"].startswith("alice--")

    def test_no_artifact_bills_zero_with_warning(self, monkeypatch, tmp_path):
        vmod = self._patch_dirs(monkeypatch, tmp_path)
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-z1", slug="z1")

        def fake(cmd, ctx, timeout_s=None):
            return json.dumps({"ok": True, "status": "succeeded",
                               "video_url": "https://cdn/v.mp4"})
        monkeypatch.setattr(vmod, "run_bridge", fake)
        view = vmod.poll(job_id, owner="alice")
        assert view["duration_sec"] is None
        assert any("billed 0" in w for w in view.get("warnings", []))
        from mcp_server.db import usage_summary
        rows = [r for r in usage_summary(owner=None) if r["tool"] == "generate_video_submit"]
        assert rows and rows[0]["units"] == 0.0  # never the fabricated 5


class TestToolLevelOwnerScoping:
    def test_video_job_status_uses_current_owner(self, monkeypatch):
        import mcp_server.tools.generate as gmod
        from mcp_server.db import insert_job
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-o1", slug="o1")
        seen = {}

        def fake_poll(jid, owner=None):
            seen["owner"] = owner
            return {"job_id": jid, "status": "running"}
        monkeypatch.setattr(gmod, "_video_poll", fake_poll)
        monkeypatch.setattr(gmod, "current_owner", lambda: "alice")
        gmod.video_job_status(job_id)
        assert seen["owner"] == "alice"  # was: owner=None → saw every tenant's jobs


class TestImageSurface:
    def test_reference_image_removed_from_signature(self):
        import inspect
        from mcp_server.generators import image as imod
        from mcp_server.tools.generate import generate_image as tool_img
        assert "reference_image" not in inspect.signature(imod.generate).parameters
        assert "reference_image" not in inspect.signature(tool_img).parameters

    def test_output_format_whitelist(self, monkeypatch, isolated_downloads):
        from mcp_server.generators import image as imod
        with pytest.raises(ValueError, match="not allowed"):
            imod.generate(prompt="p", output_format="jpeg/../../../x")

    def test_zero_artifact_fails_not_fakes_green(self, monkeypatch, isolated_downloads):
        from mcp_server.generators import image as imod
        from mcp_server.generators import runtime as rt
        monkeypatch.setattr(rt, "current_owner", lambda: "service")
        monkeypatch.setattr(imod, "ensure_directory_rel", lambda *a, **k: isolated_downloads)
        # bridge returns images with neither path nor url → silently skipped
        # before; now that is a loud failure with zero rows.
        def fake(cmd, ctx, timeout_s=None):
            return json.dumps({"ok": True, "images": [{"weird": 1}], "model": "m"})
        monkeypatch.setattr(imod, "run_bridge", fake)
        with pytest.raises(RuntimeError, match="zero artifacts"):
            imod.generate(prompt="测试图", output_format="jpeg", n=1)
        from mcp_server.db import usage_summary
        assert [r for r in usage_summary(owner=None) if r["tool"] == "generate_image"] == []

    def test_count_shortfall_disclosed_as_warning(self, monkeypatch, isolated_downloads):
        from mcp_server.generators import image as imod
        from mcp_server.generators import runtime as rt
        monkeypatch.setattr(rt, "current_owner", lambda: "tenant-a")
        monkeypatch.setenv("IMAGE_PROVIDER", "volcengine")

        def fake(cmd, ctx, timeout_s=None):
            src = isolated_downloads / "one.jpg"
            src.write_bytes(b"j")
            return json.dumps({"ok": True, "images": [{"local_path": str(src)}], "model": "m"})
        monkeypatch.setattr(imod, "run_bridge", fake)

        result = imod.generate(prompt="多图测试", output_format="jpeg", n=3)
        assert result["count"] == 1
        assert any("ignores n" in w for w in result["warnings"])
        # ledger row lands in the owner-scoped domain with the full file list
        from mcp_server.db import get_asset
        asset = get_asset(result["id"], owner="tenant-a")
        assert asset["slug"].startswith("tenant-a--")
        assert asset["metadata"]["file_paths"] == result["file_paths"]


class TestErrorScrubbing:
    def test_lane_down_classified_without_body_leak(self):
        from mcp_server.generators.errors import classify_upstream_error
        raw = ('HTTP 503: {"error":{"message":"No available compatible accounts for '
               'group 9 (account openai-next id=40 blocked)", "internal":"router detail"}}')
        err = classify_upstream_error("generate_image", raw, "ciyuan")
        msg = str(err)
        assert msg.startswith("lane_down")
        for secret_fragment in ("openai-next", "id=40", "group 9", "router detail"):
            assert secret_fragment not in msg

    def test_transient_detection(self):
        from mcp_server.generators.errors import is_transient, classify_upstream_error
        assert is_transient(ValueError("bridge returned HTTP 500 for status"))
        assert is_transient(ValueError("ciyuan video poll timed out after 600s"))
        assert not is_transient(ValueError("invalid_input: prompt required"))

    def test_bridge_failures_surfaced_as_classified(self, monkeypatch, isolated_downloads):
        from mcp_server.generators import tts as tmod
        from mcp_server.generators import runtime as rt
        monkeypatch.setattr(rt, "current_owner", lambda: "service")
        monkeypatch.setattr(tmod, "DOWNLOADS_DIR", isolated_downloads)
        monkeypatch.setattr(tmod, "_validate_voice", lambda p, v: v or "101001")

        def raiser(cmd, ctx, timeout_s=None):
            raise subprocess.CalledProcessError(
                1, cmd, stderr='HTTP 503 {"error":"No available compatible accounts"}')
        monkeypatch.setattr(tmod, "run_bridge", raiser)
        with pytest.raises(RuntimeError) as ei:
            tmod.synthesize(text="台词", format="mp3")
        assert str(ei.value).startswith("lane_down")
        assert "compatible accounts" not in str(ei.value)


class TestDownloadBaseAndPricing:
    def test_no_public_base_no_leaked_internal_host(self, monkeypatch):
        from mcp_server import hosting
        monkeypatch.delenv("VAAS_PUBLIC_URL", raising=False)
        monkeypatch.setattr(hosting, "_download_hmac_key", lambda: b"testkey")
        assert hosting.download_url("asset-1", "alice") is None
        monkeypatch.setenv("VAAS_PUBLIC_URL", "http://example.test:30950")
        url = hosting.download_url("asset-1", "alice")
        assert url and url.startswith("http://example.test:30950/download/asset-1?")

    def test_pricing_strict_refuses_missing(self, tmp_path, monkeypatch):
        from mcp_server.main import _load_pricing
        monkeypatch.setenv("VAAS_PRICING_FILE", str(tmp_path / "nope.json"))
        with pytest.raises(RuntimeError, match="pricing configuration"):
            _load_pricing(strict=True)
        assert _load_pricing(strict=False) == {}

    def test_pricing_strict_refuses_empty(self, tmp_path, monkeypatch):
        from mcp_server.main import _load_pricing
        f = tmp_path / "p.json"
        f.write_text("{}")
        monkeypatch.setenv("VAAS_PRICING_FILE", str(f))
        with pytest.raises(RuntimeError, match="empty"):
            _load_pricing(strict=True)

    def test_repo_pricing_has_real_voice_rate(self):
        p = Path(__file__).parent.parent / "pricing.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc["generate_voice"]["char"] == 0.00003  # ¥0.3/万字符（manifest price_note）
        assert doc["currency"] == "CNY"


class TestGCContainment:
    def test_gc_uses_real_path_relation(self, monkeypatch, tmp_path):
        import sys
        import time as _t
        # mcp_server/__init__ binds the name `main` to the entry function;
        # reach the actual module object via sys.modules.
        m = sys.modules.get("mcp_server.main")
        if m is None:
            import mcp_server.main  # noqa: F401  (populates sys.modules)
            m = sys.modules["mcp_server.main"]
        from mcp_server.db import insert_asset, get_asset
        from mcp_server.utils import file_manager as fm

        dl = tmp_path / "downloads"
        (dl / "audio" / "a1").mkdir(parents=True)
        (dl / "audio" / "a1" / "a1.mp3").write_bytes(b"x")
        # sibling tree with a deceptive prefix — must never be touched
        sneaky = tmp_path / "downloads_evil" / "audio" / "a1"
        sneaky.mkdir(parents=True)
        (sneaky / "keep.mp3").write_bytes(b"x")
        monkeypatch.setattr(fm, "DOWNLOADS_DIR", dl)
        # gc_expired_artifacts does `from .utils import DOWNLOADS_DIR` at call
        # time — patch the utils package attribute, not just file_manager.
        monkeypatch.setattr(sys.modules["mcp_server.utils"], "DOWNLOADS_DIR", dl)

        aid = insert_asset(type="audio", slug="a1", stage="rendered")
        conn = database.get_connection()
        conn.execute("UPDATE assets SET created_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (aid,))
        conn.execute("UPDATE assets SET file_path = ? WHERE id = ?",
                     ("../../downloads_evil/audio/a1/keep.mp3", aid))
        conn.commit()
        conn.close()

        removed = m.gc_expired_artifacts(now=_t.time())
        assert removed >= 1
        assert (sneaky / "keep.mp3").exists()  # prefix trap NOT triggered
        assert get_asset(aid) is None          # row reaped regardless


class TestRunBridgeWallClock:
    def test_timeout_raises_classified_error(self, monkeypatch):
        from mcp_server.generators import runtime as rt
        import subprocess as sp

        def raiser(cmd, **kwargs):
            assert kwargs.get("timeout"), "wall clock must be set"
            raise sp.TimeoutExpired(cmd, kwargs["timeout"])
        monkeypatch.setattr(rt.subprocess, "run", raiser)
        ctx = {"env": {}}
        with pytest.raises(RuntimeError, match="timeout"):
            rt.run_bridge(["python", "bridge", "tts"], ctx)


class TestCiyuanPythonLaneParity:
    """deliver-hosted-surface W2: python lane mirrors node lane's exit layer
    (segmentation at the length wall + synthetic captions fallback)."""

    def _load_driver(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "citts", str(Path(__file__).parent.parent.parent / "scripts" / "_ciyuan_tts.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_segmentation_at_length_wall(self):
        m = self._load_driver()
        long = '问一句话，拿回真实数据行。这是寻数科技。数据留在你手里。' * 20  # 560 chars
        segs = m.split_text_into_segments(long)
        assert len(segs) > 1
        assert all(len(s) <= 150 for s in segs)
        # sentence boundary wins; no sentence glued across a wall
        assert segs[0].endswith(("。", "！", "？", "；")) or len(segs) == 1

    def test_short_text_single_request(self):
        m = self._load_driver()
        assert m.split_text_into_segments("短句。") == ["短句。"]

    def test_token_split_matches_node_semantics(self):
        m = self._load_driver()
        assert m.split_text_into_tokens("Hello 寻数，你好。") == ["Hello", "寻", "数，", "你", "好。"]

    def test_segmented_captions_monotonic_with_gap(self):
        m = self._load_driver()
        caps = m._build_segmented_captions(["第一句。", "第二句三字。"], [1.0, 1.0], 0.22)
        assert caps
        starts = [c["startMs"] for c in caps]
        assert starts == sorted(starts)
        assert caps[-1]["endMs"] >= 1000 + 220  # second segment pushed past gap

    def test_probe_real_wav(self, tmp_path):
        import subprocess as sp
        m = self._load_driver()
        wav = tmp_path / "t.wav"
        sp.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                "-t", "1.5", str(wav)], capture_output=True)
        d = m._probe_duration_seconds(str(wav))
        assert d and abs(d - 1.5) < 0.2


class TestLaneHealthSurface:
    """deliver-hosted-surface W3: health ledger drives discovery + gating."""

    def test_lane_health_lookup_known_and_unknown(self):
        from mcp_server.lane_health import lane_health
        img = lane_health("image", "ciyuan")
        assert img["health"] == "down" and img["reason_class"] == "upstream_blocked"
        voice = lane_health("voice", "ciyuan")
        assert voice["health"] == "active"
        unknown = lane_health("voice", "mystery-provider")
        assert unknown["health"] == "degraded"  # unknown ≠ advertised as fine

    def test_registry_list_carries_lane_health(self):
        from mcp_server.tools.registry_tools import registry_list_generators
        out = registry_list_generators("image")
        by_name = {e["name"]: e for e in out["items"]}
        assert by_name["seedream-ciyuan"]["lane"]["health"] == "down"
        assert by_name["seedream"]["lane"]["health"] == "down"  # unconfigured ARK
        voice = registry_list_generators("voice")
        vby = {e["name"]: e for e in voice["items"]}
        assert vby["tts-ciyuan"]["lane"]["health"] == "active"

    def test_down_lane_refused_as_lane_down_before_subprocess(self, monkeypatch, isolated_downloads):
        from mcp_server.generators import image as imod
        from mcp_server.generators import runtime as rt
        monkeypatch.setattr(rt, "current_owner", lambda: "service")
        monkeypatch.setenv("VAAS_HOSTED", "1")  # gate is a hosted-surface discipline
        monkeypatch.setenv("OPENBAO_ADDR", "http://localhost:0")  # resolve() must not precede the gate; vault reachability is not under test here
        monkeypatch.setenv("OPENBAO_TOKEN", "test-token")
        monkeypatch.setenv("IMAGE_PROVIDER", "ciyuan")
        calls = []

        def spy(cmd, ctx, timeout_s=None):  # must never be reached
            calls.append(cmd)
            raise AssertionError("down lane must be refused before subprocess")
        monkeypatch.setattr(imod, "run_bridge", spy)
        with pytest.raises(Exception, match="lane_down"):
            imod.generate(prompt="测试", output_format="jpeg")
        assert not calls

    def test_models_voices_carries_lane_block(self):
        from mcp_server.tools.generate import models_voices
        doc = models_voices()
        assert doc["providers"]["ciyuan"]["lane"]["health"] == "active"


class TestTemplatesFailOpen:
    """deliver-hosted-surface W3: missing type dir is a loud error, not []."""

    def test_missing_types_dir_raises(self, monkeypatch, tmp_path):
        import importlib
        import mcp_server.tools.templates as tmod
        importlib.reload(tmod)
        monkeypatch.setattr(tmod, "VIDEO_TYPES_DIR", tmp_path / "no-such-dir", raising=False)
        with pytest.raises((RuntimeError, ValueError, FileNotFoundError)):
            tmod.templates_list(domain="video")


class TestConcurrentInsertRace:
    """并发同计划键：两边都过 replay 检查后都 INSERT，败者曾冒
    `UNIQUE constraint failed: assets.slug`（2026-11-09 迁移后并发实测）。
    insert_asset_idempotent 必须把唯一冲突折成「采纳先写入的行」。"""

    def test_second_insert_adopts_existing_row(self, isolated_db):
        from mcp_server.db import insert_asset_idempotent, get_asset_by_slug

        first_id, created1 = insert_asset_idempotent(
            type="audio", slug="svc--race", file_path="audio/race/a.mp3",
            metadata={"k": 1}, stage="rendered", owner="svc")
        second_id, created2 = insert_asset_idempotent(
            type="audio", slug="svc--race", file_path="audio/race/a.mp3",
            metadata={"k": 2}, stage="rendered", owner="svc")

        assert created1 is True and created2 is False
        assert second_id == first_id
        row = get_asset_by_slug("svc--race", owner="svc")
        assert row and row["id"] == first_id
        assert (row.get("metadata") or {}).get("k") == 1  # 先写入者不被覆盖

    def test_non_unique_errors_still_raise(self, isolated_db):
        from mcp_server.db import insert_asset_idempotent
        import pytest
        with pytest.raises(Exception):
            # 缺必填 type/slug 触发的是 sqlite 的 NOT NULL/约束，不该被吞成 replay
            insert_asset_idempotent(type=None, slug=None)

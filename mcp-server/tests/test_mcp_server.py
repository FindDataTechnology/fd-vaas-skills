"""
Tests for the unified VAAS MCP Server: asset store, registry, tool surface.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import (
    init_schema,
    insert_asset,
    get_asset_by_slug,
    list_assets,
    update_asset_stage,
    upsert_variant,
    insert_distribution,
    get_asset_stats,
    get_variants,
)
from mcp_server.utils import generate_slug, validate_slug
from mcp_server.registry import list_generators, dispatch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


class TestFileManager:
    def test_generate_slug(self):
        slug = generate_slug("video")
        assert slug.startswith("video-")

    def test_validate_slug(self):
        assert validate_slug("my-video") is True
        assert validate_slug("Bad Slug!") is False


class TestAssetStore:
    def test_insert_and_get_with_stage(self):
        aid = insert_asset(type="video", slug="t-video", stage="draft", title="T")
        asset = get_asset_by_slug("t-video")
        assert asset["id"] == aid
        assert asset["stage"] == "draft"
        assert asset["type"] == "video"

    def test_stage_machine_records_history(self):
        aid = insert_asset(type="video", slug="t-stage", stage="draft")
        update_asset_stage(aid, "rendered", "render:done")
        update_asset_stage(aid, "published", "publish:video")
        assert get_asset_by_slug("t-stage")["stage"] == "published"

    def test_lineage_tree(self):
        parent = insert_asset(type="video", slug="t-root", stage="rendered")
        insert_asset(type="video", slug="t-root-douyin", stage="draft",
                     parent_id=parent, lineage_root=parent)
        child = get_asset_by_slug("t-root-douyin")
        assert sorted(n["slug"] for n in child["lineage"]) == ["t-root", "t-root-douyin"]

    def test_variant_upsert(self):
        aid = insert_asset(type="video", slug="t-var")
        upsert_variant(aid, "douyin", title="抖音版", tags=["AI"])
        upsert_variant(aid, "douyin", title="抖音版2", tags=["AI", "效率"])
        vs = get_variants(aid)
        assert len(vs) == 1
        assert vs[0]["title"] == "抖音版2"
        assert vs[0]["tags"] == ["AI", "效率"]

    def test_distribution_upsert_one_row_per_platform(self):
        aid = insert_asset(type="video", slug="t-dist")
        insert_distribution(aid, "douyin", url="http://a", status="uploaded")
        insert_distribution(aid, "douyin", url="http://b", status="uploaded")
        asset = get_asset_by_slug("t-dist")
        assert len(asset["distribution"]) == 1
        assert asset["distribution"][0]["url"] == "http://b"

    def test_list_and_stats(self):
        insert_asset(type="video", slug="t-l1", stage="rendered")
        insert_asset(type="image", slug="t-l2", stage="draft")
        assert len(list_assets(type="video")) == 1
        stats = get_asset_stats()
        assert stats["total_assets"] == 2
        assert {t["type"] for t in stats["by_type"]} == {"video", "image"}


class TestRegistry:
    def test_list_generators(self):
        video = list_generators("video")["items"]
        assert any(g["name"] == "seedance" for g in video)
        assert any(g["name"] == "voiceover" for g in video)

    def test_dispatch_unknown_raises_with_list(self):
        with pytest.raises(ValueError) as exc:
            dispatch("video", "nonexistent", {})
        assert "seedance" in str(exc.value)


class TestToolSurface:
    def test_all_tools_registered(self):
        import importlib
        main_mod = importlib.import_module("mcp_server.main")

        async def names():
            return sorted(t.name for t in await main_mod.mcp.list_tools())

        tools = asyncio.run(names())
        for expected in ["assets_list", "assets_get", "assets_stats",
                         "generate_video", "publish_simulate",
                         "registry_list_generators", "assets_find_logo",
                         "publish_validate_ready"]:
            assert expected in tools, f"missing tool {expected}"
        # legacy aliases kept
        for legacy in ["list_all_content", "get_content_details",
                       "publish_video_to_platforms", "create_cover_image"]:
            assert legacy in tools, f"missing legacy alias {legacy}"



class TestOwnerIsolation:
    def test_insert_defaults_to_service_owner(self):
        aid = insert_asset(type="image", slug="own-default")
        assert get_asset_by_slug("own-default")["owner"] == "service"

    def test_tenant_lists_only_own_assets(self):
        from mcp_server.db import list_assets as la
        insert_asset(type="image", slug="a-owned", owner="alice")
        insert_asset(type="image", slug="b-owned", owner="bob")
        names = {r["slug"] for r in la(owner="alice")}
        assert "a-owned" in names and "b-owned" not in names
        # admin (owner=None) sees both
        assert len(la()) >= 2

    def test_cross_tenant_get_invisible(self):
        from mcp_server.db import get_asset as ga
        aid = insert_asset(type="image", slug="secret", owner="alice")
        assert ga(aid, owner="bob") is None
        assert ga(aid, owner="alice")["id"] == aid
        assert ga(aid)["id"] == aid  # local admin

    def test_stats_scoped_by_owner(self):
        insert_asset(type="image", slug="s1", owner="alice")
        insert_asset(type="video", slug="s2", owner="bob")
        assert get_asset_stats(owner="alice")["total_assets"] == 1
        assert get_asset_stats()["total_assets"] >= 2

    def test_legacy_db_migration_backfills_owner(self, tmp_path):
        import sqlite3
        legacy = tmp_path / "legacy.db"
        conn = sqlite3.connect(str(legacy))
        # Pre-change schema: full column set, no owner column
        conn.execute("""CREATE TABLE assets (
            id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL, type TEXT NOT NULL,
            stage TEXT NOT NULL DEFAULT 'draft', title TEXT, parent_id TEXT,
            lineage_root TEXT, provider TEXT, file_path TEXT, metadata JSON,
            video_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("INSERT INTO assets (id, slug, type) VALUES ('x', 'legacy-row', 'image')")
        conn.commit()
        conn.close()
        init_schema(legacy)
        conn = sqlite3.connect(str(legacy))
        owner, = conn.execute("SELECT owner FROM assets WHERE id='x'").fetchone()
        conn.close()
        assert owner == "service"


class TestCredentials:
    def test_rejects_credential_material_in_params(self):
        from mcp_server.credentials import reject_secrets_in_params
        reject_secrets_in_params({"prompt": "a cat", "slug": "fine"})  # no raise
        with pytest.raises(ValueError):
            reject_secrets_in_params({"prompt": "key is ark-0123abcd-1234-1234-1234-123456789abc-xyz"})
        with pytest.raises(ValueError):
            reject_secrets_in_params({"note": "sk-abcdefghijklmnop1234"})

    def test_local_mode_resolves_env_without_vault(self, monkeypatch):
        from mcp_server import credentials as C
        monkeypatch.delenv("VAAS_HOSTED", raising=False)
        monkeypatch.delenv("OPENBAO_ADDR", raising=False)
        assert C.resolve("image") == {"source": "env"}
        assert C.subprocess_env(C.resolve("image"), "image") == {}

    def test_hosted_resolution_pool_then_default(self, monkeypatch):
        from mcp_server import credentials as C
        monkeypatch.setenv("VAAS_HOSTED", "1")
        calls = []
        def fake_vault_get(path):
            calls.append(path)
            if path == "pool/wanxing/image":
                return {"api_key": "ark-pool-key", "base_url": "https://pool.example/v3"}
            return None
        monkeypatch.setattr(C, "_vault_get", fake_vault_get)
        monkeypatch.setattr(C, "_cache", {})
        r = C.resolve("image")
        assert r["source"] == "pool" and r["api_key"] == "ark-pool-key"
        env = C.subprocess_env(r, "image")
        assert env["ARK_API_KEY"] == "ark-pool-key"
        assert env["SEEDREAM_BASE_URL"] == "https://pool.example/v3"
        assert "pool/wanxing/image" in calls

        monkeypatch.setattr(C, "_cache", {})
        def only_default(path):
            return {"api_key": "ark-default"} if path == "service/default/image" else None
        monkeypatch.setattr(C, "_vault_get", only_default)
        assert C.resolve("image")["source"] == "default"

        monkeypatch.setattr(C, "_cache", {})
        monkeypatch.setattr(C, "_vault_get", lambda path: None)
        with pytest.raises(C.CredentialUnavailable):
            C.resolve("image")

    def test_vault_cache_ttl(self, monkeypatch):
        from mcp_server import credentials as C
        monkeypatch.setenv("VAAS_HOSTED", "1")
        hits = []
        def fake_vault_get(path):
            hits.append(1)
            return {"api_key": "k"}
        monkeypatch.setattr(C, "_vault_get", fake_vault_get)
        monkeypatch.setattr(C, "_cache", {})
        C.resolve("image"); C.resolve("image")
        assert len(hits) == 1  # second read served from cache


class TestGenerationJobs:
    def test_job_lifecycle_and_owner_scoping(self):
        from mcp_server.db import insert_job, get_job, update_job, insert_asset
        asset_id = insert_asset(type="video", slug="job-asset", owner="alice")
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-1", slug="j1")
        assert get_job(job_id)["status"] == "running"
        assert get_job(job_id, owner="bob") is None
        update_job(job_id, status="succeeded", asset_id=asset_id)
        assert get_job(job_id, owner="alice")["asset_id"] == asset_id

    def test_stale_jobs_expire(self):
        import datetime
        from mcp_server.db import insert_job, get_job, expire_stale_jobs
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-2",
                            ttl_hours=0)
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        assert expire_stale_jobs(now=future) >= 1
        assert get_job(job_id)["status"] == "expired"


    def test_video_submit_creates_running_job(self, monkeypatch, tmp_path):
        from mcp_server.generators import video as vmod
        from mcp_server.db import get_job
        def fake_run_bridge(cmd, ctx):
            assert "--async" in cmd
            return __import__("json").dumps({
                "ok": True, "status": "submitted", "task_id": "prov-77",
                "model": "doubao-seedance-2.0",
            })
        monkeypatch.setattr(vmod, "run_bridge", fake_run_bridge)
        result = vmod.submit(prompt="city timelapse", slug="sub1")
        assert result["status"] == "running" and result["provider_task_id"] == "prov-77"
        job = get_job(result["job_id"], owner="service")
        assert job and job["kind"] == "video"

    def test_video_poll_success_creates_owned_asset(self, monkeypatch, tmp_path):
        from mcp_server.db import insert_job
        from mcp_server.generators import video as vmod
        import mcp_server.db.database as database
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-3", slug="pollwin")
        # fake the artifact file so the asset records a real relative path
        dl = database.DB_PATH.parent  # throwaway tree
        def fake_run_bridge(cmd, ctx):
            assert "--status" in cmd and "tid-3" in cmd
            out = tmp_path / "fake.mp4"
            out.write_bytes(b"vv")
            return __import__("json").dumps({
                "ok": True, "status": "succeeded", "local_path": str(out),
                "video_url": "https://cdn.example/v.mp4",
            })
        monkeypatch.setattr(vmod, "run_bridge", fake_run_bridge)
        monkeypatch.setattr(vmod, "ensure_directory_rel", lambda *a, **k: tmp_path)
        view = vmod.poll(job_id, owner="alice")
        assert view["status"] == "succeeded" and view["asset_id"]
        from mcp_server.db import get_asset
        assert get_asset(view["asset_id"], owner="alice")["owner"] == "alice"
        assert get_asset(view["asset_id"], owner="bob") is None

    def test_video_poll_cross_tenant_invisible(self):
        from mcp_server.db import insert_job
        from mcp_server.generators import video as vmod
        job_id = insert_job(owner="alice", kind="video", provider_task_id="tid-4")
        with pytest.raises(ValueError):
            vmod.poll(job_id, owner="bob")


class TestUsageMetering:
    def test_record_and_aggregate(self):
        from mcp_server.db import record_usage, usage_summary
        record_usage("alice", "generate_image", "volcengine", "m1", 2, "image", "pool")
        record_usage("alice", "generate_image", "volcengine", "m1", 3, "image", "pool")
        record_usage("alice", "generate_voice", "volcengine", "m2", 100, "char", "default")
        rows = {(r["tool"], r["credential_source"]): r for r in usage_summary(owner="alice")}
        assert rows[("generate_image", "pool")]["calls"] == 2
        assert rows[("generate_image", "pool")]["units"] == 5
        assert rows[("generate_voice", "default")]["units"] == 100
        assert usage_summary(owner="bob") == []

    def test_usage_report_pricing(self, monkeypatch, tmp_path):
        import importlib
        from starlette.testclient import TestClient
        pricing = tmp_path / "pricing.json"
        pricing.write_text('{"currency": "CNY", "generate_image": {"image": 0.5}}')
        monkeypatch.setenv("VAAS_PRICING_FILE", str(pricing))
        main_mod = importlib.import_module("mcp_server.main")
        client = TestClient(main_mod.mcp.http_app())
        resp = client.get("/usage/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["currency"] == "CNY"
        assert isinstance(body["items"], list)


class TestSignedDownloads:
    def test_sign_verify_roundtrip(self, monkeypatch):
        from mcp_server import hosting as H
        monkeypatch.setattr(H, "_download_hmac_key", lambda: b"k" * 8)
        signed = H.sign_download("asset-1", "alice", ttl=60)
        assert H.verify_download("asset-1", "alice", signed["exp"], signed["signature"])
        assert not H.verify_download("asset-1", "bob", signed["exp"], signed["signature"])
        assert not H.verify_download("asset-1", "alice", signed["exp"] - 120, signed["signature"])
        assert not H.verify_download("asset-1", "alice", signed["exp"], "deadbeef")

    def test_download_route(self, monkeypatch, tmp_path):
        import importlib
        from starlette.testclient import TestClient
        from mcp_server import hosting as H
        monkeypatch.setattr(H, "_download_hmac_key", lambda: b"k" * 8)
        main_mod = importlib.import_module("mcp_server.main")
        fake_asset = {"id": "asset-9", "owner": "alice", "file_path": "images/sl/ok.jpg"}
        monkeypatch.setattr(main_mod, "get_asset", lambda aid, owner=None: fake_asset)
        client = TestClient(main_mod.mcp.http_app())
        # missing/invalid signature -> 403
        assert client.get("/download/asset-9", params={"owner": "alice", "exp": 1, "signature": "x"}).status_code == 403
        # valid signature but file missing -> 404 (signature IS the credential;
        # hosted bearer is deliberately not required on this route — design D19)
        signed = H.sign_download("asset-9", "alice", ttl=60)
        r = client.get("/download/asset-9", params=signed)
        assert r.status_code == 404



class TestGeneratorLocalRegression:
    def test_image_generate_local_flow(self, monkeypatch, tmp_path):
        """Local mode: bridge gets no env overlay, row lands with service owner."""
        from mcp_server.generators import image as imod
        from mcp_server.db import get_asset, usage_summary
        captured = {}
        def fake_run_bridge(cmd, ctx):
            captured["env"] = ctx["env"]
            out = tmp_path / "img.jpg"
            out.write_bytes(b"ii")
            return __import__("json").dumps({
                "model": "doubao-seedream-5.0-lite",
                "images": [{"local_path": str(out)}],
            })
        monkeypatch.setattr(imod, "run_bridge", fake_run_bridge)
        monkeypatch.setattr(imod, "ensure_directory_rel", lambda *a, **k: tmp_path)
        result = imod.generate(prompt="a cat", slug="cat-pic")
        assert captured["env"] == {}  # local mode injects nothing
        asset = get_asset(result["id"])
        assert asset["owner"] == "service"
        rows = usage_summary(owner="service")
        assert any(r["tool"] == "generate_image" and r["unit_type"] == "image" for r in rows)
        assert result["credential_source"] == "env"

    def test_image_generate_rejects_key_in_prompt(self):
        from mcp_server.generators import image as imod
        with pytest.raises(ValueError):
            imod.generate(prompt="use key sk-abcdefghijklmnop1234")


class TestHostedIdentity:
    def _fake_request(self, headers):
        class R:
            def __init__(self, h):
                self.headers = h
        return R(headers)

    def test_hosted_owner_with_bearer_and_header(self, monkeypatch):
        from mcp_server import hosting as H
        monkeypatch.setenv("VAAS_HOSTED", "1")
        monkeypatch.setenv("VAAS_BEARER_TOKEN", "svc-tok")
        monkeypatch.setattr(H, "_request",
                            lambda: self._fake_request({"authorization": "Bearer svc-tok",
                                                        "x-forwarded-user": "alice"}))
        assert H.current_owner() == "alice"

    def test_hosted_owner_rejects_bad_bearer(self, monkeypatch):
        from mcp_server import hosting as H
        monkeypatch.setenv("VAAS_HOSTED", "1")
        monkeypatch.setenv("VAAS_BEARER_TOKEN", "svc-tok")
        monkeypatch.setattr(H, "_request",
                            lambda: self._fake_request({"authorization": "Bearer wrong",
                                                        "x-forwarded-user": "alice"}))
        with pytest.raises(H.IdentityRequired):
            H.current_owner()

    def test_hosted_owner_rejects_missing_sub(self, monkeypatch):
        from mcp_server import hosting as H
        monkeypatch.setenv("VAAS_HOSTED", "1")
        monkeypatch.setenv("VAAS_BEARER_TOKEN", "svc-tok")
        monkeypatch.setattr(H, "_request",
                            lambda: self._fake_request({"authorization": "Bearer svc-tok"}))
        with pytest.raises(H.IdentityRequired):
            H.current_owner()

    def test_hosted_tool_surface_excludes_publish(self):
        """Hosted mode must not register publish plane or sync video (subprocess reload)."""
        import subprocess, sys, os
        code = (
            "import sys; sys.path.insert(0, '.');"
            "import importlib;"
            "M = importlib.import_module('mcp_server.main');"
            "import asyncio;"
            "tools = asyncio.run(M.mcp.list_tools());"
            "names = {t.name for t in tools};"
            "assert not any(n.startswith('publish') for n in names), names;"
            "assert 'generate_video' not in names, names;"
            "assert 'generate_video_submit' in names and 'video_job_status' in names;"
            "print('HOSTED_SURFACE_OK')"
        )
        env = {**os.environ, "VAAS_HOSTED": "1"}
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, env=env, cwd=".")
        assert out.returncode == 0, out.stderr
        assert "HOSTED_SURFACE_OK" in out.stdout


class TestArtifactGC:
    def test_gc_removes_only_expired_rendered(self, monkeypatch):
        import time, importlib
        from mcp_server.db import get_connection, insert_asset, get_asset, get_asset_by_slug
        import mcp_server.db.database as database
        main_mod = importlib.import_module("mcp_server.main")

        old_id = insert_asset(type="image", slug="gc-old", stage="rendered")
        keep_id = insert_asset(type="image", slug="gc-new", stage="rendered")
        dist_id = insert_asset(type="image", slug="gc-dist", stage="rendered")
        conn = get_connection()
        old_stamp = "2020-01-01T00:00:00+00:00"
        conn.execute("UPDATE assets SET created_at = ? WHERE id = ?", (old_stamp, old_id))
        conn.execute(
            "INSERT INTO distribution (asset_id, platform, status) VALUES (?, 'weixin', 'uploaded')",
            (dist_id,))
        conn.commit()
        conn.close()

        now = time.mktime(time.strptime("2020", "%Y")) + 40 * 86400
        removed = main_mod.gc_expired_artifacts(now=now, ttl_days=30)
        assert removed >= 1
        assert get_asset(old_id) is None
        assert get_asset(keep_id) is not None          # recent stays
        assert get_asset(dist_id) is not None          # distributed stays


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

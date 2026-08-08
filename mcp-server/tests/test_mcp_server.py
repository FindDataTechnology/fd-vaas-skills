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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

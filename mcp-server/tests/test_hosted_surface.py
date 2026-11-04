"""
Hosted tool-surface probes (W6.3, add-presentation-plane).

FastMCP in-memory client against mcp_server.main, executed in fresh
subprocesses: tool registration is import-time (main.py registers
CANONICAL_TOOLS filtered by is_hosted() when the module loads), so flipping
VAAS_HOSTED inside this pytest process cannot re-register the surface — a
subprocess per state is the reliable isolation.

  stdio  (default)            → 23 tools: 17 hosted + 6 publish (stdio-only plane)
  hosted (VAAS_HOSTED=1)      → 17 tools; publish_* gone, orchestrate_*/legacy
                                aliases gone, and a publish_video tool call is
                                rejected (Unknown tool — nothing executes).
"""

import functools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

# ─── Canonical surface (mirrors main.py CANONICAL_TOOLS) ───────────────────

HOSTED_TOOLS = [
    "generate_voice", "generate_image", "generate_video_submit",
    "video_job_status", "models_voices", "voiceover_assemble",
    "reference_clips_check",
    "render_video", "render_still", "render_document",
    "templates_list", "templates_get",
    "assets_list", "assets_get", "assets_stats",
    "registry_list_generators", "registry_describe_generator",
]
PUBLISH_TOOLS = [
    "publish_video", "publish_article", "publish_validate_ready",
    "publish_get_config", "publish_simulate", "publish_record",
]
STDIO_TOOLS = HOSTED_TOOLS + PUBLISH_TOOLS

# Retired in Wave1 and must never resurface (legacy aliases included).
RETIRED_TOOLS = [
    "orchestrate_brainstorm", "orchestrate_voiceover",
    "generate_cover", "generate_video",
    "assets_list_common", "assets_find_logo", "assets_list_compositions",
    "assets_validate_paths", "assets_get_scene_templates",
    "create_cover_image", "create_voiceover", "brainstorm_content",
    "publish_video_to_platforms", "publish_article_to_platforms",
    "list_all_content", "get_content_details",
]

# Runs inside a fresh python process: registers the surface under the ambient
# env, then interrogates it with the FastMCP in-memory client. With
# VAAS_PROBE_CALL_PUBLISH=1 it also attempts a publish_video call and records
# how the server rejected (or accepted — a leak) it.
_PROBE_SRC = """\
import asyncio, importlib, json, os, sys
sys.path.insert(0, ".")
M = importlib.import_module("mcp_server.main")
from fastmcp import Client

async def probe():
    async with Client(M.mcp) as client:
        tools = await client.list_tools()
        out = {"names": sorted(t.name for t in tools)}
        if os.getenv("VAAS_PROBE_CALL_PUBLISH") == "1":
            try:
                await client.call_tool("publish_video", {"slug": "surface-probe"})
                out["publish_call"] = "accepted"  # leak: tool reachable in hosted mode
            except Exception as e:
                out["publish_call"] = f"{type(e).__name__}: {e}"
        return out

print(json.dumps(asyncio.run(probe())))
"""


@functools.lru_cache(maxsize=None)
def _probe(hosted: bool, call_publish: bool) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "VAAS_HOSTED"}
    if hosted:
        env["VAAS_HOSTED"] = "1"
        env["VAAS_TRANSPORT"] = "http"
    if call_publish:
        env["VAAS_PROBE_CALL_PUBLISH"] = "1"
    out = subprocess.run(
        [sys.executable, "-c", _PROBE_SRC],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=180,
    )
    assert out.returncode == 0, f"probe subprocess failed:\n{out.stderr}"
    return json.loads(out.stdout.strip().splitlines()[-1])


class TestStdioSurface:
    """Default mode: full 23-tool surface, publish plane included."""

    def test_stdio_surface_is_23_exact(self):
        names = _probe(hosted=False, call_publish=False)["names"]
        assert sorted(names) == sorted(STDIO_TOOLS), names
        assert len(names) == 23
        for gone in RETIRED_TOOLS:
            assert gone not in names, f"retired tool still registered: {gone}"


class TestHostedSurface:
    """VAAS_HOSTED=1 / VAAS_TRANSPORT=http: 17 hosted tools, publish plane gone."""

    @pytest.fixture(scope="class")
    def hosted_names(self):
        return _probe(hosted=True, call_publish=False)["names"]

    def test_hosted_surface_is_17_exact(self, hosted_names):
        assert sorted(hosted_names) == sorted(HOSTED_TOOLS), hosted_names
        assert len(hosted_names) == 17

    def test_publish_plane_not_registered(self, hosted_names):
        leaked = [n for n in hosted_names if n.startswith("publish")]
        assert leaked == [], f"publish tools leaked into hosted surface: {leaked}"

    def test_retired_tools_and_aliases_gone(self, hosted_names):
        for gone in RETIRED_TOOLS:
            assert gone not in hosted_names, f"retired tool still registered: {gone}"

    def test_render_and_templates_planes_present(self, hosted_names):
        for expected in ["render_video", "render_still", "render_document",
                         "templates_list", "templates_get"]:
            assert expected in hosted_names, f"missing tool {expected}"


class TestHostedCallRejection:
    def test_publish_video_call_rejected(self):
        """Not listed AND not callable: the call is refused, nothing executes."""
        out = _probe(hosted=True, call_publish=True)
        rejection = out["publish_call"]
        assert rejection != "accepted", "publish_video is callable in hosted mode"
        assert "publish_video" in rejection, rejection


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

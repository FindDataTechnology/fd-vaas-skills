"""
VAAS MCP Server — unified material generation, management, and publishing.

Single MCP server exposing namespaced tools:
  generate_*    voice/image/video/cover generation (via registry)
  orchestrate_* voiceover / brainstorm pipelines
  publish_*     multi-platform publish + validate/config/simulate/record
  assets_*      material store queries + Remotion asset discovery
  registry_*    generation method discovery

Legacy tool names remain registered as deprecated aliases.
"""

from fastmcp import FastMCP

mcp = FastMCP("VAAS")

from .tools.generate import (
    generate_voice, generate_image, generate_video, generate_cover,
)
from .tools.orchestrate import orchestrate_voiceover, orchestrate_brainstorm
from .tools.publish import (
    publish_video, publish_article,
    publish_validate_ready, publish_get_config, publish_simulate, publish_record,
)
from .tools.assets import (
    assets_list, assets_get, assets_stats,
    assets_list_common, assets_find_logo, assets_list_compositions,
    assets_validate_paths, assets_get_scene_templates,
)
from .tools.registry_tools import registry_list_generators, registry_describe_generator

# ─── Canonical namespaced tools ────────────────────────────────────────────
CANONICAL_TOOLS = [
    generate_voice, generate_image, generate_video, generate_cover,
    orchestrate_voiceover, orchestrate_brainstorm,
    publish_video, publish_article,
    publish_validate_ready, publish_get_config, publish_simulate, publish_record,
    assets_list, assets_get, assets_stats,
    assets_list_common, assets_find_logo, assets_list_compositions,
    assets_validate_paths, assets_get_scene_templates,
    registry_list_generators, registry_describe_generator,
]
for fn in CANONICAL_TOOLS:
    mcp.tool()(fn)

# ─── Deprecated legacy aliases ─────────────────────────────────────────────
LEGACY_ALIASES = [
    ("create_cover_image", generate_cover, "Use generate_cover"),
    ("create_voiceover", orchestrate_voiceover, "Use orchestrate_voiceover"),
    ("brainstorm_content", orchestrate_brainstorm, "Use orchestrate_brainstorm"),
    ("publish_video_to_platforms", publish_video, "Use publish_video"),
    ("publish_article_to_platforms", publish_article, "Use publish_article"),
    ("list_all_content", assets_list, "Use assets_list"),
    ("get_content_details", assets_get, "Use assets_get"),
]
for name, fn, hint in LEGACY_ALIASES:
    mcp.tool(name=name, description=f"{fn.__doc__ or ''} (deprecated: {hint})")(fn)


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

# VAAS MCP Server

Unified MCP server for VAAS material generation, management, and publishing.
A single server replaces the former three (`vaas-mcp`, `vaas-video-assets`, and the
planned `vaas-publish`): generation, publishing, asset queries, and generator
discovery all live here, backed by one SQLite database.

## Install & Start

```bash
cd mcp-server
pip install -e .
python -m mcp_server.main        # MCP stdio server
```

Register in `.mcp.json`:

```json
{ "mcpServers": { "vaas": { "command": "python3",
    "args": ["/path/to/VAAS/mcp-server/mcp_server/main.py"] } } }
```

## Tool namespaces

Tool names use `prefix_` namespaces (MCP tool names forbid dots). The hosted
surface (`VAAS_HOSTED=1`, HTTP transport) exposes **17 tools**; local stdio
adds the 6-tool publish plane for **23 tools** total (publish never ships
multi-tenant — workspace ADR-0004).

| Namespace | Tools |
|---|---|
| `generate_*` | `generate_voice`, `generate_image`, `generate_video_submit` (async submit; poll with `video_job_status`), `models_voices`, `voiceover_assemble`, `reference_clips_check` — cloud lanes dispatch through the generation registry |
| `render_*` | `render_video` — two mutually exclusive modes: `storyboard={size, scenes:[...]}` (deterministic frame-by-frame) or `type` + `script`/`inputs` (HTML scene-builder pipeline, `renderer:"html"` in each `type.json`; identical behavior on hosted and local stdio instances — no node/Remotion needed. `voice_path` skips in-pipeline TTS and apportions segment durations by per-segment char count; `bgm={asset_id\|path, volume?, fade_out?}` matches storyboard semantics; prompt-based images return a `pending_images` list with zero artifacts until retried with `inputs.confirm_images=true`); `render_still` (`kind=cover\|chart\|graphic`); `render_document` (`format=pdf\|longimage`) |
| `templates_*` | `templates_list` / `templates_get` — presentation templates by domain `video\|cover\|doc` |
| `assets_*` | `assets_list`, `assets_stats`, `assets_get` (by `id`/`slug`; `kind=common` lists shared brand assets, `kind=logo` logo/icon only) |
| `registry_*` | `registry_list_generators`, `registry_describe_generator` — generation method discovery (`voice\|image\|video\|cover\|chart\|doc`) |
| `publish_*` (stdio only) | `publish_video`, `publish_article`, `publish_validate_ready`, `publish_get_config`, `publish_simulate`, `publish_record` |

## Generation registry

Generation methods are registered in `mcp-server/registry.json`, grouped by
asset type. Each entry: `{name, provider, model, driver}` — `driver` resolves to
a callable in `mcp_server/registry.py::DRIVERS`. `${ENV_VAR}` in `model` resolves
from `VAAS/.env`.

```json
{
  "video": [
    { "name": "seedance", "provider": "volcengine", "model": "${VIDEO_MODEL}", "driver": "generate_video" },
    { "name": "voiceover", "provider": "local", "model": "remotion", "driver": "create_voiceover" }
  ]
}
```

**Add a generation/copy method**: one `registry.json` entry + one driver line.
No core dispatch changes. `generate_voice(name=...)`, `generate_image(name=...)`
and `generate_video_submit(name=...)` dispatch by name; unknown names error with
the available list.

## Database

Single SQLite at `VAAS/data/vaas.db` — the one source of truth for the skill
chain and the MCP server.

- **`assets`** — generic material tree: `type`, `stage`
  (`draft|rendered|published|failed`), `parent_id`/`lineage_root` (需求 → 主资产 →
  平台变体), `provider`, `file_path`, `metadata`, optional `video_id` link to the
  video detail row.
- **`variants`** — per-platform adaptation (`title/body/tags/cover_path`),
  unique per `(asset_id, platform)`.
- **`distribution`** — publish records, unique per `(asset_id, platform)`, last
  publish wins.
- Video detail tables preserved: `videos`, `tts_records`, `renders`, `tags`,
  `video_tags`, `history`; generic stage log in `asset_history`.

The root `VAAS/vaas.db` (`content`/`distribution`) is **archived** — read-only,
no longer written. Migrate old data once:

```bash
python mcp-server/scripts/migrate_unify_db.py        # idempotent, backs up first
python mcp-server/scripts/migrate_unify_db.py --dry-run
```

## Publishing

Publishing is stdio/local only — the hosted surface excludes the publish plane
(ADR-0004). `publish_video` / `publish_article` run the skill `publish.mjs`
(`.agents/skills/fd-vaas-publish-videos` / `fd-vaas-publish-docs`) as subprocesses.
The skill records successful uploads to `distribution`/`variants` via
`data/db_writer.py`; the MCP wrapper records per-platform variants upfront and
reports publish results by reading the unified DB afterwards (no stdout-JSON
parsing, no double writes). Publishing is **user-confirmed** — never fire-and-forget.

## Development

```bash
pytest tests/
```

Layout: `mcp_server/main.py` (registration), `mcp_server/tools/` (namespace
tool modules), `mcp_server/generators/` (generator wrappers), `mcp_server/skills/`
(orchestration), `mcp_server/registry.py` (generator registry + dispatch),
`mcp_server/db/` (unified store), `mcp_server/utils/` (path/slug helpers).

## License

MIT

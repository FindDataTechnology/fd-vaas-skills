# Tasks

## Phase 1: Foundation (2-3 hours)

### 1.1 Initialize MCP Server Project
- [x] Create `mcp-server/` directory structure
- [x] Initialize Python project with `pyproject.toml`
- [x] Add dependencies: `fastmcp`, `pydantic`, `aiosqlite`, `python-dotenv`
- [x] Create `mcp_server/main.py` with FastMCP entry point

### 1.2 Database Layer
- [x] Implement `mcp_server/db/database.py` — SQLite connection pool + schema init
- [x] Implement `mcp_server/db/models.py` — Content/Distribution CRUD helpers
- [x] Create `vaas.db` at project root with schema from `specs/content-storage/spec.md`

### 1.3 File Manager
- [x] Implement `mcp_server/utils/file_manager.py`
  - [x] `generate_slug(prefix: str) -> str`
  - [x] `get_content_path(type: str, slug: str) -> Path`
  - [x] `validate_slug(slug: str) -> bool`
- [x] Create `downloads/{videos,articles,images,audio,presentations}/` directories

## Phase 2: Generation Tools (3-4 hours)

### 2.1 TTS Wrapper
- [x] Implement `mcp_server/generators/tts.py`
  - [x] `synthesize(text, voice, speed) -> Path` — subprocess call to `litellm-bridge.py tts`
  - [x] Parse JSON output, extract `local_path` and `captions`
- [x] Register `generate_voice` MCP tool in `main.py`

### 2.2 Image Wrapper
- [x] Implement `mcp_server/generators/image.py`
  - [x] `generate(prompt, size, n) -> list[Path]` — subprocess call to `litellm-bridge.py image`
  - [x] Parse JSON output, extract `images[].local_path`
- [x] Register `generate_image` MCP tool in `main.py`

### 2.3 Video Wrapper
- [x] Implement `mcp_server/generators/video.py`
  - [x] `generate(prompt, duration, ratio) -> Path` — subprocess call to `litellm-bridge.py video`
  - [x] Handle async polling (Seedance long-running tasks)
- [x] Register `generate_video` MCP tool in `main.py`

### 2.4 Cover Wrapper
- [x] Implement `mcp_server/skills/cover.py`
  - [x] `create_cover(title, subtitle, orientation, size) -> Path` — subprocess call to `generate-cover.mjs`
  - [x] Map parameters to Remotion CLI args
- [x] Register `create_cover` MCP tool in `main.py`

## Phase 3: Orchestration Tools (4-5 hours)

### 3.1 Voiceover Video Pipeline
- [x] Implement `mcp_server/skills/voiceover.py`
  - [x] `create_voiceover_video(script_path, visuals) -> Path`
  - [x] Call `task-render.mjs` via subprocess
  - [x] Parse output, extract final mp4 path
- [x] Register `create_voiceover_video` MCP tool in `main.py`
- [x] Integrate with DB: insert content record, update status to 'rendered'

### 3.2 Brainstorm Tool
- [x] Implement `mcp_server/skills/brainstorm.py`
  - [x] `brainstorm(mode, topic, audience, brand_context) -> dict`
  - [x] Return structured JSON per `specs/brainstorm/spec.md`
- [x] Register `brainstorm` MCP tool in `main.py`
- [x] No DB insertion (brainstorm output is transient, not persisted)

### 3.3 Publish Orchestrator
- [x] Implement `mcp_server/skills/publish.py`
  - [x] `publish_video(slug, platforms, title, description, tags) -> list[dict]`
    - [x] Look up content by slug (must be type=video, status=rendered)
    - [x] Call `fd-vaas-publish-videos/scripts/publish.mjs` via subprocess
    - [x] Parse output, extract per-platform results
    - [x] Update `distribution` table
  - [x] `publish_article(slug, platforms, title, body, tags) -> list[dict]`
    - [x] Look up content by slug (must be type=article, status=rendered)
    - [x] Call `fd-vaas-publish-docs/scripts/publish.mjs` via subprocess
    - [x] Parse output, extract per-platform results
    - [x] Update `distribution` table
- [x] Register `publish_video` and `publish_article` MCP tools in `main.py`

## Phase 4: Query Tools (1-2 hours)

### 4.1 Content Query
- [x] Implement `mcp_server/skills/query.py`
  - [x] `list_content(type, status, limit) -> list[dict]` — query DB
  - [x] `get_content(id) -> dict` — query DB + join distribution
- [x] Register `list_content` and `get_content` MCP tools in `main.py`

## Phase 5: Testing & Documentation (2-3 hours)

### 5.1 Integration Tests
- [x] Create `tests/test_mcp_server.py`
- [x] Test each MCP tool with mock subprocess calls
- [x] Test DB operations (insert, query, update)
- [x] Test file organization (slug generation, path resolution)

### 5.2 Documentation
- [x] Write `mcp-server/README.md`
  - [x] Installation instructions
  - [x] Configuration (`.env` variables)
  - [x] Usage examples for each MCP tool
- [x] Update `AGENTS.md` with MCP server reference

## Phase 6: Migration & Backward Compatibility (1-2 hours)

### 6.1 Existing Content Migration
- [x] Create `scripts/migrate_task_json_to_db.py`
  - [x] Scan `downloads/fd-videos/*/task.json`
  - [x] Insert records into `content` table
  - [x] Map `task.json` fields to DB schema
- [x] Run migration script, verify DB contents

### 6.2 Backward Compatibility
- [x] Ensure existing `task.json` / `meta.json` files remain functional
- [x] MCP tools can read from both DB and legacy JSON files
- [x] Document migration path in README

---

## Total Estimated Time: 13-19 hours

## Success Criteria

- [x] All 10 MCP tools registered and callable
- [x] SQLite DB tracks all generated content
- [x] File organization follows `specs/content-storage/spec.md`
- [x] Existing skills (`fd-vaas-video-creator`, `fd-vaas-publish-*`) remain functional
- [x] Integration tests pass
- [x] README documentation complete

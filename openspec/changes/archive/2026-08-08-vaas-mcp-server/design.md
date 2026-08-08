# Design: VAAS MCP Server

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    VAAS MCP Server (Python/FastMCP)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tools Layer                                                    │
│  ├── generate_voice(text, voice, speed) → audio path            │
│  ├── generate_image(prompt, size, n) → image paths[]            │
│  ├── generate_video(prompt, duration, ratio) → video path       │
│  ├── create_cover(title, orientation, size) → image path        │
│  ├── create_voiceover_video(script, visuals) → video path       │
│  ├── generate_ppt(source) → pptx path                           │
│  ├── brainstorm(topic, mode) → structured plan                  │
│  ├── publish_video(slug, platforms[]) → results[]               │
│  ├── publish_article(slug, platforms[]) → results[]             │
│  ├── list_content(type, status) → items[]                       │
│  └── get_content(slug) → detail + distribution[]                │
│                                                                 │
│  Generators Layer (subprocess wrappers)                         │
│  ├── tts.py → litellm-bridge.py tts                             │
│  ├── image.py → litellm-bridge.py image                         │
│  ├── video.py → litellm-bridge.py video                         │
│  ├── cover.py → remotion still (via subprocess)                 │
│  └── voiceover.py → task-render.mjs (via subprocess)            │
│                                                                 │
│  Publish Layer (subprocess wrappers)                            │
│  ├── publish_video.py → fd-vaas-publish-videos/publish.mjs      │
│  └── publish_article.py → fd-vaas-publish-docs/publish.mjs      │
│                                                                 │
│  Database Layer (SQLite)                                        │
│  ├── database.py → connection + schema init                     │
│  └── models.py → Content / Distribution CRUD                    │
│                                                                 │
│  File Manager Layer                                             │
│  └── file_manager.py → slug generation, path resolution, writes │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Python over Node.js

**Decision**: Use Python (FastMCP) for the MCP server.

**Rationale**:
- litellm-bridge.py is already Python → direct integration, no subprocess overhead
- ppt-master is Python → reuse existing code
- SQLite ecosystem is mature in Python (aiosqlite for async)
- ego-browser/patchright automation stays as Node.js/Python subprocess calls (reuse existing scripts)

**Tradeoff**: Some Node.js wrappers (tts-wrapper.js, seedream-wrapper.js, seedance-wrapper.js) need subprocess calls. Acceptable because:
- These are already CLI tools with JSON output
- Subprocess overhead is negligible compared to API latency (5-15s)
- Alternative (rewriting in Python) is more work for no user benefit

### 2. SQLite over Postgres

**Decision**: Use SQLite with a single `vaas.db` file.

**Rationale**:
- VAAS is a local tool (single user, single machine)
- No need for multi-user concurrency
- Zero configuration (no server setup)
- File-based backup (just copy vaas.db)
- Fast enough for thousands of records

**Tradeoff**: Can't scale to multi-user. Upgrade path: migrate to Postgres when needed (schema is portable).

### 3. File Organization: By Type (not by Project)

**Decision**: Organize `downloads/` by content type (videos/, articles/, images/, etc.), not by project.

**Rationale**:
- Matches current structure (fd-videos/, fd-docs/) → minimal migration
- Easier to query by type (all videos, all articles)
- Simpler path resolution (type + slug → deterministic path)
- Aligns with how users think ("show me all videos")

**Tradeoff**: Can't easily see "all content for project X". Mitigation: DB metadata can track project associations (future enhancement).

### 4. Brainstorm as Structured Prompt (not API)

**Decision**: `brainstorm` tool returns structured JSON template; LLM reasoning happens in Claude.

**Rationale**:
- Brainstorm is pure LLM reasoning (no external API calls)
- MCP tool provides structured input/output schema
- Claude fills in the content based on prompt engineering
- No need to build a separate LLM service

**Tradeoff**: Brainstorm can't be called from outside Claude. Acceptable because it's a planning tool, not a production pipeline.

### 5. Synchronous over Asynchronous (for now)

**Decision**: All MCP tools are synchronous (block until complete).

**Rationale**:
- Simpler implementation (no queue, no polling)
- MCP protocol supports long-running tools (client handles timeout)
- Video generation takes 5-15s anyway → acceptable
- Can add async later if needed (queue + status polling)

**Tradeoff**: Long operations block the MCP client. Mitigation: Claude can show progress messages. Upgrade path: add async queue when performance becomes an issue.

## Component Details

### Database Schema

```sql
-- Content table: all generated content
CREATE TABLE content (
    id TEXT PRIMARY KEY,              -- UUID
    type TEXT NOT NULL,               -- video | article | image | audio | presentation
    slug TEXT UNIQUE NOT NULL,        -- human-readable ID (e.g., "finddata-brand-2026")
    file_path TEXT NOT NULL,          -- relative to downloads/ (e.g., "videos/finddata-brand-2026/finddata-brand-2026.mp4")
    metadata JSON,                    -- structured metadata (task.json equivalent)
    status TEXT DEFAULT 'draft',      -- draft | rendered | published | failed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_content_type_status ON content(type, status);
CREATE INDEX idx_content_slug ON content(slug);

-- Distribution table: platform publish records
CREATE TABLE distribution (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id TEXT NOT NULL,         -- FK → content.id
    platform TEXT NOT NULL,           -- douyin | xiaohongshu | zhihu | ...
    url TEXT,                         -- publish URL (if available)
    status TEXT DEFAULT 'pending',    -- pending | publishing | success | failed
    error_message TEXT,
    published_at TEXT,
    FOREIGN KEY (content_id) REFERENCES content(id) ON DELETE CASCADE
);

CREATE INDEX idx_distribution_content ON distribution(content_id);
CREATE INDEX idx_distribution_platform ON distribution(platform);
```

### File Manager

```python
# mcp_server/utils/file_manager.py

def generate_slug(prefix: str) -> str:
    """Generate unique slug: prefix-YYYYMMDD-HHMMSS"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}"

def resolve_path(type: str, slug: str, filename: str = None) -> Path:
    """Resolve absolute path under downloads/<type>/<slug>/"""
    base = VAAS_ROOT / "downloads" / type / slug
    if filename:
        return base / filename
    return base

def ensure_directory(type: str, slug: str) -> Path:
    """Create directory if not exists, return path"""
    path = resolve_path(type, slug)
    path.mkdir(parents=True, exist_ok=True)
    return path
```

### Generator Wrappers

```python
# mcp_server/generators/tts.py

def synthesize(text: str, voice: str = None, speed: float = 1.0) -> dict:
    """Call litellm-bridge.py tts, return {audio_path, captions_path, duration_ms}"""
    slug = generate_slug("audio")
    output_dir = ensure_directory("audio", slug)
    audio_path = output_dir / f"{slug}.mp3"
    captions_path = output_dir / f"{slug}-captions.json"
    
    cmd = [
        "python", str(SCRIPTS_DIR / "litellm-bridge.py"), "tts",
        "--text", text,
        "--output", str(audio_path),
        "--captions", str(captions_path)
    ]
    if voice:
        cmd.extend(["--voice", voice])
    if speed != 1.0:
        cmd.extend(["--speed", str(speed)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"TTS failed: {result.stderr}")
    
    output = json.loads(result.stdout)
    return {
        "slug": slug,
        "audio_path": str(audio_path.relative_to(VAAS_ROOT / "downloads")),
        "captions_path": str(captions_path.relative_to(VAAS_ROOT / "downloads")) if captions_path.exists() else None,
        "duration_ms": output.get("audio_duration_ms")
    }
```

### Voiceover Video Pipeline

```python
# mcp_server/skills/voiceover.py

def create_voiceover_video(script_path: str, visuals: dict = None) -> dict:
    """Orchestrate TTS + captions + Remotion render"""
    slug = generate_slug("video")
    task_dir = ensure_directory("videos", slug)
    
    # 1. Create task directory (reuse existing new-task.mjs)
    subprocess.run([
        "node", str(VIDEO_CREATOR_SCRIPTS / "new-task.mjs"),
        "--slug", slug,
        "--script", script_path
    ], check=True)
    
    # 2. Run full pipeline (TTS → fix-timings → preflight → render)
    subprocess.run([
        "node", str(VIDEO_CREATOR_SCRIPTS / "task-render.mjs"),
        "--slug", slug
    ], check=True)
    
    # 3. Read task.json for metadata
    task_json = json.loads((task_dir / "task.json").read_text())
    
    # 4. Insert into DB
    content_id = db.insert_content(
        type="video",
        slug=slug,
        file_path=f"videos/{slug}/{slug}.mp4",
        metadata=task_json,
        status="rendered"
    )
    
    return {
        "id": content_id,
        "slug": slug,
        "file_path": f"videos/{slug}/{slug}.mp4",
        "duration_sec": task_json.get("render", {}).get("totalDurationSec"),
        "status": "rendered"
    }
```

### Publish Orchestrator

```python
# mcp_server/skills/publish.py

def publish_video(slug: str, platforms: list[str] = None) -> dict:
    """Call fd-vaas-publish-videos/publish.mjs, parse output, update DB"""
    if platforms is None:
        platforms = env.get("PLATFORMS", "douyin,xiaohongshu").split(",")
    
    cmd = [
        "node", str(PUBLISH_VIDEOS_SCRIPTS / "publish.mjs"),
        "--slug", slug,
        "--platforms", ",".join(platforms)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Publish failed: {result.stderr}")
    
    # Parse output (publish.mjs prints JSON)
    output = json.loads(result.stdout)
    
    # Update DB
    content_id = db.get_content_by_slug(slug).id
    for platform_result in output.get("results", []):
        db.insert_distribution(
            content_id=content_id,
            platform=platform_result["platform"],
            url=platform_result.get("url"),
            status=platform_result.get("status", "success"),
            error_message=platform_result.get("error")
        )
    
    # Update content status
    db.update_content_status(content_id, "published")
    
    return output
```

## Migration Strategy

### Phase 1: Foundation (no breaking changes)

1. Create `mcp-server/` directory with FastMCP skeleton
2. Implement DB schema + file manager
3. Add 3 generator wrappers (tts, image, video)
4. **Existing skills continue to work** (no changes to them)

### Phase 2: Skills Integration

1. Add cover.py, voiceover.py, brainstorm.py
2. Add publish_video.py, publish_article.py
3. **Existing skills still work** (MCP is additive)

### Phase 3: Migration (optional, future)

1. Update skill SKILL.md files to reference MCP tools
2. Gradually deprecate direct script calls
3. **No forced migration** (users can choose MCP or direct scripts)

## Security Considerations

1. **Path Traversal**: All file paths validated via `file_manager.resolve_path()` (no `../` allowed)
2. **SQL Injection**: Use parameterized queries (SQLite ORM pattern)
3. **Subprocess Injection**: Use `subprocess.run(cmd_list)` (not shell=True)
4. **API Keys**: Read from `.env` (already gitignored)

## Performance Considerations

1. **Subprocess Overhead**: Negligible (API latency dominates)
2. **DB Queries**: Indexed on (type, status) and slug → fast lookups
3. **File I/O**: Sequential writes (no concurrent access needed)

## Future Enhancements (Out of Scope for v1)

- Async queue for long-running operations
- Project-level grouping (tag content by project)
- Analytics dashboard (query DB for stats)
- Multi-user support (migrate to Postgres)
- Webhook notifications on publish completion

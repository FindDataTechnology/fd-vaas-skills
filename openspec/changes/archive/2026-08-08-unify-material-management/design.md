## Context

当前 VAAS 是「skill 主线 + MCP 壳」两层结构：

- **skill 主线**（`.agents/skills/fd-vaas-*`，Node.js `.mjs` + Python `.py`）：`video-creator` 产出 `downloads/fd-videos/<slug>/`（task.json + mp4 + srt），`publish-videos`（6 视频平台，ego-browser/patchright 双运行时）与 `publish-docs`（9 图文平台，instruction-driven）分发；发布成功后 `publish.mjs` 调 `data/db_writer.py` 写入 `data/vaas.db`。
- **MCP 服务器 ×3**：`vaas-mcp`（`mcp-server/`，10 工具，生成+发布+查询，写根 `vaas.db`）、`vaas-video-assets`（`.claude/mcp/vaas-assets-server.py`，素材发现+查询，读 `data/vaas.db`）、规划中的 `vaas-publish`（`mcp-publish-pipeline` 变更）。

**三个已知断裂点**：
1. 两个 SQLite 库互不同步（见 proposal）。根 `vaas.db` 只有 15 条 content、0 分发；`data/vaas.db` 有 11 videos、41 distributions、完整 tts/renders/tags 明细。
2. 三个 MCP server 职责重叠，且每个工具都是「subprocess 包脚本再包脚本」。
3. 生成器双轨：`scripts/generators/{tts,seedream,seedance}.js`（最大 41K 单文件）vs 根 `scripts/litellm-bridge.py` + `_volcengine_*.py`，同一 Volcengine 能力实现两遍。

## Goals / Non-Goals

**Goals:**
- 一个数据库作为物料唯一事实来源，skill 链路与 MCP 都写它。
- 资产血缘树：需求 → 主资产 → 平台变体，可查询、可追溯。
- 单一 MCP 服务器，工具按命名空间分区，替代三个旧 server。
- Provider 注册表：新增生成/文案方式 = 注册 + 适配器，不写巨型 wrapper。
- 保留已验证的平台驱动（.mjs/.py）不动。

**Non-Goals:**
- 不重写各平台上传脚本（`platforms/*.mjs` / `*.py` 保持现状）。
- 不实现 OAuth、云端同步、多人协作。
- 不改动 Remotion 渲染管线本身。
- 不在一期实现 UI 物料管理界面（MCP 查询工具优先，dashboard 后续接统一库）。

## Decisions

### 决策 1：统一 schema — 以 data/vaas.db 为基底泛化

`data/vaas.db` 已含视频域的丰富明细（videos/tts_records/renders/distributions/tags/history），根 `vaas.db` 只有泛型 content。选前者为基底，加一层**泛型资产表**覆盖文章/图片/音频/PPT 等非视频物料，保持视频明细表不变（既有 11 条数据不动）。

```sql
-- 资产表(泛型,物料树的节点)
CREATE TABLE assets (
    id            TEXT PRIMARY KEY,            -- 统一 id(沿用 slug 作为业务键)
    slug          TEXT UNIQUE NOT NULL,
    type          TEXT NOT NULL,               -- video|article|image|audio|presentation|cover|copy
    stage         TEXT NOT NULL DEFAULT 'draft', -- draft→rendered→published→failed
    title         TEXT,
    parent_id     TEXT REFERENCES assets(id),  -- 血缘:需求→主资产→变体
    lineage_root  TEXT,                        -- 冗余根 id,便于整树查询
    provider      TEXT,                        -- 哪个 provider/方式生成
    file_path     TEXT,
    metadata      JSON,                        -- 生成参数快照(voice/model/分辨率…)
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_assets_lineage  ON assets(lineage_root, stage);
CREATE INDEX idx_assets_type     ON assets(type, created_at);

-- 平台变体表(每平台适配版本)
CREATE TABLE variants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    platform    TEXT NOT NULL,
    title       TEXT,
    body        TEXT,        -- 图文正文/视频描述
    tags        TEXT,        -- JSON 数组
    cover_path  TEXT,
    extra       JSON,
    UNIQUE(asset_id, platform)
);

-- 发布记录(沿用现 distribution 语义)
CREATE TABLE distribution (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id      TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    platform      TEXT NOT NULL,
    url           TEXT,
    status        TEXT DEFAULT 'pending',   -- pending|uploaded|failed
    error_message TEXT,
    published_at  TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
-- 视频明细表(videos/tts_records/renders/tags/history)原样保留,加 assets.video_id 引用
```

- 旧 `videos` 表通过 `assets.video_id` 关联：一条资产可选挂接一张明细表，避免把视频特有字段塞进泛型表。
- 根 `vaas.db` 的 `content` 表数据迁移进 `assets`（type 映射：video/article/image/audio/presentation），`distribution` 并入。

### 决策 2：血缘与 stage 状态机

- **血缘**：`parent_id` 组成树。典型链路 `demand(可选) → 主资产 → 变体`。`lineage_root` 冗余根 id，一次查询拉整树（如「这条需求的所有变体」）。
- **stage 状态机**：`draft → rendered → published`，失败置 `failed`。stage 变化写 `history` 表（沿用现表），任何工具/skill 都可查物料当前所处阶段。
- **变体何时生成**：`publish` 前的平台适配（标题/正文/封面/标签）写入 `variants`，发布后回填 `distribution.url`。这样「这条内容在抖音 vs 小红书长什么样」可回查。

### 决策 3：单一 MCP 服务器

- 以 `mcp-server/` 为唯一宿主（FastMCP/Python 已成熟、有测试）。工具按命名空间分区，物理一个 server、`.mcp.json` 一条 `vaas` 注册。
- 命名空间与现有工具的映射：

| 命名空间 | 工具 | 来源 |
|---|---|---|
| `generate.*` | voice / image / video / cover | vaas-mcp(现) |
| `orchestrate.*` | voiceover / brainstorm / article | vaas-mcp(现) |
| `publish.*` | video / docs | vaas-mcp(现,发布走 skill publish.mjs) |
| `assets.*` | list / get / variants / lineage / stats | vaas-mcp(现) + vaas-video-assets(并入) |
| `registry.*` | list_generators / describe_generator | 新增 |

- **向后兼容**：旧工具名保留为命名空间工具（`generate_voice` 同时存在 `generate.voice`），别名层薄薄一层，标注 deprecated，一期后移除。
- `vaas-video-assets` 的素材发现工具（`list_common_assets`/`find_logo`/`list_compositions`/`get_scene_templates`）并入 `assets.*`，原 server 移除。
- `mcp-publish-pipeline` 变更**改道**：不新建 `vaas-publish-server.py`，把它的 orchestration 需求并入 `publish.*`，DB 写入统一库。

### 决策 4：Provider 注册表（生成方式的扩展点）

生成方式注册为可枚举条目，`generate.*` 按名查表调度：

```json
// registry 条目(存 .env / 配置文件,不写库)
{
  "video": [
    { "name": "seedance", "provider": "volcengine", "model": "doubao-seedance-2.0", "driver": "video/volcengine.py" },
    { "name": "voiceover", "provider": "local", "model": "remotion", "driver": "video/voiceover.py" }
  ],
  "copy": [
    { "name": "brainstorm", "provider": "llm", "model": "claude", "driver": "copy/brainstorm.py" }
  ]
}
```

- 适配器接口（Python，最小）：`generate(params) -> AssetResult`，一个 driver 文件对一种「方式×provider」。
- 现存 JS wrapper（`seedance.js`/`seedream.js`/`tts.js`）作为 driver 的底层被调用（subprocess），**不重写逻辑**，只换壳收敛。
- `registry.list_generators(type)` 让任何客户端（Claude/脚本）可发现「现在有哪些生成方式」——这就是「之后加更多视频/文案方式」的落点。

### 决策 5：单一 writer，skill 层不动

- 写库统一走 `mcp_server/db/`（Python sqlite3 封装）：skill 的 `db_writer.py` 改为调用同一封装（或保留其 CLI 但指向统一库路径+schema）。
- `.mjs`/`.py` 平台驱动、`task.json` 目录约定**全部保留**；`assets.file_path` 指向同一物理文件。skill 是执行层，库是记录层，二者解耦。

### 决策 6：迁移与验证

- 一次性迁移脚本 `mcp-server/scripts/migrate_unify_db.py`：`data/vaas.db`（videos→assets + video_id 关联）→ 新库；根 `vaas.db` content→assets；幂等、可重跑；迁移前自动备份旧库。
- 验证：迁移后 `assets` 总数 = 两旧库去重后总数；抽查某 slug 的血缘树完整；既有 11 条视频的 distributions 全部落入新 `distribution` 表。

## Risks / Trade-offs

- **schema 泛化 vs 视频特有字段**：用 `assets.video_id` 外挂明细表而非把全部字段塞进 assets——换得泛型表干净，代价是查询视频详情需 join。可接受（视频查询路径单一）。
- **迁移破坏性**：根 `vaas.db` 废弃是 BREAKING。用备份+幂等脚本+校验步骤兜底；`vaas-video-assets` 的 `query_videos`/`get_publish_stats` 在并入 assets.* 时同步切到新库，避免过渡期双读。
- **命名空间工具 vs 旧工具名的别名层**：短期维护双名，是平滑迁移的代价；一期后删除旧名，不留长期债。
- **Provider 注册表"配置化 vs 写代码"**：`generate.*` 的 driver 仍需写少量适配代码（注册一行 + 适配器），无法做到纯改 .env。这是「可扩展性 vs 零代码」的取舍，文档里写清楚。
- **skill 与 MCP 双写同一库的竞态**：SQLite 单写者 + 短事务，且 publish 是低频串行操作；同平台已要求串行，风险低。

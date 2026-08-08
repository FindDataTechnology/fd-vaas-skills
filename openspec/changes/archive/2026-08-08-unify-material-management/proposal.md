## Why

当前 VAAS 存在三处结构性割裂，直接阻碍「物料生成和管理」这一目标：**两个互不同步的 SQLite 数据库**（skill 链路写 `data/vaas.db`，MCP server 写根 `vaas.db`，查询结果永远残缺）、**三个职责重叠的 MCP 服务器**（`vaas-mcp`、`vaas-video-assets`、规划中的 `vaas-publish`）、以及**无资产血缘模型**（无法表达「一个需求 → 主资产 → 各平台变体」，发布后的平台适配版本丢失）。同时生成器双轨（JS 巨型 wrapper 与 Python bridge 各实现一遍 Volcengine），新增一种生成方式成本极高。

## What Changes

- **统一物料数据库**：合并 `data/vaas.db`（丰富 schema）与根 `vaas.db`（泛型 content），以 `data/vaas.db` 为基底泛化为单一 schema；提供一次性迁移脚本，此后只有唯一 writer。
- **资产血缘模型**：新增 `assets` 树（`parent_id` 表达 需求→主资产→平台变体）+ `variants` 表（每平台标题/正文/封面/标签的适配版本）+ 统一的 `stage` 状态机（draft→rendered→published→failed）。
- **单一 MCP 服务器**：合并三个 server 为一个（FastMCP/Python），工具按命名空间分区 `generate.*` / `orchestrate.*` / `publish.*` / `assets.*` / `registry.*`；所有生成与发布写入同一数据库。
- **Provider 注册表**：生成方式注册为 `{name, provider, model, driver}`，`generate.*` 按名查表；新增一种生成/文案方式 = 注册一行 + 一个适配器，不再写巨型 wrapper。
- **保留 skill 层不动**：`.mjs`/`.py`（ego-browser/patchright 平台驱动）已验证可用，作为底层保留；skill 与 MCP 都读写同一数据库，不推倒重来。
- **BREAKING**：根 `vaas.db` 的 `content`/`distribution` 表废弃，数据迁入统一库；`.mcp.json` 中三个 server 条目合并为一个。

## Capabilities

### New Capabilities
- `material-store`: 统一 SQLite schema（assets 血缘树、variants 平台变体、distribution 发布记录、history）、单一 writer、一次性迁移、资产查询（list/get/variants/lineage）
- `generation-registry`: 生成方式注册表（provider 适配器、model 清单、可发现性），支撑「更多视频生成方式、文案编辑方式」的横向扩展
- `unified-mcp-interface`: 单一 MCP 服务器 + 命名空间化工具面，合并三个旧 server 的工具并保持向后兼容

### Modified Capabilities
<!-- 无现有 spec(openspec/specs/ 为空),全部为新增 -->

## Impact

- **数据库**：`data/vaas.db` 扩展 schema（新表：assets/variants/stage 迁移）；根 `vaas.db` 废弃；迁移脚本从旧库导入。
- **MCP**：`.mcp.json` 合并为单一 `vaas` server；`mcp-server/mcp_server/` 重构为命名空间包；`.claude/mcp/vaas-assets-server.py` 工具并入后被移除；进行中的 `mcp-publish-pipeline` 变更改道为调用统一库。
- **生成器**：`scripts/generators/`（JS）与根 `scripts/litellm-bridge.py` + `_volcengine_*.py`（Python）收敛为 provider 适配器。
- **Skill 链路**：`.agents/skills/fd-vaas-*` 保持不变，`db_writer.py` 改用统一库；`fd-vaas-publish-docs` 的 `--record` 与视频发布同时写 `distribution`。
- **文件组织**：`downloads/<type>/<slug>/` 目录约定保留，成为 assets 表 `file_path` 的物理落点。

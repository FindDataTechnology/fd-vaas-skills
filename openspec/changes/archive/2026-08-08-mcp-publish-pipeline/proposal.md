## Why

当前发布流程依赖 `.agents/skills/fd-vaas-publish-videos/scripts/publish.mjs`（Node.js 脚本），与 MCP 架构割裂。用户希望所有功能都走 MCP，统一接口、便于扩展和跨工具调用。同时需要修复字幕位置定位问题（字幕显示在屏幕中间而非底部）。

## What Changes

- **新增 `vaas-publish` MCP 服务器**：替代 `publish.mjs`，提供发布编排工具
- **新增 `validate_publish_ready` MCP 工具**：发布前检查视频、封面、状态是否就绪
- **新增 `get_publish_config` MCP 工具**：读取发布配置（标题、标签、描述）
- **新增 `simulate_publish` MCP 工具**：dry-run 模拟发布，不实际上传
- **新增 `record_distribution` MCP 工具**：发布成功后写入 SQLite 数据库
- **修复字幕位置 bug**：字幕组件使用 `position: absolute; bottom: 60px; top: auto` 但实际渲染时仍显示在中间，需要修复定位逻辑
- **BREAKING**：`publish.mjs` 标记为废弃，改为调用 MCP 工具
- 保留 `publish.mjs` 作为过渡（调用 MCP），最终完全移除

## Capabilities

### New Capabilities
- `mcp-publish-orchestration`: MCP 驱动的多平台发布编排能力，包括发布前检查、配置读取、模拟发布、数据库记录
- `subtitle-positioning`: 字幕定位修复能力，确保字幕始终显示在视频底部

### Modified Capabilities
<!-- 无现有 capability 需要修改 -->

## Impact

- **新增文件**：
  - `.claude/mcp/vaas-publish-server.py` - 发布编排 MCP 服务器
  - `.mcp.json` - 注册新的 publish 服务器
- **修改文件**：
  - `remotion-app/src/CostRevolution.tsx` - 修复字幕定位 bug
  - `.agents/skills/fd-vaas-publish-videos/scripts/publish.mjs` - 标记为过渡层
- **数据库**：`data/vaas.db` 的 `distributions` 表将被 MCP 工具直接写入
- **依赖**：FastMCP 3.4.2（已安装）
- **平台兼容性**：macOS 走 ego-browser，Windows 走 patchright（保持原有运行时派发逻辑）

---

> **归档说明（2026-08-08）**：本变更 0/20 未实施即被取代。发布编排能力已并入统一 MCP 服务器的 `publish_*` 工具（见 `archive/2026-08-08-unify-material-management` 设计决策 D3）；字幕定位修复已存在于 `remotion-app/src/CostRevolution.tsx`（`SubtitleBar` 使用 `bottom={60}`）。归档仅保留记录。

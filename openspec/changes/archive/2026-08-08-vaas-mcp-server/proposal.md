# VAAS MCP Server - 统一内容生成与发布平台

## Summary

将现有的 VAAS skills（视频生成、图片生成、音频生成、封面生成、PPT 生成、口播视频制作、图文发布、视频发布、头脑风暴）全部封装为 MCP (Model Context Protocol) server 的 tools，并引入 SQLite 数据库追踪所有生成内容的元数据和发布状态。

## Motivation

**当前问题：**
1. **Skills 分散**：10+ 个 Claude Code skills 各自独立，调用方式不统一（有的是 Node.js 脚本，有的是 Python，有的是纯 prompt）
2. **状态管理靠文件**：每个视频/文章用 `task.json` 或 `meta.json` 记录状态，查询和统计困难
3. **无全局视图**：没有统一的地方查看所有已生成的内容、发布状态、历史记录
4. **跨 skill 编排复杂**：从 brainstorm → video-creator → publish 需要手工串联

**目标：**
- 统一接口：所有生成/发布能力通过 MCP tools 暴露，Claude 直接调用
- 统一存储：SQLite 数据库记录所有内容元数据，支持查询和统计
- 统一目录：`downloads/` 按内容类型组织，路径存数据库
- 自动化流水线：brainstorm → generate → publish 可一键串联

## Requirements

### 核心功能

1. **MCP Server 实现**
   - 使用 Python + FastMCP 框架
   - 暴露 10+ 个 tools（见 design.md）
   - 支持同步和异步操作

2. **数据库集成**
   - SQLite 数据库（`vaas.db`）
   - `content` 表：存储所有内容元数据
   - `distribution` 表：记录各平台发布状态
   - 自动回写：生成/发布后自动更新数据库

3. **文件组织**
   - 按类型分目录：`videos/`, `articles/`, `images/`, `audio/`, `presentations/`
   - 每个内容一个 slug 子目录
   - 所有路径相对 `downloads/` 根目录

4. **现有能力迁移**
   - TTS/图片/视频生成：复用 `litellm-bridge.py` 和 `_volcengine_*.py`
   - 封面生成：调用 Remotion 脚本（subprocess）
   - 口播视频：调用 `task-render.mjs` pipeline
   - 发布：调用 `publish.mjs`（视频/图文）
   - 头脑风暴：纯 prompt 结构化输出

### 非目标（Non-goals）

- **不重写现有脚本**：通过 subprocess 调用现有 Node.js/Python 脚本，避免重复实现
- **不支持多用户**：SQLite 单文件，本地单用户使用
- **不做 Web UI**：MCP tools 供 Claude 调用，不提供独立 Web 界面
- **不替换 ego-browser**：浏览器自动化仍用现有方案（ego-browser/patchright）

## Technical Approach

### 架构选型

**Python + FastMCP**
- 理由：litellm-bridge 和 ppt-master 已是 Python；SQLite 生态成熟；FastMCP 是官方推荐的 Python MCP 框架
- 现有 Node.js 脚本通过 subprocess 调用

**SQLite**
- 理由：零配置、单文件、本地工具够用
- 表结构：`content` + `distribution` 两表

**文件夹组织**
- 按内容类型分：`downloads/{videos,articles,images,audio,presentations}/<slug>/`
- 保持与现有 `fd-videos/` 和 `fd-docs/` 的兼容性（可软链接或迁移）

### 关键设计决策

1. **Subprocess 调用 vs 重写**
   - 选择：subprocess 调用现有脚本
   - 理由：避免重复实现，保持向后兼容，降低风险
   - 代价：启动开销（每次 spawn 进程）

2. **同步 vs 异步**
   - 选择：先做同步，观察性能再优化
   - 理由：Remotion 渲染和 TTS 本身是阻塞操作，异步收益有限
   - 未来：如需并发，可加任务队列

3. **Brainstorm 作为 MCP tool**
   - 选择：返回结构化 JSON，LLM 推理由 Claude 执行
   - 理由：brainstorm 本质是 prompt engineering，不是独立服务
   - 实现：MCP tool 只定义输入输出 schema，不内部调 LLM API

## Success Criteria

1. **功能完整性**
   - 所有现有 skills 的能力都能通过 MCP tools 调用
   - 生成/发布后数据库自动更新
   - 能查询所有历史内容和发布状态

2. **性能可接受**
   - MCP tool 调用延迟 < 100ms（不含实际生成时间）
   - 数据库查询响应 < 50ms

3. **向后兼容**
   - 现有 skills 仍可独立使用（不破坏现有工作流）
   - 文件系统结构与现有 `task.json` 兼容

4. **用户体验**
   - Claude 能直接调用 MCP tools，无需手工拼接命令
   - 生成内容自动入库，无需手工记录

## Risks & Mitigations

| 风险 | 影响 | 缓解 |
|------|------|------|
| subprocess 调用开销 | 每次调用 spawn 进程 ~100-500ms | 可接受；如需优化，可改为常驻进程 |
| ego-browser 仅 macOS | Windows 无法发布视频 | 保留 patchright fallback；MCP 内部判断系统自动路由 |
| Remotion 渲染阻塞 | 长视频渲染可能阻塞 MCP server | 先做同步版本；未来可加任务队列 |
| PPT Master 复杂流程 | 多角色协作难以封装为单 API | MCP tool 只负责启动 pipeline，状态由用户跟踪 |
| 数据库迁移 | 现有 `task.json` 数据需迁移 | 提供迁移脚本；或保持双写（task.json + DB）过渡 |

## Open Questions

1. **文件夹迁移**：是否将现有 `fd-videos/` 和 `fd-docs/` 迁移到新结构？还是保持双轨？
2. **双写策略**：过渡期是否同时写 `task.json` 和数据库？
3. **异步需求**：是否有明确的并发场景需要异步任务队列？

## Dependencies

- **Python 3.10+**
- **FastMCP** (MCP server 框架)
- **SQLite** (数据库)
- **现有脚本**：`litellm-bridge.py`, `task-render.mjs`, `publish.mjs`, `generate-cover.mjs`
- **Node.js 18+** (Remotion, ego-browser)
- **Volcengine API keys** (TTS/图片/视频生成)

## Timeline Estimate

- **Phase 1** (基础框架 + DB): 1-2 小时
- **Phase 2** (生成器 wrapper): 2-3 小时
- **Phase 3** (Skills 编排): 3-4 小时
- **Phase 4** (MCP registration + 测试): 1-2 小时
- **总计**: 7-11 小时

## References

- [MCP Protocol](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- 现有 skills: `fd-vaas-video-creator`, `fd-vaas-publish-videos`, `fd-vaas-publish-docs`, `fd-cover-image`, `ppt-master`, `fd-vaas-brainstorm`

---

> **归档说明（2026-08-08）**：本变更 78/78 已完成。其旧 spec（content-storage/generation/publishing/brainstorm）**未**同步进主 specs——物料模型已由 `archive/2026-08-08-unify-material-management` 重构（content 表 → assets 树），主 specs 以新模型为准。

## Context

当前 VAAS 项目的发布流程通过 `.agents/skills/fd-vaas-publish-videos/scripts/publish.mjs` 实现，它：
1. 读取 `task.json` 获取视频路径和发布记录
2. 按 `PLATFORMS` 配置调用各平台上传脚本（macOS ego-browser / Windows patchright）
3. 每次成功后 append 到 `task.json` 的 `distribution[]`

用户已完成数据迁移到 SQLite（`data/vaas.db`），并创建了 `vaas-video-assets` MCP 服务器用于素材发现。现在希望发布流程也走 MCP，统一接口。

同时存在字幕定位 bug：字幕组件设置了 `bottom: 60px` 但实际渲染在屏幕中间。

## Goals / Non-Goals

**Goals:**
- 所有发布编排逻辑通过 MCP 工具暴露，可通过对话直接调用
- 发布成功后自动写入 SQLite 数据库（替代 task.json）
- 修复字幕定位 bug，确保字幕在视频底部
- 保持跨平台兼容性（macOS ego-browser / Windows patchright）
- publish.mjs 作为过渡层调用 MCP，平滑迁移

**Non-Goals:**
- 不重写各平台上传脚本（`platforms/*.mjs` 和 `*.py` 保持不变）
- 不实现 OAuth 或云端同步
- 不改动 Remotion 渲染流程
- 不实现自动发布（仍需用户确认）

## Decisions

### 决策 1：MCP 服务器用 FastMCP（Python）而非 Node.js
**理由**：已有 `vaas-assets-server.py` 用 FastMCP，复用 SQLite 生态（Python sqlite3 内置）。FastMCP 3.4.2 已安装且测试通过。
**备选**：用 Node.js MCP SDK。放弃：需要额外安装依赖，与数据库工具链不统一。

### 决策 2：publish.mjs 作为过渡层而非立即移除
**理由**：各平台上传脚本（`platforms/*.mjs`）已稳定运行，直接调用 MCP 会增加迁移风险。publish.mjs 改为调用 MCP 的 `record_distribution` 工具，保持向后兼容。
**备选**：完全移除 publish.mjs，MCP 直接调用上传脚本。放弃：迁移成本高，且 MCP 不擅长长时间运行的子进程编排。

### 决策 3：MCP 工具职责划分
| MCP 工具 | 职责 | 输入 | 输出 |
|---------|------|------|------|
| `validate_publish_ready` | 检查视频/封面/状态 | slug | 就绪状态 |
| `get_publish_config` | 读取发布配置 | slug | 标题/标签/描述 |
| `simulate_publish` | dry-run 模拟 | slug, platforms | 模拟结果 |
| `record_distribution` | 写入数据库 | slug, platform, account, title | 成功/失败 |

**理由**：工具粒度细分，便于对话中灵活组合。`record_distribution` 独立出来，让 publish.mjs 调用而非 MCP 调用上传脚本。

### 决策 4：字幕定位修复方案
**问题根因**：`AbsoluteFill` 组件默认 `display: flex; align-items: center`，覆盖了 `bottom` 定位。即使设置 `top: auto` 和 `bottom: 60px`，flex 布局仍把内容居中。

**修复方案**：字幕组件外层用普通 `<div>`（非 AbsoluteFill），设置 `position: absolute; bottom: 60px; left: 0; right: 0`。字幕组件在 Sequence 之后渲染，确保 z-index 在最上层。

**备选**：用 AbsoluteFill 的 `style` prop 强制覆盖。放弃：AbsoluteFill 内部 useMemo 会合并样式，`!important` 在 Remotion 内联样式中不生效。

## Risks / Trade-offs

- **[风险] MCP 工具调用子进程不稳定** → 缓解：`record_distribution` 只做数据库写入，不调用上传脚本；上传仍由 publish.mjs 编排
- **[风险] 字幕修复影响其他 composition** → 缓解：只改 `CostRevolution.tsx`，其他 composition 用各自的 SubtitleBar 组件
- **[权衡] 双写（task.json + 数据库）保持兼容性** → 代价：数据冗余。后续可移除 task.json 的 distribution 数组
- **[风险] publish.mjs 改造引入新 bug** → 缓解：保持 CLI 参数不变，只改内部 distribution 写入逻辑

## Migration Plan

1. **阶段 1（本 change）**：
   - 创建 `vaas-publish-server.py` MCP 服务器
   - 修复字幕定位 bug
   - publish.mjs 改为调用 MCP 的 `record_distribution` 工具
   - 注册到 `.mcp.json`

2. **阶段 2（未来）**：
   - 移除 publish.mjs，MCP 直接编排上传脚本
   - 移除 task.json 的 distribution 数组，完全用数据库

**回滚策略**：publish.mjs 保留原有 task.json 写入逻辑作为 fallback，MCP 调用失败时自动降级。

## Open Questions

- MCP `record_distribution` 调用失败时是否降级到 task.json？（建议：是，保证发布记录不丢失）
- 字幕定位修复是否需要应用到其他 composition（如 VoiceoverVideo）？（建议：本 change 只修 CostRevolution，其他按需单独处理）

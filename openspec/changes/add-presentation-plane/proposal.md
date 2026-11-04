# Proposal: add-presentation-plane

## Why

VAAS 定位升级为 finddata 全系统的**展示层整体解决方案**（模态网关）：五线产出数据与判断，VAAS 负责把一切产物变成可被看见/听见的内容（视频/图片/图表/文档/语音/音乐）。现状做不到——三条病根：

1. **知识冻成了工具**：`orchestrate_brainstorm` 不调任何 API、只返回 JSON 模板给 LLM 照填（`skills/brainstorm.py` 自述），是教科书级「该做 skill 却铸成 MCP」；模板想迭代就得重发镜像。
2. **分层倒挂**：MCP server 的 Python 包住 vendored skill 脚本（`voiceover.py`/`cover.py` subprocess 调 `.agents/skills/*`），agent 拿到黑盒，无法按内容改编排；且 W3 后 `compose_video` 与 `task-render.mjs` 双视频管线并存未收敛。
3. **模态缺口**：图表静态原语（数据线入场券）、文档渲染（pdf/长图）、音乐（BGM）全部缺失，展示层不完整。

用户裁决（2026-11-04）：底座统一方向（chromium + 三出口 + 双层模板）**同意**；当前**无用户，直接 breaking 改**，不留弃用周期；图表首战**两条靶子都做**（文章/研报配图 + 视频数据场景）。

## What Changes

- **BREAKING** 工具面重切（26 → ~20）：`orchestrate_*` 整族退役（brainstorm 降为 skill，voiceover 实现并入 `render_video`）；`generate_cover` 折入 `render_still(kind=cover)`；5 个 Remotion 发现工具收敛为 `templates_list/templates_get`；全部 deprecated 别名移除。
- **NEW** `render_video`：统一视频原语，双模式——`storyboard`（W3 的 seek 契约场景：html_intro/outro/kenburns/html_full）或 `type`（video-types 注册表五类型，吸收 task-render.mjs 实现）；新增 `bgm` 混流参数。
- **NEW** `render_still`：单帧渲染原语，kind ∈ {chart, cover, graphic}；chart 用 ECharts-on-chromium（与 compose_video 同底座、同字体、同 theme.ts 品牌令牌），一份 chart spec 同时服务文章配图与视频 kenburns 输入。
- **NEW** `render_document`：md/html → pdf（chromium print）+ 长图（full-page screenshot）；文档版式归 VAAS，写作知识留在 agent 侧。
- **NEW** 双层模板制：内置模板（镜像内 Remotion 五族场景 + CoverBrand 等，官方维护随镜像滚）+ 外置 HTML 场景（seek 契约自由提交，无外链、data: URI only，安全边界成文）。
- **NEW** BGM：assets 树 `type=bgm` 素材库 + `render_video`/`voiceover_assemble` 混流；生成 API（registry 加 music 条目）后置不做在本 change。
- **NEW** 知识层 skills（in-repo）：`fd-vaas-brainstorm`（brainstorm.py 模板内容迁移）、`fd-vaas-storyboard`（seek 契约场景撰写 + 视频类型选型指南）。
- registry 资产类型分组扩展：`+chart / +doc`（确定性渲染驱动与云生成同表注册）；BGM 走资产类型不入 registry。
- 部署：镜像加 echarts bundle（pandoc 后置）；pricing.json 补 render_still/render_document/render_video 条目；README 工具表重写。

## Capabilities

### New Capabilities
- `presentation-plane`: 展示面核心契约——渲染底座统一（chromium + fonts-noto-cjk + theme.ts）、`render_video` 双模式、`render_still`/`render_document` 出口契约、外置 HTML 场景 seek 契约与安全边界、双层模板制、BGM 混流。

### Modified Capabilities
- `unified-mcp-interface`: 工具命名空间 requirement 重切（orchestrate.* 移除、render.*/templates.* 新增）；向后兼容别名 requirement 整体移除（无用户，一次性切断）；托管模式工具面收窄描述同步。
- `generation-registry`: 生成方式注册 requirement 的资产类型分组扩展 chart/doc/bgm；方式可发现性同步。
- `material-store`: 资产表新增 bgm 类型素材（可被 render_video/voiceover_assemble 引用）。

## Impact

- **代码**：`mcp-server/mcp_server/tools/`（generate.py/orchestrate.py 退役与新增 render.py）、`skills/`（brainstorm.py 等退役）、`main.py`（工具注册面）、`remotion-app/`（模板解禁不动源码）、Dockerfile（+echarts bundle、pandoc 后置）。
- **规格**：`unified-mcp-interface`/`generation-registry`/`material-store` 三 spec delta + 新 spec `presentation-plane`。
- **破坏面**：MCP 工具名单一次性更换（已裁决可 breaking）；`.agents/skills/fd-vaas-video-creator` 的 CLI 入口（new-task.mjs/task-render.mjs）保留为 render_video type 模式的内部实现，不删。
- **外部同步（本 change 之外，finddata 根无编辑权）**：`docs/vaas-trial-intro.md`（22 工具清单）、`docs/vaas-presets/`（pack 增补 fd-vaas-brainstorm/fd-vaas-storyboard）、`MCP-REGISTRY.md` `/vaas-wanxing` 行工具数——收口后另起会话同步。

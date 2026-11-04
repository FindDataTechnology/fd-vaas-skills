# Unified MCP Interface (delta)

## MODIFIED Requirements

### Requirement: 单一 MCP 服务器

系统 SHALL 以唯一一个 MCP 服务器（`.mcp.json` 中一条 `vaas` 注册，指向 `mcp-server/`）暴露全部工具。`vaas-video-assets`（`.claude/mcp/vaas-assets-server.py`）SHALL 被移除，其工具并入统一服务器。规划中的 `vaas-publish` server MUST NOT 另起新进程。

#### Scenario: 客户端仅连一个 server
- **WHEN** 任意 MCP 客户端配置本项目
- **THEN** `.mcp.json` 只含一个 vaas 服务器条目
- **AND** 生成、渲染、发布、资产、模板、注册表全部工具都来自该服务器

#### Scenario: 旧 server 已下线
- **WHEN** 统一服务器上线后
- **THEN** `.claude/mcp/vaas-assets-server.py` 不再被 `.mcp.json` 引用
- **AND** 通用素材与模板发现经统一服务器的 `assets.*` 与 `templates.*` 命名空间调用

### Requirement: 工具命名空间

系统 SHALL 按命名空间组织工具：`generate.*`（voice/image/video 提交与状态/音色目录）、`render.*`（video/still/document 确定性渲染出口）、`publish.*`（video/docs）、`assets.*`（list/get/stats）、`templates.*`（list/get）、`registry.*`（list_generators/describe_generator）。编排类知识（内容策划、场景撰写、类型选型）MUST NOT 以 MCP 工具形态暴露——它们以技能（skill）载体分发。

#### Scenario: 命名空间可被检索
- **WHEN** 客户端列出统一服务器的全部工具
- **THEN** 工具按上述命名空间前缀分组
- **AND** 每个工具可从其命名空间名推断职责
- **AND** 工具清单中不存在 orchestrate 前缀工具与纯返回提示模板的工具

### Requirement: 托管 HTTP 传输

MCP 服务器 SHALL 支持托管 HTTP 模式（流式 HTTP 传输），供謙面网关注册与远程租户调用；本地 `.mcp.json` 的 stdio 接入 MUST 保持不变且为默认。托管模式 MUST 提供健康检查端点供目录探活。发布面工具在托管模式 MUST 不可用。

#### Scenario: 本地接入不变

- **WHEN** 本机客户端按 `.mcp.json` 以 stdio 连接
- **THEN** 全部生成/渲染/发布/资产/模板/注册表工具照常可用
- **AND** 不需要密钥库与租户身份

#### Scenario: 托管模式工具面收窄

- **WHEN** 租户经托管实例列出工具
- **THEN** 可见生成、渲染、资产、模板与注册表工具
- **AND** 发布面工具不存在于工具列表且调用被拒绝

## REMOVED Requirements

### Requirement: 向后兼容别名

**移除理由**：项目当前无外部用户（2026-11-04 裁决），deprecated 别名（`create_cover_image`、`create_voiceover`、`brainstorm_content`、`publish_video_to_platforms`、`publish_article_to_platforms`、`list_all_content`、`get_content_details` 等）随本次工具面重切一次性移除，不再保留一个发布周期。规范工具名即 `generate.*`/`render.*` 等命名空间名。

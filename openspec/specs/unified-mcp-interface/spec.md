# Unified MCP Interface

单一 MCP 服务器 + 命名空间化工具面：合并三个旧 server，提供统一、可发现的生成/发布/资产接口。



### Requirement: 单一 MCP 服务器
系统 SHALL 以唯一一个 MCP 服务器（`.mcp.json` 中一条 `vaas` 注册，指向 `mcp-server/`）暴露全部工具。`vaas-video-assets`（`.claude/mcp/vaas-assets-server.py`）SHALL 被移除，其工具并入统一服务器。规划中的 `vaas-publish` server MUST NOT 另起新进程。

#### Scenario: 客户端仅连一个 server
- **WHEN** 任意 MCP 客户端配置本项目
- **THEN** `.mcp.json` 只含一个 vaas 服务器条目
- **AND** 生成、发布、资产查询、注册表全部工具都来自该服务器

#### Scenario: 旧 server 已下线
- **WHEN** 统一服务器上线后
- **THEN** `.claude/mcp/vaas-assets-server.py` 不再被 `.mcp.json` 引用
- **AND** 其素材发现工具（list_common_assets/find_logo/list_compositions/get_scene_templates）可从统一服务器的 `assets.*` 命名空间调用

### Requirement: 工具命名空间
系统 SHALL 按命名空间组织工具：`generate.*`（voice/image/video/cover）、`orchestrate.*`（voiceover/brainstorm/article）、`publish.*`（video/docs）、`assets.*`（list/get/variants/lineage/stats）、`registry.*`（list_generators/describe_generator）。

#### Scenario: 命名空间可被检索
- **WHEN** 客户端列出统一服务器的全部工具
- **THEN** 工具按上述命名空间前缀分组
- **AND** 每个工具可从其命名空间名推断职责

### Requirement: 向后兼容别名
统一服务器 SHALL 保留旧工具名（`generate_voice`、`generate_image`、`list_all_content`、`get_content_details` 等）作为别名，行为与命名空间工具一致。别名 SHALL 标记为 deprecated。旧名 MUST 至少保留一个发布周期。

#### Scenario: 旧工具名仍可用
- **WHEN** 既有脚本调用 `generate_voice`
- **THEN** 行为与 `generate.voice` 一致
- **AND** 返回结果含命名空间工具的完整字段

### Requirement: 发布编排接口
`publish.*` 工具 SHALL 提供发布就绪校验（视频/封面/状态检查）、配置读取、模拟发布（dry-run）与真实发布。发布成功后 SHALL 通过统一库记录 `distribution` 与 stage 更新。发布前 SHALL 要求用户确认（不可撤销操作）。

#### Scenario: dry-run 不实际上传
- **WHEN** 客户端调用 `publish.video(..., dry_run=true)`
- **THEN** 返回将执行的平台命令与配置预览
- **AND** 不触发任何实际上传或平台登录

#### Scenario: 发布前确认
- **WHEN** 客户端请求真实发布
- **THEN** 系统在未获用户明确确认时不得执行上传
- **AND** 确认后逐平台执行并回写 distribution 记录

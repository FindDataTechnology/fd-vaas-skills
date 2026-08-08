## ADDED Requirements

### Requirement: MCP 发布编排工具集
系统 SHALL 通过 MCP 服务器提供发布编排工具，包括发布前检查、配置读取、模拟发布、数据库记录，所有工具可通过对话直接调用。

#### Scenario: 发布前检查视频就绪状态
- **WHEN** 用户调用 `validate_publish_ready` 工具，传入 slug
- **THEN** 系统返回视频文件是否存在、封面文件是否存在、task.json 状态是否为 rendered

#### Scenario: 读取发布配置
- **WHEN** 用户调用 `get_publish_config` 工具，传入 slug
- **THEN** 系统返回标题、描述、标签列表、脚本路径，以及是否存在本地 .publish.env 覆盖配置

#### Scenario: 模拟发布（dry-run）
- **WHEN** 用户调用 `simulate_publish` 工具，传入 slug 和 platforms 列表，dry_run=true
- **THEN** 系统返回每个平台的上传状态为 "simulated"，不执行实际上传，不写入数据库

#### Scenario: 记录发布结果到数据库
- **WHEN** 发布成功后调用 `record_distribution` 工具，传入 slug、platform、account、title
- **THEN** 系统 SHALL 在 `distributions` 表插入一条记录，uploaded_at 为当前 ISO 时间戳
- **AND** 如果 slug 不存在于 videos 表，返回错误且不插入记录

### Requirement: MCP 服务器注册到项目配置
系统 SHALL 通过 `.mcp.json` 文件注册 `vaas-publish` MCP 服务器到项目级别，不进行全局注册。

#### Scenario: 项目级 MCP 注册
- **WHEN** Claude Code 启动并加载 `$VAAS/.mcp.json`
- **THEN** `vaas-publish` 服务器 SHALL 被注册，command 为 `python3`，args 指向 `.claude/mcp/vaas-publish-server.py`

#### Scenario: MCP 工具发现
- **WHEN** 用户在对话中询问可用工具
- **THEN** `validate_publish_ready`、`get_publish_config`、`simulate_publish`、`record_distribution` SHALL 出现在工具列表中

### Requirement: publish.mjs 作为过渡层调用 MCP
`publish.mjs` SHALL 在每次成功上传后，调用 MCP 工具 `record_distribution` 写入数据库，同时保留 task.json 写入作为 fallback。

#### Scenario: MCP 调用成功
- **WHEN** publish.mjs 成功上传某平台
- **THEN** 调用 `record_distribution` MCP 工具写入数据库
- **AND** 同时 append 到 task.json 的 distribution[]（兼容性保留）

#### Scenario: MCP 调用失败降级
- **WHEN** `record_distribution` MCP 工具调用失败（如数据库锁）
- **THEN** publish.mjs SHALL 降级到原有 task.json 写入逻辑，不中断发布流程
- **AND** 在 stderr 输出警告信息

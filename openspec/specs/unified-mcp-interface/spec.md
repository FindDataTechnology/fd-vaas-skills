# Unified MCP Interface

单一 MCP 服务器 + 命名空间化工具面：合并三个旧 server，提供统一、可发现的生成/发布/资产接口。

## Purpose
VAAS 能力域规格。

## Requirements

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

### Requirement: 托管 HTTP 传输

MCP 服务器 SHALL 支持托管 HTTP 模式（流式 HTTP 传输），供謙面网关注册与远程租户调用；本地 `.mcp.json` 的 stdio 接入 MUST 保持不变且为默认。托管模式 MUST 提供健康检查端点供目录探活。发布面工具在托管模式 MUST 不可用。

#### Scenario: 本地接入不变

- **WHEN** 本机客户端按 `.mcp.json` 以 stdio 连接
- **THEN** 全部生成/发布/资产/注册表工具照常可用
- **AND** 不需要密钥库与租户身份

#### Scenario: 托管模式工具面收窄

- **WHEN** 租户经托管实例列出工具
- **THEN** 可见生成、编排、资产与注册表工具
- **AND** 发布面工具不存在于工具列表且调用被拒绝

### Requirement: 托管模式身份要求

托管模式下，涉及内容读写的调用 SHALL 携带租户身份（网关注入的已验证身份头）；身份缺失或不可信时变更类调用 MUST 被拒绝（fail-closed），只读的注册表发现类工具 MUST 仍可用。服务 MUST 校验请求持有该实例的服务凭证。

#### Scenario: 缺身份变更被拒

- **WHEN** 托管实例收到未携带租户身份的资产生成调用
- **THEN** 返回身份缺失错误且不产生任何资产或计费
- **AND** 携带有效身份的同调用成功

### Requirement: 签名下载端点

托管实例 SHALL 提供产物下载端点：URL 由 HMAC 签名绑定资产标识、归属租户与过期时间（默认 24 小时，可配）；过期或签名不符 MUST 返回错误；跨租户持有他人签名链接 MUST 被拒绝。生成类工具的响应 SHALL 直接包含有效下载地址。签名密钥 SHALL 存放于密钥库服务默认路径。

#### Scenario: 生成响应即含可下载链接

- **WHEN** 租户完成一次图片生成
- **THEN** 响应中的下载地址在有效期内可直接取回该图片
- **AND** 内容与生成的文件一致

#### Scenario: 过期与跨租户链接失效

- **WHEN** 使用过期签名或把他人的签名链接换用自己身份访问
- **THEN** 均被拒绝且不泄露产物内容

### Requirement: 计价用量记录与报表

托管实例 SHALL 为每次生成调用记录用量（归属租户、工具、供应商、模型、数量、单位、凭证来源）； SHALL 提供只读计价汇总端点（按租户×工具聚合，单价来自可配置定价表），端点 MUST 要求服务凭证。定价表初值不属于代码契约，MUST 可在部署侧调整而无需改代码。

#### Scenario: 用量可查可折价

- **WHEN** 管理员以服务凭证查询计价汇总
- **THEN** 返回按租户与工具聚合的用量与折算金额
- **AND** 金额随定价表调整而变化，无需重新部署代码

#### Scenario: 用量与凭证来源对账

- **WHEN** 某租户的一批调用分别走了线池凭证与服务默认凭证
- **THEN** 汇总能按凭证来源拆分该租户用量
- **AND** 与逐条用量记录合计一致

# Material Store

统一物料数据库：所有生成与发布记录的单一事实来源，支持资产血缘查询与平台变体管理。



### Requirement: 单一统一数据库
系统 SHALL 使用一个 SQLite 数据库（`vaas.db`）作为所有物料与发布记录的唯一事实来源。skill 链路（`.agents/skills/fd-vaas-*`）与 MCP 服务器 MUST 读写同一数据库。根 `vaas.db` 的旧 `content`/`distribution` 表 MUST 被废弃并迁移。

#### Scenario: skill 与 MCP 写入同一库
- **WHEN** 视频发布脚本 `publish.mjs` 记录一次发布
- **THEN** 该记录写入统一数据库的 `distribution` 表
- **AND** MCP 工具的 `assets.get` 能查到该资产的发布记录

#### Scenario: 旧库数据已迁移
- **WHEN** 管理员运行迁移脚本
- **THEN** `data/vaas.db` 的 videos 与根 `vaas.db` 的 content 全部导入统一库的 `assets` 表
- **AND** 迁移幂等可重跑，重复运行不产生重复记录

### Requirement: 资产表与血缘树
系统 SHALL 以 `assets` 表存储所有类型物料（video/article/image/audio/presentation/cover/copy）。每条资产 SHALL 有唯一 `slug`、`type`、`stage`，并 MAY 有 `parent_id` 表达血缘（需求 → 主资产 → 平台变体）。系统 SHALL 记录 `lineage_root` 以便一次查询拉取整树。

#### Scenario: 查询整棵血缘树
- **WHEN** 客户端查询一个变体资产的 lineage
- **THEN** 返回该变体、其主资产、以及同树所有兄弟变体
- **AND** 响应含每个节点的 slug、type、stage、platform（若为变体）

#### Scenario: 主资产无父
- **WHEN** 一条视频直接由 video-creator 生成，无策划需求
- **THEN** 其 `parent_id` 为 NULL
- **AND** 其 `lineage_root` 等于自身 id

### Requirement: stage 状态机
每条资产 SHALL 处于 `draft | rendered | published | failed` 之一。资产从 draft 生成、渲染后置 rendered、发布成功后置 published、失败置 failed。stage 每次变化 SHALL 写入 `history` 表（时间戳 + action + details）。

#### Scenario: 渲染成功推进 stage
- **WHEN** 口播视频渲染完成
- **THEN** 资产 stage 从 draft 变为 rendered
- **AND** history 表新增一条 rendered 记录

#### Scenario: 发布失败置 failed
- **WHEN** 某平台上传抛错且未成功
- **THEN** 该资产 stage 置为 failed
- **AND** 平台级记录 status 置 failed 并写入 error_message
- **AND** 其他平台的上传结果不受影响

### Requirement: 平台变体管理
系统 SHALL 用 `variants` 表存储每平台适配版本（title/body/tags/cover_path）。每条 (asset_id, platform) SHALL 唯一。发布前的平台适配 SHALL 写入 variants，发布成功后 SHALL 回填 `distribution` 的 url 与 status。

#### Scenario: 记录平台适配版本
- **WHEN** 发布脚本对某资产执行抖音适配（标题/标签/封面）
- **THEN** variants 表新增 (asset_id, "douyin") 行
- **AND** 同一资产再次适配该平台时更新原行而非新增

#### Scenario: 回查平台差异
- **WHEN** 客户端按 slug 查询
- **THEN** 返回该资产的各平台 variants 列表
- **AND** 能对比同一资产在抖音与小红书的标题/正文差异

### Requirement: 发布记录统一
系统 SHALL 用 `distribution` 表记录所有平台的发布结果（platform/url/status/published_at）。视频发布（`fd-vaas-publish-videos`）与图文发布（`fd-vaas-publish-docs`）MUST 写入同一表结构。

#### Scenario: 图文发布写入同一表
- **WHEN** 公众号文章发布成功
- **THEN** distribution 表新增 (asset_id, "weixin", url, status=uploaded)
- **AND** 与视频发布记录同构，可被同一查询接口检索

### Requirement: 资产查询接口
系统 SHALL 提供 `assets.list` 与 `assets.get` 工具：`assets.list` 按 type/stage/limit 过滤；`assets.get` 按 id 或 slug 返回资产详情、lineage、variants、distribution 历史。统计工具 SHALL 提供 `assets.stats`（按 type/stage 计数、按平台发布数）。

#### Scenario: 列出某类物料
- **WHEN** 客户端调用 `assets.list(type="video", stage="published")`
- **THEN** 返回所有已发布的视频资产摘要
- **AND** 不包含 draft 或 failed 资产

#### Scenario: 查询单资产完整详情
- **WHEN** 客户端调用 `assets.get(slug="demo-video")`
- **THEN** 返回该资产的 stage、file_path、metadata、血缘树、variants、distribution 历史

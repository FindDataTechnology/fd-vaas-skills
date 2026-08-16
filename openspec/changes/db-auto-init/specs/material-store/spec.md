# material-store Spec Delta

## ADDED Requirements

### Requirement: 数据库自举（首次启动自动建库）

MCP 服务器 SHALL 在启动时确保统一数据库 `data/vaas.db` 存在且 schema 完整。首次启动 MUST 自动创建 `data/` 目录与数据库文件并铺满全部表；对已存在的库 MUST 无副作用（幂等，只增不删）。用户 MUST NOT 需要手工执行任何建库命令即可正常使用物料工具。

#### Scenario: 新用户克隆后首次启动即建库

- **WHEN** 一个全新 clone（无 `data/vaas.db`）首次启动 MCP 服务器
- **THEN** `data/vaas.db` 被创建，`.tables` 包含 videos/tts_records/renders/tags/video_tags/assets/variants/distribution/asset_history 全部表
- **AND** 物料工具（`assets_*`、`publish_record` 等）可立即读写，无 `no such table` 错误

#### Scenario: 已存在的库不受影响

- **WHEN** 在已存在且含数据的 `data/vaas.db` 上启动 MCP 服务器
- **THEN** 已有表与数据保持不变
- **AND** 启动过程不报错、不重复建表、不丢失数据

### Requirement: 显式建库命令

项目 SHALL 提供文档化的显式建库命令 `vaas-init-db`（通过 `pip install -e .` 安装的 console script 暴露），语义等价于「确保数据库存在且 schema 完整」，MUST 可安全重复执行。

#### Scenario: 手动触发建库

- **WHEN** 用户运行 `vaas-init-db`
- **THEN** `data/vaas.db` 存在且 schema 完整
- **AND** 重复运行退出码为 0、不报错、不丢数据

#### Scenario: 文档指明自动建库

- **WHEN** 用户阅读 README 的数据库小节
- **THEN** 明确说明数据库在首次启动 MCP 服务器时自动创建
- **AND** 提供 `vaas-init-db` 作为可选的手动初始化命令

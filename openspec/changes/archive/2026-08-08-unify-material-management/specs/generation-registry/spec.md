# Generation Registry

生成方式注册表：按「方式 × provider」注册生成驱动，支撑视频/文案/图片等生成方式的横向扩展。

## ADDED Requirements

### Requirement: 生成方式注册
系统 SHALL 提供生成方式注册表，每一条目 SHALL 含 `name`、`provider`、`model`、`driver`（可执行适配器路径）。注册表 SHALL 按资产类型（video/copy/image/voice/cover）分组。同一类型下 MAY 有多个 provider 的实现。

#### Scenario: 同一类型多 provider
- **WHEN** 系统配置了 video 类型下的 seedance（volcengine）与 voiceover（local/remotion）两种方式
- **THEN** 两者都出现在 video 生成方式清单中
- **AND** 客户端可按 name 精确调度

### Requirement: 生成调度
系统 SHALL 通过 `generate.*` 工具按注册的 name 调度生成。未知 name SHALL 返回明确错误并列出可用方式。生成结果 SHALL 写入统一数据库的 `assets` 表并记录 `provider` 字段。

#### Scenario: 按名生成视频
- **WHEN** 客户端调用 `generate.video(name="seedance", prompt=..., ...)`
- **THEN** 系统按注册表查找 driver 执行生成
- **AND** 成功后 assets 表新增一条 type=video、provider=volcengine 的记录
- **AND** 返回 id/slug/file_path

#### Scenario: 未知生成方式
- **WHEN** 客户端调用 `generate.video(name="nonexistent")`
- **THEN** 系统返回错误
- **AND** 错误信息中列出当前可用的 video 方式清单

### Requirement: 方式可发现性
系统 SHALL 提供 `registry.list_generators(type?)` 工具，返回可用生成方式清单（name/provider/model 及简述）。无 type 时 SHALL 返回全部类型清单。

#### Scenario: 发现全部生成方式
- **WHEN** 客户端调用 `registry.list_generators()`
- **THEN** 返回按 type 分组的全部生成方式
- **AND** 每项含 name、provider、model 字段

### Requirement: 新增方式低成本
新增一种生成/文案方式 SHALL 只需：(1) 在注册表登记一条目；(2) 提供实现统一接口（`generate(params) -> AssetResult`）的 driver。系统 MUST NOT 要求修改核心调度代码。现有 JS 生成 wrapper（tts/seedream/seedance）SHALL 以 driver 底层形式被调用，不重写其逻辑。

#### Scenario: 登记新文案方式
- **WHEN** 新增一种文案改写方式
- **THEN** 注册表新增 copy 类型条目
- **AND** `registry.list_generators(type="copy")` 立即可见
- **AND** `generate.copy(name=...)` 可直接调度
- **AND** 核心生成调度代码无改动

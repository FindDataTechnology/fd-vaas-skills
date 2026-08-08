# Generation Registry

## Purpose

生成方式注册表：按「方式 × provider」注册生成驱动，支撑视频/文案/图片等生成方式的横向扩展。
## Requirements
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

### Requirement: 视频类型声明式注册

系统 SHALL 以文件系统目录作为视频类型注册表：每个类型为 `.agents/skills/fd-vaas-video-creator/types/<type-id>/` 下的 `type.json`，含 `id`、`name`、`description`、`version`、`status`（experimental|stable）、`inputs`、`pipeline`、`composition`、`defaults`、`platforms` 字段。新增或修改类型 MUST NOT 要求改动核心调度脚本（new-task.mjs / task-render.mjs）的源码。

#### Scenario: 注册新类型

- **WHEN** 开发者新增 `types/listicle/type.json` 及对应 Remotion 模板
- **THEN** 类型列表命令立即列出 listicle
- **AND** `new-task.mjs --type listicle` 可按其 inputs 校验并建 task
- **AND** 核心调度脚本无任何改动

#### Scenario: 非法类型定义

- **WHEN** 一个 type.json 缺少必填字段（如 composition）
- **THEN** 注册表加载时报出具体字段错误
- **AND** 其他合法类型不受影响

### Requirement: 类型可发现与调度

系统 SHALL 提供类型列表命令，输出每个类型的 id、名称、状态、必填输入与适用平台。`new-task.mjs` SHALL 接受 `--type <id>` 并按 type.json 的 inputs 校验；`task-render.mjs` SHALL 按 task.json 的 `type` 查找注册表并依其 `pipeline` 顺序执行步骤。未指定 type 的 task SHALL 按 voiceover 处理，行为与注册表引入前一致。未知类型 SHALL 返回明确错误并列出可用类型。

#### Scenario: 按类型渲染

- **WHEN** 用户执行 `new-task.mjs --type listicle --slug demo --script s.txt` 后运行 `task-render.mjs --slug demo`
- **THEN** 系统按 listicle 的 pipeline（tts→fix-tts-timings→scene-align→preflight→render）执行
- **AND** 产物落在 `downloads/fd-videos/demo/`

#### Scenario: 旧命令回归

- **WHEN** 用户执行不带 `--type` 的口播渲染命令
- **THEN** 流程与产物同注册表引入前完全一致

### Requirement: 数据驱动场景映射

系统 SHALL 提供 `scripts/scene-align.mjs`：从修正后的逐字 captions 计算场景边界（句间 gap ≥ 可配阈值切段、过短段合并、帧数由真实音频时间戳推导），输出 `[{from, durationInFrames, text, role}]`。新视频类型的 Remotion 模板 MUST 从 scene-align 输出派生全部 `<Sequence>` 边界，MUST NOT 使用硬编码帧数算术（如 `durationInFrames - N`）。既有硬编码模板（IntroduceXxx 等）SHALL 标记 legacy，可继续使用但不作为新类型范式。

#### Scenario: 短音频不崩溃

- **WHEN** 用一段明显短于模板设计时长的音频渲染任一注册类型
- **THEN** 所有 Sequence 的 durationInFrames 均为正数
- **AND** preflight 通过（drift < 0.5s）
- **AND** 画面切换与口播段落边界对齐

#### Scenario: 分段可预览可覆盖

- **WHEN** 用户渲染前运行 scene-align `--preview`
- **THEN** 输出分段表（起止时间/时长/文本摘要）
- **AND** 脚本中的显式分段标记优先于自动分段


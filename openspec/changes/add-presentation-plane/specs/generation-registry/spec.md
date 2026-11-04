# Generation Registry (delta)

## MODIFIED Requirements

### Requirement: 生成方式注册

系统 SHALL 提供生成方式注册表，每一条目 SHALL 含 `name`、`provider`、`model`、`driver`（可执行适配器路径）。注册表 SHALL 按资产类型分组，类型至少覆盖 video/copy/image/voice/cover，并扩展 chart 与 doc（确定性渲染驱动与云生成驱动同表注册、同一调度入口）。同一类型下 MAY 有多个 provider 的实现。

#### Scenario: 同一类型多 provider
- **WHEN** 系统配置了 video 类型下的 seedance（volcengine）与 voiceover（local/remotion）两种方式
- **THEN** 两者都出现在 video 生成方式清单中
- **AND** 客户端可按 name 精确调度

#### Scenario: 确定性渲染驱动同表注册
- **WHEN** 系统注册 chart 类型下的声明式图表驱动（local）与 doc 类型下的分页文档驱动（local）
- **THEN** 两者分别出现在 chart 与 doc 生成方式清单中
- **AND** 与云生成驱动走同一注册表与同一按名调度入口

### Requirement: 方式可发现性

系统 SHALL 提供 `registry.list_generators(type?)` 工具，返回可用生成方式清单（name/provider/model 及简述）。无 type 时 SHALL 返回全部类型清单，含 chart 与 doc 类型。

#### Scenario: 发现全部生成方式
- **WHEN** 客户端调用 `registry.list_generators()`
- **THEN** 返回按 type 分组的全部生成方式（含 chart/doc）
- **AND** 每项含 name、provider、model 字段

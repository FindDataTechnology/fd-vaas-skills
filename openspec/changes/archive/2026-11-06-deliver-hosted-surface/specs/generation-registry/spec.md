# Generation Registry (delta)

## MODIFIED Requirements

### Requirement: 方式可发现性

系统 SHALL 提供 `registry.list_generators(type?)` 工具，返回可用生成方式清单（name/provider/model 及简述）。无 type 时 SHALL 返回全部类型清单，含 chart 与 doc 类型。清单中依赖外部车道的条目 SHALL 携带该车道健康状态（`health`: active/degraded/down、原因类别、最后验证时间），与车道缺陷台账同源；`models_voices` 等其余发现工具 SHALL 同样透出语音车道状态。发现面 MUST NOT 将 down 车道呈现为可选用能力。

#### Scenario: 发现全部生成方式

- **WHEN** 客户端调用 `registry.list_generators()`
- **THEN** 返回按 type 分组的全部生成方式（含 chart/doc）
- **AND** 每项含 name、provider、model 字段

#### Scenario: 清单携带车道状态

- **WHEN** 图像上游车道处于 down 时客户端列出 image 生成方式
- **THEN** 对应条目 health=down 且附原因类别与最后验证时间
- **AND** 语音车道 active 条目同表可对比，租户可先决策再调用

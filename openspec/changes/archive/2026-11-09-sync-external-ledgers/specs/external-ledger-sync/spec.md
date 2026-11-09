# external-ledger-sync Specification

## Purpose

VAAS 对外台账一致能力：MCP 注册台账、供给注释、市场目录与指引、plaza 物料、试用文档与发布套件声明，在任何工具面或车道状态变更后与真身保持可验证的一致。

## ADDED Requirements

### Requirement: 工具面变更触发台账对账

工具面（数量、名称、描述、参数形状）发生任何变化时，同一交付波内 MUST 完成对外台账重对账：现网探针拉取工具面实况，注册台账（条目、工具数、现网镜像 sha 与滚版时间）、供给注释底稿、市场目录描述与指引、plaza 物化物料全部更新到实况口径；已退役工具名 MUST NOT 残留在任何面向客户的指引或注释中。reconcile 校验 MUST 以零缺陷通过为收账标准。

#### Scenario: 重切后台账同波更新

- **WHEN** 托管工具面重切（如 orchestrate_* 退役、render_* 新增）上线后执行 reconcile
- **THEN** 台账条目工具数与现网一致且注释 17/17 全覆盖、无退役名孤儿注释
- **AND** 现网镜像 sha 与滚版时间登记在案

#### Scenario: 指引不再教旧工具

- **WHEN** 客户按市场目录指引发现可用工具
- **THEN** 指引中不存在已退役工具名的调用建议
- **AND** 新能力（渲染三出口/模板目录）在描述与注释中可见

### Requirement: 试用面诚实

试用/售前文档 MUST 与车道健康实况同步：处于 down/degraded 的车道在指南中如实标注（含原因类别与替代路径或等待说明），MUST NOT 让试用者按文档撞已知故障而无预警；车道修复销账后试用文档同波更新。

#### Scenario: down 车道有言在先

- **WHEN** 图像车道处于 down 期间试用者阅读指南
- **THEN** 该能力标注不可用状态与说明，可用能力清单准确
- **AND** 按指南执行的每一步要么成功要么有明确阻断提示

### Requirement: 发布套件声明过闸

经发布面（谦面 pack）分发的 VAAS 套件，其版本发布 MUST 携带与当期工具面一致的 MCP 工具声明（全名清单或显式 fullSurface），MUST NOT 以零声明发版；工具面变更后套件在下一次发布时 SHALL 更新声明。

#### Scenario: v6 发版过声明闸

- **WHEN** 万星发布套件带 vaas-wanxing 引用发布新版本
- **THEN** 声明闸校验通过（17 名或等价 fullSurface 声明在位）
- **AND** 套件描述的平台计数与技能真源一致

### Requirement: 消费旁路退役

当 VAAS 标准链已覆盖某旁路的职能（如词元 TTS 一等公民化覆盖宿主自合成），使用该旁路的项目 SHALL 迁至标准链并把旁路代码退役归档；跨仓直读他仓 `.env` 取密钥一类的隐性耦合 MUST NOT 作为长期形态保留。

#### Scenario: 旁路迁移留痕

- **WHEN** collateral 出片改走 VAAS 标准链
- **THEN** 产物口径一致（时长/字幕/音色对账通过），旁路脚本标注退役或移除
- **AND** 不再存在直读 VAAS/.env 的跨仓密钥耦合

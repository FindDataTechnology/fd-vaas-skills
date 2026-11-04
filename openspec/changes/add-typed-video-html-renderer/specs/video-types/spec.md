# Video Types (delta)

## MODIFIED Requirements

### Requirement: 金句文字动画视频（kinetic-quote）

系统 SHALL 提供 kinetic-quote 类型：纯文字动效，逐句入场、关键词放大变色，文字出现时机与句级字幕对齐。关键词 SHALL 优先采用口播稿中的显式标记。该类型 MUST NOT 依赖任何图片素材。逐字级同步为 stretch 目标，v1 承诺句级对齐（HTML 渲染器口径）。

#### Scenario: 纯文字渲染

- **WHEN** 用户仅提供口播稿（含 `**词**` 标记）执行 kinetic-quote 渲染
- **THEN** 产出逐句入场的文字动画视频
- **AND** 标记词以放大变色样式突出
- **AND** 全程无图片素材依赖

#### Scenario: 句级对齐

- **WHEN** 口播稿含 4 句而音频总时长 T
- **THEN** 每句入场时刻按其在段内比例位置对齐
- **AND** 句切换与句级字幕同步

## ADDED Requirements

### Requirement: 类型渲染器声明

每个类型的 type.json SHALL 含 `renderer` 字段声明其渲染器（`html` = 类型场景构建器，经 presentation-plane 的 type 模式渲染；历史上 Remotion 管线产物形态保留但不再是 render_video 的执行体）。type.json 的 inputs/pipeline 声明 SHALL 保持为类型输入契约的唯一真源；渲染器切换 MUST NOT 改变 inputs 契约。

#### Scenario: 渲染器切换不改输入契约

- **WHEN** 类型 type.json 标注 renderer=html
- **THEN** 该类型的 inputs 校验规则与切换前一致
- **AND** 既有调用方以相同 inputs 调用无需修改

#### Scenario: 结构校验前置不变

- **WHEN** 类型管线声明 validate-structure（如 news-flash 的要点数对照）
- **THEN** HTML 渲染器在渲染前执行同等结构校验
- **AND** 校验失败的报错形态与既有口径一致（列出对照、零部分产物）

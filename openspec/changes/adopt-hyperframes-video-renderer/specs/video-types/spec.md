# Video Types (delta)

## MODIFIED Requirements

### Requirement: 类型渲染器声明

每个类型的 type.json SHALL 含 `renderer` 字段声明其渲染器（`hyperframes` = 类型场景构建器产出 composition，经 presentation-plane 的 type 模式交视频引擎渲染；`remotion` 为历史值，其管线不再是 render_video 的执行体）。type.json 的 inputs/pipeline 声明 SHALL 保持为类型输入契约的唯一真源；渲染器切换 MUST NOT 改变 inputs 契约。

#### Scenario: 渲染器切换不改输入契约

- **WHEN** 类型 type.json 标注 renderer=hyperframes
- **THEN** 该类型的 inputs 校验规则与切换前一致
- **AND** 既有调用方以相同 inputs 调用无需修改

#### Scenario: 结构校验前置不变

- **WHEN** 类型管线声明 validate-structure（如 news-flash 的要点数对照）
- **THEN** 场景构建器在渲染前执行同等结构校验
- **AND** 校验失败的报错形态与既有口径一致（列出对照、零部分产物）

# Video Types (delta)

## MODIFIED Requirements

### Requirement: 类型渲染器声明

五个 HTML 渲染类型（carousel/listicle/data-viz/kinetic-quote/news-flash）的 type.json SHALL 含 `renderer: "html"` 字段声明其渲染器（经 presentation-plane 的 type 模式渲染）；其余类型（voiceover/screen-recording 等）MAY 省略该字段，省略即按历史 node/Remotion 管线为默认执行体。type.json 的 inputs/pipeline 声明 SHALL 保持为类型输入契约的唯一真源；渲染器切换 MUST NOT 改变 inputs 契约。执行器选择口径（何时走 Remotion 本地管线、何时走托管 HTML 构建器）SHALL 在 SKILL/README 可见。

#### Scenario: 渲染器切换不改输入契约

- **WHEN** 类型 type.json 标注 renderer=html
- **THEN** 该类型的 inputs 校验规则与切换前一致
- **AND** 既有调用方以相同 inputs 调用无需修改

#### Scenario: 未声明类型的默认执行体

- **WHEN** voiceover 类型（无 renderer 字段）经 task-render 本地渲染
- **THEN** 按 node/Remotion 管线执行，行为与注册表引入后一致
- **AND** 不因 renderer 字段缺失报错或跳过

#### Scenario: 结构校验前置不变

- **WHEN** 类型管线声明 validate-structure（如 news-flash 的要点数对照）
- **THEN** 渲染器（HTML 或 Remotion）在渲染前执行同等结构校验
- **AND** 校验失败的报错形态与既有口径一致（列出对照、零部分产物）

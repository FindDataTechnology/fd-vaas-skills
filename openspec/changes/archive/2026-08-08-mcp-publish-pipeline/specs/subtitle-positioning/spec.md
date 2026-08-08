## ADDED Requirements

### Requirement: 字幕固定显示在视频底部
字幕组件 SHALL 使用普通 `<div>` 元素（非 AbsoluteFill）定位在视频底部，避免被 AbsoluteFill 的默认 flex 居中样式覆盖。

#### Scenario: 字幕位置在底部
- **WHEN** 视频渲染时字幕组件激活
- **THEN** 字幕 SHALL 显示在距离视频底部 60px 的位置，水平居中
- **AND** 字幕不应出现在视频垂直中央

#### Scenario: 字幕 z-index 在最上层
- **WHEN** 字幕组件与场景组件同时渲染
- **THEN** 字幕 SHALL 有 `zIndex: 100`，确保在所有场景元素之上
- **AND** 字幕 SHALL 有 `pointerEvents: none`，不阻挡交互

### Requirement: 字幕组件在 Sequence 之后渲染
字幕组件 SHALL 在所有 `<Sequence>` 组件之后渲染，确保 DOM 层级在最上层。

#### Scenario: 字幕渲染顺序
- **WHEN** CostRevolution composition 渲染
- **THEN** SubtitleBar 组件 SHALL 在所有 Sequence 之后出现
- **AND** 字幕使用 `position: absolute` 定位，不参与 flex 布局

### Requirement: 字幕按句子分段显示
字幕 SHALL 按 token 序列分组显示完整句子，遇到标点符号（，。！？、；：）时分段，而非逐字显示。

#### Scenario: 句子分段
- **WHEN** captions.json 包含逐字 token
- **THEN** 字幕组件 SHALL 合并连续 token 直到遇到标点符号
- **AND** 显示完整句子而非单个字

#### Scenario: 句子时间匹配
- **WHEN** 当前时间在某个句子的 startMs 和 endMs 之间
- **THEN** 显示该句子
- **AND** 句子的 startMs 为第一个 token 的 startMs，endMs 为遇到标点符号 token 的 endMs

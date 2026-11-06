# Presentation Plane (delta)

## MODIFIED Requirements

### Requirement: render_video 双模式统一视频原语

系统 SHALL 提供唯一视频渲染工具 `render_video`，支持两种互斥模式：(1) `storyboard` 模式——调用方提交场景序列（html_intro/html_outro/kenburns/html_full，遵守 seek 契约），系统逐帧渲染合成；(2) `type` 模式——调用方指定 video-types 注册表中的类型及输入，系统经类型场景构建器（HTML 渲染器）产出场景后按同一逐帧管线渲染。同输入双跑 MUST 产出一致结果（确定性重放）。旁白音频 SHALL 可作为输入混流；type 模式 SHALL 支持 bgm 参数（语义与 storyboard 一致）并 SHALL 接受 `voice_path` 输入以跳过内置 TTS。两种模式在本地 stdio 与托管实例 SHALL 行为一致；托管镜像 MUST NOT 含 node/Remotion 运行时。storyboard 的 size 参数 SHALL 同时接受 `[width, height]` 与 `{width, height}` 两种形态；kenburns 等场景的输入文件路径 SHALL 接受渲染工具返回的 downloads 相对路径。

#### Scenario: storyboard 模式确定性出片

- **WHEN** 调用方以同一 storyboard 两次调用 render_video
- **THEN** 两次产物内容一致（确定性重放命中，不重复计费渲染）
- **AND** 逐场景与场景边界对齐

#### Scenario: type 模式按类型渲染

- **WHEN** 调用方（本地或托管实例）以 `type=listicle` 与合法 items 输入调用 render_video
- **THEN** 系统经 HTML 场景构建器按 listicle 结构渲染 hook/条目/CTA
- **AND** 类型不匹配错误在渲染前报出（输入校验前置）

#### Scenario: 双模式互斥

- **WHEN** 调用方同时提交 storyboard 与 type
- **THEN** 系统拒绝调用并说明两种模式不可混用

#### Scenario: 托管实例 type 模式指路报错

- **WHEN** 托管实例收到无 HTML 场景构建器的类型调用（type.json 未标 renderer=html 且未注册 builder）
- **THEN** 返回明确错误说明该类型仅本地 stdio 实例支持（ADR-0004 托管镜像不含 Remotion 运行时）
- **AND** 错误信息指路 storyboard 模式或已移植类型清单，不产生任何产物或计费

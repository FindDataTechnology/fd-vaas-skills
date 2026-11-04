# Presentation Plane (展示面)

## Purpose

VAAS 作为 finddata 全系统展示层的核心契约：一个渲染底座、三个出口（单帧/帧序列/分页文档）、双层模板与 BGM 混流。任何线想把产物变成视频/图片/图表/文档/配音成片，只说本面的方言，不自己碰渲染细节。

## ADDED Requirements

### Requirement: 渲染底座统一

系统 SHALL 以单一渲染底座产出全部确定性视觉产物：无头浏览器 + 内置 CJK 字体 + 品牌主题令牌（theme.ts）。三类出口（单帧、帧序列、分页文档）MUST 共享同一底座、同一字体栈与同一品牌主题，MUST NOT 为单一模态引入第二套渲染口径。视频与单帧的接口方言 SHALL 为 seek 契约（`window.__DURATION__`/`window.__SIZE__`、`window.seek(t)`、`data-stage` 标记）。

#### Scenario: 同主题跨出口一致

- **WHEN** 同一品牌主题下分别渲染单帧图表与一段视频
- **THEN** 两者的字体、品牌色板、尺寸语义一致
- **AND** 视频场景可内联复用为单帧产物的场景 HTML（seek 契约互拷）

### Requirement: render_video 双模式统一视频原语

系统 SHALL 提供唯一视频渲染工具 `render_video`，支持两种互斥模式：(1) `storyboard` 模式——调用方提交场景序列（html_intro/html_outro/kenburns/html_full，遵守 seek 契约），系统逐帧渲染合成；(2) `type` 模式——调用方指定 video-types 注册表中的类型及输入，系统按类型声明渲染。同输入双跑 MUST 产出一致结果（确定性重放）。旁白音频 SHALL 可作为输入混流。type 模式依赖本地类型管线（node/Remotion 运行时），MUST 仅在本地 stdio 实例可用；托管实例收到 type 模式调用 MUST 返回指路 storyboard 模式的明确错误。storyboard 的 size 参数 SHALL 同时接受 `[width, height]` 与 `{width, height}` 两种形态；kenburns 等场景的输入文件路径 SHALL 接受渲染工具返回的 downloads 相对路径。

#### Scenario: storyboard 模式确定性出片

- **WHEN** 调用方以同一 storyboard 两次调用 render_video
- **THEN** 两次产物内容一致（确定性重放命中，不重复计费渲染）
- **AND** 逐场景与场景边界对齐

#### Scenario: type 模式按类型渲染

- **WHEN** 本地 stdio 实例上调用方以 `type=listicle` 与合法 items 输入调用 render_video
- **THEN** 系统按 listicle 类型声明渲染 hook/条目/CTA 结构
- **AND** 类型不匹配错误在渲染前报出（输入校验前置）

#### Scenario: 双模式互斥

- **WHEN** 调用方同时提交 storyboard 与 type
- **THEN** 系统拒绝调用并说明两种模式不可混用

#### Scenario: 托管实例 type 模式指路报错

- **WHEN** 托管实例收到 type 模式调用
- **THEN** 返回明确错误说明 type 模式仅本地 stdio 实例支持（ADR-0004 托管镜像不含 Remotion 运行时）
- **AND** 错误信息指路 storyboard 模式，不产生任何产物或计费

### Requirement: render_still 单帧出口

系统 SHALL 提供单帧渲染工具 `render_still`，kind 至少覆盖 `chart`（声明式图表 spec → 图片）、`cover`（品牌封面）、`graphic`（调用方 HTML + 品牌主题 → 图片）。chart 渲染 SHALL 套用品牌主题令牌，同一 chart spec SHALL 既可出单帧图、也可作为 render_video 的视觉输入（数据线一次编排两用）。产物 SHALL 落统一资产账本并返回下载地址。

#### Scenario: 图表配图带品牌主题

- **WHEN** 调用方提交柱状图 spec 调用 render_still(kind=chart)
- **THEN** 产物图片配色取自品牌色板、字体为内置 CJK 栈
- **AND** 资产账本新增 type=chart 记录并附下载地址

#### Scenario: 同一图表 spec 服务视频

- **WHEN** 调用方将已渲染的 chart spec 作为 render_video storyboard 的视觉输入
- **THEN** 视频中该图表场景与单帧产物视觉一致

### Requirement: render_document 分页文档出口

系统 SHALL 提供文档渲染工具 `render_document`：调用方提交 md 或 HTML 源与版式模板，系统产出至少 pdf 与长图两种格式。产物 SHALL 落统一资产账本。文档内容写作不属于本工具职责（内容由调用方提供）。

#### Scenario: md 转 pdf 与长图

- **WHEN** 调用方以一篇 md 与默认版式模板调用 render_document(format=[pdf, longimage])
- **THEN** 产出分页正确的 pdf 与一张完整长图
- **AND** 两者均入资产账本并各附下载地址

#### Scenario: 版式模板可指定

- **WHEN** 调用方指定非默认版式模板（如公文/研报版式）
- **THEN** 产物按该模板排版
- **AND** 未知模板名返回可用模板清单

### Requirement: 外置 HTML 场景契约与安全边界

系统 SHALL 接受调用方自带的外置 HTML 场景（遵守 seek 契约）进入渲染底座。外置场景 MUST 在无外链环境渲染：网络访问被禁用，外部资源 MUST 以 data: URI 内联，违反时渲染失败并指明违规资源。外置场景不得访问文件系统路径以外的宿主资源。

#### Scenario: 合规外置场景渲染成功

- **WHEN** 调用方提交全部资源内联（data: URI）的外置场景并渲染
- **THEN** 渲染成功，视觉效果与内置场景同底座呈现

#### Scenario: 含外链的场景被拒

- **WHEN** 外置场景引用 http(s) 外部资源
- **THEN** 渲染失败并指明该外链资源
- **AND** 不产生部分产物

### Requirement: 双层模板制

模板 SHALL 分两层：内置模板（随镜像发布、官方维护：Remotion 场景族、封面版式、文档版式）与外置场景（调用方经 seek 契约自由提交）。系统 SHALL 提供 `templates_list`（按 domain 列出内置模板与版式）与 `templates_get`（取单个模板详情/契约说明）。新增内置模板 MUST NOT 要求改动工具面。

#### Scenario: 模板可发现

- **WHEN** 调用方调用 templates_list()
- **THEN** 返回内置视频场景族、封面版式、文档版式的可机读清单
- **AND** 每项含名称、domain、输入契约说明

### Requirement: BGM 素材与混流

系统 SHALL 在资产树支持 `type=bgm` 素材，`render_video` 与旁白混流 SHALL 支持指定 BGM（资产 id 或文件）与音量参数，输出混流后成片。BGM 素材 SHALL 授权清晰（内置曲库随镜像种子）。BGM 音乐生成 API 不在本面 v1 范围。

#### Scenario: 成片带 BGM 混流

- **WHEN** 调用方以带 bgm 参数的 storyboard 调用 render_video
- **THEN** 成片音轨为旁白与 BGM 按参数混流
- **AND** BGM 长于视频时在视频时长处收尾

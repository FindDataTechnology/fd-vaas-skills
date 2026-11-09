# presentation-plane Specification

## Purpose
VAAS 作为 finddata 全系统展示层的核心契约：一个渲染底座、三个出口（单帧/帧序列/分页文档）、双层模板与 BGM 混流。任何线想把产物变成视频/图片/图表/文档/配音成片，只说本面的方言，不自己碰渲染细节。

## Requirements

### Requirement: 渲染底座统一

系统 SHALL 以统一底座产出全部确定性视觉产物：HTML 作为唯一作者语言、内置 CJK 字体、品牌主题令牌（theme.ts 单源）。底座分两个出口引擎：视频出口经**独立渲染面**（HyperFrames composition → 逐帧 seek → MP4），静态出口经 chromium（截图/打印，在 API 面）。两个出口 MUST 共享同一字体栈与同一品牌主题，MUST NOT 为单一模态引入第二套品牌口径。视频接口方言 SHALL 为 HyperFrames composition 格式（data-* 时间轴 + 动画适配器）。API 面镜像 SHALL 自带静态出口的完整运行依赖（无头浏览器、CJK 字体、打印与截图工具、音频时长测量）；视频引擎与 Node 运行时 MUST 由渲染面承担，API 面 MUST NOT 依赖它们。被工具面与模板目录标注为 hosted 可用的能力，MUST 在托管部署态可直接执行（视频能力经渲染面）；底座或渲染面缺失时 MUST 显式报错，MUST NOT 以空清单或占位假绿静默降级。

#### Scenario: 同主题跨出口一致

- **WHEN** 同一品牌主题下分别渲染单帧图表与一段 composition 视频
- **THEN** 两者的字体、品牌色板、尺寸语义一致
- **AND** 单帧产物可内联复用为 composition 的视觉素材（data: URI）

#### Scenario: 托管实例开箱可渲

- **WHEN** 租户在重建后的托管实例上调用 render_still、render_document 或 type 模式渲染
- **THEN** 产物正常生成并落资产账本
- **AND** 中文文本以 CJK 字体正确出形（无豆腐块）

#### Scenario: 标注与真实能力一致

- **WHEN** 模板目录将某类型标注 runtime 为 hosted 而实例底座或渲染面不可用
- **THEN** 调用返回明确错误指出缺失面
- **AND** 系统不返回空清单或静默跳过的假成功

### Requirement: render_video 双模式统一视频原语

系统 SHALL 提供唯一视频渲染工具 `render_video`，支持两种互斥模式：(1) `storyboard` 模式——调用方提交场景序列（html_intro/html_outro/kenburns/html_full），系统编译为 composition 后提交渲染面；(2) `type` 模式——调用方指定 video-types 注册表中的类型及输入，系统经类型场景构建器产出 composition 后交同一渲染面渲染。同输入双跑 MUST 产出一致结果（确定性重放）。旁白音频 SHALL 作为 composition 的音频轨合流；type 模式 SHALL 支持 bgm 参数（语义与 storyboard 一致）并 SHALL 接受 `voice_path` 输入以跳过内置 TTS。两种模式在本地 stdio 与托管实例 SHALL 行为一致（本地可指向同一或本地渲染面）。API 面镜像 MUST NOT 含 Node/Remotion；视频渲染 MUST 经渲染面（ADR-0004 增补：渲染面独立）。storyboard 的 size 参数 SHALL 同时接受 `[width, height]` 与 `{width, height}` 两种形态；kenburns 等场景的输入文件路径 SHALL 接受渲染工具返回的 downloads 相对路径。

#### Scenario: storyboard 模式确定性出片

- **WHEN** 调用方以同一 storyboard 两次调用 render_video
- **THEN** 两次产物内容一致（确定性重放命中，不重复计费渲染）
- **AND** 逐场景与场景边界对齐

#### Scenario: type 模式按类型渲染

- **WHEN** 调用方（本地或托管实例）以 `type=listicle` 与合法 items 输入调用 render_video
- **THEN** 系统经类型场景构建器产出 composition 并按 listicle 结构渲染 hook/条目/CTA
- **AND** 类型不匹配错误在渲染前报出（输入校验前置）

#### Scenario: 双模式互斥

- **WHEN** 调用方同时提交 storyboard 与 type
- **THEN** 系统拒绝调用并说明两种模式不可混用

#### Scenario: 托管实例 type 模式指路报错

- **WHEN** 托管实例收到无场景构建器的类型调用（type.json 未标 renderer=hyperframes 且未注册 builder）
- **THEN** 返回明确错误并列出当前可用类型清单
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

系统 SHALL 接受调用方自带的外置 HTML 场景，契约方言为 HyperFrames composition 格式。外置场景 MUST 在渲染面的**按作业沙箱**中渲染：网络仅保留必要回环（无外网）、外部资源 MUST 以 data: URI 内联、宿主敏感路径不可达、环境变量不含平台密钥；违反时该作业失败并指明违规资源。

#### Scenario: 合规外置场景渲染成功

- **WHEN** 调用方提交全部资源内联（data: URI）的外置 composition 并渲染
- **THEN** 渲染成功，视觉效果与内置场景同底座呈现

#### Scenario: 含外链的场景被拒

- **WHEN** 外置 composition 引用 http(s) 外部资源
- **THEN** 渲染失败并指明该外链资源
- **AND** 不产生部分产物

### Requirement: 双层模板制

模板 SHALL 分两层：内置模板（随镜像/渲染面发布、官方维护：HyperFrames composition 模板族、封面版式、文档版式）与外置场景（调用方经 composition 契约自由提交）。系统 SHALL 提供 `templates_list`（按 domain 列出内置模板与版式）与 `templates_get`（取单个模板详情/契约说明）。新增内置模板 MUST NOT 要求改动工具面。

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

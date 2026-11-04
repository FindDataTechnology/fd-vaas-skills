# Typed Video HTML Renderer (类型场景构建器)

## Purpose

五类型视频的 HTML 渲染器契约：类型 = 注册的 Python 场景构建器，消费 type.json 声明的 inputs，产出 seek 契约场景流入既有逐帧管线——类型视频从此与 storyboard 同底座、同确定性纪律，本地与托管实例同一行为。

## ADDED Requirements

### Requirement: 类型渲染器声明与注册

每个视频类型的 type.json SHALL 含 `renderer` 字段（v1 全部为 `"html"`）。渲染器 SHALL 按 type id 注册为场景构建器：消费类型声明的 inputs 与口播稿，产出 storyboard 场景序列后交既有逐帧管线，MUST NOT 为单一类型改动核心渲染调度。未注册 builder 的 html 类型 SHALL 在渲染前报错并列出可用类型。

#### Scenario: 类型元数据可发现且标注托管可用

- **WHEN** 客户端在托管实例调用 templates_list(domain=video)
- **THEN** 五类型全部在列且 runtime 标注为托管可用
- **AND** 每项含 inputs 契约说明

#### Scenario: 新增类型低成本

- **WHEN** 开发者新增一个 type.json（renderer=html）+ 一个注册 builder
- **THEN** 该类型在 templates_list 与 render_video(type=...) 立即可用
- **AND** 核心渲染调度代码无改动

### Requirement: 分段对齐与字幕

类型管线 SHALL 把口播稿按 `## 段名` 分段并对齐音频：默认逐段 TTS（凭证链与 generate_voice 同源）取真实段时长；调用方提供 `voice_path` 时 SHALL 跳过 TTS、按音频总时长在段间比例分摊。场景边界 SHALL 与段边界对齐，段内 SHALL 叠加句级字幕（品牌样式）。段数与类型结构数（如 meta.points）不一致 MUST 在渲染前报错并列出对照。

#### Scenario: TTS 分段驱动场景边界

- **WHEN** 调用方以 script（3 段）+ 合法 inputs 调用 render_video(type=carousel)
- **THEN** 逐段 TTS 完成且每场景时长等于对应段音频时长（+收尾垫）
- **THEN** 场景切换与段边界对齐

#### Scenario: voice_path 跳过 TTS

- **WHEN** 调用方提供 voice_path（外部配音文件）调用 type 模式
- **THEN** 不发起任何 TTS 调用、不解析生成凭证
- **AND** 段时长按音频总长比例分摊、成片音轨为该文件

#### Scenario: 结构数不匹配前置报错

- **WHEN** meta.points 有 5 条而口播只有 3 个要点段
- **THEN** 渲染前报错并列出 5 vs 3 对照
- **AND** 不产生任何部分产物

### Requirement: 五类型结构化场景（HTML 移植）

五类型 SHALL 以 HTML 场景达成 video-types 规格所载的结构与动效行为，全部动效 SHALL 由 seek(t) 纯函数驱动（确定性），配色字体 SHALL 取品牌主题令牌：

- **carousel**：每口播段一张图（路径或 seedream 提示词自动补图，补图清单渲染前列出供确认）Ken Burns 推拉 + 段字幕。
- **listicle**：钩子卡 → 倒数条目卡（rank 弹入）→ CTA。
- **data-viz**：图表场景（bar 生长/line 描画/pie 展开）由 seek(t) 驱动进度，配色取品牌色板；图表组件可复用、不绑定单一类型。
- **kinetic-quote**：逐句入场、关键词放大变色（关键词取口播稿 `**词**` 标记），无图片素材依赖；v1 承诺句级对齐（逐字同步留 stretch）。
- **news-flash**：标题卡 → 要点卡 ×N → CTA，含来源署名位。

#### Scenario: data-viz 图表动画随 t 生长

- **WHEN** 渲染 data-viz 类型含 bar 图表段
- **THEN** 帧序列中柱高随 t 单调生长至目标值、颜色取品牌色板
- **AND** 同输入双跑产物一致

#### Scenario: 补图需确认

- **WHEN** carousel 的 images 含 seedream 提示词项
- **THEN** 渲染前先完成补图并列出清单
- **AND** 用户确认后才进入渲染

### Requirement: 托管可用与统一行为

类型管线 SHALL 不依赖 node/Remotion 运行时（echarts.min.js 已 vendor、字幕字体用内置 CJK 栈），本地 stdio 与托管实例 SHALL 行为一致：同一 type+script+inputs 产出同构产物。type 模式 SHALL 支持 bgm 参数（语义与 storyboard 模式一致：asset_id|path、volume、fade_out）。托管镜像 MUST NOT 因类型管线新增系统依赖。

#### Scenario: 托管实例类型渲染全链

- **WHEN** 托管实例收到 render_video(type=news-flash, script, meta) 调用
- **THEN** 构建器产出场景、逐帧渲染、TTS/voice 混流、成片落账本并返回签名下载
- **AND** 全程不调用 node、不需要镜像外依赖

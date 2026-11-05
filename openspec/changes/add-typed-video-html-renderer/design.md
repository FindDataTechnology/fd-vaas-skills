# Design: add-typed-video-html-renderer

## Context

上一 change（add-presentation-plane）交付了 storyboard 模式的确定性逐帧管线（chromium + seek 契约 + 计划级重放 + 外链硬校验），type 模式因 ADR-0004（托管镜像无 node/Remotion）被收口为显式指路报错（W7.6）。本 change 执行 A 路裁决：五类型移植为 HTML 场景构建器，type 模式在托管实例复活。

## Goals / Non-Goals

- **Goals**：五类型托管原生渲染；本地/托管同一行为；inputs 契约不变；voice_path 通道（无凭证可验收）；type 模式 bgm。
- **Non-Goals**：逐字 caption 同步（stretch，见裁剪）；Remotion 管线删除（留在仓，fd-vaas-video-creator skill 本地工作流照旧）；screen-recording/voiceover 两个非结构类型（不在五类型移植范围，voiceover 语义由 storyboard+generate_voice 组合承载）；新增云生成能力。

## 架构

```
render_video(type, script, inputs, voice_path?, bgm?)
   │
   ▼
tools/typed_scenes.py ── builder 注册表（按 type id）
   │  1. 解析 inputs（type.json 契约校验，结构数对照前置报错）
   │  2. 分段：script 按 `## 段名` 切
   │  3. 对齐：逐段 TTS（复用 generators/tts，凭证链同 generate_voice）
   │          或 voice_path → 总时长比例分摊
   │  4. 补图：images 里的 seedream 提示词 → generate_image（清单确认）
   │  5. builder(type, segments, inputs, theme) → storyboard 场景序列
   ▼
compose_storyboard（既有管线：seek 契约逐帧 → ffmpeg → bgm 混流 → 账本）
```

## 关键决策

1. **type 模式 = 语法糖**：`render_video(type=...)` 内部就是「builder → storyboard」，复用全部既有纪律（确定性重放、外链校验、计划哈希、bgm、账本、计价）。不新增第二条渲染管线。计划哈希把 type+script+inputs+voice+bgm 全折入——同输入重放免费。
2. **builder 位置**：`tools/typed_scenes/` 包——`__init__.py` 注册表（`BUILDER_REGISTRY: dict[str, builder]`）+ `alignment.py`（分段/对齐/字幕）+ `builders/<type_id>.py` 每类型一模块（提案期原定单文件起步，apply 时改为包布局：每类型独立模块便于并行实现与文件所有权切分，注册表哲学不变——type.json `renderer: "html"` 只是契约标记，注册表才是执行真源，与 registry.json/DRIVERS 同哲学）。
3. **对齐口径**：TTS 腿取真实段时长（tts 返回 duration）；voice_path 腿用 ffprobe 总时长 ÷ 段数加权（按段字符数加权比均分诚实）。句级字幕 = 段内按句切分、时长按字符数比例。tailPad（默认 15 frames）沿用 type.json defaults。
4. **data-viz 动画**：场景 HTML 内嵌 vendored echarts.min.js + `window.seek(t)` 里 `chart.setOption({series:[{data: value*ease(t)}]}, {lazyUpdate:true})`，animation:false 由 theme 注入（与 render_still 同纪律）。ease = 段内进度 0→1 的 cubic-out，柱/线/饼三种各自映射（bar=高度、line=逐点显影、pie=角度扫描）。
5. **kinetic-quote 句级**：`**词**` 标记解析保留（关键词放大变色）；入场=句块 opacity/translateY 随 seek 阶跃。逐字同步需要 TTS 词级时间戳（fix-tts-timings 链），/stretch 注记。
6. **品牌一致性**：builder 产出的场景 HTML 全部过 `_scene_html` 同款品牌 CSS wrapper（theme.ts 单源 → echarts-theme.json + brand 变量），字幕样式与 SubtitleBrand 语义对齐（底部条、max 2 行）。
7. **补图确认**：carousel 提示词补图沿用 video-types 既有语义——渲染前列清单待确认（v1 实现：返回 pending 清单让调用方二次调用确认，与 Remotion 版「打印清单等确认」行为对齐；CLI 交互在 MCP 语境的等价物）。
8. **W7.6 carve-out 移除节奏**：builder 就位一个类型就摘一类的报错？不——一次性切换（五 builder 全绿后同 commit 摘 carve-out），避免中间态「部分类型 hosted 可用」的口径分裂。
9. **测试策略**：builder 层纯函数测试（场景 HTML 断言：结构节点/品牌变量/seek 契约字段）；对齐层 mock TTS；确定性双跑 md5（voice_path 腿，真渲染，每类型一例）；hosted 行为=本地行为的同一测试双跑（VAAS_HOSTED=1 下 builder 路径不触凭证——voice_path 腿）。

## Risks / Trade-offs

- **视觉保真**：HTML 版 ≠ Remotion 版逐像素——动效语言（弹入/生长/描画）保真，版式细节重排。验收以 video-types 行为级 Scenario 为准，不做像素对照。
- **cheap-2 RAM 3.9G**：类型渲染与 storyboard 同底座，无新增常驻——风险不变。
- **补图确认在 MCP 语境的交互**：v1 用「pending → 二次调用 confirm」协议，比 CLI 打印确认笨但诚实；skill 文档同步写清。

## Migration Plan

一次性切换（builder 全绿 → type 模式重接 → carve-out 摘除 → 镜像滚版）。无存量调用方（type 模式 hosted 此前必报错、本地调用方走 fd-vaas-video-creator skill 不受影响）。回滚 = 回滚镜像 tag。

## Open Questions

无——A/B 已裁决（A），scope 内无悬而未决。

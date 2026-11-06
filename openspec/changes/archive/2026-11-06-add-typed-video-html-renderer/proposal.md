# Proposal: add-typed-video-html-renderer

## Why

A 路裁决（2026-11-05 用户拍板）：五类型视频（carousel/listicle/data-viz/kinetic-quote/news-flash）是 VAAS 展示层最有产品感的内容形态，但其唯一渲染管线（new-task.mjs/task-render.mjs，node+Remotion）被 ADR-0004 排除在托管镜像外——`render_video` type 模式在 hosted 实例只能显式报错（上一 change W7.6 收口）。托管实例是全系统展示面的主战场，「结构化视频模板只在本地能用」与「VAAS = 展示层整体解决方案」直接冲突。修法不走 B 路（镜像塞 node+Remotion，+1.5G 且展示主权继续寄在历史载体），而是把五类型**移植为 HTML seek 契约场景构建器**：同一 chromium 底座、同一确定性纪律、托管原生可用。

## What Changes

- **NEW** 类型场景构建器基建：`tools/typed_scenes.py`——按 type id 注册的 Python builder，消费 type.json 声明的 inputs，产出 storyboard 场景序列（seek 契约 HTML），流入既有逐帧管线。类型即内置模板（双层模板制的「内置层」从此托管原生）。
- **NEW** 五类型 HTML builder：carousel（图文轮播：分段 kenburns+字幕叠加）、listicle（钩子卡→倒数条目卡→CTA，rank 弹入动效）、data-viz（**ECharts seek 驱动动画**：柱生长/线描画/饼展开，theme 单源）、kinetic-quote（逐句入场+关键词强调）、news-flash（标题卡→要点卡→CTA）。
- **NEW** 分段对齐基建：`## 段名` 分段 → 逐段 TTS（复用 generators/tts）→ 段时长驱动场景边界与句级字幕；**新增 `voice_path` 输入**（跳过 TTS、段时长按音频总长比例分摊）——无凭证环境可全链验收，也为配音自带场景开通道。
- **BREAKING（行为）** `render_video(type=...)` 实现从 subprocess(node) 切到 builder 管线，本地与托管**同一行为**；W7.6 的 hosted 指路报错移除。Remotion 管线（new-task.mjs/task-render.mjs + fd-vaas-video-creator skill）保留在仓不删，但不再是 type 模式的执行体。
- **MODIFIED** type.json 加 `renderer: "html"` 声明；templates_list(domain=video) 标注翻转为 `runtime: "hosted"`；type 模式支持 `bgm`（与 storyboard 同参数语义）。
- **MODIFIED** kinetic-quote 承诺降级为逐句（Remotion 版是逐字严格同步；HTML v1 句级对齐，逐字留 stretch）。
- 逐字 caption 同步（char-timings 移植）不进本 change（stretch，design 记裁剪理由）。

## Capabilities

### New Capabilities
- `typed-video-html-renderer`: 类型场景构建器契约——builder 注册与 type.json 声明、分段对齐（TTS 或 voice_path）、五类型各自的结构/动效/品牌约束、确定性重放、托管可用性。

### Modified Capabilities
- `presentation-plane`: render_video requirement 修订——type 模式经 HTML 构建器在托管实例可用（移除 W7.6 carve-out），type 模式 bgm 参数与 voice_path 输入入契约。
- `video-types`: kinetic-quote requirement 逐字→逐句；五类型 requirement 不动（行为级场景本就 renderer 无关，HTML 版按同一批 Scenario 验收）；新增类型渲染器声明 requirement。

## Impact

- **代码**：`tools/typed_scenes.py`（新）、`tools/render.py`（type 模式重接：删 subprocess 分支与 hosted carve-out）、`tools/templates.py`（runtime 翻转）、`.agents/skills/fd-vaas-video-creator/types/*/type.json`（+renderer 字段）、镜像不变（无新系统依赖，echarts.min.js 已 vendor）。
- **规格**：`presentation-plane`/`video-types` 两 delta + 新 spec `typed-video-html-renderer`。
- **验收依赖**：类型模式生产 E2E 的 TTS 腿仍等 W7.5 用户 key；`voice_path` 腿可先行全链验收（设计动机之一）。
- **不碰**：Remotion 管线源码、fd-vaas-video-creator skill（本地工作流照旧）、pricing（type 模式记账名不变 render_video）。

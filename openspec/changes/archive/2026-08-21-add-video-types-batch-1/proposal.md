# 第一批新视频类型（batch-1）

## Summary

基于 `video-type-registry` 的声明式注册能力，落地 5 个新视频类型：**图文轮播**（carousel）、**榜单合集**（listicle）、**数据可视化讲解**（data-viz）、**金句文字动画**（kinetic-quote）、**热点速报**（news-flash）。每个类型 = type.json + 数据驱动 Remotion 模板 + 示例输入 + 端到端渲染验证。

## Motivation

**选型理由**（从 10 个候选中定这 5 个，决策依据：复用度 × 内容价值 × FindData 品牌契合）：

| 类型 | 为什么进 batch-1 |
|---|---|
| carousel 图文轮播 | 几乎免费：VoiceoverVideo 已有 `images` 轮播 prop，补转场/推拉即成独立类型 |
| listicle 榜单合集 | 短视频最高频格式（「Top 5 工具」），模板化收益最大 |
| data-viz 数据讲解 | FindData 是数据公司，图表动画是品牌门面；Remotion 做数据动画是强项 |
| kinetic-quote 金句 | 纯文字动效，无素材依赖，成本最低 |
| news-flash 热点速报 | 标题卡+要点卡模板，配合 brainstorm 热点选题出片快 |

**batch-2 缓议**（记录不实施）：PPT 转视频、产品 mockup 演示、双人对话/播客、纯 AI 短片、多语言变体。其中多语言变体优先级最高（LogoAnimation 已有 zh/en 先例），等 batch-1 验证注册表好用后先做它。

**目标：**
- 每个类型都走通「示例输入 → 渲染 → 音画对齐」全流程
- 每个类型都有 example/，新用户能照抄出片
- 验证注册表 schema 够用（batch-1 是 video-type-registry 的试金石）

## Requirements

### 核心功能

1. **carousel 图文轮播**
   - 输入：script + images[]（本地路径 或 seedream 提示词，`"generate": true` 时自动调 seedream 补图）
   - 画面：每场景一张图 + Ken Burns 推拉 + 交叉淡入转场；字幕沿用 tiktok-green
   - 场景边界：scene-align 自动分段，图不够时循环复用（末图不重复）

2. **listicle 榜单合集**
   - 输入：script + items.json `[{rank, title, desc, image?}]`
   - 画面：hook（「N 个 XX」大字卡）→ 倒数条目卡（排名动画弹出，每条目对应一个口播段）→ CTA
   - items 数量与口播段数不符时渲染前报错（列出段数 vs 条目数）

3. **data-viz 数据可视化讲解**
   - 输入：script + data.json（图表 spec：`{charts: [{type: bar|line|pie, title, labels, series}]}`）
   - 画面：图表组件库（柱状生长 / 折线描画 / 饼图展开，带数值动画）+ 口播段对齐切换
   - 图表配色 MUST 用 `theme.ts` COLORS（品牌一致），不新造色板

4. **kinetic-quote 金句文字动画**
   - 输入：script（可含 `## ` 分段标记显式控制场景）
   - 画面：大字排版逐句/逐词入场，关键词放大变色；无图片依赖
   - 最依赖 scene-align：文字出现时机与逐字 captions 严格同步

5. **news-flash 热点速报**
   - 输入：script + meta.json `{headline, points: [p1, p2, p3], source?}`
   - 画面：标题卡（红底快讯风）→ 要点卡 ×3 → CTA；固定结构，口播段映射到对应卡

### 通用要求

- 每个类型：`types/<id>/{type.json, README.md, example/}` 三件套
- 每个模板：`remotion-app/src/types/<TypeName>Video.tsx`，Sequence 全部来自 scene-align 输出
- 每个类型至少验证两个方向之一（默认竖屏 1080×1920；声明支持横屏的需过 1920×1080 渲染）
- 每个类型用**短于预期的音频**跑一次渲染，验证不崩（注册表 spec 的短音频场景）
- 全部类型 status 先标 `experimental`，实发过一次后升 `stable`

### 非目标（Non-goals）

- 不做 batch-2 类型（见上）
- 不做类型的发布侧差异化（publish 对类型无感）
- 不做图表类型的无限扩展（bar/line/pie 三种起步，地图/桑基图等看实际内容需要）
- 不为 5 个类型各做封面版式（沿用 fd-cover-image 现有能力）
- 不接 MCP（registry.json 同步另起变更）

## Technical Approach

- 全部基于 video-type-registry 的 pipeline：`tts → fix-tts-timings → scene-align → preflight → render`
- 类型自有输入（items/data/meta）由 new-task 校验后存 task 目录，render 时注入 props
- data-viz 图表组件做成 `src/types/charts/` 可复用组件（BarChart/LineChart/PieChart），data-viz 类型只是其第一个消费者
- carousel 的 seedream 补图作为 pipeline 自定义步骤（`steps.mjs` 插入 `generate-images`），验证注册表的扩展机制

## Success Criteria

1. `list.mjs` 输出 7 个类型（2 内置 + 5 新增），每个有简介和必填输入说明
2. 每个新类型：`node new-task.mjs --type <id>` + `task-render.mjs` 用 example/ 输入渲出 mp4，preflight 通过，画面切换与口播对齐
3. 每个新类型用短音频渲染不崩（无负 durationInFrames）
4. data-viz 渲染出的图表视觉与 theme.ts 品牌色一致
5. 至少挑 1 个类型实发一条视频（走 fd-vaas-publish-videos），验证类型对发布透明

## Risks & Mitigations

| 风险 | 影响 | 缓解 |
|------|------|------|
| data-viz 图表组件工作量大 | batch-1 延期 | 三种图表起步；复杂需求排 batch-2 |
| listicle 段数与条目数对不齐 | 渲染废片 | 渲染前强制校验 + scene-align --preview 人工确认 |
| seedream 补图质量不稳定 | carousel 画面翻车 | generate 为可选项；补图后列出清单让用户确认再渲 |
| 一次做 5 个类型摊薄质量 | 每个都半成品 | 顺序实施：carousel → kinetic-quote → news-flash → listicle → data-viz（便宜先行，每个做完可独立发布） |

## Open Questions

1. carousel 自动补图时，seedream 提示词从哪来——用户在 images[] 里写，还是从口播段文本自动生成？（倾向：用户写，自动生成作为后续增强）
2. data-viz 的 data.json 是否要兼容 CSV 直读？（倾向：v1 只要 JSON，CSV 转换留给用户/Claude 现场转）

## Dependencies

- **硬依赖 `video-type-registry`**（types/ 目录、scene-align、pipeline 解释器）
- **间接依赖 `opensource-readiness`**（模板源码公开）
- seedream 补图依赖现有 `scripts/generators/seedream-wrapper.js`

## Timeline Estimate

- carousel：2 小时
- kinetic-quote：2 小时
- news-flash：2 小时
- listicle：3 小时
- data-viz（含图表组件库）：4-5 小时
- 公共（example、文档、实发验证）：2 小时
- **总计：15-16 小时**

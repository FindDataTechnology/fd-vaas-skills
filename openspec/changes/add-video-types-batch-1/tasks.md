# Tasks

> 实施顺序即任务顺序：便宜先行，每个类型做完独立可用。所有类型共享 video-type-registry 的 pipeline。

## Phase 1: carousel 图文轮播

- [x] `types/carousel/type.json`（inputs: script + images[]，可选 `"generate": true`）
- [x] `src/types/CarouselVideo.tsx`：Ken Burns 推拉 + 交叉淡入转场，Sequence 来自 scene-align
- [x] `types/carousel/steps.mjs`：`generate-images` 步骤（调 seedream-wrapper，缺图时补）
- [x] 图数 < 场景数时循环复用（末图不重复相邻）
- [x] example/（script + 3 张示例图）+ 端到端渲染验证
- [x] 短音频渲染验证

## Phase 2: kinetic-quote 金句文字动画

- [x] `types/kinetic-quote/type.json`（inputs: 仅 script，支持 `## ` 显式分段）
- [x] `src/types/KineticQuoteVideo.tsx`：逐句入场、关键词放大变色、逐字 captions 同步
- [x] 关键词提取规则：defaults 可配（默认取每段最长词/用户标记 `**词**`）
- [x] example/ + 端到端渲染验证 + 短音频验证

## Phase 3: news-flash 热点速报

- [x] `types/news-flash/type.json`（inputs: script + meta.json `{headline, points[3], source?}`）
- [x] `src/types/NewsFlashVideo.tsx`：标题卡 → 要点卡 ×3 → CTA，口播段映射到卡
- [x] points 数量 ≠ 口播要点段数时渲染前报错并列出对照
- [x] example/ + 端到端渲染验证 + 短音频验证

## Phase 4: listicle 榜单合集

- [x] `types/listicle/type.json`（inputs: script + items.json）
- [x] `src/types/ListicleVideo.tsx`：hook 大字卡 → 倒数条目卡（排名弹出动画）→ CTA
- [x] items 数 vs scene-align 段数校验（不符时列出段数/条目数报错）
- [x] 条目图可选（无图时纯排版卡）
- [x] example/（Top 3 示例）+ 端到端渲染验证 + 短音频验证

## Phase 5: data-viz 数据可视化讲解

- [x] `src/types/charts/` 组件库：BarChart（柱状生长）/ LineChart（折线描画）/ PieChart（展开），数值动画
- [x] 图表配色只用 theme.ts COLORS；渲染前 grep 校验无裸色值
- [x] `types/data-viz/type.json`（inputs: script + data.json charts spec）
- [x] `src/types/DataVizVideo.tsx`：图表场景与口播段对齐切换
- [x] example/（一组真实感数据）+ 端到端渲染验证（竖屏 + 横屏）+ 短音频验证

## Phase 6: 收尾

- [ ] 5 个类型 README.md（用法 + 输入示例 + 注意事项）
- [ ] `list.mjs` 输出核对：7 类型，状态/必填输入正确
- [ ] 全部类型初始 status=experimental 写入 type.json
- [ ] 挑 1 个类型（建议 listicle 或 data-viz）实发一条视频，走完 publish 全流程
- [ ] SKILL.md「视频类型判断」表更新为新类型清单
- [ ] batch-2 候选（多语言变体优先）记入 demand 或新 proposal 占位

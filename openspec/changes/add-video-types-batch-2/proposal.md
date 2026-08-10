# Proposal: 第二批视频类型（batch-2）

> 占位文件。batch-1（carousel / kinetic-quote / news-flash / listicle / data-viz）完成后，记录下一批候选，**多语言变体优先**。尚未立项，只记候选与理由。

## 背景

batch-1 覆盖了「图文 / 文字 / 速报 / 榜单 / 数据」五类常见口播短视频形态，全部基于 scene-align + 结构化校验的统一渲染契约。用户原始诉求之一是「让公开项目方便更多人使用」——多语言是降低使用门槛、扩大受众的最直接方向，故 batch-2 以多语言变体打头。

## 候选清单（按优先级）

### 1. bilingual — 双语字幕口播（多语言，优先）

- 在现有任意口播类型上叠加第二语言字幕轨（默认中英，可配任意语言对）
- 实现思路：TTS 仍出主语言音频 + 字幕；第二语言走翻译 API 出文本，按主语言 token 时间戳对齐铺排（无独立音频）
- 复用 scene-align 契约；新模板 `BilingualSubtitles` = 主轨 + 副轨（副轨字号更小、半透明、居下方）
- 痛点：翻译质量与时间戳对齐——先做「整句翻译」而非逐字，降低对齐难度

### 2. tutorial — 步骤教学

- 编号步骤卡 × N，每步可选配代码片段 / 截图
- 数据结构：`{title, steps:[{title, text?, code?, image?}]}`
- 校验：steps 数 = 口播步骤段数（沿用 batch-1 的 validate 模式）
- 代码片段用 FONT_MONO + 高亮（theme.ts COLORS）

### 3. versus — 对比评测

- 左右分屏 A vs B，逐维度对比卡
- 数据结构：`{title, left:{name}, right:{name}, dimensions:[{label, left, right}]}`
- 视觉：左蓝右紫分屏，中间分隔线随维度切换高亮

### 4. faq — 问答合集

- Q 卡 → A 卡循环，问题用 accentColor 强调
- 数据结构：`{title, qa:[{question, answer}]}`
- 校验：qa 数 × 2 = 口播段数（每对问答两段）

### 5. stat-counter — 数字滚动大字

- 单个大数字从 0 滚动到目标值，配合一句话口播
- data-viz 的单数值变体；适合「X 亿用户」「增长 Y%」这类冲击力数字
- 数据结构：`{title, stats:[{value, prefix?, suffix?, label?}]}`

## 不做（已覆盖或 YAGNI）

- 名言金句卡 → 已被 kinetic-quote 覆盖（加 attribution 即可，不必新类型）
- 长叙事/章节 → 口播短视频不宜超 60s，长内容建议拆多条

## 立项触发

当 batch-1 任一类型实发成功（publish 全链路）且 status 转 stable 后，从本清单挑 1-2 个立项，补 specs/design/tasks。

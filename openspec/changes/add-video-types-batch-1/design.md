# Design: 第一批新视频类型

## 类型一览与模板结构

| id | composition | 场景结构 | 类型自有输入 |
|---|---|---|---|
| carousel | CarouselVideo | 每口播段一张图（Ken Burns + 淡入淡出） | images[] |
| kinetic-quote | KineticQuoteVideo | 每口播段一屏大字，逐词同步 | —（仅 script） |
| news-flash | NewsFlashVideo | 标题卡 → 要点卡×3 → CTA | meta.json |
| listicle | ListicleVideo | hook 卡 → 条目卡×N → CTA | items.json |
| data-viz | DataVizVideo | 每口播段一个图表场景 | data.json |

## 关键决策

### 1. 段-画映射：默认 1 口播段 = 1 场景，结构化类型用显式对齐

- carousel / kinetic-quote / data-viz：scene-align 输出 N 段 → N 场景，素材少于段时循环（carousel）或复用（data-viz 保持上一图表）
- listicle / news-flash：结构固定（条目卡对应条目段），渲染前校验「口播段数 vs 条目数」，不符直接报错——这类型的对齐错误比渲染失败更浪费

### 2. carousel 的 seedream 补图 = 注册表扩展机制的试金石

```js
// types/carousel/steps.mjs
export const steps = {
  'generate-images': async (ctx) => {
    // images[] 里标记 {prompt: "..."} 的项调 seedream-wrapper 落盘 taskDir/assets/
    // 补图清单打印出来，渲染前用户确认
  }
};
// type.json pipeline: ["generate-images", "tts", "fix-tts-timings", "scene-align", "preflight", "render"]
```

这个类型故意用上「自定义步骤」，验证 video-type-registry 的 steps.mjs 机制不是摆设。

### 3. data-viz 图表组件库独立成 `src/types/charts/`

- BarChart / LineChart / PieChart 是纯组件（props: labels/series/进度帧），不绑死 data-viz 类型——将来 PPT 转视频、财报视频都能复用
- 动画统一「生长/描画」语言：柱从 0 长高、线从左描到右、饼从 0° 展开，时长 = 所在场景帧数的 40%（到位后静止，配合口播讲解）
- 配色硬性约束：只 import theme.ts 的 COLORS；tasks 里有 grep 校验任务

### 4. kinetic-quote 的关键词标记

v1 规则（defaults 可覆盖）：
- 口播稿中 `**词**` 显式标记优先
- 否则取每段内字符数最长的名词性词（简单规则：最长连续中文词 ≥2 字）
- 关键词样式：放大 1.4× + 品牌强调色，其余文字常规

### 5. 全部类型共享的渲染契约

```
props: {
  scenes: SceneAlignOutput[],   // 必有，来自 scene-align
  audioSrc, captionsSrc,        // pipeline 注入
  ...typeProps                  // items / data / meta / images
}
总帧数 = scenes 末段 end + defaults.tailPad（默认 15 帧）
```

任何类型不满足契约 → preflight 阶段失败，不进渲染。

### 6. experimental → stable 的毕业标准

- 实发一条视频成功（publish 全链路）
- 横竖屏至少一个方向有真实使用
- type.json 里 status 翻转 + README 记录首用案例

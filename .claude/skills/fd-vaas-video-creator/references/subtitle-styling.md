# 字幕样式调参

字幕通过 `--props` 的样式字段控制。所有字段可选,有默认值。

## 样式字段

| 字段 | 默认 | 说明 |
|---|---|---|
| `subtitleColor` | `#39E508` | 当前正在朗读的词的高亮色。其余词为白色。 |
| `subtitleSize` | `90` | 字号(px)。竖屏 1080 宽下 80–110 较合适。 |
| `switchEveryMs` | `1400` | 每屏字幕分组窗口(毫秒)。**值小=每屏词少,更接近逐字;值大=每屏词多,更接近整句**。口播快节奏建议 900–1200,慢节奏 1400–1800。 |
| `bgColor` | `#0a0e14` | 无画面时的背景色(纯色兜底)。有画面时被覆盖。 |

## 颜色速选

| 风格 | `subtitleColor` |
|---|---|
| 抖音经典绿 | `#39E508`(默认) |
| 亮黄 | `#FFD60A` |
| 品牌红 | `#FF4D4F` |
| 天蓝 | `#38BDF8` |
| 紫色 | `#BC8CFF` |
| 纯白(无高亮,把高亮色也设为白) | `#FFFFFF` |

## 常见搭配示例

**抖音快节奏口播**(逐字感强):

```json
{"subtitleColor":"#FFD60A","subtitleSize":100,"switchEveryMs":1000}
```

**B站横屏整句风**(每屏词多):

```json
{"subtitleColor":"#38BDF8","subtitleSize":70,"switchEveryMs":1800,"width":1920,"height":1080}
```

## 深度自定义

要改位置(默认垂直居中)、描边、字体、动画,直接编辑 `remotion-app/src/VoiceoverVideo.tsx` 里的 `CaptionPage` 组件。改的是全局合成,所有视频共享--若想按视频定制,把样式字段加进 `VoiceoverVideoProps` 并通过 props 传入。

## 关于"整句字幕" vs "逐字高亮"

本 Skill 默认逐字高亮(卡拉OK风),这是 short-video 主流且最抓眼球。若你只想要朴素的整句字幕、不要高亮,把 `switchEveryMs` 调大(如 2500)并设 `subtitleColor` 为白色即可近似整句效果;若要严格整句无高亮,需改 `CaptionPage` 去掉 token 级着色逻辑。

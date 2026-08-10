# news-flash - 热点速报

固定结构卡片视频：标题卡(hook) -> 要点卡×N -> CTA。meta.json 提供 headline/points/source，要点数与口播段数渲染前校验一致。

## 适用场景

- 每日资讯、行业速报、突发事件盘点
- 固定「标题 + N 要点 + 结尾」结构的短卡片视频
- 强调信息密度与结构感，无需配图

## 输入

| 输入 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `script` | file | 是 | 口播稿。`## 段名` 分段：1 hook + N 要点 + 1 cta，段数须与 meta.points 数匹配 |
| `meta` | json | 是 | 结构清单 `{headline, points[], source?}`；points 可为字符串或 `{text}` |
| `orientation` | enum | 否 | `1080x1920`（默认）/ `1920x1080` |

### meta.json 格式

```json
{
  "headline": "AI 编程助手市场爆发",
  "points": [
    "头部厂商集体降价，门槛降到三成",
    "开源模型追平闭源，本地部署成现实",
    "企业采购规模化，订单同比增两倍"
  ],
  "source": "寻数科技整理"
}
```

## pipeline

```
tts -> fix-tts-timings -> scene-align -> validate-structure -> preflight -> render
```

`validate-structure` 读 meta.json + scenes.json，校验 `pointsScenes.length === meta.points.length`；不一致时打印对照表并退出，避免渲染出错位卡片。

## 示例

```bash
cd <VAAS 根目录>
node .agents/skills/fd-vaas-video-creator/scripts/new-task.mjs \
  --slug news-flash-demo --type news-flash \
  --script .agents/skills/fd-vaas-video-creator/types/news-flash/example/script.txt \
  --meta .agents/skills/fd-vaas-video-creator/types/news-flash/example/meta.json

node .agents/skills/fd-vaas-video-creator/scripts/task-render.mjs --slug news-flash-demo
```

## 设计要点

- 口播稿用 `## 速报` / `## 要点一` / `## 结尾` 显式分段，scene-align 按段对齐卡片切换。
- hook 卡：顶部 accent 色横条 + 「速报」标签 + headline；可选 source 角标。
- 要点卡：大号序号 `01/02/03`（FONT_MONO）+ point 文本，spring 弹入。
- CTA 卡：末段口播文本，accent 色放大。
- 校验失败时控制台列出 meta.points 与口播段文本对照，方便定位段数不匹配。

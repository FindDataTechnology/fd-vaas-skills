# data-viz - 数据可视化讲解

每口播段一个图表场景：hook 大字卡 -> 图表卡×N（柱状生长 / 折线描画 / 饼图展开）-> CTA。data.json 提供 charts 规格，图表数与口播段数渲染前校验一致。

## 适用场景

- 行业数据解读、市场份额对比
- 增长曲线、趋势复盘
- 任何「用数字说话」的口播内容

## 输入

| 输入 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `script` | file | 是 | 口播稿。`## 段名` 分段：1 hook + N 图表段 + 1 cta，图表段数须与 data.charts 数匹配 |
| `data` | json | 是 | 图表规格 `{title, charts:[{type, title?, labels?, values?/series?, unit?}], source?}`；charts 数须等于口播图表段数 |
| `orientation` | enum | 否 | `1080x1920`（默认）/ `1920x1080` |

### data.json 结构

```json
{
  "title": "2026 AI 编程工具市场格局",
  "source": "你的机构整理",
  "charts": [
    {
      "type": "bar",
      "title": "月活开发者（万）",
      "labels": ["Copilot", "Cursor", "Claude Code", "Cody"],
      "values": [180, 120, 210, 60],
      "unit": "万"
    },
    {
      "type": "line",
      "title": "近半年月活增长",
      "labels": ["3月", "4月", "5月", "6月", "7月", "8月"],
      "series": [
        { "name": "Claude Code", "values": [70, 95, 130, 160, 190, 210] },
        { "name": "Copilot", "values": [150, 155, 162, 168, 174, 180] }
      ],
      "unit": "万"
    },
    {
      "type": "pie",
      "title": "市场份额占比",
      "labels": ["Claude Code", "Copilot", "Cursor", "其他"],
      "values": [29, 25, 17, 29],
      "unit": "%"
    }
  ]
}
```

- `charts[].type`：`bar`（柱状）/ `line`（折线）/ `pie`（饼图）
- `bar`/`pie` 用 `values` + `labels`；`line` 用 `series:[{name, values}]` + `labels`（X 轴）
- `unit` 可选，会拼在数值/刻度后
- 图表段顺序 = 口播 `## 段名` 顺序；第 1 段是 hook，末段 role===cta 是 CTA，中间每段一个 chart

## pipeline（2026-11-09 起）

```
generate_voice（配音 + captions.json）→ render_video(type="data-viz", script, inputs)
                                        └─ 结构校验前置：charts 数须 == 口播图表段数
```

结构校验在**渲染/TTS 花费之前**（骨架段数对照）：charts 数 = 口播图表段数，且逐个校验
`chart.type` 合法、`bar`/`pie` 有 `values`、`line` 有 `series`、都有 `labels`；不符即红，零部分产物。
（本地 `new-task` / `task-render` / `fix-tts-timings` 已随 Remotion 退役。）

## 图表构建器

图表是 Python 侧 `mcp-server/mcp_server/tools/typed_scenes/builders/_charts.py` 的
**ECharts「seek 驱动器」**（`bar` / `line` / `pie` 三种，与具体视频类型解耦，可被其他 builder 复用）：

| 驱动器 | 动画语言 |
|---|---|
| `bar` | 柱从 0 长高，数值随进度累加 |
| `line` | 折线从左描到右（dashoffset），数据点逐个亮起 |
| `pie` | 环形从顶部顺时针展开，到位后显示标签与百分比 |

驱动方式是 HyperFrames 的 `window.seek(t)` 纯函数契约：每段把 40% 的时长映射成进度
（到位后静止，配合口播讲解），跨调用历史无关（轴上限 `niceMax` 首帧固定）。
`echarts.min.js` 内联进场景 body（vendor 路径与 `still_chart` 同源）——**零外链**。

**配色硬性约束**：色值全部来自 `echarts-theme.json`（真源 `brand/theme.ts` →
`scripts/gen-echarts-theme.mjs`），经 DATA 岛注入（echarts canvas 读不了 CSS 变量），
无裸色值。

## 示例

```bash
# MCP 工具面调用（托管端点或本地 stdio 均可）
#   render_video(
#     type="data-viz",
#     script=<example/script.txt 内容或路径>,
#     inputs={"data": <example/data.json 内容>},
#     slug="dataviz-demo")
```

横屏加 `inputs={"orientation": "1920x1080"}`。产物落 `downloads/video/dataviz-demo/dataviz-demo.mp4`。

## 设计要点

- 进度动画占段时长 40%：前 40% 长出来，后 60% 静止让口播讲透，节奏不赶（`seek` 纯函数驱动，双跑字节一致）。
- hook 卡顶部一条强调色横线 + 「数据」标签 + data.title；CTA 卡直接显示口播末段文字。
- 多 series 配色按 `brand/theme.ts` 的 palette 轮转（green/blue/purple/orange/cyan/red）。
- 短音频测试注意：单图表段须 ≥1500ms（minSegmentMs），否则段对齐会把图表段并进 CTA，结构校验会报段数不匹配。

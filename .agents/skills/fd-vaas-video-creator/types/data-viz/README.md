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
  "source": "寻数科技整理",
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

## pipeline

```
tts → fix-tts-timings → scene-align → validate-data → preflight → render
```

`validate-data` 校验 charts 数 = 口播图表段数，不符才渲染；并逐个校验 chart.type 合法、bar/pie 有 values、line 有 series、都有 labels。

## 图表组件

图表是 `remotion-app/src/types/charts/` 下的纯组件，不绑死 data-viz 类型，可被其他模板复用：

| 组件 | 动画语言 |
|---|---|
| `BarChart` | 柱从 0 长高，数值随进度累加 |
| `LineChart` | 折线从左描到右（dashoffset），数据点逐个亮起 |
| `PieChart` | 环形从顶部顺时针展开，到位后显示标签与百分比 |

每个组件接收 `progress: 0..1`，DataVizVideo 把段帧的 40% 映射成 progress（到位后静止，配合口播讲解）。**配色硬性约束：只 import theme.ts 的 COLORS**，无裸色值。

## 示例

```bash
cd <VAAS 根目录>
node .agents/skills/fd-vaas-video-creator/scripts/new-task.mjs \
  --slug dataviz-demo --type data-viz \
  --script .agents/skills/fd-vaas-video-creator/types/data-viz/example/script.txt \
  --data .agents/skills/fd-vaas-video-creator/types/data-viz/example/data.json

node .agents/skills/fd-vaas-video-creator/scripts/task-render.mjs --slug dataviz-demo
```

横屏加 `--orientation 1920x1080`。

## 设计要点

- 进度动画占段帧 40%：前 40% 长出来，后 60% 静止让口播讲透，节奏不赶。
- hook 卡顶部一条强调色横线 + 「数据」标签 + data.title；CTA 卡直接显示口播末段文字。
- 多 series 配色按 theme.ts 轮转（green/blue/purple/orange/cyan/red）。
- 短音频测试注意：单图表段须 ≥1500ms（minSegmentMs），否则被 scene-align 合并进 CTA，validate-data 会报段数不匹配。

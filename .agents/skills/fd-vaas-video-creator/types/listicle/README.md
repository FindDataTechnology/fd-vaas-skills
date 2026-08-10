# listicle - 榜单合集

倒数排名卡片视频：hook 大字卡 -> 条目卡×N（排名弹出动画，可选配图）-> CTA。

## 适用场景

- Top N 工具/产品/资源榜单
- 排名盘点、年度总结
- 需要编号视觉冲击力的内容

## 输入

| 输入 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `script` | file | 是 | 口播稿。`## 段名` 分段：1 hook + N 条目 + 1 cta，条目段数须与 items 数匹配 |
| `items` | json | 是 | 榜单清单 `{title, items:[{title, text?, image?}], source?}`；items 数须等于口播条目段数 |
| `orientation` | enum | 否 | `1080x1920`（默认）/ `1920x1080` |

### items.json 结构

```json
{
  "title": "2026 三款 AI 编程助手",
  "items": [
    { "title": "GitHub Copilot", "text": "生态最广、企业铺货最成熟" },
    { "title": "Cursor", "text": "编辑器深度集成、Tab 补全流畅" },
    { "title": "Claude Code", "text": "终端原生、长上下文、多步自主执行" }
  ],
  "source": "寻数科技整理"
}
```

- `items[].text` 可选，不填只显示标题
- `items[].image` 可选，任务目录下的文件名；有图时上图下文，无图纯排版
- 排名倒数：第 1 个条目 = rank N（最大），最后一个 = rank 1

## pipeline

```
tts → fix-tts-timings → scene-align → validate-items → preflight → render
```

`validate-items` 校验条目数 = 口播条目段数，不符才渲染；把条目配图拷进 public/，注入 `props.itemImages`。

## 示例

```bash
cd <VAAS 根目录>
node .agents/skills/fd-vaas-video-creator/scripts/new-task.mjs \
  --slug listicle-demo --type listicle \
  --script .agents/skills/fd-vaas-video-creator/types/listicle/example/script.txt \
  --items .agents/skills/fd-vaas-video-creator/types/listicle/example/items.json

node .agents/skills/fd-vaas-video-creator/scripts/task-render.mjs --slug listicle-demo
```

## 设计要点

- 排名数字用欠阻尼 spring（damping 12, stiffness 200）自然过冲弹出。
- 有图条目：上 55% 配图 + 渐隐压暗，下 45% 标题/正文；无图：居中大数字 + 标题/正文。
- 色取 theme.ts：accent 橙、bg 深底、muted 灰。

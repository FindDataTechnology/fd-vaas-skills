# kinetic-quote - 金句文字动画

纯文字动态排版：逐句 spring 弹入、逐字（字幕时间戳）高亮、关键词恒放大变色。无图片。

## 适用场景

- 金句/观点/语录的短动态卡片
- 投资理念、产品 slogan、文案金句的视觉强化
- 无需配图、强调文字本身的节奏感

## 输入

| 输入 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `script` | file | 是 | 口播稿。`## 段名` 显式分段；`**关键词**` 标记每段要放大的词 |
| `orientation` | enum | 否 | `1080x1920`（默认）/ `1920x1080` |

### 关键词规则（extract-keywords 步骤）

1. 优先用脚本里的 `**词**` 显式标记（归一化后命中段文本即生效）
2. 无标记则取该段内最长连续中文词（≥ `minKeywordLen`，默认 2）
3. 都没有则该段不强调关键词

## pipeline

```
tts -> fix-tts-timings -> scene-align -> extract-keywords -> preflight -> render
```

`extract-keywords` 读 script.txt 的 `**词**` 标记 + scenes.json，写 `<slug>-keywords.json`，注入 `props.keywordsSrc`。

## 示例

```bash
cd <VAAS 根目录>
node .agents/skills/fd-vaas-video-creator/scripts/new-task.mjs \
  --slug kinetic-demo --type kinetic-quote \
  --script .agents/skills/fd-vaas-video-creator/types/kinetic-quote/example/script.txt

node .agents/skills/fd-vaas-video-creator/scripts/task-render.mjs --slug kinetic-demo
```

## 设计要点

- 每段一屏，spring 弹入 + translateY；token 按字幕时间戳逐个高亮（放大 1.18× + 品牌色）。
- 关键词 token 恒放大 1.12× + 橙色，即使非活跃也保持强调。
- 渲染时剥离 token 文本里的 `*`（容错 TTS 把 `**` 当文本输出）。
- 视觉色取自 theme.ts：active 绿、keyword 橙、bg 深底。

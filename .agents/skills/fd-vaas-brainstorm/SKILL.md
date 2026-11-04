---
name: fd-vaas-brainstorm
description: >
  内容策划知识技能(纯知识,无脚本):口播短视频 + 图文双模式的选题策划与结构化内容计划。
  照 JSON 模板逐字段产出——口播模式:选题矩阵(5 维度×3-5 选题) + 脚本框架 + 差异化角度 +
  完整口播大纲;图文模式:选题矩阵 + 标题组 + 正文双版本(Markdown 版 + 纯文本版) + 标签 + 摘要。
  策划直接在对话里完成(服务端 brainstorm 工具已退役,本 skill 就是它的模板知识),定稿后自驱下游
  工具链出成品:generate_voice 配音 → render_video(storyboard 或 type)出片;长稿走
  voiceover_assemble;图文走 render_document(pdf/longimage);配图走 render_still(chart/cover)。
  触发场景:用户说"帮我想选题 / 内容策划 / brainstorm 一下 / 出几个口播脚本 / 写个脚本大纲 /
  帮我起几个标题"、"写一篇…并配口播 / 写一篇…并配图"、"给这个主题出一期内容",
  或 /fd-vaas-brainstorm。策划完不想只停在文本、要直接出片/出图的,由本 skill 串下游 MCP 工具。
compatibility: 纯知识技能,无脚本无依赖;下游调用 VAAS MCP 工具面(generate_voice / render_video / voiceover_assemble / render_document / render_still / models_voices / templates_list / templates_get)。
---

# VAAS Brainstorm——内容策划知识技能

> 给定赛道 / 主题 / 受众,产出结构化选题方向与可直接使用的口播大纲或图文草稿,然后按需自驱下游工具出成品。策划本身**在对话里完成**——服务端的 brainstorm 工具已退役,本 skill 保留的是它的 JSON 模板知识:你(LLM)就是那个"填模板"的执行者。

## 工作方式:对话内直接策划

接到策划需求后**不要上来就空想**,也不要找任何工具调用——按顺序做三件事:

1. **收集品牌上下文(brand_context)**——从对话和仓库里提取,提取不到的关键项再问用户:
   - `existing_scripts` / `existing_articles` 指到的历史脚本和文章**先读**,复用人设、调性、CTA 话术,不要凭空发明:
     - `downloads/fd-videos/<slug>/script.txt` —— 历史口播稿
     - `downloads/fd-docs/<slug>/article.md` —— 历史图文
     - `downloads/common/`、项目 README、`AGENTS.md` —— 产品定位、Slogan、名称标准写法
   - `company` / `slogan` 拿到后**原样进稿**,产品名大小写、Slogan 措辞必须与官方表述完全一致。
2. **确认模式与平台**——口播还是图文?发抖音竖屏还是 B 站横屏?图文发公众号还是知乎 / 小红书?**没明说就先问一句**,别默认。据此调整话术深度、时长、字数。
3. **确认核心信息点**——这条内容最重要的 1~3 个信息是什么?其余砍掉。

然后照下面两份模板之一,逐字段产出结构化计划。

## 输入约定

| 项 | 必填 | 说明 |
|---|---|---|
| `mode` | ✅ | `voiceover`(口播)或 `article`(图文) |
| `topic` | ✅ | 主题 / 赛道,一句话 |
| `audience` | ❌ | 目标受众描述,如"25-35 岁一线程序员" |
| `brand_context` | ❌ | 品牌上下文 dict,见下 |

```json
{
  "company": "公司名(决定品牌表述一致性)",
  "slogan": "Slogan(原样使用,不得改写)",
  "existing_scripts": ["downloads/fd-videos/<slug>/script.txt"],
  "existing_articles": ["downloads/fd-docs/<slug>/article.md"]
}
```

## 口播模式模板(mode=voiceover)

产出以下结构,**每个空都由你填满**:

```json
{
  "mode": "voiceover",
  "topic": "<主题>",
  "audience": "<受众>",
  "brand_context": { },
  "topic_matrix": [
    {"dimension": "热点型", "description": "借势热点、节日、趋势", "topics": ["3-5 个"]},
    {"dimension": "痛点型", "description": "用户真实困扰、焦虑", "topics": ["3-5 个"]},
    {"dimension": "争议型", "description": "反常识、颠覆认知、站队", "topics": ["3-5 个"]},
    {"dimension": "干货型", "description": "方法论、技巧、教程", "topics": ["3-5 个"]},
    {"dimension": "人设型", "description": "个人故事、经历、感悟", "topics": ["3-5 个"]}
  ],
  "script_frameworks": [
    {"name": "黄金三秒+痛点+方案", "structure": "钩子(3s) -> 共情痛点 -> 解决方案 -> 引导", "best_for": "通用爆款"},
    {"name": "SCQA", "structure": "情景 -> 冲突 -> 问题 -> 答案", "best_for": "知识/观点"},
    {"name": "PREP", "structure": "观点 -> 理由 -> 案例 -> 重申观点", "best_for": "说服型"}
  ],
  "differentiation_angles": ["每个选题给 2-3 个不撞车的爆款切入点"],
  "full_outline": {
    "hook": "开场钩子,前 3 秒的具体话术",
    "body": ["正文分点 / 分段,每点一句话概括 + 展开要点"],
    "cta": "结尾引导——只用平台内动作"
  },
  "compliance_check": {
    "no_competitor_platforms": null,
    "no_external_links": null,
    "no_contact_info": null,
    "brand_consistency": null
  }
}
```

补充框架(在模板三件套之上按选题加挂):**故事钩子**(悬念开头 -> 情节展开 -> 转折 -> 感悟,适合人设 / 叙述)、**清单体**("N 个方法" -> 逐条展开 -> 总结,适合干货 / 技巧)。

口播类型与语速 / 时长速查:

| 类型 | 核心 | 语速 | 时长建议 |
|------|------|------|---------|
| 知识分享型 | 信息密度 + 易懂 | 中速 | 60-120s |
| 观点输出型 | 立场鲜明 + 逻辑强 | 中快 | 45-90s |
| 故事叙述型 | 情绪起伏 + 真实感 | 慢-中 | 90-180s |
| 产品种草型 | 场景 + 利益点 | 中快 | 30-60s |
| 情绪共鸣型 | 共情 + 金句 | 慢-中 | 30-60s |

## 图文模式模板(mode=article)

```json
{
  "mode": "article",
  "topic": "<主题>",
  "audience": "<受众>",
  "brand_context": { },
  "topic_matrix": ["同口播 5 维度,适配图文(更适合长文 / 深度展开 / 可检索)"],
  "title_options": ["3-5 个标题候选,覆盖提问式 / 数字式 / 悬念式 / 价值式"],
  "article_draft": {
    "markdown_version": "完整 Markdown:# 标题 / ## 小标题 / 列表 / 加粗 / 引用 / 代码块",
    "plain_text_version": "去掉全部 markdown 符号,纯文字 + 空行 + 编号(一、二、或 1. 2.)"
  },
  "tags": ["5-8 个平台标签"],
  "summary": "100 字以内摘要",
  "compliance_check": {
    "dual_version_output": null,
    "no_competitor_platforms": null,
    "no_external_links": null,
    "brand_consistency": null
  }
}
```

**双版本纪律**:两版内容必须一致,只是排版语法不同。先写 Markdown 版,再由它派生纯文本版——纯文本版**不得出现 `#` `*` `>` `-` 等 markdown 符号**(部分平台粘贴会原样显示)。

图文平台适配速查(字数 / 标签 / 建议版本):

| 平台 | 正文字数 | 标签 | 建议版本 |
|------|---------|------|---------|
| 公众号 | 不限 | -(用合集) | Markdown 版 |
| 知乎 | 不限 | 话题 | Markdown 版 |
| 小红书 | 1000 字内最佳 | # 话题 ≤10 | 纯文本版(偏短偏轻) |
| 雪球 | 不限 | # 标签 / $代码 | Markdown 版 |
| 东财 / 同花顺 | 偏短 | 标签 | 纯文本版 |
| 微博 | 140 / 长文 | #话题# | 纯文本版 |

## 合规红线(compliance_check 逐项自检后填 true/false)

- **no_competitor_platforms**——口播稿 / 字幕 / 画面 / 图文里禁止出现其他平台名(抖音、B 站、小红书、知乎、公众号、微信、微博、快手、视频号…)。必须提及时用"某个平台""某 App"代称或删除。
- **no_external_links**——禁止外链、二维码,以及"私信我""加微信""加群""主页有链接""搜索 XXX""点左下角"等站外引流。**CTA 只用平台内动作**:点赞 / 关注 / 收藏 / 评论 / 转发 / 「主页还有更多」。
- **no_contact_info**——手机号 / 微信号 / QQ 号 / 邮箱 / 个人网址一律不进稿。
- **brand_consistency**——产品名、Slogan、定位与 brand_context 及项目公开资料完全一致。
- **dual_version_output**(仅图文)——已产出 Markdown 版 + 纯文本版双版本。
- **敏感品类克制**——金融、医疗、投资建议类表述需克制,不构成具体投资 / 用药建议。

## 策划定稿后:自驱下游出成品

用户要的不只是文本计划时,用定稿内容直接串 VAAS MCP 工具链(**动手前把成稿给用户过目,用户通过再渲染**):

| 内容形态 | 链路 |
|---|---|
| 口播短视频(结构化成品) | full_outline 展成完整口播稿 → `render_video(type=carousel\|listicle\|data-viz\|kinetic-quote\|news-flash, script=口播稿, inputs={...}, slug=<新 slug>)`。配音 / 字幕 / 场景对齐管线内自动完成 |
| 口播短视频(自定义分镜) | 口播稿 → `generate_voice(text, voice?)` 拿 `{file_path, duration_ms}` → 按 duration_ms 排场景 → `render_video(storyboard={size, scenes}, voice_path=<音频绝对路径>)` |
| 长口播 / 多段 | 口播稿切段 → `voiceover_assemble(segments=[{text, window_s?}], voice?)` 成整条音频(超窗段会返回压缩建议) → `render_video(storyboard=..., voice_path=...)` |
| 图文成稿 | `article_draft.markdown_version` → `render_document(source=markdown 文本或路径, format=pdf\|longimage)` |
| 数据配图 | 数据点 → `render_still(kind="chart", spec={echarts_option, size})`;要"讲到哪长到哪"的图表动画则改走 `render_video(type="data-viz")` |
| 封面 | `render_still(kind="cover", spec={title, subtitle?, tags?})` |

选型与传参细节(四种场景 kind、seek 契约、chart 桥、BGM)**见 `fd-vaas-storyboard` skill**。动手前的三个查询习惯:

- 音色 / 模型能力先查 `models_voices()`;
- 类型输入契约先查 `templates_get(domain="video", id=<type>)`(清单用 `templates_list(domain="video")`);
- type 模式的 slug 必须是全新的(同名 task 目录已存在会报错)。

> render_document 支持 pdf 与长图两种格式；图文档链路遇模板名报错时先 templates_list(domain="doc") 查可用版式。

分发(发布到各平台)不在本 skill 范围:图文走 `fd-vaas-publish-docs`,视频走 `fd-vaas-publish-videos`。

## 选题 / 合规 Checklist(产出后逐条自检)

- [ ] 前 3 秒 / 标题能让受众停下来?(钩子强度)
- [ ] 内容有「信息增量」?(不是常识复读)
- [ ] 受众看完会想转发 / 评论?(互动钩子)
- [ ] 和账号定位一致?(人设一致性——brand_context 历史稿读过没有)
- [ ] 同赛道有类似内容吗?(differentiation_angles 给够 2-3 个,差异化 ≥ 60%)
- [ ] **无其他平台名?无站外引流 / 联系方式?**(红线)
- [ ] **图文已出 Markdown 版 + 纯文本版双版本?**(红线)
- [ ] 产品名 / Slogan / 定位与品牌资料一致?

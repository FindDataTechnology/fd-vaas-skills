# 同花顺财经号 tonghuashun

同花顺媒体开放平台(财经号)发文。**需要先开通财经号/媒体号资质**,没开通无发文入口。编辑器富文本,不吃 markdown。

## 入口(⚠️ 2026-08-11 probe:域名 302 跳转)

| 项 | URL / 值 |
|---|---|
| 媒体开放平台 | `https://media.10jqka.com.cn/` ⚠️ probe 实测 **302 跳** `https://t.10jqka.com.cn/newcircle/creation/adviserEnterGuide/`(投顾入驻引导页) |
| 登录 | `https://upass.10jqka.com.cn/`(同花顺通行证) |
| 发文入口 | ⚠️ 未确认 —— 需登录且已开通财经号后,从创作中心找「发文章」;probe 时账号未登录,落在投顾入驻引导页 |

> ⚠️ 同花顺开放平台域名多个(`media.10jqka.com.cn` / `open.10jqka.com.cn` / `t.10jqka.com.cn/newcircle/creation/`),以你账号登录后实际能进的为准。**先登录,确认真实发文入口后回填本表**。

## 0) 首次:登录后 probe 核选择器

```bash
export PROBE_URL="https://media.10jqka.com.cn/"
# ⚠️ 会 302 跳 t.10jqka.com.cn/newcircle/creation/...;先登录(需财经号资质),确认真实发文入口后把 PROBE_URL 换成编辑器 URL 再跑 references/probe.md
```

## 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-tonghuashun')
await openOrReuseTab('https://media.10jqka.com.cn/', { wait: true, timeout: 40 })
await wait(4)
const info = await pageInfo()
// 未登录/无财经号资质会被引到 adviserEnterGuide(投顾入驻引导页)
const loggedIn = !/\/(login|upass|passport)\b/i.test(info.url) && !info.url.includes('adviserEnterGuide')
cliLog(JSON.stringify({ url: info.url, loggedIn }))
if (!loggedIn) cliLog('⚠️ 落在投顾入驻引导页 = 未登录或未开通财经号;若已登录仍跳转,先去申请财经号资质')
EOF
```

## 2) 登录 handoff

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-tonghuashun')
await openOrReuseTab('https://media.10jqka.com.cn/', { wait: true, timeout: 30 })
await wait(3)
await handOffTaskSpace(task.id)
cliLog('请在 ego-browser 窗口登录同花顺财经号后台(需已开通),完成后回复 continue')
EOF
```

收回:
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-tonghuashun')
await takeOverTaskSpace(task.id)
await wait(3)
const info = await pageInfo()
cliLog(JSON.stringify({ url: info.url, loggedIn: !/\/(login|upass|passport)\b/i.test(info.url) }))
EOF
```

## 3) 发文 heredoc 骨架

```bash
export DOC_TITLE="$(cat .adapted/tonghuashun/title.txt)" \
       DOC_BODY="$(cat .adapted/tonghuashun/body.md)" \
       DOC_TAGS="$(cat .adapted/tonghuashun/tags.txt)" \
       DOC_COVER="$(cat .adapted/tonghuashun/cover.txt)"
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-tonghuashun')
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean).slice(0, 10)
const COVER = process.env.DOC_COVER || ''

await openOrReuseTab('https://media.10jqka.com.cn/', { wait: true, timeout: 40 })
await wait(4)
// ⚠️ 302 跳 t.10jqka.com.cn/newcircle/creation/...;落在 adviserEnterGuide = 未登录/无资质,别硬点

// 进发文编辑器 ⚠️ 待 probe(需登录后从创作中心找「发文章」)
try { await click('xpath=//*[contains(text(),"发文章") or contains(text(),"写文章") or contains(text(),"发布内容")]') } catch (e) {}
await wait(4)

// 标题 ⚠️ 待 probe
await waitForElement('input[placeholder*="标题"], #title, .article-title', { timeout: 20 })
await fillInput('input[placeholder*="标题"], #title, .article-title', TITLE.slice(0, 30))

// 正文(富文本 contenteditable)⚠️ 待 probe
await click('[contenteditable="true"], .ql-editor, .editor-content')
await pressKey('Control+a'); await pressKey('Delete')
await typeText(BODY)   // 纯文本

// 封面(可选)⚠️ 待 probe
if (COVER) {
  try {
    await click('xpath=//*[contains(text(),"上传封面") or contains(text(),"封面图")]')
    await wait(1)
    await uploadFile('input[type="file"][accept*="image"]', COVER)
    await wait(3)
  } catch (e) { cliLog('封面跳过: ' + e.message) }
}

// 标签 ⚠️ 待 probe
for (const t of TAGS) {
  try {
    await click('xpath=//*[contains(text(),"添加标签") or contains(text(),"标签")]')
    await typeText(t); await wait(2); await pressKey('Enter'); await wait(1)
  } catch (e) {}
}

// 发布 ⚠️ 待 probe
await click('xpath=//button[normalize-space(text())="发布" or normalize-space(text())="提交"]')
await wait(5)
cliLog('发布指令已发,请确认')

await completeTaskSpace(task.id, { keep: false })
EOF
```

## 选择器表(⚠️ 全部待 probe 实机确认)

| 元素 | 选择器(推断) |
|---|---|
| 发文入口 | `xpath=//*[contains(text(),"发文章")]` |
| 标题 | `input[placeholder*="标题"]` / `#title` |
| 正文 | `[contenteditable="true"]` / `.ql-editor` |
| 封面上传 | `input[type="file"][accept*="image"]` |
| 标签 | `xpath=//*[contains(text(),"添加标签")]` |
| 发布按钮 | `xpath=//button["发布"]` |

## 平台坑

- **资质门槛**:必须先开通同花顺财经号/媒体号,没开通进不了发文后台。
- **开放平台域名多个**,以你账号实际能进的为准。
- **不吃 markdown**,正文灌纯文本。
- **标题 ~30 字**,publish.mjs 已截。
- 财经内容审核较严。

## ⚠️ 验证状态

**全部选择器 + 后台 URL 均未实机验证**(推断自同花顺开放平台通用结构)。2026-08-11 probe 实测:`media.10jqka.com.cn` **302 跳投顾入驻引导页**,当时账号未登录。**先登录(需已开通财经号),确认真实发文入口,重跑 `references/probe.md`**,确认后改 ✅ + 日期。

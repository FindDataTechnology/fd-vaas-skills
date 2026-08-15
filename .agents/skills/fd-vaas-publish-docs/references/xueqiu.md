# 雪球长文 xueqiu

财经社区长文,可关联 `$股票`、话题。编辑器富文本,**不吃 markdown 源码**,正文灌纯文本。

## 入口

| 项 | URL / 值 |
|---|---|
| 首页/登录 | `https://xueqiu.com/`(登录是**页内弹层**:手机验证码「发送验证码」/扫码,URL 不变) |
| 长文编辑器 | ⚠️ 旧入口 `https://xueqiu.com/zhuanlan/publish` **已 404**(2026-08-11 probe 实测);真实入口待登录后确认(疑似首页/个人页「写长文」弹层) |
| 发布成功 | URL 变 `https://xueqiu.com/<uid>/<id>` 或跳专栏列表 |

> ⚠️ 2026-08-11 probe:旧 URL 直接 404,且账号未登录(页内弹「发送验证码」)。**先登录,再从首页/个人页找「写长文」入口,重 probe 后回填本表**。

## 0) 首次:登录后 probe 核选择器

```bash
export PROBE_URL="https://xueqiu.com/"
# ⚠️ 旧入口已 404:先登录(页内弹层),在首页/个人页找到「写长文」入口后,把 PROBE_URL 换成真实编辑器 URL 再跑 references/probe.md
```

## 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xueqiu')
await openOrReuseTab('https://xueqiu.com/', { wait: true, timeout: 40 })
await wait(3)
const info = await pageInfo()
// 登录是页内弹层,URL 不变;粗判:页面同时含「发送验证码」和「登录」= 未登录
const txt = await js('document.body.innerText.slice(0, 3000)')
const loggedIn = !(txt.includes('发送验证码') && txt.includes('登录'))
cliLog(JSON.stringify({ url: info.url, loggedIn }))
EOF
```

## 2) 登录 handoff(页内弹层:手机验证码/扫码)

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xueqiu')
await openOrReuseTab('https://xueqiu.com/', { wait: true, timeout: 30 })
await wait(2)
// 触发登录弹层(首页「登录」按钮)
try { await click('xpath=//*[contains(text(),"登录")][1]') } catch (e) {}
await wait(2)
await handOffTaskSpace(task.id)
cliLog('请在 ego-browser 窗口的雪球弹层里登录(手机验证码或扫码),完成后回复 continue')
EOF
```

收回:
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xueqiu')
await takeOverTaskSpace(task.id)
await wait(2)
const txt = await js('document.body.innerText.slice(0, 3000)')
cliLog(JSON.stringify({ loggedIn: !(txt.includes('发送验证码') && txt.includes('登录')) }))
EOF
```

## 3) 发文 heredoc 骨架

```bash
export DOC_TITLE="$(cat .adapted/xueqiu/title.txt)" \
       DOC_BODY="$(cat .adapted/xueqiu/body.md)" \
       DOC_TAGS="$(cat .adapted/xueqiu/tags.txt)" \
       DOC_COVER="$(cat .adapted/xueqiu/cover.txt)"
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xueqiu')
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean).slice(0, 10)
const COVER = process.env.DOC_COVER || ''

// ⚠️ 2026-08 probe:/zhuanlan/publish 已 404。先开首页,登录后点「写长文」入口(弹层)
await openOrReuseTab('https://xueqiu.com/', { wait: true, timeout: 40 })
await wait(3)
try {
  await click('xpath=//*[contains(text(),"写长文") or contains(text(),"发长文")]')
  await wait(4)
} catch (e) { cliLog('⚠️ 未找到「写长文」入口,先跑 probe 定位真实入口: ' + e.message) }

// 标题 ⚠️ 待 probe
await waitForElement('input[placeholder*="标题"], #title', { timeout: 20 })
await fillInput('input[placeholder*="标题"], #title', TITLE.slice(0, 50))

// 正文(富文本 contenteditable)⚠️ 待 probe
await click('[contenteditable="true"], .editor-content, .ql-editor')
await pressKey('Control+a'); await pressKey('Delete')
await typeText(BODY)   // 纯文本,markdown 符号要 strip

// 封面(可选)⚠️ 待 probe
if (COVER) {
  try {
    await click('xpath=//*[contains(text(),"上传封面") or contains(text(),"封面")]')
    await wait(1)
    await uploadFile('input[type="file"][accept*="image"]', COVER)
    await wait(3)
  } catch (e) { cliLog('封面跳过: ' + e.message) }
}

// 话题 / 股票标签($代码)⚠️ 待 probe
for (const t of TAGS) {
  try {
    await click('xpath=//*[contains(text(),"添加标签") or contains(text(),"话题")]')
    await wait(1)
    await typeText(t)
    await wait(2)
    await pressKey('Enter')
    await wait(1)
  } catch (e) {}
}

// 发布 ⚠️ 待 probe
await click('xpath=//button[normalize-space(text())="发布"]')
await wait(5)
cliLog('发布指令已发,请确认页面跳转/提示')

await completeTaskSpace(task.id, { keep: false })
EOF
```

## 选择器表(⚠️ 待 probe 实机确认)

| 元素 | 选择器(推断) | 说明 |
|---|---|---|
| 标题 | `input[placeholder*="标题"]` / `#title` | 长文标题 |
| 正文 | `[contenteditable="true"]` / `.ql-editor` | 可能是 Quill 编辑器 |
| 封面上传 | `input[type="file"][accept*="image"]` | 先点「上传封面」 |
| 话题/股票 | `xpath=//*[contains(text(),"添加标签")]` | `$股票代码` 或话题 |
| 发布按钮 | `xpath=//button["发布"]` | 页面底部/右上 |

## 平台坑

- **不吃 markdown**:雪球富文本把 markdown 当纯文本,正文先 strip 符号。
- **长文入口可能变弹层**:如果 `/zhuanlan/publish` 跳走,去个人页找「写长文」按钮。
- **关联股票**:用 `$代码`(如 `$SH600519`)能关联个股,财经内容推荐率高。
- **标题 ~50 字**,publish.mjs 已截。

## ⚠️ 验证状态

选择器来自推断,**未在登录态下实机验证**;且 2026-08-11 probe 实测旧入口 `/zhuanlan/publish` **已 404**,当时账号未登录(页内弹「发送验证码」)。**先登录,再从首页/个人页确认真实「写长文」入口,重跑 `references/probe.md`**,确认后改 ✅ + 日期。

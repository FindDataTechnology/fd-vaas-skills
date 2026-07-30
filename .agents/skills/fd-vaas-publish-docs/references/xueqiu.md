# 雪球长文 xueqiu

财经社区长文,可关联 `$股票`、话题。编辑器富文本,**不吃 markdown 源码**,正文灌纯文本。

## 入口

| 项 | URL / 值 |
|---|---|
| 长文编辑器 | `https://xueqiu.com/zhuanlan/publish`(未登录跳登录) |
| 登录页 | `https://xueqiu.com/user/login` |
| 发布成功 | URL 变 `https://xueqiu.com/<uid>/<id>` 或跳专栏列表 |

> ⚠️ 雪球长文入口可能改成个人页「写长文」按钮触发弹层,而非独立 URL。probe 时如果 `/zhuanlan/publish` 跳走,改去 `https://xueqiu.com/` 个人页找「写长文」。

## 0) 首次:probe 核选择器

```bash
export PROBE_URL="https://xueqiu.com/zhuanlan/publish"
# 跑 references/probe.md;雪球编辑器结构未实机验证,必跑
```

## 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xueqiu')
await openOrReuseTab('https://xueqiu.com/zhuanlan/publish', { wait: true, timeout: 40 })
await wait(3)
const info = await pageInfo()
const loggedIn = !/\/(login|signin)\b/i.test(info.url)
cliLog(JSON.stringify({ url: info.url, loggedIn }))
EOF
```

## 2) 登录 handoff(扫码)

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xueqiu')
await openOrReuseTab('https://xueqiu.com/user/login', { wait: true, timeout: 30 })
await wait(2)
await handOffTaskSpace(task.id)
cliLog('请在 ego-browser 窗口登录雪球(扫码或账号),完成后回复 continue')
EOF
```

收回:
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xueqiu')
await takeOverTaskSpace(task.id)
await wait(2)
const info = await pageInfo()
cliLog(JSON.stringify({ url: info.url, loggedIn: !/\/(login|signin)\b/i.test(info.url) }))
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

await openOrReuseTab('https://xueqiu.com/zhuanlan/publish', { wait: true, timeout: 40 })
await wait(3)

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

选择器来自雪球编辑器结构推断,**未在登录态下实机验证**。长文入口 URL 可能已改弹层。首次发布前**必须**跑 `references/probe.md`,确认后改 ✅ + 日期。

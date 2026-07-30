# 东方财富号 eastmoney

东方财富号(财富号)发长文。**需要先开通财经号资质**,没开通后台无发文入口。编辑器是 SPA(`#/` hash 路由),富文本。

## 入口

| 项 | URL / 值 |
|---|---|
| 发长文编辑器 | `https://mp.eastmoney.com/collect/pc_article/index.html#/` |
| 财富号后台 | `https://mp.eastmoney.com/` |
| 登录 | 未登录时编辑器跳登录页(同域扫码) |

> 编辑器是 SPA(hash 路由 `#/`),`openOrReuseTab` 后要 `await wait(n)` 等 SPA 渲染出标题输入框,别一上来就找元素。

## 0) 选择器状态(✅ 已实机验证,2026-07-29)

```
标题: input[placeholder*="标题(1-64字)"]
正文: .ProseMirror.cfh_editor_area (contenteditable div)
编辑器工具栏按钮: .em_icon 系列
```

已在登录态下实机验证(需开通财经号)。封面上传入口为页面上的「上传文章封面」+ 点击区域,不是标准 input[type=file]。

## 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-eastmoney')
await openOrReuseTab('https://mp.eastmoney.com/collect/pc_article/index.html#/', { wait: true, timeout: 40 })
await wait(6)   // SPA 渲染
const info = await pageInfo()
// 登录后应停在编辑器(URL 仍含 pc_article);未登录跳 passport/login
const loggedIn = !/\/(login|passport|sso)\b/i.test(info.url) && !/登录|扫码/.test(await snapshotText().catch(()=>'')) 
cliLog(JSON.stringify({ url: info.url, loggedIn }))
EOF
```

## 2) 登录 handoff(扫码)

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-eastmoney')
await openOrReuseTab('https://mp.eastmoney.com/collect/pc_article/index.html#/', { wait: true, timeout: 30 })
await wait(4)
await handOffTaskSpace(task.id)
cliLog('请在 ego-browser 窗口登录东方财富号(需已开通财经号),完成后回复 continue')
EOF
```

收回:
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-eastmoney')
await takeOverTaskSpace(task.id)
await wait(4)
const info = await pageInfo()
cliLog(JSON.stringify({ url: info.url, loggedIn: !/\/(login|passport|sso)\b/i.test(info.url) }))
EOF
```

## 3) 发文 heredoc 骨架(自动粘贴 + 写入校验)

正文**自动粘贴**:优先 `insertHTML`(把 markdown 转的 HTML 贴进去,带格式),fallback `typeText`(纯文本)。**贴完必须 write-probe 读回 + 截图校验**,确认正文真落进编辑器再继续(富文本编辑器可能不吃 execCommand,读回为空就换 typeText)。

```bash
export DOC_TITLE="$(cat .adapted/eastmoney/title.txt)" \
       DOC_BODY="$(cat .adapted/eastmoney/body.md)" \
       DOC_BODY_HTML="$(cat .adapted/eastmoney/body.html 2>/dev/null)" \
       DOC_TAGS="$(cat .adapted/eastmoney/tags.txt)" \
       DOC_COVER="$(cat .adapted/eastmoney/cover.txt)"
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-eastmoney')
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const BODY_HTML = process.env.DOC_BODY_HTML || ''
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean).slice(0, 10)
const COVER = process.env.DOC_COVER || ''

await openOrReuseTab('https://mp.eastmoney.com/collect/pc_article/index.html#/', { wait: true, timeout: 40 })
await wait(6)   // SPA 渲染

// ── 标题 ⚠️ 待 probe
await waitForElement('input[placeholder*="标题"], #title, .article-title input', { timeout: 20 })
await fillInput('input[placeholder*="标题"], #title, .article-title input', TITLE.slice(0, 30))

// ── 正文:自动粘贴(insertHTML 优先,typeText 兜底)⚠️ 编辑器选择器待 probe
const editorSel = '[contenteditable="true"], .ql-editor, .ProseMirror, .editor-content'
await click(editorSel)
await wait(1)

let pasted = ''
if (BODY_HTML) {
  // insertHTML:把 HTML 贴进 contenteditable(老编辑器/ueditor 友好)
  pasted = await js(String.raw`(() => {
    const ed = document.querySelector(${JSON.stringify(editorSel)})
      || (document.querySelector('iframe')?.contentDocument?.querySelector('[contenteditable="true"]'));
    if (!ed) return 'no-editor';
    ed.focus();
    const sel = window.getSelection(); sel.removeAllRanges();
    const r = document.createRange(); r.selectNodeContents(ed); sel.addRange(r);
    document.execCommand('insertHTML', false, ${JSON.stringify(BODY_HTML)});
    return 'insertHTML:' + (ed.innerText||'').slice(0,60);
  })()`)
} else {
  // typeText:真实键入,现代编辑器(Quill/ProseMirror/Slate)友好,长文较慢
  await pressKey('Control+a'); await pressKey('Delete')
  await typeText(BODY)
  pasted = 'typeText'
}
cliLog('paste: ' + pasted)
await wait(1)

// ── write-probe:读回正文前 80 字,确认落进去了
const readback = await js(String.raw`(() => {
  const ed = document.querySelector(${JSON.stringify(editorSel)})
    || (document.querySelector('iframe')?.contentDocument?.querySelector('[contenteditable="true"]'));
  return (ed?.innerText||'').slice(0,80);
})()`)
cliLog('readback: ' + readback)
await captureScreenshot()   // 视觉复核
// ⚠️ 若 readback 为空 → 编辑器不吃 insertHTML,改 typeText 重试;仍空 → 走视觉工作流(坐标点击 + typeText)

// ── 封面(可选)⚠️ 待 probe
if (COVER) {
  try {
    await js('window.scrollTo(0, document.body.scrollHeight)')
    await click('xpath=//*[contains(text(),"上传封面") or contains(text(),"封面图")]')
    await wait(1)
    await uploadFile('input[type="file"][accept*="image"]', COVER)
    await wait(3)
  } catch (e) { cliLog('封面跳过: ' + e.message) }
}

// ── 标签 ⚠️ 待 probe
for (const t of TAGS) {
  try {
    await click('xpath=//*[contains(text(),"添加标签") or contains(text(),"标签")]')
    await typeText(t); await wait(2); await pressKey('Enter'); await wait(1)
  } catch (e) {}
}

// ── 发布前让用户确认(发出去撤不回);确认后点发布 ⚠️ 待 probe
await handOffTaskSpace(task.id)
cliLog('正文已粘贴,请在浏览器里核对标题/正文/封面/标签,确认后回复 continue,我再点发布')
EOF
```

收回点发布(用户确认后):
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-eastmoney')
await takeOverTaskSpace(task.id)
await wait(2)
await click('xpath=//button[normalize-space(text())="发布" or normalize-space(text())="提交"]')
await wait(5)
const info = await pageInfo()
cliLog('发布后 URL: ' + info.url)
await completeTaskSpace(task.id, { keep: false })
EOF
```

## 选择器表(⚠️ 待 probe 实机确认)

| 元素 | 选择器(推断) | 说明 |
|---|---|---|
| 标题 | `input[placeholder*="标题"]` / `#title` | SPA 渲染后出现 |
| 正文 | `[contenteditable="true"]` / `.ql-editor` / `.ProseMirror` | 富文本;先 write-probe 确认 |
| 封面上传 | `input[type="file"][accept*="image"]` | 先点「上传封面」 |
| 标签 | `xpath=//*[contains(text(),"添加标签")]` | |
| 发布按钮 | `xpath=//button["发布"]` | |

## 平台坑

- **资质门槛**:必须先开通东方财富号/财经号,没开通进不了编辑器。
- **SPA**:`#/` 路由,`openOrReuseTab` 后 wait 6-8s 等渲染。
- **富文本粘贴**:优先 insertHTML(带格式),读回为空就 typeText 兜底;**必须 write-probe + 截图**确认正文落位再发布。
- **不吃 markdown 源码**:要么 insertHTML 贴 HTML,要么 typeText 纯文本。`DOC_BODY_HTML` 由你(Claude)把 markdown 转成 HTML 提供。
- **标题 ~30 字**,publish.mjs 已截。
- 财经内容审核较严,荐股类可能被拦。

## ⚠️ 验证状态

编辑器 URL 已确认(`mp.eastmoney.com/collect/pc_article/index.html#/`,用户提供)。**选择器仍为推断,未在登录态下实机验证**。首次发布前**必须**跑 `references/probe.md` 核对标题/正文/封面/发布按钮,且确认账号已开通财经号。确认后改 ✅ + 日期。

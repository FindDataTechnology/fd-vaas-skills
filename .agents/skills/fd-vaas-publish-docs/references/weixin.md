# 微信公众号 weixin

最重的平台:富文本编辑器(ueditor)**不吃 markdown 源码**、封面必填、摘要必填、群发有频次限制。**默认存草稿,不群发**,让用户手动群发。

## 入口

| 项 | URL / 值 |
|---|---|
| 后台 | `https://mp.weixin.qq.com/`(扫码登录) |
| 图文编辑器 | 后台点「发表」->「图文消息」-> 新建;URL 形如 `https://mp.weixin.qq.com/cgi-bin/appmsg?...` |
| 发布成功 | 草稿:出现「已保存」/跳草稿箱;群发:跳群发记录 |

公众号编辑器 URL 带动态 token,**不要硬编码**,heredoc 里先开后台再点「新建图文」进去。

## 0) 首次:probe 核选择器

```bash
export PROBE_URL="https://mp.weixin.qq.com/"
# 跑 references/probe.md 的 probe;公众号编辑器可能在 iframe 里,
# probe 里 dump 不到正文框时,加 document.querySelector('iframe').contentDocument 递归 dump
```

## 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-weixin')
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 40 })
await wait(4)
const info = await pageInfo()
// 登录后 URL 会进 /cgi-bin/home 或 /cgi-bin/frame;未登录停在扫码页
const loggedIn = /\/cgi-bin\//.test(info.url)
cliLog(JSON.stringify({ url: info.url, loggedIn }))
EOF
```

## 2) 登录 handoff(扫码)

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-weixin')
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 30 })
await wait(3)
await handOffTaskSpace(task.id)
cliLog('请在 ego-browser 窗口用微信扫码登录公众号后台,完成后回复 continue')
EOF
```

收回:
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-weixin')
await takeOverTaskSpace(task.id)
await wait(3)
const info = await pageInfo()
cliLog(JSON.stringify({ url: info.url, loggedIn: /\/cgi-bin\//.test(info.url) }))
EOF
```

## 3) 发文 heredoc 骨架(默认存草稿)

⚠️ 公众号编辑器**不吃 markdown 源码**。正文用 `typeText` 灌**纯文本**(publish.mjs 写的 `.adapted/weixin/body.md` 里如果是 markdown,heredoc 里先 strip 符号,或让用户手动渲染后贴)。

```bash
export DOC_TITLE="$(cat .adapted/weixin/title.txt)" \
       DOC_BODY="$(cat .adapted/weixin/body.md)" \
       DOC_COVER="$(cat .adapted/weixin/cover.txt)" \
       DOC_SUMMARY="$(cat .adapted/weixin/summary.txt)"
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-weixin')
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const COVER = process.env.DOC_COVER || ''
const SUMMARY = process.env.DOC_SUMMARY || ''

// 1. 开后台,点「图文消息」新建 ⚠️ 待 probe
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 40 })
await wait(4)
try { await click('xpath=//*[contains(text(),"图文消息")]') } catch (e) {}
await wait(4)

// 2. 标题 ⚠️ 待 probe
await waitForElement('#title', { timeout: 30 })            // 公众号标题 input id 常为 title
await fillInput('#title', TITLE.slice(0, 64))

// 3. 正文(contenteditable 富文本;可能在 iframe 里)⚠️ 待 probe
//    先试主文档,再 fallback iframe
let editorFocused = false
try {
  await click('body[contenteditable="true"], .edui-body-container, [contenteditable="true"]')
  editorFocused = true
} catch (e) {}
if (!editorFocused) {
  await js(String.raw`
    const f = document.querySelector('iframe');
    const d = f && f.contentDocument;
    if (d) { const e = d.querySelector('[contenteditable="true"],.edui-body-container,body'); e && e.focus(); }
  `)
}
await pressKey('Control+a'); await pressKey('Delete')
await typeText(BODY)   // 纯文本;markdown 符号会原样显示,先 strip

// 4. 封面(必填 900×500)⚠️ 待 probe
if (COVER) {
  try {
    await js('window.scrollTo(0, document.body.scrollHeight)')
    await click('xpath=//*[contains(text(),"从正文选择") or contains(text(),"上传")]')  // ⚠️
    await wait(1)
    await uploadFile('input[type="file"][accept*="image"]', COVER)
    await wait(3)
    await click('xpath=//button[normalize-space(text())="完成"]')
    await wait(1)
  } catch (e) { cliLog('封面设置跳过: ' + e.message) }
}

// 5. 摘要(必填)⚠️ 待 probe
try {
  await fillInput('textarea[placeholder*="摘要"], #digest', SUMMARY)
} catch (e) {
  await js(`(()=>{const e=document.querySelector('textarea[placeholder*="摘要"], #digest'); if(e){e.value=${JSON.stringify(SUMMARY)}; e.dispatchEvent(new Event('input',{bubbles:true}))}})()`)
}

// 6. 保存草稿(默认,不群发)⚠️ 待 probe
await click('xpath=//button[normalize-space(text())="保存为草稿"] or //a[normalize-space(text())="保存为草稿"]')
await wait(3)
cliLog('已存草稿,请在后台确认;群发需手动点(订阅号每天 1 次)')

await completeTaskSpace(task.id, { keep: false })
EOF
```

## 选择器表(⚠️ 待 probe 实机确认)

| 元素 | 选择器(推断) | 说明 |
|---|---|---|
| 新建图文 | `xpath=//*[contains(text(),"图文消息")]` | 后台首页入口 |
| 标题 | `#title` | 图文标题 input |
| 正文 | `body[contenteditable]` / `.edui-body-container` / iframe 内 | ueditor 富文本,**可能在 iframe** |
| 封面上传 | `input[type="file"][accept*="image"]` | 先点「上传」让 input 出现 |
| 摘要 | `#digest` / `textarea[placeholder*="摘要"]` | **必填** |
| 保存草稿 | `xpath=//button["保存为草稿"]` | 默认走这个;群发另点 |

## 平台坑

- **不吃 markdown**:公众号 ueditor 把 markdown 源码当纯文本。要么贴前 strip 成纯文本,要么用 md2html 工具渲染成富文本再贴。**最大坑**。
- **正文可能在 iframe**:老版图文编辑器正文在 `iframe.contentDocument` 里,probe dump 不到时切 iframe。
- **封面必填 900×500**,不填不能保存。
- **摘要必填**,publish.mjs 没给 `--summary` 时从正文前 120 字生成。
- **群发频次**:订阅号每天 1 次、服务号每月 4 次。**默认存草稿**,群发让用户手动。
- **原创声明**:有「原创」开关,需账号有原创权限,**默认不勾**。

## ⚠️ 验证状态

选择器来自公众号后台通用结构推断(ueditor class、`#title`/`#digest` 常见 id),**未在登录态下实机验证**。公众号前端改版频繁、正文可能在 iframe,首次发布前**必须**跑 `references/probe.md`(含 iframe 递归 dump),确认后改 ✅ + 日期。

# 知乎专栏 zhihu

图文长文,编辑器**支持粘贴 Markdown 自动渲染**,是最省事的平台。

## 入口

| 项 | URL / 值 |
|---|---|
| 编辑器 | `https://zhuanlan.zhihu.com/write` |
| 登录页 | `https://www.zhihu.com/signin`(未登录时编辑器跳这) |
| 发布成功 | URL 变 `https://zhuanlan.zhihu.com/p/<id>` |

## 0) 选择器状态(✅ 已实机验证,2026-07-29)

```
标题: textarea[placeholder*="请输入标题（最多 100 个字）"]
正文: .public-DraftEditor-content (Draft.js contenteditable)
发布按钮: button.innerText.includes("发布")
```

已在登录态下实机验证,无需再 probe。

## 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-zhihu')
await openOrReuseTab('https://zhuanlan.zhihu.com/write', { wait: true, timeout: 40 })
await wait(3)
const info = await pageInfo()
const loggedIn = !/\/(signin|login)\b/i.test(info.url)
cliLog(JSON.stringify({ url: info.url, loggedIn }))
EOF
```

## 2) 登录 handoff(扫码)

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-zhihu')
await openOrReuseTab('https://www.zhihu.com/signin', { wait: true, timeout: 30 })
await wait(2)
// 知乎登录页默认有「扫码登录」tab,点它;找不到就 handoff 让用户手动切
try { await click('xpath=//*[contains(text(),"扫码登录")]') } catch (e) {}
await wait(1)
await handOffTaskSpace(task.id)
cliLog('请用知乎 APP 扫码登录,完成后回复 continue')
EOF
```

收回(检测登录态):
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-zhihu')
await takeOverTaskSpace(task.id)
await wait(2)
const info = await pageInfo()
cliLog(JSON.stringify({ url: info.url, loggedIn: !/\/(signin|login)\b/i.test(info.url) }))
EOF
```

## 3) 发文 heredoc 骨架

正文/标题/标签/封面全从环境变量读(publish.mjs `--plan` 打印的 export 行)。知乎支持 markdown 粘贴,直接灌 `DOC_BODY`。

```bash
export DOC_TITLE="$(cat .adapted/zhihu/title.txt)" \
       DOC_BODY="$(cat .adapted/zhihu/body.md)" \
       DOC_TAGS="$(cat .adapted/zhihu/tags.txt)" \
       DOC_COVER="$(cat .adapted/zhihu/cover.txt)"
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-zhihu')
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean).slice(0, 5)
const COVER = process.env.DOC_COVER || ''

await openOrReuseTab('https://zhuanlan.zhihu.com/write', { wait: true, timeout: 40 })
await wait(3)

// 标题 ⚠️ 选择器待 probe 确认
await waitForElement('textarea[placeholder*="标题"]', { timeout: 20 })
await fillInput('textarea[placeholder*="标题"]', TITLE)

// 正文(contenteditable,支持 markdown 粘贴渲染)⚠️ 待 probe
await click('.public-DraftEditor-content')
await pressKey('Control+a'); await pressKey('Delete')
// 用 typeText 粘贴正文;知乎会渲染 markdown
await typeText(BODY)
await wait(1)

// 封面(可选)
if (COVER) {
  try {
    await click('xpath=//*[contains(text(),"上传封面")]/ancestor::*[1]')  // ⚠️ 待 probe
    await wait(1)
    await uploadFile('input[type="file"][accept*="image"]', COVER)        // ⚠️ 待 probe
    await wait(3)
  } catch (e) { cliLog('封面上传跳过: ' + e.message) }
}

// 话题(≤5)⚠️ 待 probe:知乎话题入口通常是正文底部「+ 添加话题」
for (const t of TAGS) {
  try {
    await click('xpath=//*[contains(text(),"添加话题")]')  // ⚠️ 待 probe
    await wait(1)
    await typeText(t)
    await wait(2)
    await pressKey('Enter')
    await wait(1)
  } catch (e) {}
}

// 发布 ⚠️ 待 probe
await click('xpath=//button[normalize-space(text())="发布"]')
for (let i = 0; i < 30; i++) {
  const u = (await pageInfo()).url
  if (/\/p\/\d+/.test(u)) { cliLog('published: ' + u); break }
  await wait(1)
}
await completeTaskSpace(task.id, { keep: false })
EOF
```

## 选择器表(✅ 已实机验证)

| 元素 | 选择器 | 说明 |
|---|---|---|
| 标题 | `textarea[placeholder*="请输入标题"]` | 专栏标题输入框 |
| 正文 | `.public-DraftEditor-content` | DraftJS 富文本,支持 markdown 粘贴渲染 |
| 发布按钮 | `button.innerText.includes("发布")` | 页面底部/右上角 |
| 封面上传 | `input[type="file"][accept*="image"]` | 先点「上传封面」按钮 |

## 平台坑

- **标题别超 100 字**,超了截断但不报错,列表页显示不全。
- **markdown 粘贴**:知乎专栏编辑器识别 markdown 语法自动渲染,`DOC_BODY` 可直接灌 markdown 源码。
- **封面**:非必填,但有图卡片更吸引点击。

## ✅ 验证状态

标题/正文/发布按钮选择器**已在登录态下实机验证**(2026-07-29)。封面和话题入口暂未验证——下次发布时验证后补充。

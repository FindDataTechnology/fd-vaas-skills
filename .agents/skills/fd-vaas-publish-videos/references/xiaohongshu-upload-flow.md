# 小红书 ego-browser 上传完整流程

来源：`uploader/xiaohongshu_uploader/main.py`（Playwright）改写。登录页已实机确认；发布页选择器为 `[源码]`。

## 关键 URL

- 登录页：`https://creator.xiaohongshu.com/login`
- 视频发布页：`https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video`
- 图文发布页：`https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image`
- 发布成功：URL 含 `/publish/success?`

可被环境变量 `SAU_XHS_CREATOR_BASE_URL` 覆盖基地址（默认 `https://creator.xiaohongshu.com`）。

## 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video', { wait: true, timeout: 30 })
await wait(3)
const info = await pageInfo()
cliLog(JSON.stringify({ url: info.url, loggedIn: !/\/login\b/.test(info.url) }))
EOF
```

## 登录（handoff）

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
await openOrReuseTab('https://creator.xiaohongshu.com/login', { wait: true, timeout: 30 })
await wait(2)
// login-box 默认短信登录；点 img.css-wemwzq 切「扫一扫」
try { await click('img.css-wemwzq') } catch (e) {}
await wait(1)
await handOffTaskSpace(task.id)
cliLog('请扫码登录小红书，完成后回复 continue')
EOF
```

## 上传视频（完整版）

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
const VIDEO = '/abs/path/video.mp4'
const TITLE = '标题'
const DESC = '正文'
const TAGS = ['标签1']
const THUMB = ''            // 可选封面
const SCHEDULE = ''         // 可选 'YYYY-MM-DD HH:MM'

await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video', { wait: true, timeout: 30 })
await wait(2)
await uploadFile("div[class^='upload-content'] input.upload-input", VIDEO)  // [源码]

// 等上传完 [源码]
for (let i = 0; i < 90; i++) {
  const done = await js(String.raw`(()=>{const p=document.querySelector('input.upload-input');if(p){const n=p.parentElement&&p.parentElement.querySelector('.preview-new');if(n&&/上传成功|分辨率|重新上传|编辑封面|已上传|已选择|100%/.test(n.innerText))return true}return !!document.querySelector('input[placeholder*="填写标题"]')})()`)
  if (done) break
  await wait(2)
}

await waitForElement('input[placeholder*="填写标题"]', { timeout: 60 })
await fillInput('input[placeholder*="填写标题"]', TITLE.slice(0, 20))   // [源码] 最多 20 字

await click('p[data-placeholder*="输入正文描述"]')   // [源码]
await pressKey('Backspace'); await pressKey('Control+a'); await pressKey('Delete')
await typeText(DESC); await pressKey('Enter')

for (const t of TAGS.slice(0, 10)) {   // [源码] 最多 10 个
  await typeText('#' + t)
  try {
    await waitForElement('#creator-editor-topic-container', { timeout: 6 })
    await waitForElement('#creator-editor-topic-container .item', { timeout: 4 })
    await click('#creator-editor-topic-container .item')
  } catch (e) {
    for (let k = 0; k < ('#' + t).length; k++) await pressKey('Backspace')
  }
}

// （可选）封面 [源码]
if (THUMB) {
  await waitForElement('xpath=//div[contains(@class,"cover-plugin-title")][normalize-space(text())="设置封面"]', { timeout: 30 })
  await click('xpath=//div[contains(@class,"cover-plugin-title")][normalize-space(text())="设置封面"]/ancestor::div[contains(@class,"cover-plugin-preview")]//div[contains(@class,"cover")]/div[contains(@class,"default")]')
  await waitForElement('div.d-modal.cover-modal', { timeout: 30 })
  await uploadFile('div.d-modal.cover-modal input[type="file"][accept*="image"]', THUMB)
  await wait(2)
  await click('xpath=//div[contains(@class,"cover-modal")]//button[contains(@class,"mojito-button")][normalize-space(text())="确定"]')
}

// 原创声明（可选，等不到跳过）[源码]
try {
  const has = await js(String.raw`!!document.querySelector('div.original-declaration input[type="checkbox"], label:has-text("原创") input[type="checkbox"]')`)
  if (has) await click('xpath=//*[contains(text(),"原创声明")]/ancestor::div[1]//input[@type="checkbox"] | //label[contains(normalize-space(.),"原创")]//input[@type="checkbox"]')
} catch (e) {}

// （可选）定时发布 [源码]
if (SCHEDULE) {
  await click('xpath=//div[contains(@class,"custom-switch-card")][normalize-space(.//text())="定时发布"]//div[contains(@class,"d-switch")]')
  await wait(1)
  await fillInput('.d-datepicker-input-filter input.d-text', SCHEDULE)
  await wait(1)
}

// 发布 [源码]
const btnText = SCHEDULE ? '定时发布' : '发布'
await click('xpath=//button[normalize-space(text())="' + btnText + '"]')
for (let i = 0; i < 30; i++) {
  if (/\/publish\/success\?/.test((await pageInfo()).url)) { cliLog('published'); break }
  await wait(1)
}
await completeTaskSpace(task.id, { keep: false })
EOF
```

## 上传图文（完整版）

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
const IMAGES = ['/abs/path/1.jpg', '/abs/path/2.jpg']
const TITLE = '标题'
const NOTE = '图文正文'
const TAGS = ['标签1']
const SCHEDULE = ''

await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image', { wait: true, timeout: 30 })
await wait(2)
// [源码] 优先 input[type=file][accept*=image]，兜底 upload-content input.upload-input
let uploaded = false
try { await uploadFile('input[type="file"][accept*="image"]', IMAGES); uploaded = true } catch (e) {}
if (!uploaded) await uploadFile("div[class^='upload-content'] input.upload-input", IMAGES)

await waitForElement('input[placeholder*="填写标题"]', { timeout: 60 })   // 标题框出现 = 传完
await fillInput('input[placeholder*="填写标题"]', TITLE.slice(0, 20))
await click('p[data-placeholder*="输入正文描述"]')
await pressKey('Backspace'); await pressKey('Control+a'); await pressKey('Delete')
await typeText(NOTE); await pressKey('Enter')
for (const t of TAGS.slice(0, 10)) {
  await typeText('#' + t)
  try { await waitForElement('#creator-editor-topic-container .item', { timeout: 6 }); await click('#creator-editor-topic-container .item') }
  catch (e) { for (let k = 0; k < ('#' + t).length; k++) await pressKey('Backspace') }
}

if (SCHEDULE) {
  await click('xpath=//div[contains(@class,"custom-switch-card")][normalize-space(.//text())="定时发布"]//div[contains(@class,"d-switch")]')
  await wait(1); await fillInput('.d-datepicker-input-filter input.d-text', SCHEDULE); await wait(1)
}
const btnText = SCHEDULE ? '定时发布' : '发布'
await click('xpath=//button[normalize-space(text())="' + btnText + '"]')
for (let i = 0; i < 30; i++) {
  if (/\/publish\/success\?/.test((await pageInfo()).url)) { cliLog('published'); break }
  await wait(1)
}
await completeTaskSpace(task.id, { keep: false })
EOF
```

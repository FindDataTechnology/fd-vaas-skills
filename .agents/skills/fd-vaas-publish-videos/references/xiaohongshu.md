
# 小红书上传 Skill（ego-browser 版）

两种模式驱动小红书发布，都不需要 sau CLI、不需要 cookie 文件：

- **macOS / Windows / Linux**：ego-browser（本文主体，`ego-browser nodejs <<'EOF'` heredoc）

> ego-browser 跨平台支持 macOS / Windows / Linux。

## 核心模型：登录态持久化，不在 cookie 文件

ego-browser task space 继承用户登录态。登录一次，会话留在 ego-browser profile。没有 `--account`，没有 cookie 文件。

## 前置条件

- `ego-browser --version` 可用。
- 视频或图片的绝对路径。
- 关键 URL：
  - 登录页：`https://creator.xiaohongshu.com/login`
  - 视频发布页：`https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video`
  - 图文发布页：`https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image`
  - 发布成功：URL 含 `/publish/success?`

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 登录态校验 | open 视频发布页，看是否跳 `/login` |
| 登录（扫码） | open 登录页 -> 切「扫一扫」-> handoff |
| 视频上传 | 上传视频 -> 填标题正文话题 -> 发布 |
| 图文上传 | 上传图片 -> 填标题正文话题 -> 发布 |

元数据约定：视频 `title + desc + tags`，图文 `title + note + tags`。小红书话题上限 10 个，超过会卡住发布。

## 默认工作流

1. `check` 确认登录态。
2. 没登录就 `login` handoff 扫码。
3. `upload-video` / `upload-note`。
4. 结束 `completeTaskSpace(id, { keep: false })`。

## 关键 heredoc 片段

### 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video', { wait: true, timeout: 30 })
await wait(3)
const info = await pageInfo()
const loggedIn = !/\/login\b/.test(info.url) && !/creator\.xiaohongshu\.com\/login/.test(info.url)
cliLog(JSON.stringify({ url: info.url, loggedIn }))
EOF
```

### 2) 登录（handoff 扫码）

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
await openOrReuseTab('https://creator.xiaohongshu.com/login', { wait: true, timeout: 30 })
await wait(2)
// 默认是短信登录；点 img.css-wemwzq 切到「扫一扫」，二维码在 .login-box-container「APP扫一扫登录」旁
try { await click('img.css-wemwzq') } catch (e) {}
await wait(1)
await handOffTaskSpace(task.id)
cliLog('请用小红书 APP 扫码登录，完成后回复 continue')
EOF
```

收回：

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
await takeOverTaskSpace(task.id)
await wait(2)
const info = await pageInfo()
cliLog(JSON.stringify({ url: info.url, loggedIn: !/\/login\b/.test(info.url) }))
EOF
```

### 3) 上传视频（骨架，完整版见 references/upload-flow.md）

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
const VIDEO = '/abs/path/video.mp4'
const TITLE = '标题最多20字'
const DESC = '正文描述'
const TAGS = ['标签1', '标签2']   // 最多 10 个

await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video', { wait: true, timeout: 30 })
await wait(2)
await uploadFile("div[class^='upload-content'] input.upload-input", VIDEO)  // [源码]

// 等上传完（预览区出现「上传成功/分辨率/重新上传」或标题框出现）
for (let i = 0; i < 90; i++) {
  const done = await js(String.raw`(()=>{const p=document.querySelector('input.upload-input');if(p){const n=p.parentElement&&p.parentElement.querySelector('.preview-new');if(n&&/上传成功|分辨率|重新上传|编辑封面|已上传|已选择|100%/.test(n.innerText))return true}return !!document.querySelector('input[placeholder*="填写标题"]')})()`)
  if (done) break
  await wait(2)
}

// 标题 [源码]
await waitForElement('input[placeholder*="填写标题"]', { timeout: 60 })
await fillInput('input[placeholder*="填写标题"]', TITLE.slice(0, 20))

// 正文 [源码]
await click('p[data-placeholder*="输入正文描述"]')
await pressKey('Backspace'); await pressKey('Control+a'); await pressKey('Delete')
await typeText(DESC); await pressKey('Enter')

// 话题（最多 10 个，每个等候选框出现再点）[源码]
for (const t of TAGS.slice(0, 10)) {
  await typeText('#' + t)
  try {
    await waitForElement('#creator-editor-topic-container', { timeout: 6 })
    await waitForElement('#creator-editor-topic-container .item', { timeout: 4 })
    await click('#creator-editor-topic-container .item')
  } catch (e) {
    // 没出候选就退格清掉，避免残留进正文
    for (let k = 0; k < ('#' + t).length; k++) await pressKey('Backspace')
  }
}

// 发布 [源码]
await click('xpath=//button[normalize-space(text())="发布"]')
for (let i = 0; i < 30; i++) {
  if (/\/publish\/success\?/.test((await pageInfo()).url)) { cliLog('published'); break }
  await wait(1)
}
await completeTaskSpace(task.id, { keep: false })
EOF
```

### 4) 上传图文（骨架）

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('xhs publish')
const IMAGES = ['/abs/path/1.jpg', '/abs/path/2.jpg']
const TITLE = '标题最多20字'
const NOTE = '图文正文'
const TAGS = ['标签1']

await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image', { wait: true, timeout: 30 })
await wait(2)
await uploadFile('input[type="file"][accept*="image"]', IMAGES)  // [源码]

// 等标题框出现 = 图片传完
await waitForElement('input[placeholder*="填写标题"]', { timeout: 60 })
await fillInput('input[placeholder*="填写标题"]', TITLE.slice(0, 20))
await click('p[data-placeholder*="输入正文描述"]')
await pressKey('Backspace'); await pressKey('Control+a'); await pressKey('Delete')
await typeText(NOTE); await pressKey('Enter')
for (const t of TAGS.slice(0, 10)) {
  await typeText('#' + t)
  try { await waitForElement('#creator-editor-topic-container .item', { timeout: 6 }); await click('#creator-editor-topic-container .item') }
  catch (e) { for (let k = 0; k < ('#' + t).length; k++) await pressKey('Backspace') }
}

await click('xpath=//button[normalize-space(text())="发布"]')
for (let i = 0; i < 30; i++) {
  if (/\/publish\/success\?/.test((await pageInfo()).url)) { cliLog('published'); break }
  await wait(1)
}
await completeTaskSpace(task.id, { keep: false })
EOF
```

## 参考文档

- 完整流程（含封面、原创声明、定时发布）：`references/xiaohongshu-upload-flow.md`
- 选择器表：`references/xiaohongshu-selectors.md`
- 故障排查：`references/xiaohongshu-troubleshooting.md`

## 注意

小红书登录页（`/login`，短信登录表单）已实机确认；发布页选择器来自 `uploader/xiaohongshu_uploader/main.py`，未在登录态下实机验证。话题候选依赖联想接口，网络抖动时等不到候选就跳过该标签。

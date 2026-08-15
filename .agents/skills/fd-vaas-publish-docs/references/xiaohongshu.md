# 小红书图文笔记 xiaohongshu

> ⚠️ **已被上游取代(2026-08)**:小红书图文走 `scripts/note_adapter.py`(复用 vendored social-auto-upload 的 `XiaoHongShuNote`,cookie 与视频发布共享),publish.mjs 会自动路由。本文件留作选择器参考,不再作为发布路径维护。


小红书**没有纯文字**,「文档」= 图文笔记,**必须至少 1 张图**。选择器复用本仓库 `xiaohongshu-upload` skill(已部分实机确认)。

## 入口

| 项 | URL / 值 |
|---|---|
| 图文发布页 | `https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image` |
| 登录页 | `https://creator.xiaohongshu.com/login` |
| 发布成功 | URL 含 `/publish/success?` |

## 0) 首次:probe 核选择器

```bash
export PROBE_URL="https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image"
# 跑 references/probe.md 的 probe;小红书选择器已部分确认,probe 用于复核改版
```

## 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xhs')
await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image', { wait: true, timeout: 30 })
await wait(3)
const info = await pageInfo()
const loggedIn = !/\/login\b/.test(info.url)
cliLog(JSON.stringify({ url: info.url, loggedIn }))
EOF
```

## 2) 登录 handoff(扫码)

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xhs')
await openOrReuseTab('https://creator.xiaohongshu.com/login', { wait: true, timeout: 30 })
await wait(2)
try { await click('img.css-wemwzq') } catch (e) {}   // 切「扫一扫」
await wait(1)
await handOffTaskSpace(task.id)
cliLog('请用小红书 APP 扫码登录,完成后回复 continue')
EOF
```

收回:
```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xhs')
await takeOverTaskSpace(task.id)
await wait(2)
const info = await pageInfo()
cliLog(JSON.stringify({ url: info.url, loggedIn: !/\/login\b/.test(info.url) }))
EOF
```

## 3) 发文 heredoc 骨架(图文笔记)

⚠️ 小红书笔记体,**markdown 符号(`#` `*` `` ` ``)会原样显示很丑**。heredoc 里正文用 `typeText` 灌**纯文本**(publish.mjs 写的 `body.md` 里如果是 markdown,先 strip 符号)。封面即正文图,至少 1 张,竖图 3:4 最佳。话题 `#标签` 放正文末尾。

```bash
export DOC_TITLE="$(cat .adapted/xiaohongshu/title.txt)" \
       DOC_BODY="$(cat .adapted/xiaohongshu/body.md)" \
       DOC_TAGS="$(cat .adapted/xiaohongshu/tags.txt)" \
       DOC_COVER="$(cat .adapted/xiaohongshu/cover.txt)"
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-xhs')
const TITLE = process.env.DOC_TITLE
const NOTE  = process.env.DOC_BODY
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean).slice(0, 10)
const COVER = process.env.DOC_COVER || ''

await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image', { wait: true, timeout: 30 })
await wait(2)

// 上传图片(至少 1 张,封面即首图)✅ 已确认
await uploadFile('input[type="file"][accept*="image"]', COVER)
await waitForElement('input[placeholder*="填写标题"]', { timeout: 60 })

// 标题(≤20 字)✅ 已确认
await fillInput('input[placeholder*="填写标题"]', TITLE.slice(0, 20))

// 正文笔记 ✅ 已实机确认：编辑器是 .tiptap.ProseMirror
await click('.tiptap.ProseMirror')
await pressKey('Control+a')
await typeText(NOTE)
await wait(1)

// 话题(≤10,每个等候选框出现再点)✅ 已确认
for (const t of TAGS) {
  await typeText('#' + t)
  try {
    await waitForElement('#creator-editor-topic-container .item', { timeout: 6 })
    await click('#creator-editor-topic-container .item')
  } catch (e) {
    for (let k = 0; k < ('#' + t).length; k++) await pressKey('Backspace')
  }
}

// 发布 ✅ 已确认
await click('xpath=//button[normalize-space(text())="发布"]')
for (let i = 0; i < 30; i++) {
  if (/\/publish\/success\?/.test((await pageInfo()).url)) { cliLog('published'); break }
  await wait(1)
}
await completeTaskSpace(task.id, { keep: false })
EOF
```

## 选择器表(✅ 已实机验证,2026-07-29)

| 元素 | 选择器 | 说明 |
|---|---|---|
| 图片上传 | `.upload-input` (accept=".jpg,.jpeg,.png,.webp") | 封面/图文图上传 |
| 标题 | `input[placeholder*="填写标题"]` | 标题输入框 |
| 正文编辑器 | `.tiptap.ProseMirror` | 富文本编辑器(contenteditable) |
| 发布按钮 | 页面底部 button.innerText.includes("发布") | 发布按钮 |

> 实际页面选择器已更新,旧的 `p[data-placeholder*]` 和 `#creator-editor-topic-container` 不再适用。
> 若发布按钮是 div 而非 button,改用 `js()` 遍历定位。

## 平台坑

- **必须至少 1 张图**,纯文字发不出。`DOC_COVER` 必须有值。
- **标题 ≤ 20 字**,publish.mjs 已截。
- **话题 ≤ 10 个**,超了卡住发布。
- **笔记体**:短段、口语化,markdown 符号要 strip。话题 `#标签` 放末尾。
- **话题候选依赖联想接口**,网络抖动等不到候选就跳过该标签(heredoc 已处理)。
- **竖图 3:4**(1080×1440)效果最好。

## ✅ 验证状态

选择器复用 `xiaohongshu-upload` skill,登录页 + 图文发布页选择器**已实机确认**(登录态下图片/标题/正文/话题/发布按钮)。仅「图文笔记」流程复核过;如改版重新跑 probe。

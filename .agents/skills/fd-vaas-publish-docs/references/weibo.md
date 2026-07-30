# 微博 短博文 heredoc

**入口**: `https://weibo.com/` 首页顶部"有什么新鲜事想分享给大家？"
**选择器状态**: ✅ 2026-07-30 实机验证
**配图**: 可选,支持多张图片
**标签**: `#话题#` 形式直接放正文里
**字数**: 普通微博 ≤ 2000 字

---

## 登录态检测 handoff

```bash
ego-browser nodejs <<'EOF'
await useOrCreateTaskSpace('docs-weibo-login')
await openOrReuseTab('https://weibo.com/', { wait: true, timeout: 60 })
await wait(5)
const info = await pageInfo()
if (/\/(login|signin|passport)/i.test(info.url)) {
  cliLog("⚠️  未登录,请扫码登录")
  await handOffTaskSpace()
}
EOF
```

---

## 发短微博(推荐)

```bash
export DOC_BODY="$(cat .adapted/weibo/body.md)" \
       DOC_TAGS="$(cat .adapted/weibo/tags.txt)" \
       DOC_COVER="$(cat .adapted/weibo/cover.txt)"

ego-browser nodejs <<'EOF'
const BODY  = process.env.DOC_BODY
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean)
const COVER = process.env.DOC_COVER || ''

await useOrCreateTaskSpace('docs-weibo-publish')
await openOrReuseTab('https://weibo.com/', { wait: true, timeout: 60 })
await wait(5)

// ✅ 实机验证选择器: textarea[placeholder="有什么新鲜事想分享给大家？"]
cliLog("📝 填写微博内容...")
await click('textarea[placeholder="有什么新鲜事想分享给大家？"]')
await wait(0.5)

// 标签转 #话题# 拼末尾
const tagsStr = TAGS.map(t => `#${t}#`).join(' ')
const content = BODY.slice(0, 1000) + (tagsStr ? '\n\n' + tagsStr : '')

// 分段输入
const chunks = content.split('\n')
for (const chunk of chunks) {
  if (chunk.trim()) await typeText(chunk)
  await pressKey('Enter')
  await wait(0.1)
}
await wait(1)

// 配图(如果有)
if (COVER) {
  cliLog("🖼️ 上传配图...")
  const fileInput = await js(String.raw`document.querySelector('input[type="file"][accept*="image"]')`)
  if (fileInput) {
    // 先点"图片"按钮让 input 出现,再上传
    await click('a[title*="图片"], span:has-text("图片")')
    await wait(1)
  }
}

cliLog("✅ 微博内容已填写完成")
cliLog("👉 请确认内容,点击「发送」按钮发布")
await handOffTaskSpace()
EOF
```

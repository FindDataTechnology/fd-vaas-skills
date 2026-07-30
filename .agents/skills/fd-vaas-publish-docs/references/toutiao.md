# 今日头条(头条号) 发文 heredoc

**入口**: `https://mp.toutiao.com/profile_v4/graphic/publish`
**选择器状态**: ⚠️ 推断,首次发布前必须 probe 核对
**封面**: 可选,推荐 1280×720(16:9)
**标题**: ~30 字
**标签**: 自动提取 + 手动加,最多 ~10 个话题

---

## 登录态检测 handoff

跳登录页就跑这个,`handOffTaskSpace` 交用户扫码/登录,完了 `takeOverTaskSpace`:

```bash
ego-browser nodejs <<'EOF'
await page.goto("https://mp.toutiao.com/profile_v4/graphic/publish")
await page.waitForTimeout(2000)
const isLogin = await page.evaluate(() => location.host.includes("mp.toutiao.com") && !location.pathname.includes("login"))
if (!isLogin) {
  console.log("⚠️  未登录,跳转到登录页…")
  await handOffTaskSpace()
}
EOF
```

---

## 发文 heredoc

**先 export 环境变量**,再跑 heredoc。正文从 `.adapted/toutiao/body.md` 读,避免 shell 转义炸。

```bash
export DOC_TITLE="$(cat .adapted/toutiao/title.txt)" \
       DOC_BODY="$(cat .adapted/toutiao/body.md)" \
       DOC_TAGS="$(cat .adapted/toutiao/tags.txt)" \
       DOC_COVER="$(cat .adapted/toutiao/cover.txt)"

ego-browser nodejs <<'EOF'
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean)
const COVER = process.env.DOC_COVER || ''

await useOrCreateTaskSpace('docs-toutiao-publish')
await openOrReuseTab('https://mp.toutiao.com/profile_v4/graphic/publish', { wait: true, timeout: 60 })
await wait(5)

// ✅ 2026-07-30 实机验证选择器可用
// 填标题
cliLog('📝 填写标题...')
await click('textarea[placeholder="请输入文章标题（2～30个字）"]')
await wait(0.5)
await typeText(TITLE)
await wait(1)

// 填正文
cliLog('📝 填写正文...')
await click('.ProseMirror')
await wait(0.5)
// 正文分段输入避免超时
const lines = BODY.split('\n')
for (const line of lines.slice(0, 100)) {
  if (line.trim()) await typeText(line)
  await pressKey('Enter')
  await wait(0.1)
}
await wait(2)

// 预览
cliLog('👁️ 点击预览并发布...')
await click('button:has-text("预览并发布")')
await wait(3)

cliLog('✅ 今日头条文章已填写完成,请在预览页确认后手动发布')
await handOffTaskSpace()
EOF
```

选择器失效 → 先跑 `probe.md` 的 `snapshotText()` 重新定位。

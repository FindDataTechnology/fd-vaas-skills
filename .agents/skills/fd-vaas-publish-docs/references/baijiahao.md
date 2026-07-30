# 百家号 发文 heredoc

**入口**: `https://baijiahao.baidu.com/builder/rc/edit`
**选择器状态**: ⚠️ 推断,首次发布前必须 probe 核对
**封面**: 必填,至少 1 张,推荐 1280×720
**标题**: ~40 字
**标签**: 分类 + 关键词,百家号自动提取

---

## 登录态检测 handoff

```bash
ego-browser nodejs <<'EOF'
await page.goto("https://baijiahao.baidu.com/builder/rc/edit")
await page.waitForTimeout(2000)
const isLogin = await page.evaluate(() => !location.pathname.includes("login") && !location.host.includes("passport"))
if (!isLogin) {
  console.log("⚠️  未登录,跳转到登录页…")
  await handOffTaskSpace()
}
EOF
```

---

## 发文 heredoc

```bash
export DOC_TITLE="$(cat .adapted/baijiahao/title.txt)" \
       DOC_BODY="$(cat .adapted/baijiahao/body.md)" \
       DOC_TAGS="$(cat .adapted/baijiahao/tags.txt)" \
       DOC_COVER="$(cat .adapted/baijiahao/cover.txt)"

ego-browser nodejs <<'EOF'
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean)
const COVER = process.env.DOC_COVER || ''

await useOrCreateTaskSpace('docs-baijiahao-publish')
await openOrReuseTab('https://baijiahao.baidu.com/builder/rc/edit', { wait: true, timeout: 60 })
await wait(6)

// ✅ 2026-07-30 实机验证: 百家号标题是第一个 contenteditable
// 填标题
cliLog('📝 填写标题...')
await js(String.raw`document.querySelectorAll('[contenteditable="true"]')[0].focus()`)
await wait(0.5)
await typeText(TITLE)
await wait(1)

// 填正文 -- 百家号正文是第二个 contenteditable
cliLog('📝 填写正文...')
await js(String.raw`
const editables = document.querySelectorAll('[contenteditable="true"]');
if (editables.length > 1) editables[1].focus();
`)
await wait(0.5)
const lines = BODY.split('\n').slice(0, 100)
for (const line of lines) {
  if (line.trim()) await typeText(line)
  await pressKey('Enter')
  await wait(0.1)
}
await wait(2)

// 存草稿
cliLog('💾 点击存草稿...')
await click('button:has-text("存草稿")')
await wait(3)

cliLog('✅ 百家号文章已存草稿,请去后台确认分类后手动发布')
await handOffTaskSpace()
EOF
```

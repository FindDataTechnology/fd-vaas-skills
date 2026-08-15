# 微信公众号 weixin

最重的平台:富文本编辑器(新版是 **ProseMirror**,不再是 ueditor)**不吃 markdown 源码**、封面必填、摘要必填、群发有频次限制。**默认存草稿,不群发**,让用户手动群发。

## 入口

| 项 | URL / 值 |
|---|---|
| 后台 | `https://mp.weixin.qq.com/`(扫码登录) |
| 图文编辑器 | **直拼 appmsg URL**:`https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&lang=zh_CN&token=<TOKEN>`(token 从登录后 home 页 URL `token=(\d+)` 取) |
| 发布成功 | 草稿:出现「已保存」/跳草稿箱;群发:跳群发记录 |

⚠️ **别走「新的创作 -> 文章」下拉**(文本匹配会点中整个容器,点不动)——实测结论,直接拼 URL。

## 0) 选择器状态(✅ 已实机验证,2026-07-30,patchright 链路)

```
入口:   appmsg URL 直拼(见上)
标题:   #title —— hidden textarea,fill 会超时,用 js 赋值 + input 事件
正文:   .ProseMirror(页面有 2 个 contenteditable,第 1 个是正文)
        纯文本粘贴丢 \n -> 按行转 <p> 用 text/html 剪贴板 / insertHTML
摘要:   #js_description(不是 #digest)
封面:   input[type=file][accept*=image](hidden),先点「选择封面」区域
保存:   「保存为草稿」按钮(群发需后台手动)
```

## 1) 登录态校验

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-weixin')
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 40 })
await wait(4)
const info = await pageInfo()
// 登录后 URL 会进 /cgi-bin/home;未登录停在扫码页
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

⚠️ 公众号编辑器**不吃 markdown 源码**,用 `.adapted/weixin/body.txt`(publish.mjs 已 strip);正文按行转 `<p>` 用 `insertHTML` 灌,保留换行。

```bash
export DOC_TITLE="$(cat .adapted/weixin/title.txt)" \
       DOC_BODY="$(cat .adapted/weixin/body.txt)" \
       DOC_COVER="$(cat .adapted/weixin/cover.txt)" \
       DOC_SUMMARY="$(cat .adapted/weixin/summary.txt)"
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-publish-weixin')
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const COVER = process.env.DOC_COVER || ''
const SUMMARY = process.env.DOC_SUMMARY || ''

// 1. 开后台取 token,直拼 appmsg 编辑器 URL(不走下拉)
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 40 })
await wait(4)
const homeUrl = (await pageInfo()).url
const token = (homeUrl.match(/token=(\d+)/) || [])[1]
if (!token) { cliLog('取不到 token,未登录?'); throw new Error('no token') }
await openOrReuseTab(`https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&lang=zh_CN&token=${token}`, { wait: true, timeout: 40 })
await wait(6)

// 2. 标题:#title 是 hidden textarea,js 赋值 + input 事件
await js(`(()=>{const e=document.querySelector('#title'); e.value=${JSON.stringify(TITLE.slice(0,64))}; e.dispatchEvent(new Event('input',{bubbles:true}))})()`)

// 3. 正文:.ProseMirror,按行转 <p> 后 insertHTML(纯文本粘贴丢换行)
const htmlBody = BODY.split('\n').map(l => l.trim() ? `<p>${l.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</p>` : '<p><br></p>').join('')
await js(`(()=>{const e=document.querySelector('.ProseMirror'); e.focus(); document.execCommand('selectAll',false,null); document.execCommand('insertHTML',false,${JSON.stringify(htmlBody)})})()`)
await wait(1)

// 4. 封面(必填 900×500):先点「选择封面」区域让 hidden input 可用
if (COVER) {
  try {
    await js('window.scrollTo(0, document.body.scrollHeight)')
    await click('xpath=//*[contains(text(),"选择封面") or contains(text(),"从正文选择")]')
    await wait(1)
    await uploadFile('input[type="file"][accept*="image"]', COVER)
    await wait(3)
    await click('xpath=//button[normalize-space(text())="完成"]')
    await wait(1)
  } catch (e) { cliLog('封面设置跳过: ' + e.message) }
}

// 5. 摘要(必填):#js_description
await js(`(()=>{const e=document.querySelector('#js_description'); if(e){e.value=${JSON.stringify(SUMMARY)}; e.dispatchEvent(new Event('input',{bubbles:true}))}})()`)

// 6. 保存草稿(默认,不群发)
await click('xpath=//button[normalize-space(text())="保存为草稿"]')
await wait(3)
cliLog('已存草稿,请在后台确认;群发需手动点(订阅号每天 1 次)')

await completeTaskSpace(task.id, { keep: false })
EOF
```

## 选择器表(✅ 已实机验证 2026-07-30)

| 元素 | 选择器 | 说明 |
|---|---|---|
| 编辑器入口 | appmsg URL 直拼 `.../appmsg?...&type=77&token=<T>` | 别点「新的创作」下拉 |
| 标题 | `#title` | **hidden textarea**,js 赋值 + input 事件 |
| 正文 | `.ProseMirror` | 2 个 contenteditable 里第 1 个;**insertHTML 保换行** |
| 封面上传 | `input[type="file"][accept*="image"]` | hidden,先点「选择封面」区域 |
| 摘要 | `#js_description` | **必填**;不是 `#digest` |
| 保存草稿 | `xpath=//button["保存为草稿"]` | 默认走这个;群发另点 |

## 平台坑

- **不吃 markdown**:贴 markdown 源码会原样显示符号。用 `.adapted/weixin/body.txt`(已 strip)。
- **纯文本粘贴丢换行**:ProseMirror 不识别 `\n`。按行转 `<p>`(空行 `<p><br></p>`)走 HTML 粘贴/insertHTML。**最大坑**。
- **标题 #title 是 hidden**:`locator.fill`/`fillInput` 会超时,必须 js 赋值 + dispatchEvent。
- **封面必填 900×500**,不填不能保存。
- **摘要必填**,publish.mjs 没给 `--summary` 时从正文前 120 字生成。
- **群发频次**:订阅号每天 1 次、服务号每月 4 次。**默认存草稿**,群发让用户手动。
- **原创声明**:有「原创」开关,需账号有原创权限,**默认不勾**。

## ✅ 验证状态

选择器**已实机验证**(2026-07-30,patchright 链路跑通存草稿):appmsg URL 入口、`#title` hidden js 赋值、`.ProseMirror` HTML 粘贴、`#js_description` 摘要、`保存为草稿`。公众号前端改版频繁,点不动时重跑 `references/probe.md`。

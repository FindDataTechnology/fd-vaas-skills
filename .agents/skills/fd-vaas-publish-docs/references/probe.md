# 选择器核对流程(probe)

各平台图文编辑器前端经常改版,`references/<platform>.md` 里的选择器多为页面结构推断、**未在登录态下实机验证**。**首次发布前、以及选择器点不动时**,必须先跑 probe 重新 dump 编辑器 DOM,定位真实选择器,再改 heredoc。

## 通用 probe heredoc

把 `PROBE_URL` 换成目标平台编辑器入口(见各平台 md 顶部)。这个 heredoc 打开编辑器、等加载、dump 出所有可交互元素,你照着输出的 `tag | role | placeholder | text | class | id` 找标题/正文/封面/发布按钮的真实选择器。

```bash
export PROBE_URL="https://zhuanlan.zhihu.com/write"   # ← 换成目标平台编辑器
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('docs-probe')
await openOrReuseTab(process.env.PROBE_URL, { wait: true, timeout: 40 })
await wait(4)
const info = await pageInfo()
cliLog('URL: ' + info.url)
cliLog('TITLE: ' + info.title)

// 登录态?跳到登录页就不是
const loggedIn = !/\/(signin|login)\b/i.test(info.url)
cliLog('LOGGED_IN: ' + loggedIn)

// dump 可交互元素:input / textarea / contenteditable / button + 富文本编辑器容器
const dump = await js(String.raw`
(() => {
  const out = [];
  const sel = 'input,textarea,[contenteditable="true"],button,[role="textbox"],[role="button"],[contenteditable]';
  document.querySelectorAll(sel).forEach((el, i) => {
    if (i > 120) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;  // 跳过隐藏
    out.push({
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || '',
      role: el.getAttribute('role') || '',
      placeholder: el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || '',
      text: (el.innerText || el.value || '').slice(0, 40).replace(/\n/g,' '),
      id: el.id || '',
      cls: (el.className || '').toString().slice(0, 80),
      editable: el.getAttribute('contenteditable') || '',
    });
  });
  return JSON.stringify(out, null, 1);
})()
`)
cliLog('ELEMENTS:\n' + dump)

// 再 dump 一下文件上传入口(封面/图片靠它)
const fileInputs = await js(String.raw`
(() => {
  const out = [];
  document.querySelectorAll('input[type="file"]').forEach((el) => {
    out.push({ accept: el.getAttribute('accept') || '', id: el.id || '', cls: (el.className||'').toString().slice(0,60) });
  });
  return JSON.stringify(out);
})()
`)
cliLog('FILE_INPUTS: ' + fileInputs)

await completeTaskSpace(task.id, { keep: false })
EOF
```

## 怎么用 dump 结果

1. 找**标题**:`tag=input` 且 `placeholder` 含「标题」「title」,或 `tag=textarea` 第一个。记下它的选择器(`#title`、`input[placeholder*="标题"]`、`.title-input` 等)。
2. 找**正文**:`editable=true` 或 `role=textbox` 里最大的那个 / `placeholder` 含「正文」「输入」。正文一般是 contenteditable 富文本,不是 `<textarea>`。
3. 找**封面/图片上传**:`FILE_INPUTS` 里 `accept` 含 `image` 的。记下选择器,heredoc 里可能要先点「上传封面」按钮让 input 出现再 `uploadFile`。
4. 找**发布按钮**:`tag=button` 且 `text` 是「发布」「群发」「发表」「保存草稿」。
5. 找**话题/标签入口**:`text` 含「#」「话题」「添加标签」的按钮。

把找到的选择器填回 `references/<platform>.md` 的 heredoc,顺手把该 md 底部的「验证状态」从 ⚠️ 改成 ✅ + 日期。

## 探不到元素?

- 页面是懒加载 -> heredoc 里 `await wait(n)` 加大,或先 `await js('window.scrollTo(0, document.body.scrollHeight)')` 触发渲染。
- 编辑器在 iframe 里(公众号老编辑器常见)-> 用 `js` 切到 iframe:`document.querySelector('iframe').contentDocument.querySelector(...)`。
- 登录态没进编辑器 -> 先跑该平台 md 的「登录 handoff」扫码,再回来 probe。

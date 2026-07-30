# 平台差异化配置参考

上传全部走 `fd-vaas-publish/scripts/platforms/<platform>.mjs`（ego-browser 自动化），复用用户 Chrome
登录态，无需 cookie 文件、无需 Playwright、无需 `--account`。

以下是每个平台的重点，写进 `.env` 一次搞定，别每次发布现查。

## 抖音 douyin

- `node .../platforms/douyin.mjs --file <mp4> --title --desc --tags [--cover-horizontal <cover>] [--cover-vertical <cover>] [--schedule "YYYY-MM-DD HH:MM"]`
- **tag**：传 `a,b,c`（英文逗号分隔），会自动加 `#`。别自己在 tag 里写 `#`，会重复。
- **desc 长度**：上限 1000 左右，超过被截。放 `.env` 里 `DOUYIN_DESC_MAX=1000` 让 publish.mjs 自己截。
- **封面**：横版 1920×1080 + 竖版 1080×1440，两个都建议设置。
- **登录**：ego-browser 继承 Chrome 登录态，扫码登录一次即可。
- **风控**：短时间大量上传/切账号会被 verify，别一次跑太多个 slug。
- **技术挑战**：标准 DOM，无特殊框架。描述输入框是 contenteditable，用 execCommand。

## 小红书 xiaohongshu

- `node .../platforms/xiaohongshu.mjs --file <mp4> --title --desc --tags [--cover <cover>]`
- **标题 ≤ 20 字**（硬限制），超出自动截断。
- **tag**：硬上限 10 个，超过卡住发布。用中文短语不用英文缩写，推荐率高。
- **文体**：笔记体，分段短，末尾 3-5 个 `#tag` 话题。
- **登录**：ego-browser 继承 Chrome 登录态，登录页默认短信登录，需点 `img.css-wemwzq` 切到扫码。
- **技术挑战**：标准 DOM，无特殊框架。话题需等候选框出现再点。

## B站 bilibili

- `node .../platforms/bilibili.mjs --file <mp4> --title --desc --tags [--cover <cover>] [--tid 124]`
- **分区 tid**：默认 124（科普）。常用：
  - 36 = 科技 · 软件应用
  - 122 = 科技 · 数码
  - 124 = 知识 · 科学科普
  - 208 = 知识 · 财经商业
  - 209 = 知识 · 校园学习
- **desc 必填**，不能空。
- **tag**：6 个左右最佳，B站官方推荐 5-10 个。
- **封面**：`--cover`（注意不是 `--thumb`），建议 1920×1080。
- **定时**：暂不支持。
- **技术挑战**：**micro-app 微前端**，所有内容在 `micro-app[name=video-up].shadowRoot` 内。`uploadFile()`
  可能失效，用 CDP `DOM.setFileInputFiles` 或 HTTP 服务器 + DataTransfer 方案。

## 快手 kuaishou

- `node .../platforms/kuaishou.mjs --file <mp4> --title --desc --tags [--cover <cover>]`
- **话题标签 ≤ 4 个**（不是 5！），超过报错且需刷新页面。
- **`--schedule`**：publish.mjs 传 `YYYY-MM-DD HH:MM` 时会自动补 `:00`。
- **登录**：ego-browser 继承 Chrome 登录态，扫码登录。
- **技术挑战**：
  - **React Joyride 遮罩**：首次使用时拦截所有点击，需移除 `[class*="react-joyride"]`
  - **发布按钮在视口外**：需 `scrollIntoView({ block: 'center' })`
  - **封面选择**：Ant Design Modal

## 视频号 weixin

- `node .../platforms/weixin.mjs --file <mp4> --desc <描述> [--cover <cover>]`
- **无单独标题字段**，描述就是正文内容。
- **发布后状态**：「处理中」，转码完成后自动发布。
- **登录**：微信扫码，无法账号密码登录。
- **技术挑战**（最复杂）：
  - **Wujie 微前端**：所有内容在 `wujie-app.shadowRoot` 内
  - **文件上传必须用 HTTP 服务器 + DataTransfer API**（`uploadFile()` 和 `DOM.setFileInputFiles` 都不可用）
  - 方案：Node.js 启动 HTTP 服务器 -> 浏览器 `fetch` -> `Blob` -> `new File()` -> `DataTransfer` -> dispatch `change`

## YouTube

- `node .../platforms/youtube.mjs --file <mp4> --title --desc --tags [--thumbnail <cover>] [--visibility public|unlisted|private]`
- **默认 visibility**：`.env` 里 `YOUTUBE_VISIBILITY` 配，默认 `unlisted`。
- **需要代理**：YouTube 在部分网络被墙，脚本里配置代理。
- **登录**：Google 账号交互登录，可能碰到 2FA，遇到时交给用户处理。
- **tag**：英文逗号分隔，标签在英文语境效果更好。
- **技术挑战**：
  - **Polymer Web Components**：`tp-yt-paper-dialog` 需强制 `opened=true` + `display:block`
  - **4 步对话框**：Details -> Video elements -> Checks -> Visibility
  - **"Not made for kids" 必答**：不选则 Next 按钮禁用
  - **标题用 execCommand**：contenteditable `#textbox`，不能用 `.value`

## 通用踩坑

- **不要并发跑同一账号的多个上传**。浏览器上下文共享会打架。多平台并发 OK（各平台独立），同平台**串行**。
- **定时发布**：抖音/快手是平台定时（你退出之后平台自己在那个时间点发）；其他平台暂不支持定时。
- **失败要看日志**：上传脚本的 stdout/stderr 会直接透传到 publish.mjs 的输出。
- **选择器漂移**：各平台的 DOM 选择器来自实机观察，平台改版可能失效。详细选择器表见
  `references/<platform>.md`。
- **shadow DOM 平台**（B站、视频号）：所有 `querySelector` 必须通过 `.shadowRoot` 访问，不能直接用
  `document.querySelector`。

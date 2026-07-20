# 平台差异化(为什么每个平台都要单独一段配置)

上传引擎是 `social-auto-upload`,它对每个平台的浏览器自动化逻辑不同,暴露的 `sau` CLI 参数也不同。以下是每个平台的重点,写进 `.env` 就一次搞定,别每次发布现查。

## 抖音 douyin

- `sau douyin upload-video --account <name> --file <mp4> --title --desc --tags`
- **tag**:sau 传 `a,b,c`(英文逗号分隔),它会自动加 `#`。别自己在 tag 里写 `#`,会重复。
- **desc 长度**:上限 1000 左右,超过被截。放 `.env` 里 `DOUYIN_DESC_MAX=1000` 让 publish.mjs 自己截。
- **首次登录**:`sau douyin login --account main --headed`(HEADLESS=false),扫 QR。cookie 存 `social-auto-upload/cookies/douyin_uploader/`。
- **风控**:短时间大量上传/切账号会被 verify,别一次跑太多个 slug。
- **缩略图**:`--thumbnail-landscape` + `--thumbnail-portrait` 都传,双图能拿到更多流量位。

## 小红书 xiaohongshu

- `sau xiaohongshu upload-video --account <name> --file <mp4> --title --desc --tags`(视频)
- `sau xiaohongshu upload-note --account <name> --images … --title --note --tags`(图文)
- **注意**:视频接口是 `--desc`,图文接口是 `--note`。publish.mjs 视频走 desc、note 相当于给了个别名。
- **标题**:20 字内最好,超了列表页会折。
- **文体**:笔记体,分段短,末尾 3-5 个 `#tag` 话题。
- **tag**:sau 传 `a,b,c`,它加 `#`。tag 用**中文短语**不用英文缩写,推荐率高。
- **海外 RedNote**:如果发的是 rednote.com,`.env` 里 `SAU_XHS_CREATOR_BASE_URL=https://creator.rednote.com/…`,由 sau 的 conf.py 或环境变量读。

## B站 bilibili

- `sau bilibili upload-video --account <name> --file <mp4> --title --desc --tid <int> --tags`
- **`--tid` 必填**,一个 int。常用分区(记不全就查 https://member.bilibili.com/x/vupre/web/archive/pre?…):
  - 36 = 科技 · 软件应用
  - 122 = 科技 · 数码
  - 124 = 知识 · 科学科普
  - 208 = 知识 · 财经商业
  - 209 = 知识 · 校园学习
  - 21 = 生活 · 日常
- **desc 必填**(sau 层做的要求),不能空。
- **底层用 `biliup`,不是浏览器**。所以 `HEADLESS` 对 B 站没用。
- **登录**:`sau bilibili login --account main` 在**真终端**里跑,不要在 Claude Code 内跑 —— QR 靠字符渲染,内层 pty 容易糊,fallback 到 `qrcode.png`。
- **tag**:6 个左右最佳,B站官方推荐 5-10 个。

## 视频号 tencent(WeChat Channels)

- `sau tencent upload-video --account <name> --file <mp4> --title --desc --tags [--short-title] [--thumbnail…]`
- **`--short-title` ≤ 6 字**,视频号列表页显示的短标题。不给用 title 前 6 字。
- **缩略图三种比例**:`--thumbnail`(3:4 竖)`--thumbnail-landscape`(4:3 横)`--thumbnail-portrait`(3:4 竖)—— 视频号在不同位置用不同比例,能给都给。用 `fd-vaas-video-creator/scripts/embed-poster.mjs` 生成的 cover.jpg,再 `ffmpeg -vf "crop=w:h"` 裁不同比例。
- **首次登录**:`sau tencent login --account main --headed`,微信扫码。
- **`--draft`**:先存草稿不发,想审核过了手动发的时候用。

## 快手 kuaishou

- `sau kuaishou upload-video --account <name> --file <mp4> --title --desc --tags [--thumbnail]`
- 和抖音接口结构相似,cookie 独立。
- **登录**:`sau kuaishou login --account main --headed` 扫码。

## YouTube

- `sau youtube upload-video --account <name> --file <mp4> --title --desc --tags [--visibility public|unlisted|private] [--playlist ID]`
- **不是 GAPI 官方 API**,是浏览器自动化。这意味着:
  - 上传后视频**默认 private/locked**(YouTube 对自动化上传的限制),要在网页 studio 里手工解锁 → public。
  - 或先传 `--visibility unlisted` 拿到链接,再手动改 public。
- **需要代理**:`social-auto-upload/conf.py` 里 `YT_PROXY=http://127.0.0.1:7892`。patchright 不读系统 http_proxy,必须走 conf.py。
- **首次登录**:`sau youtube login --account main --headed`,谷歌账号交互登录,可能碰到 2FA,建议在真终端里跑。
- **tag**:英文逗号分隔,标签在英文语境效果更好。

## 通用踩坑

- **`account_name` 大小写敏感**。`.env` 里 `DOUYIN_ACCOUNT=main` 就要 `cookies/douyin_uploader/main.json`,不能一处 `main` 一处 `Main`。
- **不要并发跑同一账号的多个 `sau`**。浏览器上下文共享 cookie 会打架。多平台并发 OK(各平台独立),同平台**串行**。
- **定时发布 `--schedule` 语义**:抖音/小红书/快手/视频号是**平台定时**(你退出 sau 之后平台自己在那个时间点发);B站看 biliup 版本;YouTube 是往草稿箱里塞时间戳。所以定时发完 sau 就退出、机器可以关。
- **失败要看日志**:sau 的 stdout/stderr 会直接透传到 publish.mjs 的输出。风控/验证码/网页改版这些都是 sau 那层的问题,去改 `social-auto-upload/uploader/<platform>_uploader/` 的 selector 或者跟上游对。

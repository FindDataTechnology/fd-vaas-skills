---
name: fd-vaas-publish-videos
description: >
  把 fd-vaas-video-creator 出的口播视频一键发到多个社交平台。**编排 + 上传一体化**：
  平台差异化偏好、标签、定时由 publish.mjs 编排；每个平台的上传逻辑内置在 scripts/platforms/<platform>.* 中。
  支持抖音/小红书/B站/快手/视频号/YouTube 六个平台。**双运行时**：macOS 走 ego-browser（.mjs，复用 Chrome
  登录态，无 cookie）；Windows 走 patchright（.py，stealth Playwright，持久 profile 复用登录态）。
  ego-browser 没有 Windows 版，Windows 必须用 patchright 链路。
  触发场景：用户说"把这支视频发到抖音/小红书/B站/视频号/YouTube/快手"、"多平台一起发"、
  "分发这条视频"、"push to socials"、"posting the video"，或者刚做完一支 fd-videos/<slug>/
  里的视频、要走下一步分发时。**必须**用本 skill 的 publish.mjs，不要直接手写各平台参数。
compatibility: macOS=Node.js 18+ + ego-browser; Windows=Python 3.10+ + patchright(`pip install patchright` + `patchright install chromium`);
  各平台创作者中心已登录; fd-vaas-video-creator 已跑完（存在 downloads/fd-videos/<slug>/task.json + <slug>.mp4）。
  publish.mjs 按 process.platform 自动派发：macOS->.mjs(ego-browser)，Windows->.py(patchright)。
---

# FD VAAS 视频分发器

一支视频 = 一次发布指令 -> **多个平台 各自的偏好参数 各自的上传脚本**。本 skill 把平台差异化
配置外化到 `.env`，再让 `publish.mjs` 一行组装出对每个平台正确的上传命令，最终调用
`scripts/platforms/<platform>.mjs`（macOS/ego-browser）或 `<platform>.py`（Windows/patchright）完成自动化上传。

## 支持平台

| 平台 | 脚本 | URL | 核心技术挑战 |
|---|---|---|---|
| 抖音 (douyin) | `scripts/platforms/douyin.mjs` | `creator.douyin.com/creator-micro/content/upload` | 标准 DOM，无特殊框架 |
| 小红书 (xiaohongshu) | `scripts/platforms/xiaohongshu.mjs` | `creator.xiaohongshu.com/publish/publish?target=video` | 标题 ≤ 20 字；话题 ≤ 10 |
| B站 (bilibili) | `scripts/platforms/bilibili.mjs` | `member.bilibili.com/v2#/upload/video/frame` | **micro-app shadow DOM** |
| 快手 (kuaishou) | `scripts/platforms/kuaishou.mjs` | `cp.kuaishou.com/article/publish/video` | **React Joyride 遮罩** + **发布按钮在视口外** |
| 视频号 (weixin) | `scripts/platforms/weixin.mjs` | `channels.weixin.qq.com/platform/post/create` | **Wujie shadow DOM** + **HTTP 服务器 + DataTransfer 文件上传** |
| YouTube | `scripts/platforms/youtube.mjs` | `studio.youtube.com/videos/upload` | **Polymer dialog** 需强制打开 + 4 步流程 |

> 每个平台的完整技术档案（选择器表、ego-browser heredoc 代码、常见问题）见 `references/<platform>.md`。

## ⚠️ 硬性发布前流程（必须遵守）

**发布视频不是拿到视频就点上传**，必须按以下顺序走完前置准备，用户确认后才能发：

```
视频已渲染完成
    ↓
1. 拟定发布文案（标题 + 描述/笔记 + 各平台标签）
    ↓ 用 .env 预设 + 本次内容生成差异化文案
2. 生成各平台封面（**publish.mjs 自动生成**，无需手动跑）
    - 抖音：横封面 1920×1080 + 竖封面 1080×1440
    - 小红书：竖封面 1080×1440
    - B站：横封面 1920×1080
    - YouTube：横封面 1280×720
    - 视频号：1080×1260
    ↓ 用 Remotion BrandCover 模板生成，公司风格统一，无 AI 文字乱码
    ↓ 先预览确认可跑 `--cover-only` 单生成封面；加 `--no-cover` 跳过
3. 输出「发布确认清单」给用户
    - 各平台标题、描述、标签
    - 各平台封面预览图
    - 发布时间（立即 / 定时）
    ↓ 用户确认（必须明确说「确认发布」）
4. 逐个平台上传发布
    ↓ 每发完一个回写 task.json distribution[]
5. 发布完成汇总
    ↓
6. 关闭 ego 任务窗口（见下「发布后清理」，硬性步骤，别留给用户自己关）
```

**违反此流程直接发出去 = 事故**。封面文案都没确认就发，发出去撤不回来。

## 用法

### 一键多平台发布（推荐）

```bash
export VAAS=<VAAS 仓库根目录,如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代
SKILL=$VAAS/.agents/skills/d-vaas-publish-videos/scripts

# 最简：发到 .env 里配的默认平台
node $SKILL/publish.mjs --slug finddata-brand-2026 --title "寻数科技｜探索更开放更公平的AI未来"

# 指定平台 + 标签 + 描述
node $SKILL/publish.mjs --slug finddata-brand-2026 \
  --title "寻数科技｜探索更开放更公平的AI未来" \
  --desc "让数据驱动决策" \
  --platforms douyin,xiaohongshu,bilibili,kuaishou,weixin,youtube \
  --tags "科技,开源,AI,数据,程序员"

# 定时发布
node $SKILL/publish.mjs --slug finddata-brand-2026 \
  --title "..." --schedule "2026-07-20 21:30"

# 别真发，先看一眼每个平台会跑的命令
node $SKILL/publish.mjs --slug finddata-brand-2026 --title "..." --dry-run
```

### 单平台发布（调试用）

```bash
SKILL=$VAAS/.agents/skills/d-vaas-publish-videos/scripts/platforms

# 抖音
node $SKILL/douyin.mjs --file video.mp4 --title "标题" --desc "描述" --tags "标签1,标签2" --cover-horizontal cover.jpg

# 快手
node $SKILL/kuaishou.mjs --file video.mp4 --title "标题" --desc "描述 #话题" --tags "标签1,标签2"

# B站
node $SKILL/bilibili.mjs --file video.mp4 --title "标题" --desc "简介" --tags "标签1" --cover cover.jpg --tid 124

# 小红书
node $SKILL/xiaohongshu.mjs --file video.mp4 --title "标题≤20字" --desc "正文" --tags "标签1,标签2"

# 视频号
node $SKILL/weixin.mjs --file video.mp4 --desc "描述 #话题"

# YouTube
node $SKILL/youtube.mjs --file video.mp4 --title "Title" --desc "Description" --tags "tag1,tag2" --visibility public
```

### publish.mjs 参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `--slug` | ✅ | task 目录名，如 `finddata-brand-2026`。视频路径从 task.json 读。 |
| `--title` | ✅ | 视频标题（每个平台通用） |
| `--desc` | ❌ | 抖音/B站/视频号/快手/YouTube 用的正文 |
| `--note` | ❌ | 小红书用的笔记正文；未给则退到 `desc` |
| `--platforms` | ❌ | 逗号分隔平台列表，不给用 .env 的 `PLATFORMS` |
| `--tags` | ❌ | 逗号分隔标签，不给用 .env 的 `TAGS` 或平台专属 `XXX_TAGS` |
| `--schedule` | ❌ | `YYYY-MM-DD HH:MM`，不给立即发（仅 douyin/kuaishou 支持） |
| `--dry-run` | ❌ | 只打印命令不执行 |
| `--no-cover` | ❌ | 跳过封面生成与上传，用平台默认封面 |
| `--cover-only` | ❌ | 只跑封面生成（4 张 + 回写 task.json），不执行发布（给预览确认用） |

## 平台差异化参数路由

publish.mjs 按平台差异组装不同的 CLI 参数：

| 平台 | 封面参数 | 标签字段 | 特殊参数 | 标签上限 |
|---|---|---|---|---|
| 抖音 | `--cover-horizontal` + `--cover-vertical`（**自动传两张**） | `--tags` | `--schedule` | 10 |
| 小红书 | `--cover` | `--tags` | 标题 ≤ 20 字 | 10 |
| B站 | `--cover` | `--tags` | `--tid` (分区) | - |
| 快手 | `--cover` | `--tags` | - | **4**（不是5！） |
| 视频号 | `--cover` | (描述内 #话题) | 无单独标题字段 | - |
| YouTube | `--thumbnail` | `--tags` | `--visibility` | - |

## 各平台技术要点

### 抖音 (douyin) — 标准 DOM，最简单

- **无特殊框架**，标准 `document.querySelector` 即可
- 描述输入框是 `contenteditable`，用 `execCommand('insertText')` 填写
- 封面：横版 `.cover-Jg3T4p[0]` + 竖版 `.cover-Jg3T4p[1]`，点击后点「上传封面」
- 发布按钮：`button` 含「发布」文本 + `primary` class
- 选择器可能随版本变化，操作前先 `snapshotText()` 验证页面状态
- 详见 `references/douyin.md`

### 快手 (kuaishou) — React Joyride + 视口外按钮

- **React Joyride 遮罩**：首次使用时出现全屏遮罩拦截所有点击，必须先移除
  `[class*="react-joyride"]` 元素
- **封面选择**：Ant Design Modal，点击 `._default-cover` 打开，`.ant-btn-primary` 确认
- **发布按钮在视口外**：`._button-primary_3a3lq_60`，必须先 `scrollIntoView({ block: 'center' })`
- **话题标签 ≤ 4 个**（不是5！），超过报错且需刷新页面
- 详见 `references/kuaishou.md`

### B站 (bilibili) — micro-app shadow DOM

- **micro-app 微前端**：所有内容在 `micro-app[name=video-up].shadowRoot` 内
- 所有 `querySelector` 必须改为 `sr.querySelector`
- **文件上传**：`uploadFile()` 可能失效（找不到 shadow DOM 内 input），用 CDP
  `DOM.setFileInputFiles` 或 HTTP 服务器 + DataTransfer 方案
- 需选择分区（`--tid`），否则无法发布
- 详见 `references/bilibili.md`

### 小红书 (xiaohongshu) — 标题字数限制

- 标准 DOM，无特殊框架
- **标题 ≤ 20 字**（硬限制，超出截断）
- **话题 ≤ 10 个**，每个话题需等候选框出现再点
- 视频上传：`div[class^='upload-content'] input.upload-input`
- 发布验证：URL 含 `/publish/success?`
- 详见 `references/xiaohongshu.md`

### 视频号 (weixin) — Wujie shadow DOM，最复杂

- **Wujie 微前端**：所有内容在 `wujie-app.shadowRoot` 内
- **文件上传必须用 HTTP 服务器 + DataTransfer API**：
  1. Node.js 启动本地 HTTP 服务器提供视频文件
  2. 浏览器 `fetch('http://localhost:PORT/video.mp4')` -> `Blob` -> `new File()`
  3. `DataTransfer.items.add(file)` -> `input.files = dt.files` -> dispatch `change` 事件
- `uploadFile()` 和 `DOM.setFileInputFiles` 都不可用（React 事件不跨越 shadow DOM 边界）
- 无单独标题字段，描述就是正文
- 发布后状态「处理中」，转码完成后自动发布
- 详见 `references/weixin.md`

### YouTube — Polymer Web Components

- **Polymer dialog**：`tp-yt-paper-dialog` 需强制 `opened=true` + `display:block` + `setAttribute('opened','')`
- **4 步对话框**：Details -> Video elements -> Checks -> Visibility，每步点 Next
- **"Not made for kids" 必答**：不选则 Next 按钮禁用
- 标题用 `execCommand('insertText')`（contenteditable `#textbox`，不能用 `.value`）
- Checks 步骤需等待版权检查自动完成（30-60 秒）
- Google 登录可能需要 2FA，遇到时交给用户处理
- 详见 `references/youtube.md`

## 登录处理标准流程

所有平台共用登录处理模式（硬性 3 步）：

1. **自动切到扫码登录** — 在登录页找「扫码登录」按钮/tab，自动点击切换
2. **明确提示用户** — 告诉用户切到 ego-browser 窗口扫码
3. **自动轮询检测** — 每 3 秒检查登录状态，检测到成功自动继续，超时 120 秒才提醒

ego-browser 继承用户 Chrome 登录态。如果过期，在 ego-browser 中重新登录即可，无需 cookie 文件。

## 发布后清理：关闭 ego 任务窗口（硬性步骤，必须做）

发布完成后**必须关闭 ego-browser 的任务窗口**，不要留给用户自己关。这是流程的最后一步，不是可选项。

- **自动发布平台**（bilibili / kuaishou / xiaohongshu / youtube / weixin）：上传脚本末尾自调 `completeTaskSpace(id, { keep: false })`，成功时会自动关窗。但**脚本中途报错会让这行被跳过**，所以仍要跑下面的兜底清理。
- **手动发布平台**（douyin）：脚本在「手动点发布」处 `handOffTaskSpace` 后即退出，窗口不会自动关。**用户回复「发布完成」后**，由你跑兜底清理关掉它。

兜底清理 heredoc（每个平台发完跑一次；douyin 等用户确认发布完成后再跑）：

```bash
ego-browser nodejs <<'EOF'
const spaces = await listTaskSpaces();
let closed = 0;
for (const s of spaces) {
  const name = s.name || s.title || '';
  const id = s.id ?? s.taskId;
  if (id == null || !/publish/i.test(name)) continue;
  try {
    const r = await completeTaskSpace(id, { keep: false });
    cliLog('closed ' + name + ': ' + (r && r.done));
    closed++;
  } catch (e) { cliLog('skip ' + name + ': ' + e.message); }
}
cliLog('🧹 清理完成，关闭 ' + closed + ' 个任务窗口');
EOF
```

要点：
- `completeTaskSpace(id, { keep: false })` 对 user-owned 窗口会**先 claim 再 close**，所以**只在用户确认发布完成后才跑**——别在用户还在点发布时跑，会打断。
- 默认 `keep: false`：发布完不需要保留页面，关掉。只有用户明确说「保留页面」或要继续看发布结果时才 `keep: true`。
- 别只关当前平台：用户在多平台发布时会积一堆 `*-publish-*` 窗口，跑一次把所有 `publish` 命名的任务窗口都清掉。

## 首次配置

```bash
cd $VAAS
[ -f .env ] || cp .env.example .env
$EDITOR .env   # 改 PLATFORMS 和各平台 XXX_TAGS
```

关键项：
- `PLATFORMS`：逗号分隔，默认发到哪些平台
- `TAGS`：全局默认标签；`DOUYIN_TAGS` / `BILIBILI_TAGS` 等平台专属覆盖
- `SCHEDULE`：全局默认定时，一般留空（立即发）

**分层覆盖**：每支视频想微调，在该 task 目录放 `downloads/fd-videos/<slug>/.publish.env`。
优先级：`--flag CLI > <task>/.publish.env > <VAAS>/.env > 内置默认`。

## Windows 上传链路（patchright）

ego-browser 只有 macOS arm64 二进制，**没有 Windows 版**。Windows 上用 patchright（stealth 版
Playwright，能绕过抖音/小红书/B站的自动化检测）替代，脚本在 `scripts/platforms/<platform>.py`。
publish.mjs 按 `process.platform` 自动派发，CLI 参数与 macOS 的 `.mjs` 完全一致，无需改用法。

### 一次性安装（Windows）

```powershell
# 1. 装 patchright（stealth Playwright fork）
pip install patchright
# 2. 下载 stealth chromium 浏览器内核
patchright install chromium
# 3. （可选）想复用系统 Chrome 而非自带 chromium：在 .env 设 PATCHRIGHT_CHANNEL=chrome
```

### 登录态：持久 profile（模拟 ego-browser）

patchright 用 `launch_persistent_context` 把登录态存到 `VAAS/.profiles/<platform>/`，
跨次运行复用 —— 首次开浏览器扫码登录，之后不用重登（和 ego-browser 一样不存 cookie 文件）。
profile 过期了就在弹出的浏览器窗口里重新登录。

### 与 macOS 链路的差异

| | macOS (.mjs) | Windows (.py) |
|---|---|---|
| 自动化引擎 | ego-browser | patchright (stealth Playwright) |
| 登录态复用 | 继承用户 Chrome | 独立持久 profile（`VAAS/.profiles/<platform>/`） |
| 页内 JS | `js(...)` 注入 | `page.evaluate(...)`（JS 与 .mjs 基本同源） |
| 文件上传 | `uploadFile()` | `set_input_files()`；视频号用 HTTP 服务器 + DataTransfer |
| 用户交接 | `handOffTaskSpace` | `input()` 阻塞回车（浏览器窗口始终开着） |

### 配置项（.env）

- `PYTHON`：Windows 上 Python 解释器命令，默认 `python`（也可 `py`/`python3`）
- `VAAS_ROOT`：publish.mjs 自动透传给 .py，定位 `.profiles/` 目录

### 直接调单平台 .py（调试用）

```bash
python scripts/platforms/douyin.py --file video.mp4 --title "标题" --tags "科技,开源" --dry-run
```

### ⚠️ 已知限制 / 待真机验证

- **视频号 weixin** 最难：Wujie shadow DOM + React 事件不跨边界，已用 HTTP 服务器 + DataTransfer
  方案 port，但未在真机登录态下验证完整上传；建议先 `--dry-run` 看能否进到上传页。
- **B站 bilibili**：micro-app 的 shadow DOM 若为 closed，patchright locator 无法穿透，
  需改用 weixin 同款 HTTP+DataTransfer（当前先按 open 处理）。
- **小红书 tags**：中文话题用 `keyboard.type`，CJK 在个别输入框可能需改 `evaluate` 直填。
- 各平台选择器会随站点改版漂移；失败先读 `references/<platform>.md` 的选择器表，必要时更新 .py 里的 JS。

## 故障排查

| 问题 | 解决方案 |
|---|---|
| 某平台上传失败 | 读 `references/<platform>.md` 的技术挑战章节 |
| 登录态失效 | ego-browser 继承 Chrome 登录态，在 ego-browser 中重新登录 |
| shadow DOM 找不到元素 | B站用 `micro-app[name=video-up].shadowRoot`，视频号用 `wujie-app.shadowRoot` |
| 文件上传失败 | 视频号必须用 HTTP 服务器 + DataTransfer 方案（见 `references/weixin.md`） |
| 快手点击没反应 | 移除 React Joyride 遮罩 + scrollIntoView 发布按钮 |
| YouTube 对话框打不开 | 强制 `paper.opened=true` + `display:block` + `setAttribute('opened','')` |
| YouTube Next 按钮灰色 | 必选 "Not made for kids" + 等 Checks 步骤完成 |
| 快手话题报错 | 话题 ≤ 4 个，超过需刷新页面 |
| 想只看命令不真发 | 加 `--dry-run` |
| Windows: `command not found: python` | .env 设 `PYTHON=py` 或 `PYTHON=python3` |
| Windows: patchright 报找不到 chromium | 跑 `patchright install chromium` |
| Windows: 登录态每次都丢 | 确认 `VAAS_ROOT` 指向 VAAS，profile 在 `VAAS/.profiles/<platform>/` |
| Windows: 视频号文件传不上去 | HTTP+DataTransfer 方案已内置；确认本地 HTTP 服务器端口未被占（脚本自动选空闲端口） |

## 参考

- `scripts/publish.mjs` — 主入口（编排 + 路由到各平台脚本）
- `scripts/platforms/<platform>.mjs` — 各平台 ego-browser 上传脚本
- `scripts/platforms/<platform>.py` - 各平台 patchright 上传脚本（Windows），CLI 参数与 .mjs 一致
- `scripts/platforms/lib/browser_utils.py` - patchright 共享工具（launch/登录/点击/上传）
- `scripts/platforms/requirements.txt` - Windows 依赖（patchright）
- `scripts/lib/browser-utils.mjs` — 共享浏览器工具函数
- `references/platform-quirks.md` — 各平台坑详解
- `references/<platform>.md` — 各平台完整技术档案（选择器表、heredoc 代码、常见问题）
- `references/xiaohongshu-*.md` — 小红书额外参考（upload-flow, selectors, troubleshooting）
- **fd-cover-image skill** — 封面生成（Remotion 方案，优先用）
- **fd-vaas-video-creator skill** — 视频产出（本 skill 只读成片，不生成视频）

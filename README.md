# VAAS - 可变资源创作与分发

> **🌐 语言：** 简体中文（本文件） · [English](README.en.md)

> 🚀 **一键安装：** `curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-vaas-skills/main/install.sh | bash`

> 接收一个内容需求，生成**可变类型的资源**（幻灯片、文档、屏幕录制视频、AI 图片/视频，或 Remotion 渲染的口播视频），然后**自动发布到不同的社交媒体账号**--理想情况下为每个平台产出*不同*的变体。

VAAS 是架在两半之上的一个**编排层**，自身没有应用代码：

1. **创作技能（Creation skills）**--把需求变成一个素材文件（`.pptx`、`.docx`、`.mp4`、图片……），源码在 `.agents/skills/`。
2. **分发引擎（Distribution engine）**--两个发布技能把素材发到各平台：`fd-vaas-publish-videos`（视频 -> 6 个视频平台）和 `fd-vaas-publish-docs`（图文 -> 9 个图文平台）。每个平台的上传逻辑内置在 `scripts/platforms/<platform>.{mjs,py}`：**macOS** 走 ego-browser（复用 Chrome 登录态，无 cookie），**Windows** 走 patchright（隐身 Playwright，持久 profile 复用登录态）。

> **架构变更（重要）：** 旧版基于上游 `social-auto-upload/` + `sau` CLI 的分发栈**已移除**。现在分发完全内置在发布技能里（ego-browser + patchright）。如果你看到旧文档提到 `sau`、cookie 文件或 `account_name`，那些都已过时。

当有人说「做一个资源并发出去」时，预期的流程是：

```
创作技能产出一个文件  ->  发布技能把它上传到一个或多个账号
```

两条已接好的**主线**通过 `fd-vaas-*` 技能把这个流程端到端串起来（无需手写胶水代码）：

```
视频主线： 需求 -> /fd-vaas-brainstorm-koubo -> /fd-vaas-video-creator -> /fd-vaas-publish-videos -> 视频平台
图文主线： 文章 -> /fd-vaas-publish-docs -> 图文平台
```

---

## 目录

- [VAAS - 可变资源创作与分发](#vaas---可变资源创作与分发)
  - [工作原理](#工作原理)
  - [VAAS 主线](#vaas-主线)
  - [仓库结构](#仓库结构)
  - [前置条件](#前置条件)
  - [安装与部署](#安装与部署)
    - [1. 分发运行时（ego-browser + patchright）](#1-分发运行时ego-browser--patchright)
    - [2. 创作工具](#2-创作工具)
    - [3. Remotion 视频项目](#3-remotion-视频项目)
    - [4. Claude Code 技能](#4-claude-code-技能)
  - [技能一览](#技能一览)
  - [平台支持矩阵](#平台支持矩阵)
  - [端到端使用示例](#端到端使用示例)
  - [多模态模型配置（LiteLLM Bridge）](#多模态模型配置litellm-bridge)
  - [配置与代理说明](#配置与代理说明)
  - [坑与排错](#坑与排错)

---

## 工作原理

```
 ┌─────────────────────────── 创作（CREATION）──────────────────────────┐   ┌──── 分发（DISTRIBUTION）────┐

  需求 ──► ppt-master ──────► .pptx          ┐
        ├─► officecli  ──────► .docx/.xlsx    ├─► 素材文件 ──► fd-vaas-publish-videos ──► 视频平台
        ├─► cap        ──────► .mp4/.gif      │               （抖音、快手、小红书、
        ├─► fd-cover-image ──► 封面图          │                B站、视频号、YouTube）
        ├─► remotion   ──────► .mp4           │
        └─► fd-vaas-video-creator ► .mp4+.srt ┘               ──► fd-vaas-publish-docs ──► 图文平台
                                                            （知乎、公众号、小红书、雪球、
                                                             东财、同花顺、头条、百家、微博）
```

- **创作技能**产出具体的文件。每个技能的 `SKILL.md` 是权威契约--驱动工具前先读它。
- **分发**只消费文件 + 元数据（视频 = `title + desc + tags`；图文 = `title + content + tags`）。两半之间没有共享胶水代码，*除了* `fd-vaas-*` 主线--创作技能产出的素材路径就是发布技能读取的那个。
- **登录态**：macOS 由 ego-browser 继承用户 Chrome 登录态（无需 cookie/账号文件）；Windows 由 patchright 持久 profile（`VAAS/.profiles/<platform>/`）复用登录态。

---

## VAAS 主线

`fd-vaas-*` 技能是接好的「需求到发布」流水线。

### 视频主线（「做一支视频并发布」）

1. **`/fd-vaas-brainstorm-koubo`** *（可选）*--给定赛道/主题，返回选题矩阵（热点/痛点/争议/干货/人设）、推荐脚本框架（黄金三秒 / SCQA / PREP / 故事钩子 / 清单体）、差异化角度，以及可选的完整大纲。
2. **`/fd-vaas-video-creator`**--把文案变成成片。支持两种视频类型：
   - **口播视频**：`new-task -> TTS（seed-tts-2.0，返回音频 + 官方逐字时间戳）-> fix-tts-timings（修正 Latin token 的假 endMs）-> preflight -> Remotion 渲染 -> <slug>.mp4（+ .srt）`。**必须跑 `fix-tts-timings`，否则字幕错位。**
   - **录屏/网页操作视频**：用 ego-browser 打开目标页面操作，过程中用 cap 录屏，产出 mp4（可配麦克风解说）。
   所有产物落在 `downloads/fd-videos/<slug>/`，由 `task.json` 管理。画面层 = 已有素材 / seedance 视频 / seedream 图片 / ppt 母带。**内置三大生成器**（TTS / Seedream / Seedance）在 `scripts/generators/`。
3. **`/fd-vaas-publish-videos`**--一支视频 -> 6 个平台。`publish.mjs` 按 `process.platform` 派发：macOS 走 `.mjs`（ego-browser），Windows 走 `.py`（patchright）。从 `.env` 读取各平台偏好（标签、`BILIBILI_TID`、`TENCENT_SHORT_TITLE`、`YOUTUBE_VISIBILITY`、定时），把结果回写到 `task.json` 的 `distribution[]`。`--dry-run` 可预览命令。

```bash
SKILL_V=/Users/chengsishi/VAAS/.agents/skills/fd-vaas-video-creator/scripts
SKILL_P=/Users/chengsishi/VAAS/.agents/skills/fd-vaas-publish-videos/scripts

# 2. 文案 -> 口播视频
node $SKILL_V/new-task.mjs    --slug <slug> --script /path/to/script.txt
node $SKILL_V/task-render.mjs --slug <slug>            # -> downloads/fd-videos/<slug>/<slug>.mp4

# 3. 多平台发布
node $SKILL_P/publish.mjs --slug <slug> --title "…" --platforms douyin,xiaohongshu,bilibili --dry-run
```

### 图文主线（「发一篇文章」）

**`/fd-vaas-publish-docs`**--把一篇文章/图文一键分发到 9 个图文平台。**只做编排**（平台差异化文案/字数/标签/封面 + 内容适配 + 发布记录），浏览器自动化全部用 ego-browser，由本 skill 的 `references/<platform>.md` heredoc 驱动。`publish.mjs` 只负责 prep + 记录。

- **支持平台**：知乎、微信公众号、小红书、雪球、东方财富号、同花顺财经号、今日头条、百家号、微博。
- **`_DOC_TAGS` 后缀**和视频 skill 的 `<PLATFORM>_TAGS` 区分，共用 `.env` 不冲突。
- ⚠️ **发布前必须让用户确认**（发出去撤不回来）。各平台浏览器选择器多为页面结构推断、**未在登录态下实机验证**，首次发布前必须用 `references/probe.md` 的 `snapshotText` 流程核对选择器再驱动。

```bash
SKILL_D=/Users/chengsishi/VAAS/.agents/skills/fd-vaas-publish-docs/scripts
node $SKILL_D/publish.mjs --slug <slug> --platforms zhihu,xiaohongshu --dry-run   # 预览；确认后再去掉 --dry-run
```

---

## 仓库结构

```
VAAS/
├── .agents/skills/             # ★ 技能真相源（21 个技能，已 git 跟踪）
│   ├── cap/  officecli/  ppt-master/   # 创作工具
│   ├── ego-browser/                     # 浏览器自动化（agent 隔离空间，复用 Chrome 登录态）
│   ├── fd-browser-record/              # 录屏/网页操作视频
│   ├── fd-cover-image/                 # Remotion 品牌封面图
│   ├── fd-coding-{bore,cloudflare,wifi}-tunnel/   # 内网穿透 / 局域网分享
│   ├── fd-vaas-brainstorm-koubo/        # 口播选题 + 脚本大纲
│   ├── fd-vaas-video-creator/          # 文案 -> 口播视频（.mp4 + .srt）；内置 TTS/Seedream/Seedance 生成器
│   │   └── scripts/generators/         #   tts-wrapper.js / seedream-wrapper.js / seedance-wrapper.js
│   ├── fd-vaas-publish-videos/         # 视频多平台发布（ego-browser .mjs + patchright .py 双运行时）
│   │   └── scripts/{publish.mjs, platforms/<platform>.{mjs,py}, lib/}
│   ├── fd-vaas-publish-docs/          # 图文多平台发布（ego-browser 指令驱动）
│   ├── fd-vaas-dashboard/  fd-vaas-dashboard-sharing/   # 内容看板 + 分享
│   └── remotion-*/                     # 7 个 Remotion 创作技能（best-practices、captions、create、
│                                       #   interactivity、markup、render、saas）
├── .claude/skills/                     # 指向 .agents/skills/ 子集的软链接（供 /<name> 调用）
├── scripts/                            # 多模态媒体桥
│   ├── litellm-bridge.py               #   统一多 Provider 入口（TTS / 图像 / 视频）
│   ├── _volcengine_{tts,image,video}.py#   火山方舟直连实现
│   ├── requirements.txt / pyproject.toml
├── remotion-app/                       # Remotion 视频项目（React -> 视频）     [已 gitignore]
├── downloads/fd-videos/<slug>/         # fd-vaas-video-creator 每支视频的产出   [已 gitignore]
├── downloads/fd-docs/<slug>/          # fd-vaas-publish-docs 每篇文章的产出     [已 gitignore]
├── .env / .env.example                 # 平台偏好与多模态 Provider 配置
├── goal.md                             # 项目目标（why）
└── AGENTS.md                           # 给 Claude Code 的工程指引
```

> **VAAS 根目录是一个 git 仓库**（远程：`github.com/FindDataTechnology/fd-vaas-skills`）。`remotion-app/`、`downloads/`、`demands/`、`demand.md`、`.env` 已 gitignore。**`social-auto-upload/` 已删除**，不要再引用它。

---

## 前置条件

- **Node.js 18+**（带 Git）--Remotion 项目和所有 `fd-vaas-*` 技能。
- **Python 3.10–3.12**（`<3.13`）和 [`uv`](https://docs.astral.sh/uv/)--仅 Windows 的 patchright 链路和根目录 `scripts/` 的 LiteLLM bridge 需要。
- **ffmpeg/ffprobe**--`fd-vaas-video-creator` 的时长/帧数校验。
- **ego-browser**（macOS 分发）--`which ego-browser` 检查。
- **patchright**（Windows 分发）--`pip install patchright` + `patchright install chromium`。
- **Claude Code**--`.claude/skills/` 下的技能以 `/cap`、`/officecli`、`/fd-vaas-video-creator` 等方式调用。
- **macOS** 推荐使用 ego-browser 链路；**Windows** 用 patchright 链路（ego-browser 无 Windows 版）。
- 如果你所在网络需要代理，本地 HTTP 代理在 `127.0.0.1:7892`（备用 `7890`）--见[代理说明](#配置与代理说明)。
- 在 `.env` 里配置火山方舟 Ark API key，供内置生成器（TTS / Seedance / Seedream）使用。
- **LiteLLM**（可选）：`pip install -r scripts/requirements.txt`，用于切换非火山 Provider（OpenAI、Azure、ElevenLabs 等）。

---

## 安装与部署

### 1. 分发运行时（ego-browser + patchright）

分发栈**不再是** `social-auto-upload`。现在分两层：

```bash
# macOS：ego-browser（继承用户 Chrome 登录态，无 cookie / 无 account 文件）
which ego-browser            # 若未装，按 ego-browser 官方文档安装
# 在真实 Chrome 里登录各平台一次，ego-browser 之后复用该登录态

# Windows：patchright（stealth Playwright，持久 profile）
pip install patchright
patchright install chromium   # 国内可加 PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
# 登录态持久化到 VAAS/.profiles/<platform>/
```

发布技能会按 `process.platform` 自动选择运行时，无需手选。

### 2. 创作工具

`cap` 和 `officecli` 是外部单文件 CLI（无需装 Office）。全局装一次：

```bash
# cap - 对 agent 友好的屏幕录制 / 截图 / 上传（cap.so）
curl -fsSL https://cap.so/install-cli.sh | sh
cap --version                    # 二进制 -> ~/.local/bin/cap

# officecli - 创建/编辑/分析 .docx .xlsx .pptx
curl -fsSL https://d.officecli.ai/install.sh | bash      # macOS / Linux
# Windows (PowerShell):  irm https://d.officecli.ai/install.ps1 | iex
officecli --version
```

`ppt-master` 是仓库内的工作流（不是外部二进制）。如果用到它的生图步骤，按 `.agents/skills/ppt-master/requirements.txt` 装依赖。

### 3. Remotion 视频项目

```bash
cd remotion-app
npm install
npm run dev        # Remotion Studio 预览  ->  http://localhost:3001
                   #（3000 端口已被占用；Studio 回落到 3001）
npx remotion render      # 把视频渲染成文件
```

> `fd-vaas-video-creator` 需要 `@remotion/captions` 和一个 `VoiceoverVideo` composition--一次性设置见 `.agents/skills/fd-vaas-video-creator/references/setup.md`。

### 4. Claude Code 技能

技能**已签入本仓库**（源码在 `.agents/skills/`，`.claude/skills/` 是指向其子集的软链接），打开 VAAS 目录时 Claude Code 会自动发现。直接调用：

- `/cap`--录屏、截图、导出/上传视频。
- `/officecli`--创建、分析、校对、修改 Office 文档。
- `/ppt-master`--把源文档（PDF/DOCX/URL/Markdown）变成 SVG 幻灯片并导出 `.pptx`。
- `/ego-browser`--浏览器自动化（开页、填表、点击、抓数据、登录）。
- `/fd-browser-record`--开网页 + 录屏 / 截图。
- `/fd-cover-image`--用 Remotion 生成品牌封面图（横/竖）。
- `/fd-vaas-brainstorm-koubo`--口播选题矩阵 + 脚本大纲。
- `/fd-vaas-video-creator`--文案 -> 口播视频（`.mp4` + `.srt`），或录屏视频。
- `/fd-vaas-publish-videos`--一支视频 -> 多平台发布（6 个视频平台）。
- `/fd-vaas-publish-docs`--一篇文章 -> 多平台发布（9 个图文平台）。
- `/dashboard`、`/share-dashboard`--内容看板与分享。
- `/remotion-*`--创作 Remotion 视频（create、markup、captions、render 等）。

> **约定：** 新建 Claude Code 技能放在 `VAAS/.agents/skills/`（真相源），再到 `.claude/skills/` 建软链接，不要放全局 `~/.claude/skills/`。

---

## 技能一览

| 技能 | 产出 | 类型 | 入口 |
|---|---|---|---|
| `ppt-master` | SVG 幻灯片 -> 导出 `.pptx`（策略 -> 执行 -> QC） | 仓库工作流 | `/ppt-master` |
| `officecli` | `.docx`/`.xlsx`/`.pptx` 创建+编辑 | 外部 CLI | `/officecli` · `~/.local/bin/officecli` |
| `cap` | 屏幕录制 / 截图 -> `.mp4`/`.gif` + 分享链接 | 外部 CLI | `/cap` · `~/.local/bin/cap` |
| `ego-browser` | 浏览器自动化（隔离 agent 空间，复用 Chrome 登录态） | 仓库技能 | `ego-browser` CLI |
| `fd-browser-record` | 开网页 + 录屏 / 截图（ego-browser + cap） | 仓库技能 | `/fd-browser-record` |
| `fd-cover-image` | Remotion 品牌封面图（横/竖） | 仓库技能 | `/fd-cover-image` |
| `fd-coding-bore-tunnel` | bore.pub 内网穿透 | 仓库技能 | `/bore-tunnel` |
| `fd-coding-cloudflare-tunnel` | Cloudflare Tunnel（HTTPS）内网穿透 | 仓库技能 | `/cf-tunnel` |
| `fd-coding-wifi-tunnel` | 局域网 / WiFi 分享本地服务 | 仓库技能 | `/wifi-tunnel` |
| `fd-vaas-brainstorm-koubo` | 选题矩阵 + 脚本框架 + 差异化角度 + 大纲 | 仓库技能（纯提示词） | `/fd-vaas-brainstorm-koubo` |
| `fd-vaas-video-creator` | 文案 -> 口播视频 `.mp4`+`.srt`；或录屏视频；内置 TTS/Seedream/Seedance | 仓库技能 | `/fd-vaas-video-creator` |
| `fd-vaas-publish-videos` | 一支视频 -> 6 个视频平台（ego-browser .mjs + patchright .py 双运行时） | 仓库技能 | `/fd-vaas-publish-videos` |
| `fd-vaas-publish-docs` | 一篇文章 -> 9 个图文平台（ego-browser 指令驱动） | 仓库技能 | `/fd-vaas-publish-docs` |
| `fd-vaas-dashboard` | 内容看板（展示所有生成的文章和视频） | 仓库技能 | `/dashboard` |
| `fd-vaas-dashboard-sharing` | 分享看板（走隧道） | 仓库技能 | `/share-dashboard` |
| `remotion-create` | 脚手架新建 Remotion 项目/composition | 仓库技能 | `/remotion-create` |
| `remotion-markup` | Remotion 的 React markup 最佳实践 | 仓库技能 | `/remotion-markup` |
| `remotion-captions` | 字幕处理（JSON `Caption` 类型） | 仓库技能 | `/remotion-captions` |
| `remotion-render` | 渲染视频（`npx remotion render`） | 仓库技能 | `/remotion-render` |
| `remotion-interactivity` | 适配 Studio 视觉模式的动画 | 仓库技能 | `/remotion-interactivity` |
| `remotion-best-practices` | Remotion 最佳实践索引 | 仓库技能 | `/remotion-best-practices` |
| `remotion-saas` | 用 Remotion 构建视频应用（框架/Player/Lambda） | 仓库技能 | `/remotion-saas` |

外部 CLI 自带帮助系统--优先用它，别猜参数：`cap guide` / `cap guide --json`、`officecli help` / `officecli help docx paragraph`。

---

## 平台支持矩阵

### 视频平台（`fd-vaas-publish-videos`）

6 个平台，每个都有 ego-browser（`.mjs`，macOS）和 patchright（`.py`，Windows）两套实现。浏览器自动化默认**无头**。

| 平台 | 脚本 | 核心技术挑战 | 备注 |
|---|---|---|---|
| `douyin` | `douyin.{mjs,py}` | 标准 DOM | `--cover-horizontal` + `--cover-vertical`；`--schedule`；tag ≤ 10 |
| `kuaishou` | `kuaishou.{mjs,py}` | React Joyride 遮罩 + 发布按钮在视口外 | tag ≤ **4**（不是 5） |
| `xiaohongshu` | `xiaohongshu.{mjs,py}` | 标准 DOM | title ≤ 20 字；tag ≤ 10 |
| `bilibili` | `bilibili.{mjs,py}` | **micro-app shadow DOM** | `--cover`（不是 `--thumb`）；`--tid` 分区；不支持 `--schedule` |
| `weixin`（视频号） | `weixin.{mjs,py}` | **Wujie shadow DOM** + HTTP server + DataTransfer | 无独立标题字段；处理后自动发布 |
| `youtube` | `youtube.{mjs,py}` | **Polymer dialog** + 4 步流程 | `--thumbnail`；`--visibility`；"Not made for kids" 强制 |

详见 `.agents/skills/fd-vaas-publish-videos/references/platform-quirks.md` 与 `references/<platform>.md`。

### 图文平台（`fd-vaas-publish-docs`）

9 个平台，全部走 ego-browser（指令驱动，`references/<platform>.md` heredoc）。

| 平台 | 备注 |
|---|---|
| 知乎 `zhihu` | 文章 |
| 微信公众号 `weixin` | 图文 |
| 小红书 `xiaohongshu` | 图文笔记 |
| 雪球 `xueqiu` | 财经专栏 |
| 东方财富号 `eastmoney` | 财经 |
| 同花顺财经号 `tonghuashun` | 财经 |
| 今日头条 `toutiao` | 文章 |
| 百家号 `baijiahao` | 文章 |
| 微博 `weibo` | 长文 |

> ⚠️ 这些平台的选择器多为页面结构推断，**未在登录态下实机验证**。首次发布前用 `references/probe.md` 的 `snapshotText` 流程核对选择器。

---

## 端到端使用示例

### 视频：从文案到多平台发布

```bash
SKILL_V=/Users/chengsishi/VAAS/.agents/skills/fd-vaas-video-creator/scripts
SKILL_P=/Users/chengsishi/VAAS/.agents/skills/fd-vaas-publish-videos/scripts

# 1. 文案 -> 口播视频
node $SKILL_V/new-task.mjs    --slug demo --script ./script.txt
node $SKILL_V/task-render.mjs --slug demo          # -> downloads/fd-videos/demo/demo.mp4

# 2. 多平台发布（先预览，确认后再去掉 --dry-run）
node $SKILL_P/publish.mjs --slug demo --title "标题" \
    --platforms douyin,xiaohongshu,bilibili --tags 开源,AI --dry-run

# 3. 单平台临时上传（调试）
node $SKILL_P/platforms/douyin.mjs --file downloads/fd-videos/demo/demo.mp4 \
    --title "标题" --desc "描述。" --tags 开源,AI
```

### 图文：发布一篇文章

```bash
SKILL_D=/Users/chengsishi/VAAS/.agents/skills/fd-vaas-publish-docs/scripts
# 文章放在 downloads/fd-docs/<slug>/ 下
node $SKILL_D/publish.mjs --slug <slug> --platforms zhihu,xiaohongshu --dry-run
# 确认选择器无误、用户同意后，去掉 --dry-run 真正发布
```

### 登录

- **macOS（ego-browser）**：在真实 Chrome 里登录各平台一次，ego-browser 之后复用该登录态。登录过期就在 ego-browser 里重新登录，**无需 cookie 文件、无需 `--account`**。
- **Windows（patchright）**：首次运行会打开登录页，登录态持久化到 `VAAS/.profiles/<platform>/`。

**元数据约定**：视频 = `title + desc + tags`；图文 = `title + content + tags`。传 `--schedule "YYYY-MM-DD HH:MM"` 切到定时发布（不传 = 立即）。仅部分平台支持 `--schedule`。

---

## 多模态模型配置（LiteLLM Bridge）

`fd-vaas-video-creator` 内置的生成器（TTS / 图像 / 视频）通过根目录 `scripts/litellm-bridge.py` 统一入口，支持多 Provider 切换。模型配置全部在 `.env` 里管理，改 Provider 不需要改代码。**已没有独立的 `voice/image/video-generator` 技能**--它们已合并进 `fd-vaas-video-creator/scripts/generators/`。

### 支持的 Provider

| 模态 | LiteLLM Provider | 火山直连 |
|------|-----------------|----------|
| **TTS** | openai、azure、vertex_ai、elevenlabs、minimax、polly | ✅（带逐字时间戳） |
| **图像** | openai、azure、google-ai-studio、vertex-ai、bedrock、black-forest-labs、recraft、openrouter | ✅（带参考图/联网搜索/批量） |
| **视频** | 有限支持（litellm video 接口尚在早期） | ✅（带异步轮询/参考媒体） |

### `.env` 配置示例

```env
# ─── 语音合成 ───
TTS_PROVIDER=volcengine        # volcengine | openai | elevenlabs | azure | ...
TTS_MODEL=seed-tts-2.0         # volcengine 用 plain name；其他用 "provider/model"（如 "openai/tts-1"）
TTS_VOICE=zh_female_gaolengyujie_uranus_bigtts

# ─── 图像生成 ───
IMAGE_PROVIDER=volcengine      # volcengine | openai | azure | google-ai-studio | ...
IMAGE_MODEL=doubao-seedream-5.0-lite

# ─── 视频生成 ───
VIDEO_PROVIDER=volcengine      # 推荐用 volcengine（功能最全）
VIDEO_MODEL=doubao-seedance-2.0

# 非火山 Provider 的 API Key（按需设置）
# OPENAI_API_KEY=sk-...
# ELEVENLABS_API_KEY=...
# AZURE_API_KEY=...
# GOOGLE_AI_STUDIO_API_KEY=...
```

### 自动路由

- **`.env` 中 `*_PROVIDER != volcengine`** -> 生成器自动走 LiteLLM bridge，无需加任何 flag。
- **`--litellm` flag** -> 强制走 bridge（即使 Provider 设的是 volcengine）。
- **volcengine 直连** -> 保留全部高级功能（TTS 逐字时间戳、图像参考图/联网搜索、视频异步任务/参考媒体）。

### 安装依赖

```bash
pip install -r scripts/requirements.txt
# 或：cd scripts && pip install -e .
```

> ⚠️ **字幕注意**：只有 volcengine TTS 直连才带官方逐字时间戳（`captions.json`）。切换到其他 Provider 后，`fd-vaas-video-creator` 的字幕功能会降级或不可用。如需字幕，推荐保留 TTS 用 volcengine。

---

## 配置与代理说明

- **`fd-vaas-*` 配置**：从项目根 `.env` 读取（见 `.env.example`）。两套命名空间共存：
  - **视频**：`PLATFORMS`、`TAGS`、`<PLATFORM>_TAGS`、`BILIBILI_TID`、`TENCENT_SHORT_TITLE`、`YOUTUBE_VISIBILITY`、`SCHEDULE`、`HEADLESS`。
  - **图文**：`PLATFORMS_DOCS`、`DOC_TAGS`、`<PLATFORM>_DOC_TAGS`、`DOC_SCHEDULE`、`DOC_HEADLESS`（`_DOC_TAGS` 后缀避免和视频 skill 的 `<PLATFORM>_TAGS` 冲突）。
- **单任务覆盖**：视频放 `downloads/fd-videos/<slug>/.publish.env`，图文放 `downloads/fd-docs/<slug>/.publish.env`。优先级：`--flag CLI > <task>/.publish.env > <VAAS>/.env > 内置默认`。
- **登录态**：macOS = ego-browser 继承 Chrome 登录态；Windows = patchright 持久 profile（`VAAS/.profiles/<platform>/`）。同一平台必须串行；不同平台可并发。
- **发布后清理**：发布完成后关闭 ego 任务窗口，别留给用户自己关；抖音手动发布需等用户确认「发布完成」再跑 `completeTaskSpace` 兜底清理。
- **代理（通用）**：如果网络命令连不上主机，走本地代理：`export http_proxy=http://127.0.0.1:7892`（备用 `7890`）。通用场景**不要设 `https_proxy`**。
- **代理 + patchright**：patchright 的 chromium **不**读系统代理。Playwright/patchright 浏览器*安装本身*需要显式设 `https_proxy` 才能连 `cdn.playwright.dev`（国内可加 `PLAYWRIGHT_DOWNLOAD_HOST` 镜像）。
- 某些主机（`officecli.ai`、`raw.githubusercontent.com`）走代理会 TLS 失败--用 `env -u http_proxy -u https_proxy <cmd>` 绕过。

---

## 坑与排错

- **`social-auto-upload/` 已移除**--旧文档里所有 `sau`、`sau_cli.py`、cookie 文件、`account_name` 的描述都过时了。分发现在由 `fd-vaas-publish-videos` / `fd-vaas-publish-docs` 内置的 ego-browser + patchright 完成。
- **独立的 `voice/image/video-generator` 技能已不存在**--生成器合并进了 `fd-vaas-video-creator/scripts/generators/`。多 Provider 切换仍由根目录 `scripts/litellm-bridge.py` 提供。
- **PPTX 幻灯片不能直接当视频上传。** `cap`（屏幕录制）、`fd-vaas-video-creator`、或 `ppt-master` 的导出/渲染步骤，是把幻灯片变成可发布视频的桥。
- **`fd-vaas-video-creator` 跳过 `fix-tts-timings` 会让字幕错位**--seed-tts-2.0 对 Latin token（英文名、URL）返回假的 `endMs`。流水线会自动跑这步；手工路径必须显式跑。
- **Windows patchright 链路未在真机登录态下完整验证**（尤其 `weixin`/`bilibili` 的 `.py`）。先用 `--dry-run` 看能否进到上传页，再考虑真发。
- **图文平台选择器多为推断、未实机验证**--首次发布前用 `references/probe.md` 的 `snapshotText` 流程核对，确认后再驱动。
- **发布前必须让用户确认**（尤其图文，发出去撤不回来）。

# VAAS - 可变资源创作与分发

> **谦面 Facet 产品线** · [寻数 FindData](https://www.finddatatech.cloud/products/facet) 的内容创作线 —— 自然语言视频创作与多平台分发技能链。

> **🌐 语言：** 简体中文（本文件） · [English](README.en.md)

> 🚀 **一键安装：** `curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-vaas-skills/main/install.sh | bash`

## ⚡ 5 分钟第一支视频

```bash
export VAAS=<克隆下来的仓库根目录，如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代

# 1. 安装（已跑过一键安装可跳过）
cd $VAAS && ./install.sh

# 2. 填密钥：编辑 .env，填入 vol_agent_api_key（火山方舟，https://console.volcengine.com/ark）
#    不确定环境是否就绪？随时跑：
node $VAAS/scripts/doctor.mjs

# 3. 出片走 MCP 工具面（本地 stdio 或托管端点均可；2026-11-09 起无本地 node 渲染链）
#    generate_voice(text="你好，这是 VAAS 的第一支视频。", slug="demo")   -> 配音 + captions.json
#    render_video(type="news-flash", script="…", inputs={...}, slug="demo") -> 成片 mp4
#    （也可 render_still 出封面/图表、render_document 出 PDF/长图）

# 产物：$VAAS/downloads/video/demo/demo.mp4（+ review URL / 签名 download_url）
```

> 接收一个内容需求，生成**可变类型的资源**（幻灯片、文档、屏幕录制视频、AI 图片/视频，或渲染面渲染的口播视频），然后**自动发布到不同的社交媒体账号**——理想情况下为每个平台产出*不同*的变体。

VAAS 是架在两半之上的一个**编排层**，自身没有应用代码：

1. **创作技能（Creation skills）**——把需求变成一个素材文件（`.pptx`、`.docx`、`.mp4`、图片……），源码在 `.agents/skills/`。
2. **分发引擎（Distribution engine）**——两个发布技能把素材发到各平台：`fd-vaas-publish-videos`（视频 -> 6 个视频平台）和 `fd-vaas-publish-docs`（图文 -> 11 个图文平台）。分发走「**vendor 上游 + 薄适配层**」：把 `social-auto-upload` 上游整个 vendor 进发布技能的 `scripts/upstream/`，薄适配层（`sau_adapter.py` / `note_adapter.py`）把 CLI 翻译成上游 `<Platform>Video(...).main()` 调用，统一 **py 运行时（patchright）**，登录态是 cookie 文件（`upstream/cookies/<platform>_uploader/account.json`）；bilibili 例外（上游用 biliup 二进制，走本地 `bilibili.py`）。

> **架构变更（重要）：** 分发栈已重新 vendor 上游 `social-auto-upload`——这是第二次架构翻转。先前「`social-auto-upload` 已移除、分发完全内置、macOS 走 ego-browser（`.mjs`）/ Windows 走 patchright（`.py`）双运行时」的表述**全部作废**。现在统一 py/patchright 运行时 + cookie 登录；各平台手写的 `.mjs`/`.py` 已删除。如果你看到旧文档提到 ego-browser 复用 Chrome 登录态发视频、`--runtime` 按 OS 派发，那些都已过时。

当有人说「做一个资源并发出去」时，预期的流程是：

```
创作技能产出一个文件  ->  发布技能把它上传到一个或多个账号
```

两条已接好的**主线**通过 `fd-vaas-*` 技能把这个流程端到端串起来（无需手写胶水代码）：

```
视频主线： 需求 -> /fd-vaas-brainstorm -> /fd-vaas-video-creator -> /fd-vaas-publish-videos -> 视频平台
图文主线： 选题 -> /fd-vaas-brainstorm(图文模式) -> 文章 -> /fd-vaas-publish-docs -> 图文平台
```

---

## 目录

- [VAAS - 可变资源创作与分发](#vaas---可变资源创作与分发)
  - [⚡ 5 分钟第一支视频](#5-分钟第一支视频)
  - [工作原理](#工作原理)
  - [VAAS 主线](#vaas-主线)
  - [仓库结构](#仓库结构)
  - [前置条件](#前置条件)
  - [安装与部署](#安装与部署)
    - [1. 分发运行时（patchright）与登录](#1-分发运行时patchright与登录)
    - [2. 创作工具](#2-创作工具)
    - [3. Remotion 视频项目](#3-remotion-视频项目)
    - [4. Claude Code 技能](#4-claude-code-技能)
  - [技能一览](#技能一览)
  - [平台支持矩阵](#平台支持矩阵)
  - [端到端使用示例](#端到端使用示例)
  - [生成后端配置（volcengine / ciyuan 双档）](#生成后端配置volcengine--ciyuan-双档)
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
                                                            （知乎、公众号、小红书、抖音、
                                                             快手、雪球、东财、同花顺、
                                                             头条、百家、微博）
```

- **创作技能**产出具体的文件。每个技能的 `SKILL.md` 是权威契约--驱动工具前先读它。
- **分发**只消费文件 + 元数据（视频 = `title + desc + tags`；图文 = `title + content + tags`）。两半之间没有共享胶水代码，*除了* `fd-vaas-*` 主线--创作技能产出的素材路径就是发布技能读取的那个。
- **登录态**：发布走 cookie 文件（`scripts/upstream/cookies/<platform>_uploader/account.json`），统一用 `/fd-vaas-login`（localhost:8766）扫码登录，视频与图文共享同一份 cookie。图文自有逻辑平台另可走 `--runtime patchright`（独立持久 profile `VAAS/.profiles/<platform>/`）。ego-browser 仅用于录屏和图文自有平台的默认运行时。

---

## VAAS 主线

`fd-vaas-*` 技能是接好的「需求到发布」流水线。

### 视频主线（「做一支视频并发布」）

1. **`/fd-vaas-brainstorm`** *（可选）*--给定赛道/主题，按口播 / 图文模式返回选题矩阵（热点/痛点/争议/干货/人设）、脚本框架或图文草稿（Markdown 版 + 纯文本简洁版）、差异化角度，以及可选的完整大纲。内置合规红线：口播稿不出现其他平台名、不引流站外。
2. **`/fd-vaas-video-creator`**--把文案变成成片。通过**类型注册表**（`new-task --type <id>`）选视频类型，`node scripts/types/list.mjs` 看全部类型。稳定类型：口播 `voiceover`、录屏 `screen-recording`；实验类型：`carousel`（轮播）、`kinetic-quote`（动态金句）、`news-flash`（快讯）、`listicle`（盘点）、`data-viz`（数据可视化）。
   - **口播视频**：`generate_voice（volcengine 直连=官方逐字时间戳；词元 ciyuan 档=出口层分段合成+合成字幕，captions_source 可审计）-> render_video(type=… | storyboard=…) -> <slug>.mp4`。渲染由**独立无状态渲染面**承担（HyperFrames，API 面无 Node）；本地 `new-task.mjs`/`task-render.mjs`/`fix-tts-timings` 已于 2026-11-09 随 Remotion 退役，字幕时间以出口层实测/合成口径为准。
   - **录屏/网页操作视频**：用 ego-browser 打开目标页面操作，过程中用 cap 录屏，产出 mp4（可配麦克风解说）。
   所有产物落在 `downloads/<kind>/<slug>/`。画面层 = 已有素材 / seedance 视频 / seedream 图片 / ppt 母带。**生成能力在托管 MCP 面**（`generate_voice` / `generate_image` / `generate_video_submit` / `render_*`），多模态桥在根 `scripts/litellm-bridge.py`（volcengine / ciyuan 两档）。
3. **`/fd-vaas-publish-videos`**--一支视频 -> 6 个平台。分发走「**vendor 上游 + 薄适配层**」：上游 `social-auto-upload` vendored 在 `scripts/upstream/`，`sau_adapter.py` 把 CLI 翻译成上游 `<Platform>Video(...).main()` 调用，统一 **py 运行时（patchright）**；bilibili 例外（上游用 biliup 二进制，走本地 `bilibili.py`）。登录态是 cookie 文件（`upstream/cookies/<platform>_uploader/account.json`，快手用 `kuaishou_creator.json`），由 `/fd-vaas-login` 统一扫码。从 `.env` 读取各平台偏好（标签、`BILIBILI_TID`、`TENCENT_SHORT_TITLE`、`YOUTUBE_VISIBILITY`、定时），把结果回写到 `task.json` 的 `distribution[]`。`--dry-run` 可预览命令。

```bash
export VAAS=<VAAS 仓库根目录,如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代
SKILL_V=$VAAS/.agents/skills/fd-vaas-video-creator/scripts
SKILL_P=$VAAS/.agents/skills/fd-vaas-publish-videos/scripts

# 2. 文案 -> 成片（MCP 工具面）
#     generate_voice(text|file_path, slug)                    -> downloads/audio/<slug>/<slug>.mp3 + captions.json
#     render_video(type=<id>, script=…, inputs={…}, slug=…)    -> downloads/video/<slug>/<slug>.mp4

# 3. 多平台发布
node $SKILL_P/publish.mjs --slug <slug> --title "…" --platforms douyin,xiaohongshu,bilibili --dry-run
```

### 渲染执行体（单一：HyperFrames 渲染面）

2026-11-09 起视频渲染只有一条执行体：类型/storyboard 编译成 composition，提交给**独立、无状态、
可多实例的渲染面**（HyperFrames 0.9.26），API 面镜像**不含 Node**（ADR-0004 增补）。
本地 Remotion 管线与 `remotion-app/` 已彻底退役。

| 项 | 口径 |
|---|---|
| 提交入口 | `render_video(type=<id> | storyboard=…)`；`render_still` / `render_document` 同底座 |
| 渲染面 | 独立服务，`VAAS_RENDER_URL(S)` 指向；部署与容量口径见 `deploy/README.md`「渲染面（Render Plane）」 |
| 隔离 | 渲染面接 internal 网络（无出网）；作业 env 白名单不含平台密钥 |
| BGM | ✅ 原生多轨（不再成片后混流） |
| 字幕粒度 | 句/段级——volcengine 直连带官方逐字戳（`captions_source: official`），ciyuan 档由出口层按段实测对齐合成（`synthetic`） |
| 回滚 | 渲染面镜像 tag 级（`ccr…/yizuo/vaas-render-plane:sha-*`） |

### 图文主线（「发一篇文章」）

**`/fd-vaas-publish-docs`**--把一篇文章/图文一键分发到 11 个图文平台。**只做编排**（平台差异化文案/字数/标签/封面 + 内容适配 + 发布记录）。分发走「**上游优先**」路由：小红书/抖音/快手图文走 `note_adapter.py`（与视频共享同一份 cookie）；其余 8 个自有逻辑平台用 ego-browser（默认，`references/<platform>.md` heredoc 驱动）或 `--runtime patchright`（独立持久 profile）。`publish.mjs` 负责 prep + 记录。平台路由与验证状态的单一事实源是 `_shared/publish/platform-registry.json`。

- **支持平台（11）**：知乎、微信公众号、小红书、抖音、快手、雪球、东方财富号、同花顺财经号、今日头条、百家号、微博。
- **`_DOC_TAGS` 后缀**和视频 skill 的 `<PLATFORM>_TAGS` 区分，共用 `.env` 不冲突。
- ⚠️ **发布前必须让用户确认**（发出去撤不回来）。验证状态见[平台支持矩阵](#平台支持矩阵)——已实机验证的平台可直接用；标 ⚠️/❌ 的首次发布前用 `references/probe.md` 的 `snapshotText` 流程核对选择器再驱动。

```bash
SKILL_D=$VAAS/.agents/skills/fd-vaas-publish-docs/scripts
node $SKILL_D/publish.mjs --slug <slug> --platforms zhihu,xiaohongshu --dry-run   # 预览；确认后再去掉 --dry-run
```

---

## 仓库结构

```
VAAS/
├── .agents/skills/             # ★ 技能真相源（23 个技能 + _shared/，已 git 跟踪）
│   ├── cap/  officecli/  ppt-master/   # 创作工具
│   ├── ego-browser/                     # 浏览器自动化（agent 隔离空间，复用 Chrome 登录态）
│   ├── fd-browser-record/              # 录屏/网页操作视频
│   ├── fd-cover-image/                 # Remotion 品牌封面图
│   ├── fd-coding-{bore,cloudflare,wifi}-tunnel/   # 内网穿透 / 局域网分享
│   ├── fd-vaas-brainstorm/              # 口播 + 图文选题 / 脚本 / 草稿
│   ├── fd-vaas-video-creator/          # 视频类型注册表（type.json 契约；渲染走渲染面）
│   │   └── scripts/generators/         #   tts-wrapper.js / seedream-wrapper.js / seedance-wrapper.js
│   ├── fd-vaas-login/                  # 登录管理 Web 页（:8766，扫码/状态总览，cookie 共享）
│   ├── fd-vaas-publish-videos/         # 视频多平台发布（vendor 上游 + 薄适配层，统一 py/patchright）
│   │   └── scripts/{publish.mjs, platforms/sau_adapter.py, platforms/bilibili.py, upstream/, sync-upstream.sh}
│   ├── fd-vaas-publish-docs/          # 图文多平台发布（上游优先 note_adapter + 自有逻辑）
│   │   └── scripts/{publish.mjs, note_adapter.py, platforms/<platform>.py}
│   ├── _shared/publish/               # 跨技能共享：platform-registry.json（路由+验证状态真相源）、browser_utils.py、publish-common.mjs
│   ├── fd-vaas-dashboard/  fd-vaas-dashboard-sharing/   # 内容看板 + 分享
│   └── remotion-*/                     # 7 个 Remotion 创作技能（best-practices、captions、create、
│                                       #   interactivity、markup、render、saas）
├── .claude/skills/                     # 指向 .agents/skills/ 子集的软链接（供 /<name> 调用）
├── scripts/                            # 多模态媒体桥
│   ├── litellm-bridge.py               #   统一生成入口（TTS / 图像 / 视频；volcengine|ciyuan 两档）
│   ├── _volcengine_{tts,image,video}.py#   火山方舟直连实现
│   ├── requirements.txt / pyproject.toml
├── render-plane/                       # 独立渲染面（HyperFrames composition -> MP4）
├── downloads/<kind>/<slug>/            # 各能力产物（video/audio/images/graphic/doc）[已 gitignore]
├── downloads/fd-docs/<slug>/          # fd-vaas-publish-docs 每篇文章的产出     [已 gitignore]
├── .env / .env.example                 # 平台偏好与多模态 Provider 配置
├── goal.md                             # 项目目标（why）
└── AGENTS.md                           # 给 Claude Code 的工程指引
```

> **VAAS 根目录是一个 git 仓库**（远程：`github.com/FindDataTechnology/fd-vaas-skills`）。`downloads/`、`demands/`、`demand.md`、`.env`、`.mcp.json` 已 gitignore。`social-auto-upload` 上游被 vendor 进 `fd-vaas-publish-videos/scripts/upstream/`（不是根目录独立目录）；用 `.agents/skills/fd-vaas-publish-videos/scripts/sync-upstream.sh` 同步上游更新（改动只落适配层，vendor 内手改会被下次 rsync --delete 冲掉）。托管镜像单源：canonical 在 `deploy/mcp-server.Dockerfile`，根 `./Dockerfile` 由其生成（`bash scripts/gen-root-dockerfile.sh`）。

---

## 前置条件

- **Node.js 18+**（带 Git）--Remotion 项目和所有 `fd-vaas-*` 技能。
- **Python 3.10–3.12**（`<3.13`）和 [`uv`](https://docs.astral.sh/uv/)--**全平台必需**：视频发布统一走 py 运行时（patchright），根目录 `scripts/` 的 LiteLLM bridge 也用它。
- **patchright**（stealth Playwright，全平台发布运行时）--`uv pip install patchright` + `patchright install chromium`；登录态是 cookie 文件，由 `/fd-vaas-login` 统一扫码。
- **ffmpeg/ffprobe**--`fd-vaas-video-creator` 的时长/帧数校验。
- **ego-browser**（macOS 可选）--仅用于录屏（`/fd-browser-record`）和图文自有逻辑平台的默认运行时；`which ego-browser` 检查。无 Windows/Linux 版。
- **Claude Code**--`.claude/skills/` 下的技能以 `/cap`、`/officecli`、`/fd-vaas-video-creator`、`/fd-vaas-login` 等方式调用。
- 如果你所在网络需要代理，本地 HTTP 代理在 `127.0.0.1:7892`（备用 `7890`）--见[代理说明](#配置与代理说明)。
- 在 `.env` 里配置火山方舟 Ark API key，供内置生成器（TTS / Seedance / Seedream）使用。
- **LiteLLM**（可选）：`pip install -r scripts/requirements.txt`，用于切换非火山 Provider（OpenAI、Azure、ElevenLabs 等）。

---

## 安装与部署

### 1. 分发运行时（patchright）与登录

分发走「**vendor 上游 + 薄适配层**」：上游 `social-auto-upload` vendored 在 `fd-vaas-publish-videos/scripts/upstream/`，`sau_adapter.py` 把 CLI 翻译成上游 `<Platform>Video(...).main()` 调用，统一 **py 运行时（patchright）**。全平台一致，不再按 OS 派发。

```bash
# 全平台：patchright（stealth Playwright）
uv pip install patchright      # 或 pip install patchright
patchright install chromium    # 国内可加 PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
```

登录态是 cookie 文件（`upstream/cookies/<platform>_uploader/account.json`，快手用 `kuaishou_creator.json`），由 `/fd-vaas-login` 统一扫码管理：

```bash
# 启动登录管理页（Claude Code 里也可直接 /fd-vaas-login）
python3 $VAAS/.agents/skills/fd-vaas-login/scripts/login-manager.py
# 浏览器打开 http://localhost:8766 -> 选平台 -> 扫码/登录 -> cookie 落盘
# 视频与图文共享同一份 cookie；过期就重扫
```

> ego-browser 现在只剩两条用途：`/fd-browser-record` 录屏、图文自有逻辑平台的默认运行时（macOS，可用 `--runtime patchright` 切到独立持久 profile `VAAS/.profiles/<platform>/`）。

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

`ppt-master` 是仓库内的工作流（不是外部二进制），但 VAAS 只签入**薄壳**——首次用 `/ppt-master` 前先拉取上游：`bash scripts/fetch-ppt-master.sh`（~98 MB，落在 gitignore 的 `.agents/skills/ppt-master/upstream/`）。如果用到它的生图步骤，按 `upstream/requirements.txt` 装依赖。

### 3. 渲染面（自建托管时才需要）

本地只做发布与编排时**无需**任何渲染依赖——出片交给托管实例。自建部署见
`deploy/README.md`「渲染面（Render Plane）」：镜像走发布通道（`law-ai-official/vaas-mcp-images`
的 `target=vaas-render-plane`），节点侧以无出网桥接运行，`/healthz` 的 `doctor.checks` 须全 OK。

> Remotion 相关的一次性设置（`@remotion/captions`、`VoiceoverVideo`）已随 2026-11-09 退役失效。

### 4. Claude Code 技能

技能**已签入本仓库**（源码在 `.agents/skills/`，`.claude/skills/` 是指向其子集的软链接），打开 VAAS 目录时 Claude Code 会自动发现。直接调用：

- `/cap`--录屏、截图、导出/上传视频。
- `/officecli`--创建、分析、校对、修改 Office 文档。
- `/ppt-master`--把源文档（PDF/DOCX/URL/Markdown）变成 SVG 幻灯片并导出 `.pptx`。
- `/ego-browser`--浏览器自动化（开页、填表、点击、抓数据、登录）。
- `/fd-browser-record`--开网页 + 录屏 / 截图。
- `/fd-cover-image`--用 Remotion 生成品牌封面图（横/竖）。
- `/fd-vaas-brainstorm`--口播 + 图文选题矩阵、脚本大纲 / 图文草稿（Markdown + 纯文本双版本）。
- `/fd-vaas-video-creator`--文案 -> 口播视频（`.mp4` + `.srt`），或录屏视频。
- `/fd-vaas-publish-videos`--一支视频 -> 多平台发布（6 个视频平台）。
- `/fd-vaas-publish-docs`--一篇文章 -> 多平台发布（11 个图文平台）。
- `/fd-vaas-login`--登录管理页（:8766），扫码登录各视频/图文平台，cookie 共享。
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
| `fd-vaas-brainstorm` | 口播选题矩阵 + 脚本大纲 / 图文草稿（Markdown + 纯文本双版本）+ 差异化角度 | 仓库技能（纯提示词） | `/fd-vaas-brainstorm` |
| `fd-vaas-video-creator` | **视频类型注册表**（`types/*/type.json`，`renderer: hyperframes`）；出片走 `render_video`（独立渲染面）。本地 Remotion 管线已退役 | 仓库技能 | `/fd-vaas-video-creator` |
| `fd-vaas-login` | 登录管理 Web 页（:8766，扫码/状态总览，cookie 共享） | 仓库技能 | `/fd-vaas-login` |
| `fd-vaas-publish-videos` | 一支视频 -> 6 个视频平台（vendor 上游 + sau_adapter，统一 py/patchright） | 仓库技能 | `/fd-vaas-publish-videos` |
| `fd-vaas-publish-docs` | 一篇文章 -> 11 个图文平台（上游优先 note_adapter + 自有逻辑） | 仓库技能 | `/fd-vaas-publish-docs` |
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

6 个平台，统一走 **py 运行时（patchright）**。除 bilibili 外都经 `sau_adapter.py` 调上游 `<Platform>Video.main()`；bilibili 走本地 `bilibili.py`（biliup 二进制）。验证状态来自 `_shared/publish/platform-registry.json`。

| 平台 | 路由 | 备注 | 验证状态 |
|---|---|---|---|
| `douyin` | upstream（`sau_adapter`） | `--schedule`；tag ≤ 10 | 🔄 上游维护 |
| `kuaishou` | upstream（`sau_adapter`） | tag ≤ **4**；cookie = `kuaishou_creator.json` | 🔄 上游维护 |
| `xiaohongshu` | upstream（`sau_adapter`） | title ≤ 20 字；tag ≤ 10 | 🔄 上游维护 |
| `bilibili` | own（`bilibili.py` + biliup） | biliup 二进制（非 Playwright）；`--tid` 分区；不支持 `--schedule` | ⚠️ 未实机验证 |
| `weixin`（视频号） | upstream（`sau_adapter`） | Wujie shadow DOM；无独立标题；处理后自动发布 | ✅ 已验证（2026-07-30） |
| `youtube` | upstream（`sau_adapter`） | `--visibility`；不支持 `--schedule`（无 publish_date） | 🔄 上游维护 |

详见 `.agents/skills/fd-vaas-publish-videos/references/platform-quirks.md` 与 `references/<platform>.md`。

### 图文平台（`fd-vaas-publish-docs`）

11 个平台，走「**上游优先**」路由：小红书/抖音/快手图文经 `note_adapter.py`（与视频共享 cookie）；其余 8 个自有逻辑平台用 ego-browser 或 `--runtime patchright`。验证状态来自 `_shared/publish/platform-registry.json`。

| 平台 | 路由 | 备注 | 验证状态 |
|---|---|---|---|
| 小红书 `xiaohongshu` | upstream-note（`note_adapter`） | 图文/视频共享 cookie | 🔄 上游维护 |
| 抖音 `douyin` | upstream-note（`note_adapter`） | 无封面图时复用 xhs 图 | 🔄 上游维护 |
| 快手 `kuaishou` | upstream-note（`note_adapter`） | cookie = `kuaishou_creator.json` | 🔄 上游维护 |
| 知乎 `zhihu` | own（ego/patchright） | 标题 `textarea[placeholder*=请输入标题]`；正文可粘 markdown | ✅ 已验证（2026-07-29） |
| 微信公众号 `weixin` | own（ego/patchright） | appmsg URL；标题 `#title` 需 js；正文 `.ProseMirror` | ✅ 已验证（2026-07-30） |
| 雪球 `xueqiu` | own | 旧入口 404，真实发文入口待重 probe | ❌ 入口失效（2026-08-11） |
| 东方财富号 `eastmoney` | own | `oa.eastmoney.com` 创作者后台；需财经号资质 | ✅ 已验证（2026-07-29） |
| 同花顺 `tonghuashun` | own | `media.10jqka.com.cn` 302 跳投顾入驻 | ❌ 入口失效（2026-08-11） |
| 今日头条 `toutiao` | own | `mp.toutiao.com`；标题 ≤ 30 字 | ✅ 已验证（2026-07-29） |
| 百家号 `baijiahao` | own | `baijiahao.baidu.com`；封面必填、需选分类 | ✅ 已验证（2026-07-29） |
| 微博 `weibo` | own | `weibo.com/newblog` 长文；#话题# 放正文 | ✅ 已验证（2026-07-29） |

> 状态图例：✅ 已实机验证 / 🔄 上游维护（选择器由 social-auto-upload 上游负责） / ❌ 入口失效 / ⚠️ 未验证。标 ❌/⚠️ 的平台首次发布前用 `references/probe.md` 的 `snapshotText` 流程重新核对选择器。

---

## 端到端使用示例

### 视频：从文案到多平台发布

```bash
SKILL_V=$VAAS/.agents/skills/fd-vaas-video-creator/scripts
SKILL_P=$VAAS/.agents/skills/fd-vaas-publish-videos/scripts

# 1. 文案 -> 成片（MCP 工具面：generate_voice 出声 -> render_video 出片）
#    generate_voice(text=…, slug="demo")                        -> downloads/audio/demo/demo.mp3 + captions.json
#    render_video(type="news-flash", script=…, inputs={…}, slug="demo") -> downloads/video/demo/demo.mp4

# 2. 多平台发布（先预览，确认后再去掉 --dry-run）
node $SKILL_P/publish.mjs --slug demo --title "标题" \
    --platforms douyin,xiaohongshu,bilibili --tags 开源,AI --dry-run

# 3. 单平台临时上传（调试，用 --platforms 指定单个）
node $SKILL_P/publish.mjs --slug demo --title "标题" \
    --platforms douyin --tags 开源,AI --dry-run
```

### 图文：发布一篇文章

```bash
SKILL_D=$VAAS/.agents/skills/fd-vaas-publish-docs/scripts
# 文章放在 downloads/fd-docs/<slug>/ 下
node $SKILL_D/publish.mjs --slug <slug> --platforms zhihu,xiaohongshu --dry-run
# 确认选择器无误、用户同意后，去掉 --dry-run 真正发布
```

### 登录

视频与图文发布都走 cookie 登录，统一用 `/fd-vaas-login` 扫码管理：

```bash
python3 $VAAS/.agents/skills/fd-vaas-login/scripts/login-manager.py
# 浏览器打开 http://localhost:8766 -> 选平台 -> 扫码/登录
# cookie 落盘到 upstream/cookies/<platform>_uploader/account.json（快手用 kuaishou_creator.json）
# 视频与图文共享同一份 cookie；过期就重扫
```

- bilibili 是 profile 模式（非扫码 cookie），youtube 走 Google 账号登录，其余 4 个视频平台走二维码。
- 图文自有逻辑平台：3 个走共享视频 cookie（小红书/抖音/快手 via `note_adapter`），8 个由 `docs_login.py` + patchright 开窗检测登录态、登录后自动关窗。

**元数据约定**：视频 = `title + desc + tags`；图文 = `title + content + tags`。传 `--schedule "YYYY-MM-DD HH:MM"` 切到定时发布（不传 = 立即）。仅部分平台支持 `--schedule`。

---

## 生成后端配置（volcengine / ciyuan 双档）

`fd-vaas-video-creator` 内置的生成器（TTS / 图像 / 视频）通过根目录 `scripts/litellm-bridge.py` 统一入口。生成后端是**两条自有路径**（litellm 已退役——詞元本身就是网关，不再需要第三方桥接库）：`volcengine`（火山方舟直连，默认）与 `ciyuan`（萬星·词元车道）。模型配置全部在 `.env` 里管理，改 Provider 不需要改代码。**已没有独立的 `voice/image/video-generator` 技能**--它们已合并进 `fd-vaas-video-creator/scripts/generators/`。

### 支持的 Provider（仅两档）

| 模态 | volcengine（Ark 直连） | ciyuan（萬星·词元车道） |
|------|------------------------|--------------------------|
| **TTS** | ✅ 带逐字时间戳 | ✅ `POST /v1/audio/speech`（无字幕） |
| **图像** | ✅ 参考图/联网搜索/批量 | ✅ `POST /v1/images/generations`（b64_json） |
| **视频** | ✅ 异步轮询/参考媒体 | ✅ 异步任务协议（创建→轮询→下载） |

### `.env` 配置示例

```env
# ─── 语音合成 ───
TTS_PROVIDER=volcengine        # volcengine | ciyuan
TTS_MODEL=seed-tts-2.0         # volcengine 档
TTS_VOICE=zh_female_gaolengyujie_uranus_bigtts

# ─── 图像生成 ───
IMAGE_PROVIDER=volcengine      # volcengine | ciyuan
IMAGE_MODEL=doubao-seedream-5.0-lite

# ─── 视频生成 ───
VIDEO_PROVIDER=volcengine      # volcengine | ciyuan
VIDEO_MODEL=doubao-seedance-2.0

# ─── ciyuan 档（萬星·词元，router.finddatatech.cloud）──
# 词元密钥按「分组」划能力：语音一把（组3）、图像+视频一把（组9），需两把 key。
# 托管模式经 OpenBAO 按 kind 注入；本地模式直接配：
#CIYUAN_API_KEY=sk-...          # 按 kind 分别注入不同分组的 key（语音用 VAAS 专用账号的语音分组 key）
#CIYUAN_BASE_URL=https://router.finddatatech.cloud
# 实测可用模型（2026-11-06，见下「词元车道实测白名单」）
#TTS_PROVIDER=ciyuan            # 语音切词元档
#TTS_MODEL=tencent-tts          # 腾讯云语音（audio 车道按 protocol 路由，模型名任意）
#TTS_VOICE=101001               # 腾讯音色 id；qwen3 档用 Cherry
#IMAGE_MODEL=gemini-3-pro-image
#VIDEO_MODEL=doubao-seedance-2-0-fast-260128
```

### 词元车道实测白名单（2026-11-06 更新）

`/v1/models` 列出的是「可识别」不是「可服务」——换模型前先实调。实测（VAAS 专用账号）：

- **TTS（2026-11-06）**：`tencent-tts` + voice `101001` ✅（腾讯云语音，audio 车道按 protocol 路由、
  **模型名任意且不进 `/v1/models` 目录**；⚠️ 单次请求长度墙 ~170 字——165 通 / 170 挂，超限 502 且触发
  上游熔断摘除约 5 分钟；VAAS 出口层已按 ≤150 字分段合成 + 段级实测时长对齐 captions）。
  `qwen3-tts-flash` + voice `Cherry` ✅（2026-10-16）；`tts-1` 502、`gpt-4o-mini-audio-preview`/`speech-1.6` 503。
- **图像**：`gemini-3-pro-image` ✅（合规 b64_json）。⚠️ `gpt-image-*` 返回 HTTP 200 但 body 是 HTML（上游缺陷，客户端会显式报错拒绝）；`doubao-seedream-*`/`flux-*`/`imagen-4` 400。
- **视频**：`doubao-seedance-2-0-fast-260128` ✅。⚠️ `doubao-seedance-1-0-pro`/`seedance-2-5` 503、`veo3.1`/`sora-2`/`kling-*` 404（目录挂名不可路由）。
- **ASR**：词元侧上游账号未配置（503），暂不可用；端点协议已就绪，词元配好后即用。

### 自动路由

- **`*_PROVIDER` 只接受 `volcengine` 与 `ciyuan`**；写其他值会被显式拒绝（不再静默兜底第三方）。
- **volcengine 直连** -> 保留全部高级功能（TTS 逐字时间戳、图像参考图/联网搜索、视频异步任务/参考媒体）。
- **ciyuan 车道** -> 钱与用量进自家账本（词元按分组计价）；错误含车道标识，如实上抛不换模型兜底。

### 安装依赖

```bash
pip install -r scripts/requirements.txt   # 只剩 python-dotenv，三车道全走 stdlib
# 或：cd scripts && pip install -e .
```

> **字幕口径（2026-11-06 起）**：volcengine 直连带官方逐字时间戳（`captions_source: official`）；词元 ciyuan 档由 TTS 出口层**合成字幕兜底**（>170 字自动分段、段级实测时长对齐，`captions_source: synthetic`）——两条腿都保证 `captions.json` 落盘，管线零感知。来源随 task.json 审计。（图像/视频可独立切 ciyuan——三档各自独立配置。）

---

## 配置与代理说明

- **`fd-vaas-*` 配置**：从项目根 `.env` 读取（见 `.env.example`）。两套命名空间共存：
  - **视频**：`PLATFORMS`、`TAGS`、`<PLATFORM>_TAGS`、`BILIBILI_TID`、`TENCENT_SHORT_TITLE`、`YOUTUBE_VISIBILITY`、`SCHEDULE`、`HEADLESS`。
  - **图文**：`PLATFORMS_DOCS`、`DOC_TAGS`、`<PLATFORM>_DOC_TAGS`、`DOC_SCHEDULE`、`DOC_HEADLESS`（`_DOC_TAGS` 后缀避免和视频 skill 的 `<PLATFORM>_TAGS` 冲突）。
- **单任务覆盖**：视频放 `downloads/fd-videos/<slug>/.publish.env`，图文放 `downloads/fd-docs/<slug>/.publish.env`。优先级：`--flag CLI > <task>/.publish.env > <VAAS>/.env > 内置默认`。
- **登录态**：视频与图文都走 cookie 文件（`upstream/cookies/<platform>_uploader/account.json`），由 `/fd-vaas-login` 统一扫码。图文自有平台用 `--runtime patchright` 时走独立持久 profile（`VAAS/.profiles/<platform>/`）。同一平台必须串行；不同平台可并发。
- **发布后清理**：ego-browser 驱动的图文自有平台发布完成后，关闭 ego 任务窗口，别留给用户自己关；抖音手动发布需等用户确认「发布完成」再跑 `completeTaskSpace` 兜底清理。
- **代理（通用）**：如果网络命令连不上主机，走本地代理：`export http_proxy=http://127.0.0.1:7892`（备用 `7890`）。通用场景**不要设 `https_proxy`**。
- **代理 + patchright**：patchright 的 chromium **不**读系统代理。Playwright/patchright 浏览器*安装本身*需要显式设 `https_proxy` 才能连 `cdn.playwright.dev`（国内可加 `PLAYWRIGHT_DOWNLOAD_HOST` 镜像）。
- 某些主机（`officecli.ai`、`raw.githubusercontent.com`）走代理会 TLS 失败--用 `env -u http_proxy -u https_proxy <cmd>` 绕过。

---

## 坑与排错

> **第一排查手段：** `node scripts/doctor.mjs` —— 逐项检查 Node/ffmpeg/密钥/remotion 依赖/技能链接，给出修复命令。

- **分发栈 = vendor 上游 + 薄适配层**：`social-auto-upload` 上游 vendored 在 `fd-vaas-publish-videos/scripts/upstream/`（不是根目录独立目录，别再去找根目录的 `social-auto-upload/`）。同步上游更新用 `.agents/skills/fd-vaas-publish-videos/scripts/sync-upstream.sh`。改平台选择器状态要回写 `_shared/publish/platform-registry.json`（用 `probe.py`），别手改文档。
- **cookie 过期要重扫**：发布报登录失败多半是 cookie 过期，用 `/fd-vaas-login` 重扫即可，不用手改 cookie 文件。
- **patchright 全平台一致**：视频发布不再按 OS 派发，macOS 也要装 patchright。ego-browser 只剩录屏 + 图文自有平台两条用途。
- **独立的 `voice/image/video-generator` 技能已不存在**--生成器合并进了 `fd-vaas-video-creator/scripts/generators/`。后端切换（volcengine|ciyuan）仍由根目录 `scripts/litellm-bridge.py` 提供。
- **PPTX 幻灯片不能直接当视频上传。** `cap`（屏幕录制）、`fd-vaas-video-creator`、或 `ppt-master` 的导出/渲染步骤，是把幻灯片变成可发布视频的桥。
- **字幕时间以出口层口径为准**--volcengine 直连带官方逐字戳（可能对 Latin token 给假 `endMs`），ciyuan 档按段实测对齐合成；两者都落 `captions.json` 且 `captions_source` 可审计。`fix-tts-timings` 已随 Remotion 管线退役（2026-11-09）。
- **平台验证状态见矩阵，别凭记忆**：bilibili 未实机验证、xueqiu/tonghuashun 入口已失效。标 ❌/⚠️ 的平台首次发布前用 `references/probe.md` 的 `snapshotText` 流程核对选择器再驱动。
- **发布前必须让用户确认**（尤其图文，发出去撤不回来）。

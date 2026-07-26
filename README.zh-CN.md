# VAAS - 可变资源创作与分发

> **🌐 语言：** [English](README.md) · 简体中文（本文件）

> 接收一个内容需求，生成**可变类型的资源**（幻灯片、文档、屏幕录制视频、图片，或 Remotion 渲染的口播视频），然后**自动发布到不同的社交媒体账号**——理想情况下为每个平台产出*不同*的变体。

VAAS 是架在两半之上的一个**编排层**，自身没有应用代码：

1. **创作技能（Creation skills）**——把需求变成一个素材文件（`.pptx`、`.docx`、`.mp4`、图片……）。
2. **分发引擎（Distribution engine）**——`social-auto-upload/`，一个上游开源项目，通过浏览器自动化把素材上传到各社交平台。

当有人说「做一个资源并发出去」时，预期的流程是：

```
创作技能产出一个文件  ->  `sau` CLI 把它上传到一个或多个账号
```

一条已接好的**主线**通过 `fd-vaas-*` 技能把这个流程端到端串起来（无需手写胶水代码）：

```
需求  ->  /fd-vaas-brainstorm-koubo  ->  /fd-vaas-video-creator  ->  /fd-vaas-publish  ->  社交平台
```

---

## 目录

- [工作原理](#工作原理)
- [VAAS 主线](#vaas-主线)
- [仓库结构](#仓库结构)
- [前置条件](#前置条件)
- [安装与部署](#安装与部署)
  - [1. 分发引擎（`sau`）](#1-分发引擎sau)
  - [2. 创作工具](#2-创作工具)
  - [3. Remotion 视频项目](#3-remotion-视频项目)
  - [4. Claude Code 技能](#4-claude-code-技能)
- [技能一览](#技能一览)
- [平台支持矩阵](#平台支持矩阵)
- [端到端使用示例](#端到端使用示例)
- [配置与代理说明](#配置与代理说明)
- [坑与排错](#坑与排错)

---

## 工作原理

```
 ┌─────────────────────────── 创作（CREATION）──────────────────────────┐   ┌──── 分发（DISTRIBUTION）────┐

  需求 ──► ppt-master ──► .pptx          ┐
        ├─► officecli  ──► .docx/.xlsx    ├─► 素材文件 ──► sau ──► 社交平台
        ├─► cap        ──► .mp4/.gif      │                （抖音、快手、小红书、
        ├─► remotion   ──► .mp4           │                 B站、视频号、YouTube）
        ├─► seedream   ──► 图片           │
        ├─► seedance   ──► 视频           │
        └─► fd-vaas-video-creator ──► .mp4+.srt ┘
```

- **创作技能**产出具体的文件。每个技能的 `SKILL.md` 是权威契约——驱动工具前先读它。
- **分发**只消费文件 + 元数据（`title` / `desc` / `note` / `tags`）。两半之间没有共享胶水代码，*除了*下面的 `fd-vaas-*` 主线——创作技能产出的素材路径就是你传给 `sau <platform> upload-video --file <path>` 的那个。
- 一个 `account_name` 只是一个用户自取的标签，映射到一个持久化的 cookie 文件。每个平台支持多账号、可并发——这是「不同的社交媒体账号」这一目标的基本单位。

---

## VAAS 主线

`fd-vaas-*` 技能是接好的「需求到发布」流水线——当目标是「做一支视频并发布」时推荐走这条路：

1. **`/fd-vaas-brainstorm-koubo`** *（可选）*——给定赛道/主题，返回选题矩阵（热点/痛点/争议/干货/人设）、推荐脚本框架（黄金三秒 / SCQA / PREP / 故事钩子 / 清单体）、差异化角度，以及可选的完整大纲。
2. **`/fd-vaas-video-creator`**——把文案变成成片口播视频。流程：`new-task -> TTS（seed-tts-2.0，返回音频 + 官方逐字时间戳）-> fix-tts-timings（修正 Latin token 的假 endMs）-> preflight -> Remotion 渲染 -> <slug>.mp4（+ .srt）`。所有产物落在 `downloads/fd-videos/<slug>/`，由 `task.json` 管理。画面层 = 已有素材 / seedance 视频 / seedream 图片 / ppt 母带。**必须跑 `fix-tts-timings`，否则字幕会错位。**
3. **`/fd-vaas-publish`**——一支视频 -> 多平台。从 `.env` 读取各平台偏好（账号、标签、`BILIBILI_TID`、`TENCENT_SHORT_TITLE`、`YOUTUBE_VISIBILITY`、定时），为每个平台组装正确的 `sau upload-video`，shell out 调用，并把结果回写到 `task.json` 的 `distribution[]`。**上传/cookie/浏览器的事全部委托给 `sau`，绝不重造轮子。** `--dry-run` 可预览命令。

```bash
SKILL_V=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-video-creator/scripts
SKILL_P=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-publish/scripts

# 2. 文案 -> 口播视频
node $SKILL_V/new-task.mjs    --slug <slug> --script /path/to/script.txt
node $SKILL_V/task-render.mjs --slug <slug>            # -> downloads/fd-videos/<slug>/<slug>.mp4

# 3. 多平台发布
node $SKILL_P/publish.mjs --slug <slug> --title "…" --platforms douyin,xiaohongshu,bilibili --dry-run
```

---

## 仓库结构

```
VAAS/
├── .claude/skills/              # 项目级 Claude Code 技能（可直接使用）
│   ├── cap/                     #   屏幕录制 / 截图                   （外部 CLI）
│   ├── officecli/               #   .docx/.xlsx/.pptx 创建+编辑       （外部 CLI）
│   ├── ppt-master -> ../../.agents/skills/ppt-master   # 软链接
│   ├── byted-ark-tts-skill/     #   豆包 seed-tts-2.0 语音合成       （火山方舟）
│   ├── byted-ark-seedance-skill/#   豆包 Seedance AI 视频生成        （火山方舟）
│   ├── byted-ark-seedream-skill/#   豆包 Seedream AI 图像生成        （火山方舟）
│   ├── fd-vaas-brainstorm-koubo/#   口播选题 + 脚本大纲策划
│   ├── fd-vaas-video-creator/   #   文案 -> 口播视频（.mp4 + .srt）
│   ├── fd-vaas-publish/         #   一支视频 -> 多平台发布（编排 sau）
│   └── remotion-*/              #   7 个 Remotion 创作技能（best-practices、captions、
│                                #   create、interactivity、markup、render、saas）
├── .agents/skills/ppt-master/   # ppt-master 的真相源（大 SKILL.md + workflows/、
│                                #   templates/、scripts/、references/）
├── remotion-app/                # Remotion 视频项目（React -> 视频）    [已 gitignore]
├── downloads/fd-videos/<slug>/  # fd-vaas-video-creator 每支视频的产出  [已 gitignore]
└── social-auto-upload/          # dreammis/social-auto-upload 的 vendored 克隆（嵌套 git 仓库）
    ├── sau_cli.py               #   ★ `sau` CLI 的真相源
    ├── uploader/<platform>_uploader/
    ├── cookies/                 #   持久化的账号 cookie 文件在这里
    ├── conf.py / conf.example.py
    ├── tests/                   #   标准库 unittest，mock 掉浏览器层
    └── sau_backend.py + sau_frontend/   # 遗留 Flask+Vue web 应用（非主线）
```

> **VAAS 根目录是一个 git 仓库**（远程：`github.com/FindDataOfficial/VAAS`）。`social-auto-upload/` 仍然是一个带独立 git 历史的 vendored 第三方依赖——把它当作嵌套仓库，不是 submodule。

---

## 前置条件

- **Python 3.10–3.12**（`<3.13`）和 [`uv`](https://docs.astral.sh/uv/)——用于分发引擎。
- **Node.js 18+**（带 Git）——用于 Remotion 项目和 `fd-vaas-*` 技能。
- **ffmpeg/ffprobe**——用于 `fd-vaas-video-creator` 的时长/帧数校验。
- **Claude Code**——`.claude/skills/` 下的技能以 `/cap`、`/officecli`、`/ppt-master`、`/fd-vaas-video-creator` 等方式调用。
- **macOS / Linux** 推荐（Windows 通过上游的 `start-win.bat` 部分支持）。
- 如果你所在网络需要代理，本地 HTTP 代理在 `127.0.0.1:7892`（备用 `7890`）——见[代理说明](#配置与代理说明)。
- 在 `.env` 里配置火山方舟 Ark API key，供 `byted-ark-*` 媒体技能（TTS / Seedance / Seedream）使用。

---

## 安装与部署

### 1. 分发引擎（`sau`）

```bash
cd social-auto-upload

# 一次性环境 + 安装（注册 `sau` 命令）
uv venv && source .venv/bin/activate
uv pip install -e .

# 安装隐身浏览器（patchright = Playwright 的隐身 fork）。
# 国内镜像；在海外请去掉环境变量。
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" patchright install chromium
```

验证：

```bash
sau --help                       # 或：python sau_cli.py --help
sau douyin --help
```

> 如果 `sau` 不在 PATH 上，可直接 `python sau_cli.py <platform> <action> …`——无需安装。

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

`ppt-master` 是仓库内的工作流（不是外部二进制）。如果某条路线用到它的生图步骤，按 `.agents/skills/ppt-master/requirements.txt` 装它的 Python 依赖。

### 3. Remotion 视频项目

```bash
cd remotion-app
npm install
npm run dev        # Remotion Studio 预览  ->  http://localhost:3001
                   #（3000 端口已被占用；Studio 回落到 3001）
npx remotion render      # 把视频渲染成文件
```

> `fd-vaas-video-creator` 需要 `@remotion/captions` 和一个 `VoiceoverVideo` composition——一次性设置见 `.claude/skills/fd-vaas-video-creator/references/setup.md`。

### 4. Claude Code 技能

`.claude/skills/` 下的技能**已签入本仓库**，打开 VAAS 目录时 Claude Code 会自动发现。无需安装，直接调用：

- `/cap`——录屏、截图、导出/上传视频。
- `/officecli`——创建、分析、校对、修改 Office 文档。
- `/ppt-master`——把源文档（PDF/DOCX/URL/Markdown）变成 SVG 幻灯片并导出 `.pptx`。
- `/byted-ark-tts-skill`——文本 -> 自然语音（seed-tts-2.0），带逐字时间戳。
- `/byted-ark-seedream-skill`——文本 -> AI 图片（豆包 Seedream）。
- `/byted-ark-seedance-skill`——文本/图片 -> AI 视频（豆包 Seedance）。
- `/fd-vaas-brainstorm-koubo`——口播选题矩阵 + 脚本大纲策划。
- `/fd-vaas-video-creator`——文案 -> 口播视频（`.mp4` + `.srt`）。
- `/fd-vaas-publish`——一支视频 -> 多平台发布（编排 `sau`）。
- `/remotion-*`——创作 Remotion 视频（create、markup、captions、render 等）。

> **约定：** 新建 Claude Code 技能放在 `VAAS/.claude/skills/`（项目级），不要放全局 `~/.claude/skills/`。

---

## 技能一览

| 技能 | 产出 | 类型 | 入口 |
|---|---|---|---|
| `ppt-master` | SVG 幻灯片 -> 导出 `.pptx`（多角色流水线：策略 -> 执行 -> QC） | 仓库工作流 | `/ppt-master` · 源码在 `.agents/skills/ppt-master/` |
| `officecli` | `.docx` / `.xlsx` / `.pptx` 创建+编辑（L1 读 -> L2 DOM -> L3 XML） | 外部 CLI | `/officecli` · `~/.local/bin/officecli` |
| `cap` | 屏幕录制 / 截图 -> `.mp4`/`.gif` + 可分享上传链接 | 外部 CLI | `/cap` · `~/.local/bin/cap` |
| `byted-ark-tts` | 文本 -> 语音音频 + 逐字时间戳（seed-tts-2.0） | 仓库技能（火山方舟） | `/byted-ark-tts-skill` |
| `byted-ark-seedance` | 文本/图片 -> AI 视频（豆包 Seedance） | 仓库技能（火山方舟） | `/byted-ark-seedance-skill` |
| `byted-ark-seedream` | 文本 -> AI 图片（豆包 Seedream） | 仓库技能（火山方舟） | `/byted-ark-seedream-skill` |
| `fd-vaas-brainstorm-koubo` | 口播选题矩阵 + 脚本框架 + 差异化角度 + 大纲 | 仓库技能（纯提示词） | `/fd-vaas-brainstorm-koubo` |
| `fd-vaas-video-creator` | 文案 -> 口播视频 `.mp4` + `.srt`（TTS + 逐字字幕 + Remotion） | 仓库技能 | `/fd-vaas-video-creator` |
| `fd-vaas-publish` | 一支视频 -> 多平台帖子（编排 `sau`） | 仓库技能 | `/fd-vaas-publish` |
| `remotion-create` | 脚手架新建 Remotion 项目/composition | 仓库技能 | `/remotion-create` |
| `remotion-markup` | Remotion 的 React markup 最佳实践 | 仓库技能 | `/remotion-markup` |
| `remotion-captions` | 字幕处理（JSON `Caption` 类型） | 仓库技能 | `/remotion-captions` |
| `remotion-render` | 渲染视频（`npx remotion render`） | 仓库技能 | `/remotion-render` |
| `remotion-interactivity` | 适配 Studio 视觉模式的动画 | 仓库技能 | `/remotion-interactivity` |
| `remotion-best-practices` | Remotion 最佳实践索引 | 仓库技能 | `/remotion-best-practices` |
| `remotion-saas` | 用 Remotion 构建视频应用（框架/Player/Lambda） | 仓库技能 | `/remotion-saas` |

外部 CLI 自带帮助系统——优先用它，别猜参数：
- `cap guide` / `cap guide --json`——官方 agent 能力清单。
- `officecli help` / `officecli help docx paragraph`——完整元素 schema。

---

## 平台支持矩阵

来自 `sau_cli.py`（`add_parser` 调用）+ 上游 README。浏览器自动化用 **`patchright`**，默认**无头**。

| 平台 | `login` / `check` | `upload-video` | `upload-note`（图文） | 备注 |
|---|---|---|---|---|
| `douyin` | ✅ | ✅ | ✅ | 最完整；`--product-link`、双比例缩略图 |
| `kuaishou` | ✅ | ✅ | ✅ | 浏览器自动化 |
| `xiaohongshu` | ✅ | ✅ | ✅ | `SAU_XHS_CREATOR_BASE_URL` 供海外 / RedNote |
| `bilibili` | ✅ | ✅ | ❌ | 自动下载/更新 `biliup`；需要 `--tid`；登录最好在真终端里做 |
| `tencent`（视频号） | ✅ | ✅ | ❌ | `tencent_uploader` |
| `youtube` | ✅ | ✅ | ❌ | 交互式 Google 登录；浏览器自动化（非 API）；`--playlist`、`--visibility`；youtube.com 被墙时设 `YT_PROXY` |

---

## 端到端使用示例

一个账号 == `social-auto-upload/cookies/<platform>_uploader/` 下的一个账号文件。

```bash
cd social-auto-upload
source .venv/bin/activate

# 1. 登录一次（扫描生成的 QR 图片）
sau douyin login --account my_account

# 2. 验证保存的 cookie 是否仍有效
sau douyin check --account my_account

# 3. 发布一支由创作技能产出的视频
sau douyin upload-video \
    --account my_account \
    --file ../remotion-app/out/my_video.mp4 \
    --title "标题" --desc "描述。" --tags demo,vaas

# 4. ……或一条 图文 / 图片笔记
sau douyin upload-note \
    --account my_account \
    --images 1.png 2.png \
    --title "标题" --note "正文。" --tags demo,vaas

# 5. 定时发布（而非立即）
sau douyin upload-video --account my_account --file … --schedule "2026-07-20 21:30"
```

走接好的 `fd-vaas-*` 流程（无需手写 `sau` 参数），见 [VAAS 主线](#vaas-主线)。

**元数据约定**（所有浏览器平台）：视频 = `title + desc + tags`；图文 = `title + note + tags`。传 `--schedule "YYYY-MM-DD HH:MM"` 切到定时发布策略（不传 = 立即）。B站还需要 `--tid`。

`--debug`、`--headless`、`--headed` 是三个独立维度；默认无头。

---

## 配置与代理说明

- **配置文件：** `social-auto-upload/conf.py`（`conf.example.py` 的拷贝）存放 `BASE_DIR`、`LOCAL_CHROME_PATH`、`LOCAL_CHROME_HEADLESS`、`DEBUG_MODE`、`YT_PROXY`。`XHS_SERVER` 是遗留的 xhs-only 配置。
- **`fd-vaas-*` 配置：** 从项目根 `.env` 读取（见 `.env.example`）——`PLATFORMS`、`<PLATFORM>_ACCOUNT`、`BILIBILI_TID`、`TENCENT_SHORT_TITLE`、`YOUTUBE_VISIBILITY`、`TAGS`、`SCHEDULE`、`HEADLESS`。单条视频的覆盖放在 `downloads/fd-videos/<slug>/.publish.env`。优先级：`--flag CLI > <task>/.publish.env > <VAAS>/.env > 内置默认`。
- **发布策略：** 每个 uploader 暴露 `*_PUBLISH_STRATEGY_IMMEDIATE` / `*_PUBLISH_STRATEGY_SCHEDULED` 常量；`sau_cli.py` 按 `--schedule` 选择。
- **二维码登录**（抖音/快手/小红书）会生成一张本地 PNG——把它打开/展示给用户扫，不要只打印路径。**B站**登录最好由用户在真终端里跑（QR 可能渲染不全；回退到 `qrcode.png`）。
- **代理（通用）：** 如果网络命令连不上主机，走本地代理：`export http_proxy=http://127.0.0.1:7892`（备用 `7890`）。通用场景**不要设 `https_proxy`**。
- **代理 + patchright：** patchright 的 chromium **不**读系统代理。YouTube 在 `conf.py` 里设 `YT_PROXY`。Playwright/patchright 浏览器*安装本身*需要显式设 `https_proxy` 才能连 `cdn.playwright.dev`。
- 某些主机（`officecli.ai`、`raw.githubusercontent.com`）走代理会 TLS 失败——用 `env -u http_proxy -u https_proxy <cmd>` 绕过。

---

## 坑与排错

- **VAAS 根目录现在可以跑 `git` 了**——根目录是仓库（`github.com/FindDataOfficial/VAAS`）。`social-auto-upload/` 是一个*嵌套* git 仓库，有自己的历史；把它当第三方依赖，内部细节看它自己的 `CLAUDE.md` 和 `docs/`，除非任务专门针对那个项目，否则别改它。
- **vendored 的 `social-auto-upload/CLAUDE.md` 部分过时**——它引用了一个不存在的 `cli_main.py` 和一个未实现的 `sau skill install` 命令。`sau_cli.py` 才是真相源。拿不准就跑 `sau <platform> --help`。
- **PPTX 幻灯片不能直接当视频上传。** `cap`（屏幕录制）、`fd-vaas-video-creator`、或 `ppt-master` 的导出/渲染步骤，是把幻灯片变成可发布视频的桥。
- **`fd-vaas-video-creator` 跳过 `fix-tts-timings` 会让字幕错位**——seed-tts-2.0 对 Latin token（英文名、URL）返回假的 `endMs`。流水线会自动跑这步；手工路径必须显式跑。
- **测试**是标准库 `unittest`（可用 `unittest` 或 `pytest` 跑），在 `social-auto-upload/tests/`。它们 mock 掉浏览器层——无需网络/cookie：
  ```bash
  cd social-auto-upload
  python -m unittest discover -s tests
  python -m unittest tests.test_sau_bilibili_cli
  ```
- **遗留 web 应用**（`sau_backend.py` Flask 在 :5409 + `sau_frontend/` Vue/Vite 在 :5173）上游保留但**非主线**——不保证能跑或与 CLI 同步。`requirements.txt` 是历史 web 依赖文件；`pyproject.toml` 是主线安装入口。

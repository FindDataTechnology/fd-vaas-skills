# VAAS - Variable Asset Authoring & Syndication

> **🌐 Languages:** English (this file) · [简体中文](README.zh-CN.md)

> Take a content demand, generate a **variable-type resource** (deck, document, screen-recording video, images, or a Remotion-rendered voiceover video), then **publish it automatically to different social-media accounts** - ideally producing a *different* variant per platform/account.

VAAS is an **orchestration layer** over two halves, with no application code of its own:

1. **Creation skills** - turn a demand into an asset file (`.pptx`, `.docx`, `.mp4`, images, …).
2. **Distribution engine** - `social-auto-upload/`, a vendored upstream project that uploads assets to social platforms via browser automation.

The intended flow when someone says *"make a resource and post it"*:

```
creation skill produces a file  ->  `sau` CLI uploads it to one or more accounts
```

A wired **mainline** chains this end-to-end via the `fd-vaas-*` skills (no glue code to write):

```
demand  ->  /fd-vaas-brainstorm-koubo  ->  /fd-vaas-video-creator  ->  /fd-vaas-publish  ->  social platforms
```

---

## Table of contents

- [How it works](#how-it-works)
- [VAAS mainline](#vaas-mainline)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Setup & deploy](#setup--deploy)
  - [1. Distribution engine (`sau`)](#1-distribution-engine-sau)
  - [2. Creation tools](#2-creation-tools)
  - [3. Remotion video app](#3-remotion-video-app)
  - [4. Claude Code skills](#4-claude-code-skills)
- [Skills reference](#skills-reference)
- [Platform support matrix](#platform-support-matrix)
- [End-to-end usage example](#end-to-end-usage-example)
- [Configuration & proxy notes](#configuration--proxy-notes)
- [Gotchas & troubleshooting](#gotchas--troubleshooting)

---

## How it works

```
 ┌─────────────────────────── CREATION ───────────────────────────┐   ┌──── DISTRIBUTION ────┐

  demand ──► ppt-master ──► .pptx          ┐
          ├─► officecli  ──► .docx/.xlsx    ├─► asset file ──► sau ──► social platform(s)
          ├─► cap        ──► .mp4/.gif      │                   (douyin, kuaishou, xhs,
          ├─► remotion   ──► .mp4           │                    bilibili, 视频号, youtube)
          ├─► seedream   ──► image          │
          ├─► seedance   ──► video          │
          └─► fd-vaas-video-creator ──► .mp4+.srt ┘
```

- **Creation skills** emit concrete files. Each skill's `SKILL.md` is the authoritative contract - read it before driving the tool.
- **Distribution** only consumes files + metadata (`title` / `desc` / `note` / `tags`). There is no shared glue code between the two halves *except* the `fd-vaas-*` mainline below - the asset path a creation skill produces is what you pass to `sau <platform> upload-video --file <path>`.
- An `account_name` is just a user-chosen label mapping to one persisted cookie file. Multiple accounts per platform are supported and run concurrently - this is the unit of "different social-media account".

---

## VAAS mainline

The `fd-vaas-*` skills are the wired demand-to-post pipeline - the recommended path when the goal is "make a video and post it":

1. **`/fd-vaas-brainstorm-koubo`** *(optional)* - given a 赛道/主题, returns a 选题矩阵 (热点/痛点/争议/干货/人设), recommended 脚本框架 (黄金三秒 / SCQA / PREP / 故事钩子 / 清单体), 差异化角度, and an optional full 大纲.
2. **`/fd-vaas-video-creator`** - turns a 文案 into a finished 口播视频. Pipeline: `new-task -> TTS (seed-tts-2.0, audio + official word-level timestamps) -> fix-tts-timings (corrects fake Latin-token endMs) -> preflight -> Remotion render -> <slug>.mp4 (+ .srt)`. All artifacts land in `downloads/fd-videos/<slug>/`, managed by `task.json`. Visual layer = existing assets / a seedance video / a seedream image / a ppt master tape. **Run `fix-tts-timings` or subtitles desync.**
3. **`/fd-vaas-publish`** - one video -> many platforms. Reads per-platform preferences (accounts, tags, `BILIBILI_TID`, `TENCENT_SHORT_TITLE`, `YOUTUBE_VISIBILITY`, schedule) from `.env`, assembles the correct `sau upload-video` per platform, shells out, and writes results back to `task.json`'s `distribution[]`. **Delegates all upload / cookie / browser work to `sau` - never re-implements it.** `--dry-run` previews the commands.

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

## Repository layout

```
VAAS/
├── .claude/skills/              # project-scoped Claude Code skills (usable directly)
│   ├── cap/                     #   screen recording / screenshots           (external CLI)
│   ├── officecli/               #   .docx/.xlsx/.pptx create+edit            (external CLI)
│   ├── ppt-master -> ../../.agents/skills/ppt-master   # symlink
│   ├── byted-ark-tts-skill/     #   豆包 seed-tts-2.0 语音合成               (VolcEngine)
│   ├── byted-ark-seedance-skill/#   豆包 Seedance AI 视频生成                (VolcEngine)
│   ├── byted-ark-seedream-skill/#   豆包 Seedream AI 图像生成                (VolcEngine)
│   ├── fd-vaas-brainstorm-koubo/#   口播选题 + 脚本大纲策划
│   ├── fd-vaas-video-creator/   #   文案 -> 口播视频 (.mp4 + .srt)
│   ├── fd-vaas-publish/         #   一支视频 -> 多平台发布 (编排 sau)
│   └── remotion-*/              #   7 Remotion authoring skills (best-practices, captions,
│                                #   create, interactivity, markup, render, saas)
├── .agents/skills/ppt-master/   # source of truth for ppt-master (large SKILL.md + workflows/,
│                                #   templates/, scripts/, references/)
├── remotion-app/                # a Remotion video project (React -> video)  [gitignored]
├── downloads/fd-videos/<slug>/  # fd-vaas-video-creator output per video     [gitignored]
└── social-auto-upload/          # vendored clone of dreammis/social-auto-upload (nested git repo)
    ├── sau_cli.py               #   ★ THE source of truth for the `sau` CLI
    ├── uploader/<platform>_uploader/
    ├── cookies/                 #   persisted account cookie files live here
    ├── conf.py / conf.example.py
    ├── tests/                   #   stdlib unittest, mocks the browser layer
    └── sau_backend.py + sau_frontend/   # legacy Flask+Vue web app (not mainline)
```

> **The VAAS root is a git repository** (remote: `github.com/FindDataOfficial/VAAS`). `social-auto-upload/` remains a vendored third-party dependency with its own git history - treat it as a nested repo, not a submodule.

---

## Prerequisites

- **Python 3.10–3.12** (`<3.13`) and [`uv`](https://docs.astral.sh/uv/) - for the distribution engine.
- **Node.js 18+** (with Git) - for the Remotion app and the `fd-vaas-*` skills.
- **ffmpeg/ffprobe** - for `fd-vaas-video-creator` timing/duration checks.
- **Claude Code** - the skills in `.claude/skills/` are invoked as `/cap`, `/officecli`, `/ppt-master`, `/fd-vaas-video-creator`, etc.
- **macOS / Linux** recommended (Windows is partially supported by upstream via `start-win.bat`).
- A local HTTP proxy at `127.0.0.1:7892` (fallback `7890`) **if** you are in a network that needs one - see [proxy notes](#configuration--proxy-notes).
- A VolcEngine Ark API key in `.env` for the `byted-ark-*` media skills (TTS / Seedance / Seedream).

---

## Setup & deploy

### 1. Distribution engine (`sau`)

```bash
cd social-auto-upload

# one-time environment + install (registers the `sau` command)
uv venv && source .venv/bin/activate
uv pip install -e .

# install the stealth browser (patchright = a stealth fork of Playwright).
# CN mirror; drop the env var if you are outside China.
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" patchright install chromium
```

Verify:

```bash
sau --help                       # or: python sau_cli.py --help
sau douyin --help
```

> If `sau` is not on PATH, run `python sau_cli.py <platform> <action> …` directly - no install needed.

### 2. Creation tools

`cap` and `officecli` are external single-binary CLIs (no Office installation required). Install once, globally:

```bash
# cap - agent-friendly screen recording / screenshots / upload (cap.so)
curl -fsSL https://cap.so/install-cli.sh | sh
cap --version                    # binary -> ~/.local/bin/cap

# officecli - create/edit/analyze .docx .xlsx .pptx
curl -fsSL https://d.officecli.ai/install.sh | bash      # macOS / Linux
# Windows (PowerShell):  irm https://d.officecli.ai/install.ps1 | iex
officecli --version
```

`ppt-master` is a repo-specific workflow (not an external binary). If a route uses its image-generation step, install its Python deps from `.agents/skills/ppt-master/requirements.txt`.

### 3. Remotion video app

```bash
cd remotion-app
npm install
npm run dev        # Remotion Studio preview  ->  http://localhost:3001
                   # (port 3000 is pre-occupied; Studio falls back to 3001)
npx remotion render      # render a video to a file
```

> `fd-vaas-video-creator` requires `@remotion/captions` and a `VoiceoverVideo` composition - see `.claude/skills/fd-vaas-video-creator/references/setup.md` for the one-time setup.

### 4. Claude Code skills

The skills under `.claude/skills/` are **already checked into this repo** and are auto-discovered by Claude Code when you open the VAAS folder. No install step - just invoke them:

- `/cap` - record screen, capture screenshots, export/upload video.
- `/officecli` - create, analyze, proofread, or modify Office documents.
- `/ppt-master` - turn a source document (PDF/DOCX/URL/Markdown) into an SVG deck and export `.pptx`.
- `/byted-ark-tts-skill` - text -> natural speech (seed-tts-2.0) with word-level timestamps.
- `/byted-ark-seedream-skill` - text -> AI image (豆包 Seedream).
- `/byted-ark-seedance-skill` - text/image -> AI video (豆包 Seedance).
- `/fd-vaas-brainstorm-koubo` - 口播选题矩阵 + 脚本大纲策划.
- `/fd-vaas-video-creator` - 文案 -> 口播视频 (`.mp4` + `.srt`).
- `/fd-vaas-publish` - one video -> multi-platform publish (orchestrates `sau`).
- `/remotion-*` - author Remotion videos (create, markup, captions, render, etc.).

> **Convention:** create new Claude Code skills at `VAAS/.claude/skills/` (project scope), not in the global `~/.claude/skills/`.

---

## Skills reference

| Skill | Produces | Type | Entry |
|---|---|---|---|
| `ppt-master` | SVG deck -> exported `.pptx` (multi-role pipeline: strategist -> executor -> QC) | repo workflow | `/ppt-master` · source at `.agents/skills/ppt-master/` |
| `officecli` | `.docx` / `.xlsx` / `.pptx` create+edit (L1 read -> L2 DOM -> L3 XML) | external CLI | `/officecli` · `~/.local/bin/officecli` |
| `cap` | screen recording / screenshots -> `.mp4`/`.gif` + shareable upload link | external CLI | `/cap` · `~/.local/bin/cap` |
| `byted-ark-tts` | text -> speech audio + word-level timestamps (seed-tts-2.0) | repo skill (VolcEngine) | `/byted-ark-tts-skill` |
| `byted-ark-seedance` | text/image -> AI video (豆包 Seedance) | repo skill (VolcEngine) | `/byted-ark-seedance-skill` |
| `byted-ark-seedream` | text -> AI image (豆包 Seedream) | repo skill (VolcEngine) | `/byted-ark-seedream-skill` |
| `fd-vaas-brainstorm-koubo` | 口播选题矩阵 + 脚本框架 + 差异化角度 + 大纲 | repo skill (pure prompt) | `/fd-vaas-brainstorm-koubo` |
| `fd-vaas-video-creator` | 文案 -> 口播视频 `.mp4` + `.srt` (TTS + 逐字字幕 + Remotion) | repo skill | `/fd-vaas-video-creator` |
| `fd-vaas-publish` | one video -> multi-platform posts (orchestrates `sau`) | repo skill | `/fd-vaas-publish` |
| `remotion-create` | scaffold a new Remotion project/composition | repo skill | `/remotion-create` |
| `remotion-markup` | React markup best practices for Remotion | repo skill | `/remotion-markup` |
| `remotion-captions` | caption/subtitle handling (JSON `Caption` type) | repo skill | `/remotion-captions` |
| `remotion-render` | rendering videos (`npx remotion render`) | repo skill | `/remotion-render` |
| `remotion-interactivity` | Studio-visual-mode-friendly animations | repo skill | `/remotion-interactivity` |
| `remotion-best-practices` | index of Remotion best practices | repo skill | `/remotion-best-practices` |
| `remotion-saas` | building video apps with Remotion (framework/Player/Lambda) | repo skill | `/remotion-saas` |

External CLIs come with a built-in help system - prefer it over guessing:
- `cap guide` / `cap guide --json` - official agent capability manifest.
- `officecli help` / `officecli help docx paragraph` - full element schemas.

---

## Platform support matrix

From `sau_cli.py` (`add_parser` calls) + upstream README. Browser automation uses **`patchright`**, default **headless**.

| Platform | `login` / `check` | `upload-video` | `upload-note` (图文) | Notes |
|---|---|---|---|---|
| `douyin` | ✅ | ✅ | ✅ | most complete; `--product-link`, dual-ratio thumbnails |
| `kuaishou` | ✅ | ✅ | ✅ | browser automation |
| `xiaohongshu` | ✅ | ✅ | ✅ | `SAU_XHS_CREATOR_BASE_URL` for overseas / RedNote |
| `bilibili` | ✅ | ✅ | ❌ | auto-downloads/updates `biliup`; `--tid` required; login best done in a real terminal |
| `tencent` (视频号) | ✅ | ✅ | ❌ | `tencent_uploader` |
| `youtube` | ✅ | ✅ | ❌ | interactive Google login; browser automation (not API); `--playlist`, `--visibility`; set `YT_PROXY` where youtube.com is blocked |

---

## End-to-end usage example

A single account == one account file under `social-auto-upload/cookies/<platform>_uploader/`.

```bash
cd social-auto-upload
source .venv/bin/activate

# 1. log in once (scan the QR PNG that gets generated)
sau douyin login --account my_account

# 2. verify the saved cookie is still valid
sau douyin check --account my_account

# 3. post a video produced by a creation skill
sau douyin upload-video \
    --account my_account \
    --file ../remotion-app/out/my_video.mp4 \
    --title "My title" --desc "Description." --tags demo,vaas

# 4. …or a 图文 / image note
sau douyin upload-note \
    --account my_account \
    --images 1.png 2.png \
    --title "My title" --note "Body text." --tags demo,vaas

# 5. timed publish instead of immediate
sau douyin upload-video --account my_account --file … --schedule "2026-07-20 21:30"
```

For the wired `fd-vaas-*` flow (no hand-written `sau` args), see [VAAS mainline](#vaas-mainline).

**Metadata convention** (all browser platforms): video = `title + desc + tags`; note/图文 = `title + note + tags`. Pass `--schedule "YYYY-MM-DD HH:MM"` to switch a platform to its timed-publish strategy (omitted = immediate). Bilibili additionally requires `--tid`.

`--debug`, `--headless`, `--headed` are independent dimensions; default is headless.

---

## Configuration & proxy notes

- **Config file:** `social-auto-upload/conf.py` (a copy of `conf.example.py`) holds `BASE_DIR`, `LOCAL_CHROME_PATH`, `LOCAL_CHROME_HEADLESS`, `DEBUG_MODE`, and `YT_PROXY`. `XHS_SERVER` is legacy xhs-only.
- **`fd-vaas-*` config:** reads from the project-root `.env` (see `.env.example`) - `PLATFORMS`, `<PLATFORM>_ACCOUNT`, `BILIBILI_TID`, `TENCENT_SHORT_TITLE`, `YOUTUBE_VISIBILITY`, `TAGS`, `SCHEDULE`, `HEADLESS`. Per-task overrides go in `downloads/fd-videos/<slug>/.publish.env`. Priority: `--flag CLI > <task>/.publish.env > <VAAS>/.env > built-in default`.
- **Publish strategies:** each uploader exposes `*_PUBLISH_STRATEGY_IMMEDIATE` / `*_PUBLISH_STRATEGY_SCHEDULED` constants; `sau_cli.py` selects based on `--schedule`.
- **QR-code logins** (douyin/kuaishou/xiaohongshu) generate a local PNG - open/display that image for the user to scan; don't just print the path. **Bilibili** login should be run by the user in a real terminal (QR may render incomplete; fall back to `qrcode.png`).
- **Proxy (general):** if a network command can't reach a host, route through the local proxy: `export http_proxy=http://127.0.0.1:7892` (fallback `7890`). **Do NOT set `https_proxy`** for general use.
- **Proxy + patchright:** patchright's chromium does **not** read the system proxy. For YouTube set `YT_PROXY` in `conf.py`. The Playwright/patchright browser *install itself* needs `https_proxy` set explicitly to reach `cdn.playwright.dev`.
- Some hosts (`officecli.ai`, `raw.githubusercontent.com`) fail TLS through the proxy - bypass with `env -u http_proxy -u https_proxy <cmd>`.

---

## Gotchas & troubleshooting

- **`git` at the VAAS root works now** - the root is a repo (`github.com/FindDataOfficial/VAAS`). `social-auto-upload/` is a *nested* git repo with its own history; treat it as a third-party dependency, prefer its own `CLAUDE.md` and `docs/` for internals, and avoid editing it unless the task is specifically about that project.
- **The vendored `social-auto-upload/CLAUDE.md` is partly stale** - it references a non-existent `cli_main.py` and an unimplemented `sau skill install` command. `sau_cli.py` is the real source of truth. When in doubt, run `sau <platform> --help`.
- **PPTX decks are not directly uploadable as video.** `cap` (screen recording), `fd-vaas-video-creator`, or `ppt-master`'s export/render step is the bridge when a deck must become a publishable video.
- **`fd-vaas-video-creator` subtitles desync if you skip `fix-tts-timings`** - seed-tts-2.0 returns fake `endMs` for Latin tokens (English names, URLs). The pipeline runs it for you; the manual path must run it explicitly.
- **Tests** are stdlib `unittest` (runnable via `unittest` or `pytest`) and live in `social-auto-upload/tests/`. They mock the browser layer - no network/cookies needed:
  ```bash
  cd social-auto-upload
  python -m unittest discover -s tests
  python -m unittest tests.test_sau_bilibili_cli
  ```
- **Legacy web app** (`sau_backend.py` Flask on :5409 + `sau_frontend/` Vue/Vite on :5173) is retained by upstream but **not mainline** - not guaranteed to run or stay in sync with the CLI. `requirements.txt` is the historical web-deps file; `pyproject.toml` is the mainline install entry.

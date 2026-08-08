# VAAS - Variable Asset Authoring & Syndication

> **🌐 Language:** [简体中文](README.md) · English (this file)

> 🚀 **One-line install:** `curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-vaas-skills/main/install.sh | bash`

## ⚡ Your first video in 5 minutes

```bash
export VAAS=<path to the cloned VAAS repo, e.g. ~/fd-vaas-skills>   # all commands below use $VAAS

# 1. Install (skip if you already ran the one-line install)
cd $VAAS && ./install.sh

# 2. Fill in the key: edit .env, set vol_agent_api_key (Volcengine Ark, https://console.volcengine.com/ark)
#    Not sure the environment is ready? Run anytime:
node $VAAS/scripts/doctor.mjs

# 3. Write one line of voiceover and render
echo "Hello, this is my first VAAS video." > /tmp/demo-script.txt
node $VAAS/.agents/skills/fd-vaas-video-creator/scripts/new-task.mjs --slug demo --script /tmp/demo-script.txt
node $VAAS/.agents/skills/fd-vaas-video-creator/scripts/task-render.mjs --slug demo

# Output: $VAAS/downloads/fd-videos/demo/demo.mp4 (+ .srt subtitles)
```

> Take a content demand, generate a **variable-type resource** (slide deck, document, screen-recording video, AI image/video, or a Remotion-rendered voiceover video), then **publish it automatically to different social-media accounts** - ideally producing a *different* variant per platform.

VAAS is an **orchestration layer** over two halves, with no application code of its own:

1. **Creation skills** - turn a demand into an asset file (`.pptx`, `.docx`, `.mp4`, image, …), sourced from `.agents/skills/`.
2. **Distribution engine** - two publish skills ship the asset to platforms: `fd-vaas-publish-videos` (video -> 6 video platforms) and `fd-vaas-publish-docs` (article -> 9 article platforms). Each platform's upload logic is built into `scripts/platforms/<platform>.{mjs,py}`: **macOS** uses ego-browser (reuses the Chrome login, no cookies), **Windows** uses patchright (stealth Playwright with a persistent profile).

> **Architecture change (important):** the old distribution stack based on the upstream `social-auto-upload/` + `sau` CLI **has been removed**. Distribution is now fully built into the publish skills (ego-browser + patchright). Any reference to `sau`, cookie files, or `account_name` in older docs is obsolete.

When someone says "make a resource and post it", the expected flow is:

```
creation skill produces a file  ->  a publish skill uploads it to one or more accounts
```

Two **mainlines** wire this end-to-end via the `fd-vaas-*` skills (no glue code to write):

```
Video: demand -> /fd-vaas-brainstorm -> /fd-vaas-video-creator -> /fd-vaas-publish-videos -> video platforms
Article: topic -> /fd-vaas-brainstorm (图文 mode) -> article -> /fd-vaas-publish-docs -> article platforms
```

---

## Table of contents

- [VAAS - Variable Asset Authoring & Syndication](#vaas---variable-asset-authoring--syndication)
  - [⚡ Your first video in 5 minutes](#your-first-video-in-5-minutes)
  - [How it works](#how-it-works)
  - [VAAS mainlines](#vaas-mainlines)
  - [Repository layout](#repository-layout)
  - [Prerequisites](#prerequisites)
  - [Install & deploy](#install--deploy)
    - [1. Distribution runtime (ego-browser + patchright)](#1-distribution-runtime-ego-browser--patchright)
    - [2. Creation tools](#2-creation-tools)
    - [3. Remotion video project](#3-remotion-video-project)
    - [4. Claude Code skills](#4-claude-code-skills)
  - [Skill catalog](#skill-catalog)
  - [Platform support matrix](#platform-support-matrix)
  - [End-to-end examples](#end-to-end-examples)
  - [Multimodal model config (LiteLLM Bridge)](#multimodal-model-config-litellm-bridge)
  - [Config & proxy notes](#config--proxy-notes)
  - [Pitfalls & troubleshooting](#pitfalls--troubleshooting)

---

## How it works

```
 ┌─────────────────────────── CREATION ───────────────────────────┐   ┌──── DISTRIBUTION ────┐

  demand ──► ppt-master ──────► .pptx          ┐
          ├─► officecli  ──────► .docx/.xlsx    ├─► asset ──► fd-vaas-publish-videos ──► video platforms
          ├─► cap        ──────► .mp4/.gif      │             (Douyin, Kuaishou, Xiaohongshu,
          ├─► fd-cover-image ──► cover image     │              Bilibili, WeChat Channels, YouTube)
          ├─► remotion   ──────► .mp4           │
          └─► fd-vaas-video-creator ► .mp4+.srt ┘             ──► fd-vaas-publish-docs ──► article platforms
                                                          (Zhihu, WeChat OA, Xiaohongshu, Xueqiu,
                                                           Eastmoney, Tonghuashun, Toutiao, Baijiahao, Weibo)
```

- **Creation skills** produce concrete files. Each skill's `SKILL.md` is the authoritative contract - read it before driving the tool.
- **Distribution** only consumes files + metadata (video = `title + desc + tags`; article = `title + content + tags`). There is no shared glue between the two halves *except* the `fd-vaas-*` mainline - the asset path a creation skill produces is the one the publish skill reads.
- **Login state**: macOS - ego-browser inherits the user's Chrome login (no cookie/account files); Windows - patchright persistent profile (`VAAS/.profiles/<platform>/`).

---

## VAAS mainlines

The `fd-vaas-*` skills are the wired demand-to-publish pipeline.

### Video mainline ("make a video and post it")

1. **`/fd-vaas-brainstorm`** *(optional)* - given a niche/topic, returns a topic matrix (hot/pain/controversy/dry-good/persona) in 口播 (voiceover) or 图文 (article) mode: a script framework or article draft (Markdown + plain-text versions), a differentiation angle, and an optional full outline. Built-in compliance: voiceover scripts must not name other platforms or drive traffic off-platform.
2. **`/fd-vaas-video-creator`** - turns a script into a finished video. Two video types:
   - **Voiceover video**: `new-task -> TTS (seed-tts-2.0, returns audio + official word-level timestamps) -> fix-tts-timings (corrects fake Latin-token endMs) -> preflight -> Remotion render -> <slug>.mp4 (+ .srt)`. **Must run `fix-tts-timings` or subtitles desync.**
   - **Screen-recording video**: open the target page in ego-browser, record with cap during the operation, produce an mp4 (optional mic narration).
   All artifacts land in `downloads/fd-videos/<slug>/`, managed by `task.json`. Visual layer = existing assets / seedance video / seedream image / ppt master tape. **Built-in generators** (TTS / Seedream / Seedance) live in `scripts/generators/`.
3. **`/fd-vaas-publish-videos`** - one video -> 6 platforms. `publish.mjs` dispatches by `process.platform`: macOS -> `.mjs` (ego-browser), Windows -> `.py` (patchright). Reads per-platform preferences from `.env` (tags, `BILIBILI_TID`, `TENCENT_SHORT_TITLE`, `YOUTUBE_VISIBILITY`, schedule), writes results back to `task.json`'s `distribution[]`. `--dry-run` previews the commands.

```bash
export VAAS=<path to the cloned VAAS repo, e.g. ~/fd-vaas-skills>   # all commands below use $VAAS
SKILL_V=$VAAS/.agents/skills/fd-vaas-video-creator/scripts
SKILL_P=$VAAS/.agents/skills/fd-vaas-publish-videos/scripts

# 2. script -> voiceover video
node $SKILL_V/new-task.mjs    --slug <slug> --script /path/to/script.txt
node $SKILL_V/task-render.mjs --slug <slug>            # -> downloads/fd-videos/<slug>/<slug>.mp4

# 3. multi-platform publish
node $SKILL_P/publish.mjs --slug <slug> --title "…" --platforms douyin,xiaohongshu,bilibili --dry-run
```

### Article mainline ("publish an article")

**`/fd-vaas-publish-docs`** - distributes an article to 9 article platforms in one go. **Orchestration only** (per-platform copy/length/tag/cover adaptation + content adaptation + publish record); all browser automation uses ego-browser, driven by heredocs in this skill's `references/<platform>.md`. `publish.mjs` does prep + recording only.

- **Platforms**: Zhihu, WeChat Official Account, Xiaohongshu, Xueqiu, Eastmoney, Tonghuashun, Toutiao, Baijiahao, Weibo.
- The `_DOC_TAGS` suffix avoids collision with the video skill's `<PLATFORM>_TAGS`, sharing `.env`.
- ⚠️ **Get user confirmation before publishing** (cannot undo). Platform selectors are mostly page-structure inferences, **unverified on a real logged-in session** - before first publish, verify selectors via `references/probe.md`'s `snapshotText` flow, then drive.

```bash
SKILL_D=$VAAS/.agents/skills/fd-vaas-publish-docs/scripts
node $SKILL_D/publish.mjs --slug <slug> --platforms zhihu,xiaohongshu --dry-run   # preview; drop --dry-run only after user confirms
```

---

## Repository layout

```
VAAS/
├── .agents/skills/             # ★ skills source of truth (21 skills, git-tracked)
│   ├── cap/  officecli/  ppt-master/   # creation tools
│   ├── ego-browser/                     # browser automation (isolated agent space, reuses Chrome login)
│   ├── fd-browser-record/              # screen/page recording
│   ├── fd-cover-image/                 # Remotion brand cover images
│   ├── fd-coding-{bore,cloudflare,wifi}-tunnel/   # tunnels / LAN sharing
│   ├── fd-vaas-brainstorm/              # voiceover + article brainstorm
│   ├── fd-vaas-video-creator/          # script -> voiceover video (.mp4 + .srt); built-in TTS/Seedream/Seedance
│   │   └── scripts/generators/         #   tts-wrapper.js / seedream-wrapper.js / seedance-wrapper.js
│   ├── fd-vaas-publish-videos/         # video multi-platform publish (ego-browser .mjs + patchright .py)
│   │   └── scripts/{publish.mjs, platforms/<platform>.{mjs,py}, lib/}
│   ├── fd-vaas-publish-docs/          # article multi-platform publish (ego-browser instruction-driven)
│   ├── fd-vaas-dashboard/  fd-vaas-dashboard-sharing/   # content dashboard + sharing
│   └── remotion-*/                     # 7 Remotion authoring skills (best-practices, captions, create,
│                                       #   interactivity, markup, render, saas)
├── .claude/skills/                     # symlinks to a subset of .agents/skills/ (for /<name> invocation)
├── scripts/                            # multimodal media bridge
│   ├── litellm-bridge.py               #   unified multi-provider entry (TTS / image / video)
│   ├── _volcengine_{tts,image,video}.py#   Volcengine Ark direct implementation
│   ├── requirements.txt / pyproject.toml
├── remotion-app/                       # Remotion video project (React -> video)     [gitignored]
├── downloads/fd-videos/<slug>/         # fd-vaas-video-creator outputs              [gitignored]
├── downloads/fd-docs/<slug>/          # fd-vaas-publish-docs outputs                 [gitignored]
├── .env / .env.example                 # platform prefs + multimodal provider config
├── goal.md                             # project goal (the why)
└── AGENTS.md                           # engineering guidance for Claude Code
```

> **The VAAS root is a git repository** (remote: `github.com/FindDataTechnology/fd-vaas-skills`). `remotion-app/`, `downloads/`, `demands/`, `demand.md`, `.env` are gitignored. **`social-auto-upload/` has been deleted** - do not reference it.

---

## Prerequisites

- **Node.js 18+** (with Git) - the Remotion project and all `fd-vaas-*` skills.
- **Python 3.10–3.12** (`<3.13`) and [`uv`](https://docs.astral.sh/uv/) - only needed for the Windows patchright path and the root `scripts/` LiteLLM bridge.
- **ffmpeg/ffprobe** - `fd-vaas-video-creator` duration/frame validation.
- **ego-browser** (macOS distribution) - check with `which ego-browser`.
- **patchright** (Windows distribution) - `pip install patchright` + `patchright install chromium`.
- **Claude Code** - skills under `.claude/skills/` are invoked as `/cap`, `/officecli`, `/fd-vaas-video-creator`, etc.
- **macOS** recommended for the ego-browser path; **Windows** uses the patchright path (ego-browser has no Windows build).
- If your network needs a proxy, the local HTTP proxy is `127.0.0.1:7892` (fallback `7890`) - see [proxy notes](#config--proxy-notes).
- Configure a Volcengine Ark API key in `.env` for the built-in generators (TTS / Seedance / Seedream).
- **LiteLLM** (optional): `pip install -r scripts/requirements.txt`, to switch to non-Volcengine providers (OpenAI, Azure, ElevenLabs, …).

---

## Install & deploy

### 1. Distribution runtime (ego-browser + patchright)

The distribution stack is **no longer** `social-auto-upload`. It is now two layers:

```bash
# macOS: ego-browser (inherits Chrome login, no cookie / account files)
which ego-browser            # install per ego-browser's official docs if missing
# log in to each platform once in a real Chrome; ego-browser reuses it thereafter

# Windows: patchright (stealth Playwright, persistent profile)
pip install patchright
patchright install chromium   # CN mirror: PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
# login persists in VAAS/.profiles/<platform>/
```

The publish skill auto-selects the runtime by `process.platform` - you don't choose manually.

### 2. Creation tools

`cap` and `officecli` are external single-file CLIs (no Office needed). Install globally once:

```bash
# cap - agent-friendly screen recording / screenshots / upload (cap.so)
curl -fsSL https://cap.so/install-cli.sh | sh
cap --version                    # binary -> ~/.local/bin/cap

# officecli - create/edit/analyze .docx .xlsx .pptx
curl -fsSL https://d.officecli.ai/install.sh | bash      # macOS / Linux
# Windows (PowerShell):  irm https://d.officecli.ai/install.ps1 | iex
officecli --version
```

`ppt-master` is an in-repo workflow (not an external binary). If a route uses its image-generation step, install its Python deps from `.agents/skills/ppt-master/requirements.txt`.

### 3. Remotion video project

```bash
cd remotion-app
npm install
npm run dev        # Remotion Studio preview  ->  http://localhost:3001
                   # (port 3000 is taken; Studio falls back to 3001)
npx remotion render      # render the video to a file
```

> `fd-vaas-video-creator` needs `@remotion/captions` and a `VoiceoverVideo` composition - one-time setup in `.agents/skills/fd-vaas-video-creator/references/setup.md`.

### 4. Claude Code skills

Skills are **checked into this repo** (source in `.agents/skills/`; `.claude/skills/` holds symlinks to a subset). Claude Code auto-discovers them when you open the VAAS directory. Invoke directly:

- `/cap` - record, screenshot, export/upload video.
- `/officecli` - create, analyze, proofread, modify Office documents.
- `/ppt-master` - turn a source doc (PDF/DOCX/URL/Markdown) into SVG slides and export `.pptx`.
- `/ego-browser` - browser automation (open pages, fill forms, click, scrape, log in).
- `/fd-browser-record` - open a page + record/screenshot.
- `/fd-cover-image` - generate brand cover images (horizontal/vertical) via Remotion.
- `/fd-vaas-brainstorm` - voiceover + article topic matrix, script outline / article draft (dual versions).
- `/fd-vaas-video-creator` - script -> voiceover video (`.mp4` + `.srt`), or screen-recording video.
- `/fd-vaas-publish-videos` - one video -> multi-platform (6 video platforms).
- `/fd-vaas-publish-docs` - one article -> multi-platform (9 article platforms).
- `/dashboard`, `/share-dashboard` - content dashboard and sharing.
- `/remotion-*` - author Remotion videos (create, markup, captions, render, …).

> **Convention:** author new Claude Code skills in `VAAS/.agents/skills/` (source of truth), then add a symlink in `.claude/skills/`. Do not put them in the global `~/.claude/skills/`.

---

## Skill catalog

| Skill | Produces | Type | Entry |
|---|---|---|---|
| `ppt-master` | SVG slides -> exported `.pptx` (strategy -> executor -> QC) | repo workflow | `/ppt-master` |
| `officecli` | `.docx`/`.xlsx`/`.pptx` create+edit | external CLI | `/officecli` · `~/.local/bin/officecli` |
| `cap` | screen recording / screenshot -> `.mp4`/`.gif` + share link | external CLI | `/cap` · `~/.local/bin/cap` |
| `ego-browser` | browser automation (isolated agent space, reuses Chrome login) | repo skill | `ego-browser` CLI |
| `fd-browser-record` | open page + record/screenshot (ego-browser + cap) | repo skill | `/fd-browser-record` |
| `fd-cover-image` | Remotion brand cover images (horizontal/vertical) | repo skill | `/fd-cover-image` |
| `fd-coding-bore-tunnel` | bore.pub tunnel | repo skill | `/bore-tunnel` |
| `fd-coding-cloudflare-tunnel` | Cloudflare Tunnel (HTTPS) | repo skill | `/cf-tunnel` |
| `fd-coding-wifi-tunnel` | share a local service over LAN/WiFi | repo skill | `/wifi-tunnel` |
| `fd-vaas-brainstorm` | voiceover topic matrix + script outline / article draft (Markdown + plain-text) + angle | repo skill (prompt) | `/fd-vaas-brainstorm` |
| `fd-vaas-video-creator` | script -> voiceover `.mp4`+`.srt`; or screen recording; built-in TTS/Seedream/Seedance | repo skill | `/fd-vaas-video-creator` |
| `fd-vaas-publish-videos` | one video -> 6 video platforms (ego-browser .mjs + patchright .py) | repo skill | `/fd-vaas-publish-videos` |
| `fd-vaas-publish-docs` | one article -> 9 article platforms (ego-browser instruction-driven) | repo skill | `/fd-vaas-publish-docs` |
| `fd-vaas-dashboard` | content dashboard (lists all generated articles + videos) | repo skill | `/dashboard` |
| `fd-vaas-dashboard-sharing` | share the dashboard (via tunnel) | repo skill | `/share-dashboard` |
| `remotion-create` | scaffold a new Remotion project/composition | repo skill | `/remotion-create` |
| `remotion-markup` | Remotion React markup best practices | repo skill | `/remotion-markup` |
| `remotion-captions` | caption handling (JSON `Caption` type) | repo skill | `/remotion-captions` |
| `remotion-render` | render video (`npx remotion render`) | repo skill | `/remotion-render` |
| `remotion-interactivity` | animations for Studio Visual Mode | repo skill | `/remotion-interactivity` |
| `remotion-best-practices` | Remotion best-practices index | repo skill | `/remotion-best-practices` |
| `remotion-saas` | build video apps with Remotion (framework/Player/Lambda) | repo skill | `/remotion-saas` |

External CLIs ship their own help - prefer it over guessing flags: `cap guide` / `cap guide --json`, `officecli help` / `officecli help docx paragraph`.

---

## Platform support matrix

### Video platforms (`fd-vaas-publish-videos`)

6 platforms, each with both an ego-browser (`.mjs`, macOS) and a patchright (`.py`, Windows) implementation. Browser automation is **headless** by default.

| Platform | Script | Key technical challenge | Notes | Verified |
|---|---|---|---|---|
| `douyin` | `douyin.{mjs,py}` | standard DOM | `--cover-horizontal` + `--cover-vertical`; `--schedule`; tag ≤ 10 | ✅ macOS ego, real session / ⚠️ Windows patchright inferred |
| `kuaishou` | `kuaishou.{mjs,py}` | React Joyride overlay + off-screen publish btn | tag ≤ **4** (not 5) | ✅ macOS ego, real session / ⚠️ Windows patchright inferred |
| `xiaohongshu` | `xiaohongshu.{mjs,py}` | standard DOM | title ≤ 20 chars; tag ≤ 10 | ✅ macOS ego, real session / ⚠️ Windows patchright inferred |
| `bilibili` | `bilibili.{mjs,py}` | **micro-app shadow DOM** | `--cover` (not `--thumb`); `--tid` category; no `--schedule` | ⚠️ inferred, unverified |
| `weixin` (Channels) | `weixin.{mjs,py}` | **Wujie shadow DOM** + HTTP server + DataTransfer | no separate title; auto-publishes after processing | ⚠️ inferred, unverified |
| `youtube` | `youtube.{mjs,py}` | **Polymer dialog** + 4-step flow | `--thumbnail`; `--visibility`; "not for kids" mandatory | ⚠️ inferred, unverified |

See `.agents/skills/fd-vaas-publish-videos/references/platform-quirks.md` and `references/<platform>.md`.

### Article platforms (`fd-vaas-publish-docs`)

9 platforms, all via ego-browser (instruction-driven, `references/<platform>.md` heredocs).

| Platform | Notes | Verified |
|---|---|---|
| Zhihu `zhihu` | article | ⚠️ inferred, unverified |
| WeChat Official Account `weixin` | article | ⚠️ inferred, unverified |
| Xiaohongshu `xiaohongshu` | image-text note | ⚠️ inferred, unverified |
| Xueqiu `xueqiu` | finance column | ⚠️ inferred, unverified |
| Eastmoney `eastmoney` | finance | ⚠️ inferred, unverified |
| Tonghuashun `tonghuashun` | finance | ⚠️ inferred, unverified |
| Toutiao `toutiao` | article | ⚠️ inferred, unverified |
| Baijiahao `baijiahao` | article | ⚠️ inferred, unverified |
| Weibo `weibo` | long-form | ⚠️ inferred, unverified |

> ⚠️ Selectors are mostly page-structure inferences, **unverified on a real logged-in session**. Verify via `references/probe.md`'s `snapshotText` flow before first publish.

---

## End-to-end examples

### Video: script -> multi-platform publish

```bash
SKILL_V=$VAAS/.agents/skills/fd-vaas-video-creator/scripts
SKILL_P=$VAAS/.agents/skills/fd-vaas-publish-videos/scripts

# 1. script -> voiceover video
node $SKILL_V/new-task.mjs    --slug demo --script ./script.txt
node $SKILL_V/task-render.mjs --slug demo          # -> downloads/fd-videos/demo/demo.mp4

# 2. multi-platform publish (preview first, drop --dry-run after confirming)
node $SKILL_P/publish.mjs --slug demo --title "Title" \
    --platforms douyin,xiaohongshu,bilibili --tags oss,AI --dry-run

# 3. single-platform ad-hoc upload (debug)
node $SKILL_P/platforms/douyin.mjs --file downloads/fd-videos/demo/demo.mp4 \
    --title "Title" --desc "Description." --tags oss,AI
```

### Article: publish an article

```bash
SKILL_D=$VAAS/.agents/skills/fd-vaas-publish-docs/scripts
# article lives under downloads/fd-docs/<slug>/
node $SKILL_D/publish.mjs --slug <slug> --platforms zhihu,xiaohongshu --dry-run
# after selectors check + user confirmation, drop --dry-run to actually publish
```

### Login

- **macOS (ego-browser)**: log in to each platform once in a real Chrome; ego-browser reuses it thereafter. If it expires, re-login in ego-browser - **no cookie files, no `--account`**.
- **Windows (patchright)**: first run opens the login page; login persists in `VAAS/.profiles/<platform>/`.

**Metadata convention**: video = `title + desc + tags`; article = `title + content + tags`. Pass `--schedule "YYYY-MM-DD HH:MM"` for timed publish (omitted = immediate). Only some platforms support `--schedule`.

---

## Multimodal model config (LiteLLM Bridge)

The generators built into `fd-vaas-video-creator` (TTS / image / video) go through the root `scripts/litellm-bridge.py` unified entry, supporting multi-provider switching. All model config lives in `.env` - changing providers needs no code change. **There are no longer standalone `voice/image/video-generator` skills** - they have been merged into `fd-vaas-video-creator/scripts/generators/`.

### Supported providers

| Modality | LiteLLM provider | Volcengine direct |
|------|-----------------|----------|
| **TTS** | openai, azure, vertex_ai, elevenlabs, minimax, polly | ✅ (with word-level timestamps) |
| **Image** | openai, azure, google-ai-studio, vertex-ai, bedrock, black-forest-labs, recraft, openrouter | ✅ (reference image / web search / batch) |
| **Video** | limited (litellm video API is early) | ✅ (async polling / reference media) |

### `.env` example

```env
# ─── TTS ───
TTS_PROVIDER=volcengine        # volcengine | openai | elevenlabs | azure | ...
TTS_MODEL=seed-tts-2.0         # volcengine uses plain name; others use "provider/model" (e.g. "openai/tts-1")
TTS_VOICE=zh_female_gaolengyujie_uranus_bigtts

# ─── Image ───
IMAGE_PROVIDER=volcengine      # volcengine | openai | azure | google-ai-studio | ...
IMAGE_MODEL=doubao-seedream-5.0-lite

# ─── Video ───
VIDEO_PROVIDER=volcengine      # volcengine recommended (most features)
VIDEO_MODEL=doubao-seedance-2.0

# API keys for non-Volcengine providers (set as needed)
# OPENAI_API_KEY=sk-...
# ELEVENLABS_API_KEY=...
# AZURE_API_KEY=...
# GOOGLE_AI_STUDIO_API_KEY=...
```

### Auto-routing

- **`*_PROVIDER != volcengine` in `.env`** -> generators auto-route through the LiteLLM bridge, no flag needed.
- **`--litellm` flag** -> force the bridge even when provider is volcengine.
- **Volcengine direct** -> keeps all advanced features (TTS word-level timestamps, image reference/web search, video async tasks/reference media).

### Install deps

```bash
pip install -r scripts/requirements.txt
# or: cd scripts && pip install -e .
```

> ⚠️ **Caption note**: only Volcengine TTS direct provides official word-level timestamps (`captions.json`). Switching to another provider degrades or disables `fd-vaas-video-creator`'s caption feature. If you need captions, keep TTS on volcengine.

---

## Config & proxy notes

- **`fd-vaas-*` config**: read from the project-root `.env` (see `.env.example`). Two namespaces coexist:
  - **Video**: `PLATFORMS`, `TAGS`, `<PLATFORM>_TAGS`, `BILIBILI_TID`, `TENCENT_SHORT_TITLE`, `YOUTUBE_VISIBILITY`, `SCHEDULE`, `HEADLESS`.
  - **Article**: `PLATFORMS_DOCS`, `DOC_TAGS`, `<PLATFORM>_DOC_TAGS`, `DOC_SCHEDULE`, `DOC_HEADLESS` (the `_DOC_TAGS` suffix avoids collision with the video skill's `<PLATFORM>_TAGS`).
- **Per-task overrides**: video -> `downloads/fd-videos/<slug>/.publish.env`, article -> `downloads/fd-docs/<slug>/.publish.env`. Priority: `CLI --flag > <task>/.publish.env > <VAAS>/.env > built-in default`.
- **Login state**: macOS = ego-browser inherits Chrome login; Windows = patchright persistent profile (`VAAS/.profiles/<platform>/`). Same platform must be serial; different platforms can run concurrently.
- **Post-publish cleanup**: close the ego task window after publishing - don't leave it for the user; for Douyin's manual-publish path, wait for the user to confirm "发布完成" before running the `completeTaskSpace` fallback cleanup.
- **Proxy (general)**: if a network command can't reach a host, use the local proxy: `export http_proxy=http://127.0.0.1:7892` (fallback `7890`). Do **not** set `https_proxy` for general use.
- **Proxy + patchright**: patchright's chromium does **not** read the system proxy. Installing Playwright/patchright browsers needs `https_proxy` set explicitly to reach `cdn.playwright.dev` (CN mirror via `PLAYWRIGHT_DOWNLOAD_HOST`).
- Some hosts (`officecli.ai`, `raw.githubusercontent.com`) fail TLS through the proxy - bypass with `env -u http_proxy -u https_proxy <cmd>`.

---

## Pitfalls & troubleshooting

> **First line of diagnosis:** `node scripts/doctor.mjs` — checks Node/ffmpeg/keys/remotion deps/skill links and prints the fix for each.

- **`social-auto-upload/` has been removed** - all `sau`, `sau_cli.py`, cookie-file, and `account_name` references in old docs are obsolete. Distribution is now done by ego-browser + patchright built into `fd-vaas-publish-videos` / `fd-vaas-publish-docs`.
- **Standalone `voice/image/video-generator` skills no longer exist** - generators were merged into `fd-vaas-video-creator/scripts/generators/`. Multi-provider switching is still provided by the root `scripts/litellm-bridge.py`.
- **PPTX slides can't be uploaded as video directly.** `cap` (screen recording), `fd-vaas-video-creator`, or `ppt-master`'s export/render step is the bridge from a deck to a publishable video.
- **Skipping `fix-tts-timings` in `fd-vaas-video-creator` desyncs subtitles** - seed-tts-2.0 returns fake `endMs` for Latin tokens (English names, URLs). The pipeline runs this automatically; a manual path must run it explicitly.
- **The Windows patchright path is not fully verified on a real logged-in session** (especially `weixin`/`bilibili` `.py`). Use `--dry-run` first to confirm it reaches the upload page before a real publish.
- **Article-platform selectors are mostly inferred and unverified** - verify via `references/probe.md`'s `snapshotText` flow before first publish.
- **Always get user confirmation before publishing** (especially articles - it can't be undone).

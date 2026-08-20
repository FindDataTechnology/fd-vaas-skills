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
2. **Distribution engine** - two publish skills ship the asset to platforms: `fd-vaas-publish-videos` (video -> 6 video platforms) and `fd-vaas-publish-docs` (article -> 11 article platforms). Distribution uses "**vendor upstream + thin adapter layer**": vendor the entire `social-auto-upload` upstream into `fd-vaas-publish-videos/scripts/upstream/`, use a thin adapter (`sau_adapter.py` / `note_adapter.py`) to translate CLI calls into upstream `<Platform>Video(...).main()` invocations, unify on **py runtime (patchright)**, login state via cookie files (`upstream/cookies/<platform>_uploader/account.json`); bilibili exception (upstream uses biliup binary, handled by local `bilibili.py`).

> **Architecture change (important):** distribution stack re-vendored upstream `social-auto-upload` — this is the **second architecture flip**. All previous statements about "`social-auto-upload` removed, fully built-in distribution, macOS using ego-browser (`.mjs`) / Windows using patchright (`.py`) dual runtime" are now **obsolete**. Now unified py/patchright runtime + cookie login; per-platform handwritten `.mjs`/`.py` deleted. If you see old docs mentioning ego-browser reusing Chrome login for video publishing or `--runtime` dispatching by OS, those are outdated.

When someone says "make a resource and post it", the expected flow is:

```
creation skill produces a file  ->  a publish skill uploads it to one or more accounts
```

Two **mainlines** wire this end-to-end via the `fd-vaas-*` skills (no glue code to write):

```
Video: demand -> /fd-vaas-brainstorm -> /fd-vaas-video-creator -> /fd-vaas-publish-videos -> video platforms
Article: topic -> /fd-vaas-brainstorm(article mode) -> article -> /fd-vaas-publish-docs -> article platforms
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
    - [1. Distribution runtime (patchright) and login](#1-distribution-runtime-patchright-and-login)
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
                                                          (Zhihu, WeChat OA, Xiaohongshu, Douyin,
                                                           Kuaishou, Xueqiu, Eastmoney, Tonghuashun,
                                                           Toutiao, Baijiahao, Weibo)
```

- **Creation skills** produce concrete files. Each skill's `SKILL.md` is the authoritative contract - read it before driving the tool.
- **Distribution** only consumes files + metadata (video = `title + desc + tags`; article = `title + content + tags`). There is no shared glue between the two halves *except* the `fd-vaas-*` mainline - the asset path a creation skill produces is the one the publish skill reads.
- **Login state**: Publish uses cookie files (`scripts/upstream/cookies/<platform>_uploader/account.json`), unified via `/fd-vaas-login` (localhost:8766) QR scan login, videos and articles share same cookie. Article own-logic platforms additionally can use `--runtime patchright` (independent persistent profile `VAAS/.profiles/<platform>/`). ego-browser used only for screen recording and article own-logic default runtime.

---

## VAAS mainlines

The `fd-vaas-*` skills are the wired demand-to-publish pipeline.

### Video mainline ("make a video and post it")

1. **`/fd-vaas-brainstorm`** *(optional)* - given a niche/topic, returns a topic matrix (hot/pain/controversy/dry-good/persona), script framework or article draft (Markdown version + plain-text simplified version), differentiation angle, and optional full outline. Built-in compliance: voiceover scripts must not name other platforms or drive traffic off-platform.
2. **`/fd-vaas-video-creator`** - turns a script into a finished video. Select video type via **type registry** (`new-task --type <id>`), run `node scripts/types/list.mjs` to see all types. Stable types: voiceover `voiceover`, screen-recording `screen-recording`; experimental types: `carousel` (carousel), `kinetic-quote` (kinetic quote), `news-flash` (news flash), `listicle` (listicle), `data-viz` (data visualization).
   - **Voiceover video**: `new-task -> TTS (seed-tts-2.0, returns audio + official word-level timestamps) -> fix-tts-timings (corrects fake Latin-token endMs) -> scene-align (rearrange scenes per voiceover timestamps) -> preflight -> Remotion render -> <slug>.mp4 (+ .srt)`. **Must run `fix-tts-timings` or subtitles desync.**
   - **Screen-recording/web operation video**: open target page in ego-browser, operate during recording with cap, produce mp4 (optional mic narration).
   All artifacts land in `downloads/fd-videos/<slug>/`, managed by `task.json`. Visual layer = existing assets / seedance video / seedream images / ppt master tape. **Built-in generators** (TTS / Seedream / Seedance) live in `scripts/generators/`.
3. **`/fd-vaas-publish-videos`** - one video -> 6 platforms. Distribution uses "**vendor upstream + thin adapter layer**": upstream `social-auto-upload` vendored in `scripts/upstream/`, `sau_adapter.py` translates CLI into upstream `<Platform>Video(...).main()` calls, unified **py runtime (patchright)**; bilibili exception (upstream uses biliup binary, handled by local `bilibili.py`). Login state via cookie files (`upstream/cookies/<platform>_uploader/account.json`, kuaishou uses `kuaishou_creator.json`), managed by `/fd-vaas-login` unified QR scan. Reads per-platform preferences from `.env` (tags, `BILIBILI_TID`, `TENCENT_SHORT_TITLE`, `YOUTUBE_VISIBILITY`, schedule), writes results back to `task.json`'s `distribution[]`. `--dry-run` previews the commands.

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

**`/fd-vaas-publish-docs`** - distributes an article to 11 article platforms in one go. **Orchestration only** (per-platform copy/length/tag/cover adaptation + content adaptation + publish record). Distribution uses "**upstream-first**" routing: xiaohongshu/douyin/kuaishou article/image-video routed via `note_adapter.py` (shares same cookie as video); remaining 8 own-logic platforms use ego-browser (default, `references/<platform>.md` heredocs driven) or `--runtime patchright` (independent persistent profile). `publish.mjs` handles prep + recording. Single source of truth for platform routing and verification status is `_shared/publish/platform-registry.json`.

- **Platforms supported (11)**: Zhihu, WeChat Official Account, Xiaohongshu, Douyin, Kuaishou, Xueqiu, Eastmoney, Tonghuashun, Toutiao, Baijiahao, Weibo.
- **`_DOC_TAGS` suffix** avoids collision with video skill's `<PLATFORM>_TAGS`, sharing `.env` without conflict.
- ⚠️ **Get user confirmation before publishing** (cannot undo). Platform verification status see [Platform support matrix](#platform-support-matrix) - platforms marked ✅ verified can be used directly; those marked ⚠️/❌ need selector re-verification via `references/probe.md`'s `snapshotText` flow before first publish.

```bash
SKILL_D=$VAAS/.agents/skills/fd-vaas-publish-docs/scripts
node $SKILL_D/publish.mjs --slug <slug> --platforms zhihu,xiaohongshu --dry-run   # preview; drop --dry-run only after user confirms
```

---

## Repository layout

```
VAAS/
├── .agents/skills/             # ★ skills source of truth (23 skills + _shared/, git-tracked)
│   ├── cap/  officecli/  ppt-master/   # creation tools
│   ├── ego-browser/                     # browser automation (isolated agent space, reuses Chrome login)
│   ├── fd-browser-record/              # screen/page recording
│   ├── fd-cover-image/                 # Remotion brand cover images
│   ├── fd-coding-{bore,cloudflare,wifi}-tunnel/   # tunnels / LAN sharing
│   ├── fd-vaas-brainstorm/              # voiceover + article brainstorm
│   ├── fd-vaas-video-creator/          # script -> voiceover video (.mp4 + .srt); built-in TTS/Seedream/Seedance
│   │   └── scripts/generators/         #   tts-wrapper.js / seedream-wrapper.js / seedance-wrapper.js
│   ├── fd-vaas-login/                  # login management web page (:8766, QR scan/status overview, cookie shared)
│   ├── fd-vaas-publish-videos/         # video multi-platform publish (vendor upstream + thin adapter, unified py/patchright)
│   │   └── scripts/{publish.mjs, platforms/sau_adapter.py, platforms/bilibili.py, upstream/, sync-upstream.sh}
│   ├── fd-vaas-publish-docs/          # article multi-platform publish (upstream-first note_adapter + own logic)
│   │   └── scripts/{publish.mjs, note_adapter.py, platforms/<platform>.py}
│   ├── _shared/publish/               # cross-skill shared: platform-registry.json (routing+verification status truth source), browser_utils.py, publish-common.mjs
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

> **The VAAS root is a git repository** (remote: `github.com/FindDataTechnology/fd-vaas-skills`). `remotion-app/`, `downloads/`, `demands/`, `demand.md`, `.env` are gitignored. `social-auto-upload` upstream vendored into `fd-vaas-publish-videos/scripts/upstream/` (not standalone root directory); use `scripts/sync-upstream.sh` to sync upstream updates.

---

## Prerequisites

- **Node.js 18+** (with Git) - Remotion projects and all `fd-vaas-*` skills.
- **Python 3.10–3.12** (`<3.13`) and [`uv`](https://docs.astral.sh/uv/) - **required ALL platforms**: video distribution unified py runtime (patchright), LiteLLM bridge in root `scripts/` also uses it.
- **patchright** (stealth Playwright, ALL-platform distribution runtime) - `uv pip install patchright` + `patchright install chromium`; login state via cookie files, unified QR scan via `/fd-vaas-login`.
- **ffmpeg/ffprobe** - duration/frame validation for `fd-vaas-video-creator`.
- **ego-browser** (macOS optional) - used only for screen recording (`/fd-browser-record`) and article own-logic default runtime; check with `which ego-browser`. No Windows/Linux version.
- **Claude Code** - skills under `.claude/skills/` invoked as `/cap`, `/officecli`, `/fd-vaas-video-creator`, `/fd-vaas-login`, etc.
- If your network needs a proxy, local HTTP proxy at `127.0.0.1:7892` (fallback `7890`) - see [proxy notes](#config--proxy-notes).
- Configure Volcengine Ark API key in `.env` for built-in generators (TTS / Seedance / Seedream).
- **LiteLLM** (optional): `pip install -r scripts/requirements.txt`, to switch to non-Volcengine providers (OpenAI, Azure, ElevenLabs, …).

---

## Install & deploy

### 1. Distribution runtime (patchright) and login

Distribution uses "**vendor upstream + thin adapter layer**": upstream `social-auto-upload` vendored in `fd-vaas-publish-videos/scripts/upstream/`, `sau_adapter.py` translates CLI into upstream `<Platform>Video(...).main()` calls, unified **py runtime (patchright)**. Consistent across all platforms, no OS-based dispatch.

```bash
# ALL platforms: patchright (stealth Playwright)
uv pip install patchright      # or pip install patchright
patchright install chromium    # CN mirror: PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
```

Login state via cookie files (`upstream/cookies/<platform>_uploader/account.json`, kuaishou uses `kuaishou_creator.json`), managed by `/fd-vaas-login` unified QR scan:

```bash
# Start login management page (also available directly in Claude Code as /fd-vaas-login)
python3 $VAAS/.agents/skills/fd-vaas-login/scripts/login-manager.py
# Browser opens http://localhost:8766 -> select platform -> QR scan/login -> cookie written
# Videos and articles share same cookie; rescan when expired
```

> ego-browser now has only two uses: `/fd-browser-record` screen recording, article own-logic default runtime (macOS, can switch to independent persistent profile `VAAS/.profiles/<platform>/` with `--runtime patchright`).

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

`ppt-master` is an in-repo workflow (not an external binary), but VAAS ships only a **thin shell** — fetch the upstream before first using `/ppt-master`: `bash scripts/fetch-ppt-master.sh` (~98 MB, lands in the gitignored `.agents/skills/ppt-master/upstream/`). If a route uses its image-generation step, install its Python deps from `upstream/requirements.txt`.

### 3. Remotion video project

```bash
cd remotion-app
npm install
npm run dev        # Remotion Studio preview  ->  http://localhost:3001
                   # (port 3000 taken; Studio falls back to 3001)
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
- `/fd-vaas-brainstorm` - voiceover + article topic matrix, script outline / article draft (Markdown + plain-text dual versions).
- `/fd-vaas-video-creator` - script -> voiceover video (`.mp4` + `.srt`), or screen-recording video.
- `/fd-vaas-publish-videos` - one video -> multi-platform (6 video platforms).
- `/fd-vaas-publish-docs` - one article -> multi-platform (11 article platforms).
- `/fd-vaas-login` - login management page (:8766), QR scan login for all video/article platforms, cookie shared.
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
| `fd-vaas-login` | login management web page (:8766, QR scan/status overview, cookie shared) | repo skill | `/fd-vaas-login` |
| `fd-vaas-publish-videos` | one video -> 6 video platforms (vendor upstream + sau_adapter, unified py/patchright) | repo skill | `/fd-vaas-publish-videos` |
| `fd-vaas-publish-docs` | one article -> 11 article platforms (upstream-first note_adapter + own logic) | repo skill | `/fd-vaas-publish-docs` |
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

6 platforms, unified **py runtime (patchright)**. All except bilibili routed via `sau_adapter.py` calling upstream `<Platform>Video.main()`; bilibili handled by local `bilibili.py` (biliup binary). Verification status from `_shared/publish/platform-registry.json`.

| Platform | Route | Notes | Verification Status |
|---|---|---|---|
| `douyin` | upstream (`sau_adapter`) | `--schedule`; tag ≤ 10 | 🔄 upstream maintained |
| `kuaishou` | upstream (`sau_adapter`) | tag ≤ **4**; cookie = `kuaishou_creator.json` | 🔄 upstream maintained |
| `xiaohongshu` | upstream (`sau_adapter`) | title ≤ 20 chars; tag ≤ 10 | 🔄 upstream maintained |
| `bilibili` | own (`bilibili.py` + biliup) | biliup binary (non-Playwright); `--tid` category; no `--schedule` | ⚠️ unverified on real session |
| `weixin` (Channels) | upstream (`sau_adapter`) | Wujie shadow DOM; no separate title; auto-publishes after processing | ✅ verified (2026-07-30) |
| `youtube` | upstream (`sau_adapter`) | `--visibility`; no `--schedule` (no publish_date) | 🔄 upstream maintained |

See `.agents/skills/fd-vaas-publish-videos/references/platform-quirks.md` and `references/<platform>.md`.

### Article platforms (`fd-vaas-publish-docs`)

11 platforms, "**upstream-first**" routing: xiaohongshu/douyin/kuaishou article notes via `note_adapter.py` (shares same cookie as video); remaining 8 own-logic platforms use ego-browser or `--runtime patchright`. Verification status from `_shared/publish/platform-registry.json`.

| Platform | Route | Notes | Verification Status |
|---|---|---|---|
| Xiaohongshu `xiaohongshu` | upstream-note (`note_adapter`) | image+video share cookie | 🔄 upstream maintained |
| Douyin `douyin` | upstream-note (`note_adapter`) | reuse xhs image when no cover | 🔄 upstream maintained |
| Kuaishou `kuaishou` | upstream-note (`note_adapter`) | cookie = `kuaishou_creator.json` | 🔄 upstream maintained |
| Zhihu `zhihu` | own (ego/patchright) | title `textarea[placeholder*=请输入标题]`; body supports paste markdown | ✅ verified (2026-07-29) |
| WeChat OA `weixin` | own (ego/patchright) | appmsg URL; title `#title` needs js; body `.ProseMirror` | ✅ verified (2026-07-30) |
| Xueqiu `xueqiu` | own | old entry 404, real publish entry needs re-probe | ❌ entry broken (2026-08-11) |
| Eastmoney `eastmoney` | own | `oa.eastmoney.com` creator backend; needs finance account qualification | ✅ verified (2026-07-29) |
| Tonghuashun `tonghuashun` | own | `media.10jqka.com.cn` 302 redirects to investor settlement | ❌ entry broken (2026-08-11) |
| Toutiao `toutiao` | own | `mp.toutiao.com`; title ≤ 30 chars | ✅ verified (2026-07-29) |
| Baijiahao `baijiahao` | own | `baijiahao.baidu.com`; cover required, select category | ✅ verified (2026-07-29) |
| Weibo `weibo` | own | `weibo.com/newblog` long-form; #topics# in body | ✅ verified (2026-07-29) |

> Status legend: ✅ real-session verified / 🔄 upstream maintained (selectors managed by social-auto-upload upstream) / ❌ entry broken / ⚠️ unverified. Platforms marked ❌/⚠️ use `references/probe.md`'s `snapshotText` flow to re-verify selectors before first publish.

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

# 3. single-platform ad-hoc upload (debug, specify single platform with --platforms)
node $SKILL_P/publish.mjs --slug demo --title "Title" \
    --platforms douyin --tags oss,AI --dry-run
```

### Article: publish an article

```bash
SKILL_D=$VAAS/.agents/skills/fd-vaas-publish-docs/scripts
# article lives under downloads/fd-docs/<slug>/
node $SKILL_D/publish.mjs --slug <slug> --platforms zhihu,xiaohongshu --dry-run
# after selectors check + user confirmation, drop --dry-run to actually publish
```

### Login

Videos and articles both use cookie login, unified via `/fd-vaas-login` QR scan management:

```bash
python3 $VAAS/.agents/skills/fd-vaas-login/scripts/login-manager.py
# Browser opens http://localhost:8766 -> select platform -> QR scan/login
# cookie written to upstream/cookies/<platform>_uploader/account.json (kuaishou uses kuaishou_creator.json)
# Videos and articles share same cookie; rescan when expired
```

- bilibili uses profile mode (non-QR cookie), youtube uses Google account login, remaining 4 video platforms use QR code.
- Article own-logic platforms: 3 use shared video cookie (xiaohongshu/douyin/kuaishou via `note_adapter`), 8 logged in via `docs_login.py` + patchright window detection, auto-close window after login.

**Metadata convention**: video = `title + desc + tags`; article = `title + content + tags`. Pass `--schedule "YYYY-MM-DD HH:MM"` for timed publish (omitted = immediate). Only some platforms support `--schedule`.

---

## Multimodal model config (LiteLLM Bridge)

The generators built into `fd-vaas-video-creator` (TTS / image / video) go through the root `scripts/litellm-bridge.py` unified entry, supporting multi-provider switching. All model config lives in `.env` - changing providers needs no code change. **There are no longer standalone `voice/image/video-generator` skills** - they have been merged into `fd-vaas-video-creator/scripts/generators/`.

### Supported providers

| Modality | LiteLLM Provider | Volcengine Direct |
|------|-----------------|----------|
| **TTS** | openai, azure, vertex_ai, elevenlabs, minimax, polly | ✅ (with word-level timestamps) |
| **Image** | openai, azure, google-ai-studio, vertex-ai, bedrock, black-forest-labs, recraft, openrouter | ✅ (reference image / web search / batch) |
| **Video** | limited support (litellm video API early) | ✅ (async polling / reference media) |

### `.env` configuration example

```env
# ─── TTS ───
TTS_PROVIDER=volcengine        # volcengine | openai | elevenlabs | azure | ...
TTS_MODEL=seed-tts-2.0         # volcengine uses plain name; others use "provider/model" (e.g. "openai/tts-1")
TTS_VOICE=zh_female_gaolengyujie_uranus_bigtts

# ─── Image ───
IMAGE_PROVIDER=volcengine      # volcengine | openai | azure | google-ai-studio | ...
IMAGE_MODEL=doubao-seedream-5.0-lite

# ─── Video ───
VIDEO_PROVIDER=volcengine      # recommended: volcengine (most features)
VIDEO_MODEL=doubao-seedance-2.0

# API keys for non-Volcengine providers (set as needed)
# OPENAI_API_KEY=sk-...
# ELEVENLABS_API_KEY=...
# AZURE_API_KEY=...
# GOOGLE_AI_STUDIO_API_KEY=...
```

### Auto-routing

- **`*_PROVIDER != volcengine` in `.env`** -> generators auto-route through LiteLLM bridge, no flag needed.
- **`--litellm` flag** -> force bridge even when provider is volcengine.
- **volcengine direct** -> retains all advanced features (TTS word-level timestamps, image reference/web search, video async tasks/reference media).

### Install dependencies

```bash
pip install -r scripts/requirements.txt
# or: cd scripts && pip install -e .
```

> ⚠️ **Caption note**: only Volcengine TTS direct provides official word-level timestamps (`captions.json`). Switching to another provider degrades or disables `fd-vaas-video-creator`'s caption feature. For captions, recommend keeping TTS on volcengine.

---

## Config & proxy notes

- **`fd-vaas-*` config**: read from project-root `.env` (see `.env.example`). Two namespaces coexist:
  - **Video**: `PLATFORMS`, `TAGS`, `<PLATFORM>_TAGS`, `BILIBILI_TID`, `TENCENT_SHORT_TITLE`, `YOUTUBE_VISIBILITY`, `SCHEDULE`, `HEADLESS`.
  - **Article**: `PLATFORMS_DOCS`, `DOC_TAGS`, `<PLATFORM>_DOC_TAGS`, `DOC_SCHEDULE`, `DOC_HEADLESS` (`_DOC_TAGS` suffix avoids collision with video skill's `<PLATFORM>_TAGS`).
- **Per-task overrides**: video -> `downloads/fd-videos/<slug>/.publish.env`, article -> `downloads/fd-docs/<slug>/.publish.env`. Priority: `CLI --flag > <task>/.publish.env > <VAAS>/.env > built-in default`.
- **Login state**: videos and articles both use cookie files (`upstream/cookies/<platform>_uploader/account.json`), unified QR scan via `/fd-vaas-login`. Article own-platforms using `--runtime patchright` use independent persistent profiles (`VAAS/.profiles/<platform>/`). Same platform must be serial; different platforms can run concurrently.
- **Post-publish cleanup**: after ego-browser driven article own-platform publishing, close ego task window - don't leave for user to close manually; for Douyin manual publish path, wait for user to confirm "发布完成" before running `completeTaskSpace` fallback cleanup.
- **Proxy (general)**: if network command can't reach host, use local proxy: `export http_proxy=http://127.0.0.1:7892` (fallback `7890`). Do **not** set `https_proxy` for general use.
- **Proxy + patchright**: patchright's chromium does **not** read system proxy. Installing Playwright/patchright browsers needs `https_proxy` set explicitly to reach `cdn.playwright.dev` (CN mirror via `PLAYWRIGHT_DOWNLOAD_HOST`).
- Some hosts (`officecli.ai`, `raw.githubusercontent.com`) fail TLS through proxy - bypass with `env -u http_proxy -u https_proxy <cmd>`.

---

## Pitfalls & troubleshooting

> **First diagnostic step:** `node scripts/doctor.mjs` — checks Node/ffmpeg/keys/remotion deps/skill links item-by-item, prints fix commands.

- **Distribution stack = vendor upstream + thin adapter layer**: `social-auto-upload` upstream vendored in `fd-vaas-publish-videos/scripts/upstream/` (not standalone root directory, stop looking for root-level `social-auto-upload/`). Sync upstream updates with `scripts/sync-upstream.sh`. To update platform selector status, write back to `_shared/publish/platform-registry.json` (use `probe.py`), do not manually edit docs.
- **Cookie expires, need rescan**: publish login failures mostly due to expired cookies, use `/fd-vaas-login` to rescan, no need to manually edit cookie files.
- **patchright consistent across ALL platforms**: video distribution no longer dispatches by OS, macOS also needs patchright installed. ego-browser has only two uses: screen recording + article own-platforms.
- **Standalone `voice/image/video-generator` skills no longer exist** - generators merged into `fd-vaas-video-creator/scripts/generators/`. Multi-provider switching still provided by root `scripts/litellm-bridge.py`.
- **PPTX slides cannot be uploaded as video directly**. `cap` (screen recording), `fd-vaas-video-creator`, or `ppt-master`'s export/render step is the bridge from deck to publishable video.
- **Skipping `fix-tts-timings` in `fd-vaas-video-creator` causes subtitle desync** - seed-tts-2.0 returns fake `endMs` for Latin tokens (English names, URLs). Pipeline runs this automatically; manual paths must run it explicitly.
- **Platform verification status see matrix, don't rely on memory**: bilibili unverified on real session, xueqiu/tonghuashun entries broken. Platforms marked ❌/⚠️ use `references/probe.md`'s `snapshotText` flow to re-verify selectors before first publish.
- **Always get user confirmation before publishing** (especially articles - it can't be undone).

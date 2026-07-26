# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What VAAS is

VAAS is a content-creation + multi-platform distribution workspace. The goal: take a content
demand, generate a **variable-type resource** (deck, document, screen-recording video, images, or a
Remotion-rendered voiceover video), then **publish it automatically to different social-media
accounts** — and ideally produce a *different* resource variant per platform/account. It is an
orchestration layer over two halves:

1. **Creation skills** (this repo's `.claude/skills/` + `.agents/skills/`) — turn a demand into an asset file.
2. **Distribution engine** — `social-auto-upload/`, a vendored upstream project that uploads assets to social platforms via browser automation.

There is **no monolithic VAAS application** — the workspace wires skills to a distribution CLI. But
the **mainline is now wired end-to-end** via the `fd-vaas-*` skills (no glue code to write by hand):

```
demand / 文案
  → /fd-vaas-brainstorm-koubo   (optional: 选题 + 脚本大纲 planning)
  → /fd-vaas-video-creator      (文案 → 口播视频 .mp4 + .srt;
                                 uses byted-ark-tts + Remotion,
                                 optionally byted-ark-seedance/seedream for visuals)
  → /fd-vaas-publish            (mp4 → 多平台发布; delegates to `sau`)
```

When the user says "make a resource and post it", the flow is:
*creation skill produces a file → `fd-vaas-publish` (or `sau` directly) uploads it to one or more `account_name`s.*

## Repository shape — read this first

- The VAAS root **is a git repository** (remote: `github.com/FindDataOfficial/VAAS`). `social-auto-upload/`
  is a **vendored clone of `dreammis/social-auto-upload`** (origin: `https://github.com/dreammis/social-auto-upload.git`)
  with its own git history — treat it as a nested third-party dependency, not a submodule: prefer its own
  `social-auto-upload/CLAUDE.md` and `docs/` for its internals, and avoid editing it unless the task is
  specifically about that project.
- Skills live in two places:
  - `.claude/skills/` — project-scoped Claude Code skills: `cap`, `officecli`, `ppt-master` (a symlink to
    `../../.agents/skills/ppt-master`), the `byted-ark-*` VolcEngine media skills (seedance / seedream / tts),
    the `remotion-*` authoring skills (7 of them), and the `fd-vaas-*` mainline skills
    (brainstorm-koubo, video-creator, publish).
  - `.agents/skills/ppt-master/` — the source of truth for the ppt-master skill (large SKILL.md + `workflows/`, `templates/`, `scripts/`, `references/`).
  - `social-auto-upload/skills/{douyin,kuaishou,xiaohongshu,bilibili}-upload/` — per-platform upload skills shipped by the upstream project.

## The two halves

### Creation skills (demand → asset file)

| Skill | Produces | Entry | Binary / location |
|---|---|---|---|
| `ppt-master` | SVG-deck → exported `.pptx` (multi-role pipeline: strategist → executor → QC) | `/ppt-master` skill | source at `.agents/skills/ppt-master/` |
| `officecli` | `.docx` / `.xlsx` / `.pptx` create+edit (L1 read → L2 DOM → L3 XML) | `/officecli` skill | `~/.local/bin/officecli` (global) |
| `cap` | screen recording / screenshots → `.mp4`/`.gif` + shareable upload link | `/cap` skill | `~/.local/bin/cap` (global) |
| `byted-ark-tts` | text → natural speech audio + word-level timestamps (seed-tts-2.0) | `/byted-ark-tts-skill` skill | scripts at `.claude/skills/byted-ark-tts-skill/` |
| `byted-ark-seedance` | text/image → AI video (豆包 Seedance, VolcEngine Agent Plan) | `/byted-ark-seedance-skill` skill | scripts at `.claude/skills/byted-ark-seedance-skill/` |
| `byted-ark-seedream` | text → AI image (豆包 Seedream, VolcEngine Agent Plan) | `/byted-ark-seedream-skill` skill | scripts at `.claude/skills/byted-ark-seedream-skill/` |
| `fd-vaas-brainstorm-koubo` | 口播选题矩阵 + 脚本框架 + 差异化角度 + 完整大纲 | `/fd-vaas-brainstorm-koubo` skill | pure-prompt skill at `.claude/skills/fd-vaas-brainstorm-koubo/` |
| `fd-vaas-video-creator` | 文案 → 口播视频 `.mp4` + `.srt` (TTS + 逐字字幕 + Remotion 渲染) | `/fd-vaas-video-creator` skill | scripts at `.claude/skills/fd-vaas-video-creator/scripts/`; outputs to `downloads/fd-videos/<slug>/` |
| `fd-vaas-publish` | one video → posts on many platforms (orchestrates `sau`) | `/fd-vaas-publish` skill | `publish.mjs` at `.claude/skills/fd-vaas-publish/scripts/` |
| `remotion-*` (7 skills) | scaffold / compose / render Remotion videos | `/remotion-create` etc. | skills at `.claude/skills/remotion-*`; project at `remotion-app/` |

Each skill's `SKILL.md` is the authoritative contract — read it before driving the tool. `officecli`
and `cap` are external CLIs (run `<cmd> --help` / `cap guide` instead of guessing flags). `ppt-master`
is a repo-specific workflow with a strict serial pipeline and `MUST`/`GATE` rules — do not treat it
as a generic code scaffold.

### VAAS mainline (the wired demand → post flow)

The `fd-vaas-*` skills are the mainline — they chain a demand all the way to a published post:

1. **`/fd-vaas-brainstorm-koubo`** (optional) — given a 赛道/主题, produces a 选题矩阵 (热点/痛点/争议/干货/人设),
   recommended 脚本框架 (黄金三秒 / SCQA / PREP / 故事钩子 / 清单体), 差异化角度, and an optional full 大纲.
2. **`/fd-vaas-video-creator`** — turns a 文案 into a finished 口播视频. Pipeline:
   `new-task → TTS (seed-tts-2.0, returns audio + official word-level timestamps) → fix-tts-timings
   (corrects fake Latin-token endMs) → preflight → Remotion render → <slug>.mp4 (+ .srt)`.
   Every artifact lands in `downloads/fd-videos/<slug>/`, managed by `task.json`. Visual layer can be
   existing assets, a seedance video, a seedream image, or a ppt master tape. **Must run `fix-tts-timings`**
   or subtitles flash and desync.
3. **`/fd-vaas-publish`** — one video → many platforms. **Only orchestrates**: reads per-platform
   preferences (accounts, tags, `BILIBILI_TID`, `TENCENT_SHORT_TITLE`, `YOUTUBE_VISIBILITY`, schedule)
   from `.env` once, assembles the correct `sau upload-video` per platform, shells out, and writes results
   back to `task.json`'s `distribution[]`. **Delegates all upload / cookie / browser work to `sau`** — never
   re-implements it. Use `publish.mjs --dry-run` to preview.

### Distribution engine (`social-auto-upload/`)

Unified CLI entry is **`sau`**, implemented entirely in `social-auto-upload/sau_cli.py`
(`build_parser()` → `main()`). `sau_cli.py` is the source of truth for subcommands — the vendored
`CLAUDE.md` is partly stale (it references a non-existent `cli_main.py` and a `sau skill install`
command that is not implemented). When in doubt, run `sau <platform> --help`.

Platforms and CLI maturity (from `sau_cli.py` `add_parser` calls + upstream README):

| Platform | `login`/`check` | `upload-video` | `upload-note` (图文) | Notes |
|---|---|---|---|---|
| `douyin` | ✅ | ✅ | ✅ | most complete; `--product-link`, dual-ratio thumbnails |
| `kuaishou` | ✅ | ✅ | ✅ | browser automation |
| `xiaohongshu` | ✅ | ✅ | ✅ | `SAU_XHS_CREATOR_BASE_URL` for overseas/RedNote |
| `bilibili` | ✅ | ✅ | ❌ | auto-downloads/updates `biliup`; `--tid` required; login best done by user in a real terminal |
| `tencent` (视频号) | ✅ | ✅ | ❌ | `tencent_uploader` |
| `youtube` | ✅ | ✅ | ❌ | interactive Google login; browser automation (not API — see README note on private-lock); `--playlist`, `--visibility`; set `YT_PROXY` in `conf.py` where youtube.com is blocked |

Per-platform implementations live in `social-auto-upload/uploader/<platform>_uploader/`.
Browser automation uses **`patchright`** (a stealth fork of Playwright), default **headless**.

## Common commands

### Distribution (`sau`) — run from `social-auto-upload/`

```bash
# one-time setup (registers the `sau` command)
cd social-auto-upload
uv venv && source .venv/bin/activate
uv pip install -e .
PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright" patchright install chromium   # CN mirror; drop env var otherwise

# usage — one account_name == one account file; metadata convention below
sau douyin login   --account <name>            # scan the QR png that gets generated
sau douyin check   --account <name>            # verify saved cookie still valid
sau douyin upload-video --account <name> --file videos/demo.mp4 --title "…" --desc "…" --tags a,b
sau douyin upload-note   --account <name> --images 1.png 2.png --title "…" --note "…" --tags a,b
sau douyin upload-video --account <name> --file … --schedule "2026-03-24 21:30"   # timed publish
```

If `sau` is not on PATH, run `python sau_cli.py <platform> <action> …` directly (no install needed).
`--debug`, `--headless`, `--headed` are independent dimensions; default is headless.

### Mainline (`fd-vaas-*`) — run from `VAAS/`

```bash
# 1. (optional) brainstorm topics + script outline for a 赛道
#    /fd-vaas-brainstorm-koubo <赛道>

# 2. 文案 → 口播视频 (one-shot: TTS → fix-tts-timings → preflight → render)
SKILL=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-video-creator/scripts
node $SKILL/new-task.mjs    --slug <slug> --script /path/to/script.txt [--width 1920 --height 1080]
node $SKILL/task-render.mjs --slug <slug> [--voice <id>] [--composition VoiceoverVideo]
# → downloads/fd-videos/<slug>/<slug>.mp4 (+ .srt)

# 3. one video → many platforms (reads .env; --dry-run to preview the sau commands)
SKILL=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-publish/scripts
node $SKILL/publish.mjs --slug <slug> --title "…" [--platforms douyin,xiaohongshu,bilibili] [--tags a,b] [--schedule "2026-07-20 21:30"]
```

### Tests

Tests are stdlib `unittest` (runnable via `unittest` or `pytest`) and live in
`social-auto-upload/tests/`. They mock the browser layer — no network/cookies needed.

```bash
cd social-auto-upload
python -m unittest discover -s tests          # all
python -m unittest tests.test_sau_bilibili_cli  # single module
python -m unittest tests.test_sau_bilibili_cli.BilibiliCliTests.test_build_parser_accepts_bilibili_login  # single test
```

### Legacy web app (not mainline)

Flask backend `social-auto-upload/sau_backend.py` (port 5409) + Vue/Vite frontend
`social-auto-upload/sau_frontend/` (port 5173). Retained by upstream but **not the current
mainline** — not guaranteed to run or stay in sync with the CLI. `requirements.txt` is the
historical web deps file; `pyproject.toml` is the mainline install entry.

## Architecture notes that span files

- **Account model**: an `account_name` is just a user-chosen label. Each maps to one persisted
  cookie/account file under `social-auto-upload/cookies/<platform>_uploader/`. Multiple accounts per
  platform are supported and can run concurrently. `account_name` is the unit of "different social
  media account" in the user's goal.
- **Metadata convention** (all browser platforms): video = `title + desc + tags`;
  note/图文 = `title + note + tags`. Pass `--schedule "YYYY-MM-DD HH:MM"` to switch a platform to
  its timed-publish strategy (omitted = immediate). Bilibili additionally requires `--tid`.
- **Publish strategies**: each uploader exposes `*_PUBLISH_STRATEGY_IMMEDIATE` /
  `*_PUBLISH_STRATEGY_SCHEDULED` constants; `sau_cli.py` selects based on `--schedule`.
- **QR-code logins** (douyin/kuaishou/xiaohongshu): generate a local PNG. Open/display that image
  for the user to scan — don't just print the path. Bilibili login should be run by the user in a
  real terminal (QR may render incomplete; fall back to `qrcode.png`).
- **Config**: `social-auto-upload/conf.py` (copy of `conf.example.py`) holds `BASE_DIR`,
  `LOCAL_CHROME_PATH`, `LOCAL_CHROME_HEADLESS`, `DEBUG_MODE`, and `YT_PROXY`. `XHS_SERVER` is
  legacy xhs-only. The `fd-vaas-*` skills read their own preferences from the project-root `.env`
  (see `.env.example`); per-task overrides go in `downloads/fd-videos/<slug>/.publish.env`.
- **Network / proxy gotchas** (this environment): the local HTTP proxy is `127.0.0.1:7892`
  (fallback `7890`) — set `http_proxy` (NOT `https_proxy`) for general use. But `patchright`'s
  chromium does **not** read the system proxy: for YouTube set `YT_PROXY` in `conf.py`, and the
  Playwright/patchright browser install itself needs `https_proxy` set explicitly to reach
  `cdn.playwright.dev`. Some hosts (`officecli.ai`, `raw.githubusercontent.com`) fail TLS through
  the proxy — bypass with `env -u http_proxy -u https_proxy`.
- **Creation → distribution handoff**: the `fd-vaas-*` mainline now wires this end-to-end
  (`fd-vaas-video-creator` produces `downloads/fd-videos/<slug>/<slug>.mp4`; `fd-vaas-publish` ships it).
  For ad-hoc uploads the asset path a creation skill produces is what you pass to
  `sau <platform> upload-video --file <path>`. PPTX decks are not directly uploadable as video; `cap`,
  `fd-vaas-video-creator`, or `ppt-master`'s export/render step is the bridge when a deck must become a
  publishable video.

# image generate
use skill `byted-ark-seedream-skill` for images, `byted-ark-seedance-skill` for video.

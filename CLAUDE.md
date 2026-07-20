# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What VAAS is

VAAS is a content-creation + multi-platform distribution workspace. The goal: take a content
demand, generate a **variable-type resource** (deck, document, screen-recording video, images),
then **publish it automatically to different social-media accounts** — and ideally produce a
*different* resource variant per platform/account. It is an orchestration layer over two halves:

1. **Creation skills** (this repo's `.claude/skills/` + `.agents/skills/`) — turn a demand into an asset file.
2. **Distribution engine** — `social-auto-upload/`, a vendored upstream project that uploads assets to social platforms via browser automation.

There is **no VAAS application code yet** — the workspace is a staging area wiring skills to a
distribution CLI. When the user says "make a resource and post it", the intended flow is:
*creation skill produces a file → `sau` CLI uploads it to one or more `account_name`s.*

## Repository shape — read this first

- The VAAS root is **not a git repository**. The only git repo is `social-auto-upload/`, which is a
  **vendored clone of `dreammis/social-auto-upload`** (origin: `https://github.com/dreammis/social-auto-upload.git`).
  Treat `social-auto-upload/` as a third-party dependency: prefer its own `social-auto-upload/CLAUDE.md`
  and `docs/` for its internals, and avoid editing it unless the task is specifically about that project.
- `git` commands run at the VAAS root will fail; `cd` into `social-auto-upload/` first.
- Skills live in two places:
  - `.claude/skills/` — project-scoped Claude Code skills: `cap`, `officecli`, and `ppt-master`
    (a symlink to `../../.agents/skills/ppt-master`).
  - `.agents/skills/ppt-master/` — the source of truth for the ppt-master skill (large SKILL.md + `workflows/`, `templates/`, `scripts/`, `references/`).
  - `social-auto-upload/skills/{douyin,kuaishou,xiaohongshu,bilibili}-upload/` — per-platform upload skills shipped by the upstream project.

## The two halves

### Creation skills (demand → asset file)

| Skill | Produces | Entry | Binary / location |
|---|---|---|---|
| `ppt-master` | SVG-deck → exported `.pptx` (multi-role pipeline: strategist → executor → QC) | `/ppt-master` skill | source at `.agents/skills/ppt-master/` |
| `officecli` | `.docx` / `.xlsx` / `.pptx` create+edit (L1 read → L2 DOM → L3 XML) | `/officecli` skill | `~/.local/bin/officecli` (global) |
| `cap` | screen recording / screenshots → `.mp4`/`.gif` + shareable upload link | `/cap` skill | `~/.local/bin/cap` (global) |

Each skill's `SKILL.md` is the authoritative contract — read it before driving the tool. `officecli`
and `cap` are external CLIs (run `<cmd> --help` / `cap guide` instead of guessing flags). `ppt-master`
is a repo-specific workflow with a strict serial pipeline and `MUST`/`GATE` rules — do not treat it
as a generic code scaffold.

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
  legacy xhs-only.
- **Network / proxy gotchas** (this environment): the local HTTP proxy is `127.0.0.1:7892`
  (fallback `7890`) — set `http_proxy` (NOT `https_proxy`) for general use. But `patchright`'s
  chromium does **not** read the system proxy: for YouTube set `YT_PROXY` in `conf.py`, and the
  Playwright/patchright browser install itself needs `https_proxy` set explicitly to reach
  `cdn.playwright.dev`. Some hosts (`officecli.ai`, `raw.githubusercontent.com`) fail TLS through
  the proxy — bypass with `env -u http_proxy -u https_proxy`.
- **Creation → distribution handoff**: creation skills emit concrete files (`.mp4`, `.pptx`, images).
  The distribution layer only consumes files + metadata — there is no shared in-repo glue code yet.
  When wiring a demand-to-post flow, the asset path produced by a creation skill is what you pass to
  `sau <platform> upload-video --file <path>`. PPTX decks are not directly uploadable as video; `cap`
  or `ppt-master`'s export/render step is the bridge when a deck must become a publishable video.


# image generate
use skill byted-ark-seedance-skill
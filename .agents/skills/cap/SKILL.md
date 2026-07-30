---
name: cap
description: Record the screen, capture screenshots, and export/upload video using the cap CLI (cap.so). Use when the user wants to record their screen or a window, take a screenshot, render a .cap project to mp4/gif, or get a shareable upload link.
---

# cap

Agent-friendly screen recording CLI from [cap.so](https://cap.so). Single binary bundled with Cap Desktop. Designed to be driven by automation and AI agents - add `--json` to any command for machine-readable output.

## Install

If `cap` is not installed:

```bash
curl -fsSL https://cap.so/install-cli.sh | sh
```

Verify with `cap --version`. Installs the binary to `~/.local/bin/cap` and Cap Desktop to `/Applications/Cap.app`. If still not found after install, open a new terminal or run `cap desktop install-cli`.

---

## Canonical workflow

**targets → record → export → upload.** A recording produces a `.cap` project directory; export renders it to a video file; upload returns a shareable link.

```bash
cap targets screens --json          # 1. find the screen/window id to capture
cap record start --screen 1 --detach --duration 30   # 2. record (background, 30s)
cap record stop                     # 3. finalize (if not auto-stopped by --duration)
cap export ./<recordingId>.cap out.mp4 --json         # 4. render to video
cap upload out.mp4 --name "Demo" --json               # 5. get a shareable link
```

Add `--json` for structured output. `record` and `export` stream newline-delimited JSON (NDJSON) events on stdout.

---

## Help system (IMPORTANT)

**When unsure about flags or output shape, run `cap guide` or `<cmd> --help` instead of guessing.** `cap guide` prints the official agent capability manifest; `cap guide --json` is the full machine-readable schema.

```bash
cap guide                 # Human-readable capability + JSON-schema manifest
cap guide --json          # Full machine-readable manifest (commands, env, exit codes)
cap record start --help   # Flags for a specific subcommand
cap --help                # Top-level command list
```

---

## Agent recording rule (no TTY)

**A non-interactive agent cannot run a foreground recording.** Recording without `--duration` requires either `--detach` or an interactive terminal. Always use `--detach`:

- `--detach --duration N` → auto-stops after N seconds; returns immediately with `recordingId`.
- `--detach` (no duration) → returns immediately; stop later with `cap record stop` (by `recordingId` or `--path`).

Foreground (interactive) emits `started` then `stopped` NDJSON events; success requires `recordingMetaExists:true`. With `--detach`, the stream emits only `started` (or `error`) and returns; the `stopped` event is delivered by `cap record stop`.

---

## Permissions & readiness (macOS)

**Run `cap doctor` first.** It reports capture readiness and exits 0 even when checks fail - branch on `ok` / `captureReady`, not on exit code.

```bash
cap doctor --json        # check screen-recording permission, ffmpeg, CLI install
```

Screen recording requires **Screen Recording permission** in System Settings → Privacy & Security. If not granted, `doctor` warns `screenRecordingPermission` and recording will fail. Camera/mic require their own permissions. `screenshot` of a screen/window also needs Screen Recording permission.

---

## Auth (for upload)

`cap upload` authenticates by reusing the Cap Desktop login automatically, OR via `CAP_API_KEY`. Check state:

```bash
cap auth status --json
```

For headless/CI, set `CAP_API_KEY` to a Cap auth key (from Cap Desktop Settings). `auth status` never prints the secret.

---

## Commands

### record

```bash
cap record start [OPTIONS]            # start a recording
cap record stop [--recording-id ID | --path PATH]   # finalize a detached recording
cap record status                     # list active/recent detached sessions
```

`record start` options:

| Flag | Description |
|------|-------------|
| `--screen <ID>` | Screen id to capture (from `cap targets screens`) |
| `--window <ID>` | Window id to capture (from `cap targets windows`) |
| `--mode <MODE>` | `studio` (default) or `instant` |
| `--camera <DEVICE_ID>` | Camera device id (from `cap targets cameras`) |
| `--mic <NAME>` | Microphone name (from `cap targets mics`) |
| `--system-audio` | Capture system audio |
| `--path <PATH>` | Save the `.cap` project here (default: `<recordingId>.cap` in cwd) |
| `--fps <N>` | Max fps (clamped 1-120) |
| `--duration <SEC>` | Auto-stop after N seconds |
| `--detach` | Background recording; stop later with `cap record stop` |

```bash
# Background 15s screen recording to a known path
cap record start --screen 1 --detach --duration 15 --path ./demo.cap --json

# Camera + mic, stop manually
cap record start --camera <deviceId> --mic <name> --detach --json
cap record stop --path ./demo.cap --json
```

### screenshot

```bash
cap screenshot --path <OUT> [--screen <ID> | --window <ID>] [--json]
```

Format inferred from extension (e.g. `.png`). JSON emits `{path, width, height}`.

```bash
cap screenshot --screen 1 --path ./shot.png --json
```

### export

Render a `.cap` project to a video file. Streams NDJSON progress (`{"type":"Progress",...}`, then `{"type":"Completed","path":"..."}` or `{"type":"Error","error":"..."}`).

```bash
cap export <PROJECT_PATH> [OUTPUT_PATH] [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `-o, --output <FILE>` | Output file (positional alternative) |
| `--format <F>` | Container: `mp4` (default), `gif`, `mov` - NOT the output mode |
| `--fps <N>` | Frames per second to render |
| `--resolution <WxH>` | e.g. `1920x1080` |
| `--quality <Q>` | mp4 only: `maximum`, `social`, `web`, `potato` |
| `--optimize-filesize` | Smaller files via CRF (mp4 only) |
| `--settings-json <JSON>` | Full export settings (mutually exclusive with flags above) |
| `--force-ffmpeg-decoder` | Decode source with FFmpeg instead of platform hardware |

```bash
cap export ./demo.cap ./demo.mp4 --format mp4 --quality social --resolution 1920x1080 --json
```

> **Casing exception:** export NDJSON uses PascalCase `type` tags and snake_case fields (`rendered_count`, `total_frames`) for desktop compatibility. Other `--json` output is camelCase.

### upload

Upload a `.cap` project or video file; returns a shareable link.

```bash
cap upload <FILE> [--name <TITLE>] [--export] [--video-id <ID>] [--json]
```

`--export` exports a `.cap` project to video first if no exported video exists yet. `--video-id` reuses an existing video id instead of creating a new one.

```bash
cap upload ./demo.mp4 --name "Feature demo" --json
```

### targets / devices

```bash
cap targets screens --json     # → id, name, fps, primary, size
cap targets windows --json     # → id, name, owner
cap targets cameras --json     # → deviceId, name
cap targets mics --json        # → name
```

(`cap record screens|windows|cameras|mics` are aliases.) Feed `id` (screen/window), `deviceId` (camera), and `name` (mic) back into `record`/`screenshot`.

### recordings / project / automations

```bash
cap recordings list [--dir <PATH>]      # list .cap recordings (desktop library or custom dir)
cap project inspect <PATH>              # metadata + editor config (RecordingMeta, snake_case)
cap project validate <PATH>             # verify metadata + media exist (exits non-zero if invalid)
cap project config get|set <PATH>       # read/replace project-config.json
cap automations list                    # automation rules from Cap Desktop (Settings > Automations)
```

### management

```bash
cap doctor                # environment + capture-readiness diagnostics
cap auth status           # upload auth state + source
cap version               # CLI version + execution context (distribution, bundled binaries)
cap desktop status        # is the `cap` shim installed and on PATH?
cap desktop install-cli   # install/repair the `cap` shim on PATH
cap update                # download latest Cap Desktop bundle + repair shim
cap selftest              # end-to-end diagnostics
cap completions <shell>   # bash/zsh/fish/powershell completion script
```

---

## Environment

| Variable | Used by | Description |
|----------|---------|-------------|
| `CAP_API_KEY` | upload | Overrides upload auth (Cap auth key from Settings). Optional when signed into Cap Desktop. |
| `CAP_SERVER_URL` | upload | Cap server base URL. Defaults to `https://cap.so`. |
| `CAP_NO_MODIFY_PATH` | desktop install-cli | Skip editing shell profiles / PATH during install. |
| `CAP_DESKTOP_FORCE_INSTALL` | install scripts, update | Force-replace Cap Desktop before linking the CLI. |

---

## Output & exit codes

- **stdout** is the authoritative result. JSON when `--json` (global) or `--format json` is set; stderr stays human-readable.
- **Errors** exit non-zero. In JSON mode a final object/event carries an `"error"` field; clap parse errors exit `2`.
- **Streaming:** `record` and `export` emit NDJSON events on stdout.
- Exit `0` = success (or a diagnostic ran - inspect `ok`/`valid`/`captureReady`). Exit `1` = runtime failure. Exit `2` = usage/parse error.

---

## Common pitfalls

| Pitfall | Correct approach |
|---------|-----------------|
| Foreground record hangs / fails in an agent | Use `--detach` (+ `--duration`, or `cap record stop`). No-TTY recording requires `--detach`. |
| Recording fails with permission error | Run `cap doctor`; grant Screen Recording (and Camera/Mic) permission in System Settings. |
| `cap record start` with no target | Pass `--screen` or `--window` (find ids via `cap targets screens\|windows`). |
| `--format` on export gives JSON, not mp4 | `--format` selects the **container** (mp4/gif/mov); use `--json` for machine-readable output. |
| Upload returns "not authenticated" | Sign in to Cap Desktop (CLI reuses its login) or set `CAP_API_KEY`. Check with `cap auth status`. |
| Guessing a flag or field name | Run `cap guide` / `<cmd> --help` instead of guessing. |
| Forgetting to finalize a detached recording | `cap record stop --path ./foo.cap` (or `--recording-id`); verify with `cap project validate`. |

---

## Notes

- A recording is a `.cap` **project directory**, not a video file. Export it (`cap export`) to get mp4/gif/mov, or let `cap upload --export` do it inline.
- `cap doctor` and `cap project validate` exit 0 even on failed checks - branch on the JSON `ok`/`valid`/`captureReady` field, not the exit code.
- `cap guide --json` is the canonical, always-current reference; prefer it over this file when flags may have changed.

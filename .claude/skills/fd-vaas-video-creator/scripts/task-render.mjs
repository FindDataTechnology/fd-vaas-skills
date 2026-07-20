#!/usr/bin/env node
/**
 * task-render.mjs
 *
 * 一支视频的端到端 pipeline，围绕 downloads/fd-videos/<slug>/ 目录跑：
 *
 *   1. 读 task.json + script.txt
 *   2. 调 TTS wrapper 生成音频 + 逐字字幕（保留原始 caption 到 captions-raw.json）
 *   3. 跑 fix-tts-timings.mjs → captions.json（修正 Latin token 假时长）
 *   4. 从 captions 算出 durationInFrames（+15 帧尾余量）
 *   5. 跑 preflight.mjs（音频/字幕/时长三方对齐）
 *   6. 调用 remotion render（合成 id 由 --composition 指定，默认 VoiceoverVideo）
 *   7. 把音频/字幕/成片都拷进 task 目录，并回写 task.json + append history.md
 *
 * 用法:
 *   node task-render.mjs --slug finddata-intro \
 *     [--voice zh_female_gaolengyujie_uranus_bigtts] \
 *     [--composition VoiceoverVideo | IntroduceOrg | ...] \
 *     [--extra-props '{"videoSrc":"bg.mp4"}']  # 追加到 render props
 *
 * 前置:
 *   - byted-ark-tts-skill 已可用（.env 里有 VOL_AGENT_API_KEY 等）
 *   - remotion-app 已 setup（见 references/setup.md）
 */
import fs from "fs";
import path from "path";
import { execSync, spawnSync } from "child_process";

const args = process.argv.slice(2);
function getArg(k) {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
}

const slug = getArg("--slug");
const voice = getArg("--voice");
const composition = getArg("--composition") ?? "VoiceoverVideo";
const extraProps = getArg("--extra-props");
if (!slug) {
  console.error("Usage: --slug <name> [--voice id] [--composition id] [--extra-props JSON]");
  process.exit(1);
}

const VAAS = "/Users/chengsishi/VAAS";
const TASK_DIR = path.join(VAAS, "downloads/fd-videos", slug);
const REMOTION = path.join(VAAS, "remotion-app");
const PUBLIC = path.join(REMOTION, "public");
const SKILL = path.join(VAAS, ".claude/skills/fd-vaas-video-creator");
const TTS_WRAPPER = path.join(
  VAAS,
  ".claude/skills/byted-ark-tts-skill/scripts/tts-wrapper.js",
);

if (!fs.existsSync(TASK_DIR)) {
  console.error(`❌ task dir not found: ${TASK_DIR}. Run new-task.mjs first.`);
  process.exit(1);
}

const manifestPath = path.join(TASK_DIR, "task.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
const scriptPath = path.join(TASK_DIR, "script.txt");
const script = fs.readFileSync(scriptPath, "utf8").trim();

// -------- 1. TTS --------
console.log("🎤 [1/6] TTS…");
const ttsArgs = ["node", TTS_WRAPPER, "--text", script];
if (voice) ttsArgs.push("--voice", voice);
const ttsRes = spawnSync(ttsArgs[0], ttsArgs.slice(1), {
  cwd: REMOTION,
  encoding: "utf8",
});
if (ttsRes.status !== 0) {
  console.error(ttsRes.stderr || ttsRes.stdout);
  process.exit(ttsRes.status || 1);
}
process.stdout.write(ttsRes.stdout);

// Find the most recent Ark-TTS output (matches generate-voiceover.mjs logic)
function findLatestArkTTS() {
  const home = process.env.HOME;
  const candidates = [
    path.join(home, "Desktop/Ark-TTS"),
    path.join(home, "Ark-TTS"),
  ];
  let newest = null, newestTime = 0;
  for (const base of candidates) {
    if (!fs.existsSync(base)) continue;
    for (const d of fs.readdirSync(base)) {
      const full = path.join(base, d);
      if (!fs.statSync(full).isDirectory()) continue;
      const m = fs.statSync(full).mtimeMs;
      if (m > newestTime) { newestTime = m; newest = full; }
    }
  }
  return newest;
}
const arkDir = findLatestArkTTS();
if (!arkDir) throw new Error("could not locate Ark-TTS output dir");
const files = fs.readdirSync(arkDir);
const audioFile = files.find((f) => f.endsWith(".mp3") || f.endsWith(".wav"));
const captionsFile = files.includes("captions.json") ? "captions.json" : null;
if (!audioFile) throw new Error("no audio in Ark-TTS dir: " + arkDir);
if (!captionsFile) throw new Error("no captions.json — did TTS run with enable_subtitle?");

// Copy TTS artifacts into the task dir
const audioName = "voiceover" + path.extname(audioFile);
fs.copyFileSync(path.join(arkDir, audioFile), path.join(TASK_DIR, audioName));
fs.copyFileSync(
  path.join(arkDir, captionsFile),
  path.join(TASK_DIR, "captions-raw.json"),
);

// -------- 2. Fix Latin-token timings --------
console.log("🔧 [2/6] fix-tts-timings…");
spawnSync(
  "node",
  [
    path.join(SKILL, "scripts/fix-tts-timings.mjs"),
    "--in",
    path.join(TASK_DIR, "captions-raw.json"),
    "--out",
    path.join(TASK_DIR, "captions.json"),
  ],
  { stdio: "inherit" },
);

// -------- 3. Compute duration --------
const caps = JSON.parse(
  fs.readFileSync(path.join(TASK_DIR, "captions.json"), "utf8"),
);
const lastEndMs = caps[caps.length - 1].endMs;
const fps = manifest.video.fps;
const durationInFrames = Math.ceil((lastEndMs / 1000) * fps) + 15;
console.log(`⏱️  [3/6] duration: ${lastEndMs}ms → ${durationInFrames} frames`);

// -------- 4. Copy audio/captions into remotion-app/public/ (with task slug) --------
const publicAudio = `${slug}-voiceover${path.extname(audioFile)}`;
const publicCaps = `${slug}-captions.json`;
fs.copyFileSync(path.join(TASK_DIR, audioName), path.join(PUBLIC, publicAudio));
fs.copyFileSync(
  path.join(TASK_DIR, "captions.json"),
  path.join(PUBLIC, publicCaps),
);

// -------- 5. Preflight --------
console.log("🩺 [4/6] preflight…");
const pre = spawnSync(
  "node",
  [
    path.join(SKILL, "scripts/preflight.mjs"),
    "--audio",
    path.join(PUBLIC, publicAudio),
    "--captions",
    path.join(PUBLIC, publicCaps),
    "--frames",
    String(durationInFrames),
    "--fps",
    String(fps),
  ],
  { stdio: "inherit" },
);
if (pre.status !== 0) {
  console.error("preflight failed — aborting render");
  process.exit(pre.status);
}

// -------- 6. Render --------
console.log("🎬 [5/6] render…");
const outMp4 = path.join(TASK_DIR, `${slug}.mp4`);
const props = {
  audioSrc: publicAudio,
  captionsSrc: publicCaps,
  durationInFrames,
  width: manifest.video.width,
  height: manifest.video.height,
  ...(extraProps ? JSON.parse(extraProps) : {}),
};
const renderRes = spawnSync(
  "npx",
  [
    "remotion",
    "render",
    composition,
    outMp4,
    `--props=${JSON.stringify(props)}`,
  ],
  { cwd: REMOTION, stdio: "inherit" },
);
if (renderRes.status !== 0) process.exit(renderRes.status);

// -------- 7. Update manifest + history --------
console.log("📝 [6/6] updating manifest…");
manifest.status = "rendered";
manifest.tts = {
  ...manifest.tts,
  voice: voice ?? manifest.tts.voice,
  audio: audioName,
  captions: "captions.json",
  captionsRaw: "captions-raw.json",
  audioDurationSec: lastEndMs / 1000,
  tokenCount: caps.length,
};
manifest.render = {
  composition,
  durationInFrames,
  output: `${slug}.mp4`,
  props,
};
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

const now = new Date().toISOString();
fs.appendFileSync(
  path.join(TASK_DIR, "history.md"),
  `- ${now} — rendered ${slug}.mp4 (${composition}, ${durationInFrames}f, ${manifest.video.width}×${manifest.video.height}, voice=${voice ?? "default"})\n`,
);

console.log(`\n✅ done → ${outMp4}`);

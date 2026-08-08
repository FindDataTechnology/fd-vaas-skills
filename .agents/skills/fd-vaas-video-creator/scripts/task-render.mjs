#!/usr/bin/env node
/**
 * task-render.mjs — 视频类型 pipeline 解释器
 *
 * 一支视频的端到端 pipeline，围绕 downloads/fd-videos/<slug>/ 目录跑。
 * pipeline 由「视频类型」决定：
 *   - task.json 带 type → 查 types/<id>/type.json 的 pipeline 数组，按序执行
 *   - 不带 type → 兼容旧行为：视为 voiceover，
 *     tts → fix-tts-timings → preflight → render（与旧版逐步一致）
 *
 * 内置步骤（BUILTIN_STEPS）:
 *   tts              调 TTS wrapper → voiceover.mp3 + captions-raw.json（落 task 目录）
 *   fix-tts-timings  修正 Latin token 假时长 → captions.json；由字幕推导
 *                    durationInFrames（+tailPad 尾余量）；音频/字幕拷到
 *                    remotion-app/public/（带 slug 前缀）
 *   preflight        音频/字幕/时长三方对齐校验，失败即中止
 *   scene-align      由字幕时间戳推导 Sequence 分段 → <slug>-scenes.json
 *                    拷到 remotion-app/public/，props 注入 scenesSrc
 *                    （参数取 type.defaults 的 gapMs/minSegmentMs/padFrames）
 *   render           组装 props → remotion render → 回写 task.json + history.md
 *
 * 类型可带 types/<id>/steps.mjs（default export {步骤名: (ctx) => ctx}），
 * 覆盖同名内置步骤或提供全新步骤（如 screen-recording 的 ingest）。
 *
 * ctx 约定（步骤签名统一 (ctx) => ctx）:
 *   { slug, taskDir, manifestPath, task (=task.json 对象), type, fps,
 *     voice, composition, tailPad, extraProps, props, log,
 *     ...步骤间累积字段（audioName/caps/durationInFrames/publicAudio 等） }
 *
 * 用法:
 *   node task-render.mjs --slug finddata-intro \
 *     [--voice zh_female_gaolengyujie_uranus_bigtts] \
 *     [--composition VoiceoverVideo]               # 覆盖类型默认 composition
 *     [--extra-props '{"videoSrc":"bg.mp4"}']      # 最高优先级，追加/覆盖 render props
 *
 * props 优先级: type.defaults（非保留键）< 类型输入（<key>Src / 原值）
 *              < 计算值（audioSrc/captionsSrc/durationInFrames/width/height）
 *              < pipeline 注入（ctx.renderProps，如 scenesSrc）< --extra-props
 *
 * 前置:
 *   - TTS 生成器已可用（.env 里有 VOL_AGENT_API_KEY 等）
 *   - remotion-app 已 setup（见 references/setup.md）
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";
import {
  getType,
  listTypes,
  registryErrors,
  loadTypeSteps,
} from "./types/registry.mjs";

const args = process.argv.slice(2);
function getArg(k) {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
}

const slug = getArg("--slug");
const voiceArg = getArg("--voice");
const compositionArg = getArg("--composition");
const extraPropsArg = getArg("--extra-props");
if (!slug) {
  console.error("Usage: --slug <name> [--voice id] [--composition id] [--extra-props JSON]");
  process.exit(1);
}

const VAAS = process.env.VAAS_ROOT ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const TASK_DIR = path.join(VAAS, "downloads/fd-videos", slug);
const REMOTION = path.join(VAAS, "remotion-app");
const PUBLIC = path.join(REMOTION, "public");
const SKILL = path.join(VAAS, ".agents/skills/fd-vaas-video-creator");
const TTS_WRAPPER = path.join(SKILL, "scripts/generators/tts-wrapper.js");

if (!fs.existsSync(TASK_DIR)) {
  console.error(`❌ task dir not found: ${TASK_DIR}. Run new-task.mjs first.`);
  process.exit(1);
}

const manifestPath = path.join(TASK_DIR, "task.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

// ---------- 类型解析 ----------
// 无 type 的旧任务视为 voiceover；类型尚未注册（老仓库）时退回内置默认 pipeline。
const DEFAULT_TYPE = "voiceover";
const DEFAULT_PIPELINE = ["tts", "fix-tts-timings", "preflight", "render"];
// defaults 里的保留键由 pipeline 消费，不透传到 render props
const RESERVED_DEFAULT_KEYS = new Set([
  "voice",
  "tailPad",
  "gapMs",
  "minSegmentMs",
  "padFrames",
]);

for (const e of registryErrors()) {
  console.warn(`⚠️  非法类型定义被跳过: ${e.path}`);
  for (const msg of e.errors) console.warn(`   - ${msg}`);
}

const typeId = manifest.type ?? DEFAULT_TYPE;
let type = getType(typeId);
if (!type && manifest.type) {
  console.error(`❌ 未知视频类型 "${manifest.type}"（task.json.type）`);
  const avail = listTypes().map((t) => t.id);
  console.error(
    avail.length
      ? `   可用类型: ${avail.join(", ")}`
      : "   （types/ 下还没有注册任何视频类型）",
  );
  console.error("   查看详情: node .agents/skills/fd-vaas-video-creator/scripts/types/list.mjs");
  process.exit(1);
}
if (!type) {
  // voiceover type.json 还没注册（老仓库）→ 内置默认 pipeline，行为与旧版一致
  type = null;
}

const pipeline = type?.pipeline ?? DEFAULT_PIPELINE;
// composition 优先级: CLI --composition > type.composition > "VoiceoverVideo"
const composition = compositionArg ?? type?.composition ?? "VoiceoverVideo";
// defaults.voice = "auto" 表示交给 TTS wrapper 默认音色
const voice =
  voiceArg ??
  (type?.defaults?.voice && type.defaults.voice !== "auto"
    ? type.defaults.voice
    : null);
const tailPad = type?.defaults?.tailPad ?? 15;

const ctx = {
  slug,
  VAAS,
  REMOTION,
  PUBLIC,
  SKILL,
  TTS_WRAPPER,
  taskDir: TASK_DIR,
  manifestPath,
  task: manifest,
  type,
  fps: manifest.video.fps,
  voice,
  composition,
  tailPad,
  extraProps: extraPropsArg ? JSON.parse(extraPropsArg) : {},
  renderProps: {}, // pipeline 步骤注入的渲染 props（如 scene-align 的 scenesSrc）
  props: {},
  log: (m) => console.log(m),
};

// ---------- 内置步骤 ----------
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

/** tts: TTS wrapper → voiceover.mp3 + captions-raw.json 落 task 目录 */
function stepTts(ctx) {
  const scriptPath = path.join(ctx.taskDir, "script.txt");
  if (!fs.existsSync(scriptPath)) {
    console.error(`❌ script.txt 不存在于 ${ctx.taskDir}（tts 步骤需要口播稿）`);
    process.exit(1);
  }
  const script = fs.readFileSync(scriptPath, "utf8").trim();

  console.log("🎤 TTS…");
  const ttsArgs = [ctx.TTS_WRAPPER, "--text", script];
  if (ctx.voice) ttsArgs.push("--voice", ctx.voice);
  const ttsRes = spawnSync("node", ttsArgs, { cwd: ctx.REMOTION, encoding: "utf8" });
  if (ttsRes.status !== 0) {
    console.error(ttsRes.stderr || ttsRes.stdout);
    process.exit(ttsRes.status || 1);
  }
  process.stdout.write(ttsRes.stdout);

  const arkDir = findLatestArkTTS();
  if (!arkDir) throw new Error("could not locate Ark-TTS output dir");
  const files = fs.readdirSync(arkDir);
  const audioFile = files.find((f) => f.endsWith(".mp3") || f.endsWith(".wav"));
  const captionsFile = files.includes("captions.json") ? "captions.json" : null;
  if (!audioFile) throw new Error("no audio in Ark-TTS dir: " + arkDir);
  if (!captionsFile) throw new Error("no captions.json — did TTS run with enable_subtitle?");

  ctx.audioExt = path.extname(audioFile);
  ctx.audioName = "voiceover" + ctx.audioExt;
  fs.copyFileSync(path.join(arkDir, audioFile), path.join(ctx.taskDir, ctx.audioName));
  fs.copyFileSync(
    path.join(arkDir, captionsFile),
    path.join(ctx.taskDir, "captions-raw.json"),
  );
  return ctx;
}

/** fix-tts-timings: 修正字幕 → 推导总帧数 → 音频/字幕拷进 remotion-app/public/ */
function stepFixTtsTimings(ctx) {
  console.log("🔧 fix-tts-timings…");
  spawnSync(
    "node",
    [
      path.join(ctx.SKILL, "scripts/fix-tts-timings.mjs"),
      "--in",
      path.join(ctx.taskDir, "captions-raw.json"),
      "--out",
      path.join(ctx.taskDir, "captions.json"),
    ],
    { stdio: "inherit" },
  );

  ctx.caps = JSON.parse(
    fs.readFileSync(path.join(ctx.taskDir, "captions.json"), "utf8"),
  );
  ctx.lastEndMs = ctx.caps[ctx.caps.length - 1].endMs;
  ctx.durationInFrames = Math.ceil((ctx.lastEndMs / 1000) * ctx.fps) + ctx.tailPad;
  console.log(`⏱️  duration: ${ctx.lastEndMs}ms → ${ctx.durationInFrames} frames`);

  ctx.publicAudio = `${ctx.slug}-voiceover${ctx.audioExt}`;
  ctx.publicCaps = `${ctx.slug}-captions.json`;
  fs.copyFileSync(
    path.join(ctx.taskDir, ctx.audioName),
    path.join(ctx.PUBLIC, ctx.publicAudio),
  );
  fs.copyFileSync(
    path.join(ctx.taskDir, "captions.json"),
    path.join(ctx.PUBLIC, ctx.publicCaps),
  );
  return ctx;
}

/** preflight: 音频/字幕/时长三方对齐，失败即中止 */
function stepPreflight(ctx) {
  console.log("🩺 preflight…");
  const pre = spawnSync(
    "node",
    [
      path.join(ctx.SKILL, "scripts/preflight.mjs"),
      "--audio",
      path.join(ctx.PUBLIC, ctx.publicAudio),
      "--captions",
      path.join(ctx.PUBLIC, ctx.publicCaps),
      "--frames",
      String(ctx.durationInFrames),
      "--fps",
      String(ctx.fps),
    ],
    { stdio: "inherit" },
  );
  if (pre.status !== 0) {
    console.error("preflight failed — aborting render");
    process.exit(pre.status);
  }
  return ctx;
}

/** scene-align: 字幕时间戳 → Sequence 分段 JSON → props.scenesSrc */
function stepSceneAlign(ctx) {
  console.log("🧭 scene-align…");
  const pubName = `${ctx.slug}-scenes.json`;
  const d = ctx.type?.defaults ?? {};
  const sceneArgs = [
    path.join(ctx.SKILL, "scripts/scene-align.mjs"),
    "--captions",
    path.join(ctx.taskDir, "captions.json"),
    "--fps",
    String(ctx.fps),
    "--gap-ms",
    String(d.gapMs ?? 300),
    "--min-seg-ms",
    String(d.minSegmentMs ?? 1500),
    "--pad-frames",
    String(d.padFrames ?? 0),
    "--out",
    path.join(ctx.PUBLIC, pubName),
  ];
  // script.txt 存在时传入：有 ## 标记走显式分段，无标记自动分段
  const scriptPath = path.join(ctx.taskDir, "script.txt");
  if (fs.existsSync(scriptPath)) sceneArgs.push("--script", scriptPath);
  const res = spawnSync("node", sceneArgs, { stdio: "inherit" });
  if (res.status !== 0) process.exit(res.status || 1);
  ctx.renderProps.scenesSrc = pubName;
  return ctx;
}

/** render: 组装 props → remotion render → 回写 task.json + history.md */
function stepRender(ctx) {
  const { task } = ctx;
  console.log("🎬 render…");
  const outMp4 = path.join(ctx.taskDir, `${ctx.slug}.mp4`);

  // 类型 defaults（非保留键）→ 最低优先级 props
  const defaultProps = {};
  for (const [k, v] of Object.entries(ctx.type?.defaults ?? {})) {
    if (!RESERVED_DEFAULT_KEYS.has(k)) defaultProps[k] = v;
  }
  // 类型输入 → props：file/json 拷到 public 并以 <key>Src 传引用；text/enum 传原值
  const inputProps = {};
  for (const [key, inp] of Object.entries(ctx.type?.inputs ?? {})) {
    const val = task.inputs?.[key];
    if (val === undefined || key === "script" || key === "orientation") continue;
    if (inp.type === "file" || inp.type === "json") {
      const src = path.join(ctx.taskDir, val);
      if (!fs.existsSync(src)) {
        console.error(`❌ 输入文件缺失: ${src}（task.json.inputs.${key}）`);
        process.exit(1);
      }
      const pubName = `${ctx.slug}-${key}${path.extname(val)}`;
      fs.copyFileSync(src, path.join(ctx.PUBLIC, pubName));
      inputProps[`${key}Src`] = pubName;
    } else {
      inputProps[key] = val;
    }
  }

  ctx.props = {
    ...defaultProps,
    ...inputProps,
    audioSrc: ctx.publicAudio,
    captionsSrc: ctx.publicCaps,
    durationInFrames: ctx.durationInFrames,
    width: task.video.width,
    height: task.video.height,
    ...ctx.renderProps,
    ...ctx.extraProps,
  };

  const renderRes = spawnSync(
    "npx",
    [
      "remotion",
      "render",
      ctx.composition,
      outMp4,
      `--props=${JSON.stringify(ctx.props)}`,
    ],
    { cwd: ctx.REMOTION, stdio: "inherit" },
  );
  if (renderRes.status !== 0) process.exit(renderRes.status);

  console.log("📝 updating manifest…");
  task.status = "rendered";
  task.tts = {
    ...task.tts,
    voice: ctx.voice ?? task.tts?.voice ?? null,
    audio: ctx.audioName,
    captions: "captions.json",
    captionsRaw: "captions-raw.json",
    audioDurationSec: ctx.lastEndMs / 1000,
    tokenCount: ctx.caps.length,
  };
  task.render = {
    composition: ctx.composition,
    durationInFrames: ctx.durationInFrames,
    output: `${ctx.slug}.mp4`,
    props: ctx.props,
  };
  fs.writeFileSync(ctx.manifestPath, JSON.stringify(task, null, 2) + "\n");

  const now = new Date().toISOString();
  fs.appendFileSync(
    path.join(ctx.taskDir, "history.md"),
    `- ${now} — rendered ${ctx.slug}.mp4 (${ctx.composition}, ${ctx.durationInFrames}f, ${task.video.width}×${task.video.height}, voice=${ctx.voice ?? "default"})\n`,
  );

  console.log(`\n✅ done → ${outMp4}`);
  return ctx;
}

const BUILTIN_STEPS = {
  tts: stepTts,
  "fix-tts-timings": stepFixTtsTimings,
  preflight: stepPreflight,
  "scene-align": stepSceneAlign,
  render: stepRender,
};

// ---------- 执行 pipeline ----------
const customSteps = type ? await loadTypeSteps(type) : {};
const runnable = {};
for (const name of pipeline) {
  const fn = customSteps[name] ?? BUILTIN_STEPS[name];
  if (typeof fn !== "function") {
    console.error(
      `❌ pipeline 含未知步骤 "${name}"${type ? `（类型 "${type.id}"）` : ""}`,
    );
    console.error(`   内置步骤: ${Object.keys(BUILTIN_STEPS).join(", ")}`);
    console.error(
      `   自定义步骤: ${
        Object.keys(customSteps).length
          ? Object.keys(customSteps).join(", ")
          : "（无 — 可在 types/<id>/steps.mjs 的 default export 提供）"
      }`,
    );
    process.exit(1);
  }
  runnable[name] = fn;
}

console.log(
  `🧩 type: ${type ? `${type.id}（${type.name}）` : "voiceover（默认，兼容旧任务）"}`,
);
console.log(`🪜 pipeline: ${pipeline.join(" → ")}\n`);

for (let i = 0; i < pipeline.length; i++) {
  const name = pipeline[i];
  console.log(`▶  [${i + 1}/${pipeline.length}] ${name}`);
  await runnable[name](ctx);
}

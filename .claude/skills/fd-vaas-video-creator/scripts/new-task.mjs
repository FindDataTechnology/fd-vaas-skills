#!/usr/bin/env node
/**
 * new-task.mjs
 *
 * 为一支新视频创建结构化的 task 目录。所有产物、脚本、字幕、manifest
 * 都放在一起,后续 agent / 人类都能凭 slug 找到全套素材。
 *
 * 目录约定:
 *   downloads/fd-videos/<slug>/
 *   ├── task.json         # 结构化 manifest(voice, dims, timings)
 *   ├── script.txt        # 口播稿原文
 *   ├── voiceover.mp3     # TTS 产物
 *   ├── captions.json     # TTS 官方逐字时间戳(已修正)
 *   ├── captions-raw.json # TTS 原始返回(未修正,存档用)
 *   ├── captions.srt      # 软字幕(可选)
 *   ├── <slug>.mp4        # 最终成片
 *   └── history.md        # 每次改动的 append-only 记录
 *
 * 用法:
 *   node new-task.mjs --slug finddata-intro --script /path/to/script.txt \
 *                     [--width 1920] [--height 1080] [--voice zh_female_...]
 */
import fs from "fs";
import path from "path";

const args = process.argv.slice(2);
function getArg(k) {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
}

const slug = getArg("--slug");
const scriptPath = getArg("--script");
const width = Number(getArg("--width") ?? 1080);
const height = Number(getArg("--height") ?? 1920);
const voice = getArg("--voice") ?? null;

if (!slug || !scriptPath) {
  console.error(
    "Usage: node new-task.mjs --slug <name> --script <script.txt> [--width w --height h --voice id]",
  );
  process.exit(1);
}
if (!/^[a-z0-9][a-z0-9-]*$/.test(slug)) {
  console.error(`❌ slug must be [a-z0-9-], got: "${slug}"`);
  process.exit(1);
}

const ROOT = "/Users/chengsishi/VAAS/downloads/fd-videos";
const dir = path.join(ROOT, slug);
if (fs.existsSync(dir)) {
  console.error(`❌ task dir already exists: ${dir}`);
  process.exit(1);
}
fs.mkdirSync(dir, { recursive: true });

// Copy script
const scriptDest = path.join(dir, "script.txt");
fs.copyFileSync(scriptPath, scriptDest);

// Manifest — the canonical source of truth
const manifest = {
  slug,
  createdAt: new Date().toISOString(),
  status: "draft", // draft | voiced | rendered | published
  script: "script.txt",
  video: { width, height, fps: 30 },
  tts: {
    model: "seed-tts-2.0",
    voice, // filled after TTS
    audio: null, // "voiceover.mp3"
    captions: null, // "captions.json"
    captionsRaw: null, // "captions-raw.json"
    audioDurationSec: null,
    tokenCount: null,
    fixedLatinTokens: 0,
  },
  render: {
    composition: null, // e.g. "IntroduceOrg" or "VoiceoverVideo"
    durationInFrames: null,
    output: null, // "<slug>.mp4"
  },
  distribution: [], // [{platform, account, uploadedAt, url}]
};
fs.writeFileSync(
  path.join(dir, "task.json"),
  JSON.stringify(manifest, null, 2) + "\n",
);

// History log — append-only, human-readable
const now = new Date().toISOString();
fs.writeFileSync(
  path.join(dir, "history.md"),
  `# ${slug} — history\n\n- ${now} — task created (${width}×${height})\n`,
);

console.log(`✅ task scaffolded: ${dir}`);
console.log(`   script.txt copied from ${scriptPath}`);
console.log(`   task.json + history.md initialised`);
console.log(`\nNext:`);
console.log(`  1. TTS  : generate voiceover -> voiceover.mp3 + captions-raw.json`);
console.log(`  2. fix  : fix-tts-timings.mjs --in captions-raw.json --out captions.json`);
console.log(`  3. update task.json (tts.*)`);
console.log(`  4. render: --props='{"audioSrc":"...","captionsSrc":"...", ...}'`);
console.log(`  5. update task.json (render.*)`);

#!/usr/bin/env node
/**
 * preflight.mjs
 *
 * 渲染前的一次性体检：捕捉这次会议踩过的三个坑。
 *
 *   1. mp3 时长 vs 传入的 durationInFrames 差 > 0.5s（可用 --cover-frames 减去封面）
 *   2. captions.json 里存在 dur < 100ms & gap > 100ms 的 Latin token 假时长
 *   3. captions 最后一个 endMs 超过 mp3 时长 > 100ms（说明字幕/音频不是一对）
 *
 * 用法:
 *   node preflight.mjs --audio public/x.mp3 --captions public/x.json --frames 2461 [--fps 30] [--cover-frames 60]
 *   非 0 退出 = 至少一项检查失败。
 */
import fs from "fs";
import { execSync } from "child_process";

const args = process.argv.slice(2);
function getArg(k) {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
}

const audio = getArg("--audio");
const captions = getArg("--captions");
const frames = Number(getArg("--frames"));
const fps = Number(getArg("--fps") ?? 30);
const coverFrames = Number(getArg("--cover-frames") ?? 0);
if (!audio || !captions || !frames) {
  console.error(
    "Usage: node preflight.mjs --audio <mp3> --captions <json> --frames <n> [--fps 30] [--cover-frames 0]",
  );
  process.exit(1);
}

const errors = [];

// 1. mp3 duration vs frames
const audioDur = Number(
  execSync(
    `ffprobe -v error -show_entries format=duration -of csv=p=0 "${audio}"`,
  )
    .toString()
    .trim(),
);
const compDur = frames / fps;
const narrationDur = (frames - coverFrames) / fps; // 讲解正片时长(减去封面)
const drift = Math.abs(narrationDur - audioDur);
if (drift > 0.5) {
  errors.push(
    `duration drift: narration ${narrationDur.toFixed(2)}s (${frames}f - cover ${coverFrames}f) vs audio ${audioDur.toFixed(2)}s (Δ=${drift.toFixed(2)}s > 0.5s)`,
  );
}

// 2. Latin-token fake timestamps
const caps = JSON.parse(fs.readFileSync(captions, "utf8"));
const suspects = [];
for (let i = 0; i < caps.length - 1; i++) {
  const dur = caps[i].endMs - caps[i].startMs;
  const gap = caps[i + 1].startMs - caps[i].endMs;
  if (dur < 100 && gap > 100) suspects.push({ i, ...caps[i], gap });
}
if (suspects.length) {
  const first = suspects.slice(0, 3).map((s) => `"${s.text}" (dur=${s.endMs - s.startMs}ms, gap=${s.gap}ms)`).join(", ");
  errors.push(
    `${suspects.length} Latin token(s) with fake short endMs — run fix-tts-timings.mjs first. First: ${first}`,
  );
}

// 3. captions endMs vs audio duration
const lastEnd = caps[caps.length - 1].endMs / 1000;
if (lastEnd > audioDur + 0.1) {
  errors.push(
    `captions extend past audio: last endMs=${lastEnd.toFixed(2)}s > audio ${audioDur.toFixed(2)}s`,
  );
}

console.log(`audio       : ${audioDur.toFixed(2)}s`);
console.log(`composition : ${compDur.toFixed(2)}s (${frames}f @ ${fps}fps${coverFrames ? `, cover ${coverFrames}f` : ""})`);
console.log(`captions    : ${caps.length} tokens, ends at ${lastEnd.toFixed(2)}s`);
console.log(`suspect tokens: ${suspects.length}`);

if (errors.length) {
  console.error(`\n❌ ${errors.length} preflight error(s):`);
  errors.forEach((e) => console.error(`  - ${e}`));
  process.exit(1);
}
console.log("\n✅ preflight ok");

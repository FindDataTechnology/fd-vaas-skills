#!/usr/bin/env node
/**
 * captions-to-srt.mjs
 *
 * 把 @remotion/captions 的 Caption[] JSON 转成标准 .srt 字幕文件。
 * 用于平台软字幕或人工校对。
 *
 * 用法:
 *   node scripts/captions-to-srt.mjs --json public/captions-x.json --out out/name.srt
 */

import fs from "fs";

const args = process.argv.slice(2);
function getArg(key) {
  const i = args.indexOf(key);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
}

const jsonPath = getArg("--json");
const out = getArg("--out") || "captions.srt";

if (!jsonPath) {
  console.error("Usage: --json <captions.json> --out <out.srt>");
  process.exit(1);
}

const captions = JSON.parse(fs.readFileSync(jsonPath, "utf8"));

function pad(n, len) {
  return String(n).padStart(len, "0");
}

function fmt(ms) {
  const totalMs = Math.max(0, Math.round(ms));
  const h = Math.floor(totalMs / 3600000);
  const m = Math.floor((totalMs % 3600000) / 60000);
  const s = Math.floor((totalMs % 60000) / 1000);
  const msec = totalMs % 1000;
  return `${pad(h, 2)}:${pad(m, 2)}:${pad(s, 2)},${pad(msec, 3)}`;
}

let srt = "";
captions.forEach((c, i) => {
  const text = (c.text ?? "").replace(/\s+/g, " ").trim();
  if (!text) return;
  srt += `${i + 1}\n${fmt(c.startMs)} --> ${fmt(c.endMs)}\n${text}\n\n`;
});

fs.writeFileSync(out, srt.trim() + "\n");
console.log(`✅ ${captions.length} entries -> ${out}`);

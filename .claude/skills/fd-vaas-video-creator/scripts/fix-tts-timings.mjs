#!/usr/bin/env node
/**
 * fix-tts-timings.mjs
 *
 * 修复 seed-tts-2.0 官方 captions.json 里英文/字母 token 的假时长。
 *
 * 现象:形如 `FindDataTechnology,` / `fd-cn-gov,` / `github.com/...` /
 *      `Star、` 这些 Latin token，接口只标 30-45ms 的 endMs，但实际读音
 *      要 2-3 秒。字幕会闪一下就消失，和声音对不上。
 *
 * 修法:每个 token 的 endMs 延伸到下一个 token 的 startMs。TTS 内字与字
 *      之间没有真空隙，只有句间停顿，所以这样安全，不会把字幕拖到下一
 *      句音频上面。最后一个 token 保留原 endMs。
 *
 * 用法:
 *   node fix-tts-timings.mjs --in public/captions-x.json [--out public/captions-x-fixed.json]
 *   # 不传 --out 就原地改写
 */
import fs from "fs";

const args = process.argv.slice(2);
function getArg(k) {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
}

const input = getArg("--in");
const output = getArg("--out") || input;
if (!input) {
  console.error("Usage: node fix-tts-timings.mjs --in <captions.json> [--out <out.json>]");
  process.exit(1);
}

const caps = JSON.parse(fs.readFileSync(input, "utf8"));
let fixed = 0;
for (let i = 0; i < caps.length - 1; i++) {
  const dur = caps[i].endMs - caps[i].startMs;
  const gap = caps[i + 1].startMs - caps[i].endMs;
  // Only "extend to next" when the reported duration is suspiciously short
  // AND there's a positive gap. Otherwise leave alone (per-char CJK timings
  // are already accurate).
  if (dur < 100 && gap > 100) {
    caps[i].endMs = caps[i + 1].startMs;
    fixed++;
  }
}

fs.writeFileSync(output, JSON.stringify(caps, null, 2));
console.log(`✅ ${fixed} token(s) endMs extended → ${output}`);

#!/usr/bin/env node
/**
 * scene-align.mjs — 由真实字幕时间戳推导 Remotion Sequence 分段
 *
 * 解决 VAASTutorial 9140f 事故的根因：场景帧数硬编码，音频一变全部漂移。
 * 本脚本只信 captions.json（fix-tts-timings 修正后）里的真实时间戳。
 *
 * 分段策略（二选一）:
 *   1. 显式分段：脚本文件里写 `## 段落名` 标记。每处标记 = 一个新场景边界，
 *      通过归一化字符偏移匹配（忽略空白/标点/大小写）定位到字幕 token。
 *      标记文本必须与 TTS 实际朗读内容一致，否则报错退出（防止脚本/音频脱节）。
 *   2. 自动分段：相邻 token 的句间 gap ≥ --gap-ms（默认 300）视为边界。
 *      依据：seed-tts 句间停顿 250-600ms，逗号停顿 <200ms。
 *
 * 两种模式之后都会:
 *   - 合并时长 < --min-seg-ms（默认 1500）的短段并入前段（避免场景闪烁；
 *     首段无前段可并，原样保留 —— 首段通常是 hook）
 *   - 帧数推导：from = round(startMs/1000*fps)
 *              durationInFrames = round((endMs-startMs)/1000*fps) + padFrames
 *   - role 标注：首段 hook；末段含 CTA 关键词（关注/点赞/star/github…）→ cta；
 *     其余 body；单段视频 → body
 *
 * 用法:
 *   node scene-align.mjs --captions captions.json [--script script.txt] \
 *        [--fps 30] [--gap-ms 300] [--min-seg-ms 1500] [--pad-frames 0] \
 *        --out scenes.json
 *   node scene-align.mjs --captions captions.json --preview   # 只打印分段表
 *
 * 输出: [{from, durationInFrames, text, role}, ...]
 */
import fs from "fs";

const args = process.argv.slice(2);
function getArg(k) {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
}

const captionsPath = getArg("--captions");
const scriptPath = getArg("--script");
const fps = Number(getArg("--fps") ?? 30);
const gapMs = Number(getArg("--gap-ms") ?? 300);
const minSegMs = Number(getArg("--min-seg-ms") ?? 1500);
const padFrames = Number(getArg("--pad-frames") ?? 0);
const outPath = getArg("--out");
const preview = args.includes("--preview");

if (!captionsPath || (!outPath && !preview)) {
  console.error(
    "Usage: node scene-align.mjs --captions <captions.json> [--script <script.txt>] " +
      "[--fps 30] [--gap-ms 300] [--min-seg-ms 1500] [--pad-frames 0] " +
      "[--out <scenes.json> | --preview]",
  );
  process.exit(1);
}
if (!fs.existsSync(captionsPath)) {
  console.error(`❌ captions not found: ${captionsPath}`);
  process.exit(1);
}

const caps = JSON.parse(fs.readFileSync(captionsPath, "utf8"));
if (!Array.isArray(caps) || caps.length === 0) {
  console.error(`❌ captions is empty or not an array: ${captionsPath}`);
  process.exit(1);
}
for (const [i, c] of caps.entries()) {
  if (typeof c.startMs !== "number" || typeof c.endMs !== "number" || typeof c.text !== "string") {
    console.error(`❌ captions[${i}] missing text/startMs/endMs`);
    process.exit(1);
  }
}

// ---------- 归一化匹配（script ↔ captions） ----------
// 只保留字母/数字（CJK 字也在 \p{L} 内），忽略空白、标点、大小写
function normalize(s) {
  return (s ?? "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

const normToks = caps.map((c) => normalize(c.text));
const tokOffsets = []; // 每个 token 在拼接串里的起始字符偏移
let allText = "";
for (const t of normToks) {
  tokOffsets.push(allText.length);
  allText += t;
}

/** 字符偏移 → token 下标（偏移落在 token 内部时取该 token） */
function tokenIndexAt(charOffset) {
  let lo = 0, hi = tokOffsets.length - 1, ans = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (tokOffsets[mid] <= charOffset) { ans = mid; lo = mid + 1; }
    else hi = mid - 1;
  }
  return ans;
}

// ---------- 分段边界 ----------
let cuts = []; // 新场景的起始 token 下标（不含 0）
let mode = "auto";

if (scriptPath) {
  if (!fs.existsSync(scriptPath)) {
    console.error(`❌ script not found: ${scriptPath}`);
    process.exit(1);
  }
  const script = fs.readFileSync(scriptPath, "utf8");
  const lines = script.split(/\r?\n/);
  const sections = [{ title: null, text: "" }];
  for (const line of lines) {
    const m = /^##\s+(.*)$/.exec(line);
    if (m) sections.push({ title: m[1].trim(), text: "" });
    else sections[sections.length - 1].text += line + "\n";
  }

  if (sections.length > 1) {
    mode = "explicit";
    let searchFrom = 0;
    for (let i = 1; i < sections.length; i++) {
      const sec = sections[i];
      const full = normalize(sec.text);
      if (!full) {
        console.error(`❌ 分段标记 "## ${sec.title}" 后面没有可匹配的文本`);
        process.exit(1);
      }
      // 优先整段匹配；失败退化为前 20 个归一化字符（容忍尾部措辞微调）
      let pos = allText.indexOf(full, searchFrom);
      if (pos === -1) pos = allText.indexOf(full.slice(0, 20), searchFrom);
      if (pos === -1) {
        console.error(
          `❌ 分段标记 "## ${sec.title}" 的文本在字幕里找不到（前 20 字: ${full.slice(0, 20)}…）。` +
            `脚本必须与 TTS 朗读内容一致；如只要自动分段，去掉 ## 标记或不传 --script。`,
        );
        process.exit(1);
      }
      cuts.push(tokenIndexAt(pos));
      searchFrom = pos;
    }
  }
}

if (mode === "auto") {
  for (let i = 0; i < caps.length - 1; i++) {
    if (caps[i + 1].startMs - caps[i].endMs >= gapMs) cuts.push(i + 1);
  }
}

// 排序去重，剔除 0 / 越界
cuts = [...new Set(cuts)].filter((c) => c > 0 && c < caps.length).sort((a, b) => a - b);

// ---------- 组装场景 ----------
const starts = [0, ...cuts];
let segments = starts.map((s, idx) => {
  const e = idx + 1 < starts.length ? starts[idx + 1] : caps.length;
  const toks = caps.slice(s, e);
  return {
    startMs: toks[0].startMs,
    endMs: toks[toks.length - 1].endMs,
    text: toks.map((t) => t.text).join("").trim(),
  };
});

// 合并 < minSegMs 的短段并入前段（首段无前段可并，原样保留）
const merged = [];
for (const seg of segments) {
  if (merged.length && seg.endMs - seg.startMs < minSegMs) {
    const prev = merged[merged.length - 1];
    prev.endMs = seg.endMs;
    prev.text += seg.text;
  } else {
    merged.push({ ...seg });
  }
}
segments = merged;

// ---------- role 标注 ----------
const CTA_RE = /(关注|点赞|收藏|评论|私信|转发|扫码|领取|下载|订阅|官网|链接|试试|体验|star|github)/i;
segments.forEach((seg, i) => {
  if (segments.length === 1) seg.role = "body";
  else if (i === 0) seg.role = "hook";
  else if (i === segments.length - 1 && CTA_RE.test(seg.text)) seg.role = "cta";
  else seg.role = "body";
});

// ---------- 帧数推导（只信真实时间戳，禁止硬编码） ----------
const scenes = segments.map((seg) => ({
  from: Math.round((seg.startMs / 1000) * fps),
  durationInFrames:
    Math.max(1, Math.round(((seg.endMs - seg.startMs) / 1000) * fps)) + padFrames,
  text: seg.text,
  role: seg.role,
}));

// ---------- 输出 ----------
const fmtS = (ms) => (ms / 1000).toFixed(2).padStart(7);
console.log(
  `🧭 scene-align [${mode}] ${scenes.length} 段 @${fps}fps ` +
    `(gap≥${gapMs}ms, minSeg=${minSegMs}ms, pad=${padFrames}f)`,
);
console.log("  #   起(s)    止(s)   时长(s)  frames        role   文本");
scenes.forEach((sc, i) => {
  const startMs = segments[i].startMs;
  const endMs = segments[i].endMs;
  const durS = ((endMs - startMs) / 1000).toFixed(2).padStart(6);
  const frames = `${sc.from}+${sc.durationInFrames}`.padEnd(12);
  const previewText = sc.text.length > 20 ? sc.text.slice(0, 20) + "…" : sc.text;
  console.log(
    `  ${String(i + 1).padStart(2)}  ${fmtS(startMs)}  ${fmtS(endMs)}  ${durS}  ${frames}  ${sc.role.padEnd(5)}  ${previewText}`,
  );
});
const total = scenes[scenes.length - 1].from + scenes[scenes.length - 1].durationInFrames;
console.log(`  合计 ${total}f（末段 from+duration）`);

if (!preview) {
  fs.writeFileSync(outPath, JSON.stringify(scenes, null, 2) + "\n");
  console.log(`✅ scenes written → ${outPath}`);
}

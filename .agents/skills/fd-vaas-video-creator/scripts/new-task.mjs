#!/usr/bin/env node
/**
 * new-task.mjs
 *
 * 为一支新视频创建结构化的 task 目录。所有产物、脚本、字幕、manifest
 * 都放在一起,后续 agent / 人类都能凭 slug 找到全套素材。
 *
 * 目录约定:
 *   downloads/fd-videos/<slug>/
 *   ├── task.json         # 结构化 manifest(type, voice, dims, timings)
 *   ├── script.txt        # 口播稿原文(script 是类型输入时才有)
 *   ├── <key>.json        # 类型的 json 输入(如 items.json)
 *   ├── voiceover.mp3     # TTS 产物
 *   ├── captions.json     # TTS 官方逐字时间戳(已修正)
 *   ├── captions-raw.json # TTS 原始返回(未修正,存档用)
 *   ├── captions.srt      # 软字幕(可选)
 *   ├── <slug>.mp4        # 最终成片
 *   └── history.md        # 每次改动的 append-only 记录
 *
 * 用法:
 *   # 口播视频(旧式，不带 --type = voiceover 兼容路径，--script 必填)
 *   node new-task.mjs --slug finddata-intro --script /path/to/script.txt \
 *                     [--width 1920] [--height 1080] [--voice zh_female_...]
 *
 *   # 指定视频类型(输入项由 types/<id>/type.json 的 inputs 声明)
 *   node new-task.mjs --slug my-list --type listicle \
 *                     --script /path/script.txt --items /path/items.json \
 *                     [--orientation 1080x1920]
 *
 * --type 规则:
 *   - 类型必须已注册(node scripts/types/list.mjs 可查)
 *   - inputs 里的必填输入全部按 --<key> <value> 传入;有 default 的可省略
 *   - file → 拷进任务目录(script 固定为 script.txt;其他保留扩展名)
 *     json → 可为文件路径或内联 JSON,统一存成 <key>.json
 *     text/enum → 原值记进 task.json.inputs
 *   - enum 输入 orientation("1080x1920")决定视频宽高;显式 --width/--height 优先
 *   - task.json 会多 type + inputs 两个字段;不带 --type 时 manifest 与旧版一致
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { getType, listTypes } from "./types/registry.mjs";

const args = process.argv.slice(2);
function getArg(k) {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
}

const slug = getArg("--slug");
const typeId = getArg("--type");
const scriptPath = getArg("--script");
const widthArg = getArg("--width");
const heightArg = getArg("--height");
let width = Number(widthArg ?? 1080);
let height = Number(heightArg ?? 1920);
const voice = getArg("--voice") ?? null;

if (!slug) {
  console.error(
    "Usage: node new-task.mjs --slug <name> [--type <id>] [--script <script.txt>] " +
      "[--width w --height h --voice id] [--<type-input> <value>…]",
  );
  process.exit(1);
}
if (!/^[a-z0-9][a-z0-9-]*$/.test(slug)) {
  console.error(`❌ slug must be [a-z0-9-], got: "${slug}"`);
  process.exit(1);
}

// -------- 类型解析 --------
let type = null;
if (typeId) {
  type = getType(typeId);
  if (!type) {
    console.error(`❌ 未知视频类型 "${typeId}"`);
    const avail = listTypes().map((t) => t.id);
    console.error(
      avail.length
        ? `   可用类型: ${avail.join(", ")}`
        : "   (types/ 下还没有注册任何视频类型)",
    );
    console.error(
      "   查看详情: node .agents/skills/fd-vaas-video-creator/scripts/types/list.mjs",
    );
    process.exit(1);
  }
}
if (!type && !scriptPath) {
  console.error(
    "❌ 缺少 --script(不带 --type 时按口播视频处理,script 必填)。用法见文件头注释。",
  );
  process.exit(1);
}

const VAAS = process.env.VAAS_ROOT ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const ROOT = path.join(VAAS, "downloads/fd-videos");
const dir = path.join(ROOT, slug);
if (fs.existsSync(dir)) {
  console.error(`❌ task dir already exists: ${dir}`);
  process.exit(1);
}

// -------- 类型输入解析(先全部校验,通过后才落盘) --------
const inputsOut = {};
const copyPlan = []; // {src, destName}
const writePlan = []; // {destName, data}

if (type) {
  const missing = [];
  const errors = [];
  for (const [key, inp] of Object.entries(type.inputs ?? {})) {
    let raw = getArg(`--${key}`);
    if (raw == null && inp.default !== undefined) raw = String(inp.default);
    if (raw == null) {
      if (inp.required) {
        missing.push(
          `  --${key} (${inp.type}${
            inp.type === "enum" ? ": " + inp.enum.join(" | ") : ""
          }) — ${inp.desc}`,
        );
      }
      continue;
    }
    if (inp.type === "enum") {
      if (!inp.enum.includes(raw)) {
        errors.push(`  --${key} 必须是 ${inp.enum.join(" | ")},收到 "${raw}"`);
        continue;
      }
      inputsOut[key] = raw;
    } else if (inp.type === "text") {
      inputsOut[key] = raw;
    } else if (inp.type === "file") {
      if (!fs.existsSync(raw)) {
        errors.push(`  --${key} 文件不存在: ${raw}`);
        continue;
      }
      const destName = key === "script" ? "script.txt" : `${key}${path.extname(raw)}`;
      copyPlan.push({ src: raw, destName });
      inputsOut[key] = destName;
    } else if (inp.type === "json") {
      let data;
      if (fs.existsSync(raw)) {
        try {
          data = JSON.parse(fs.readFileSync(raw, "utf8"));
        } catch (e) {
          errors.push(`  --${key} JSON 文件解析失败: ${e.message}`);
          continue;
        }
      } else {
        try {
          data = JSON.parse(raw);
        } catch {
          errors.push(`  --${key} 既不是存在的文件,也不是合法 JSON`);
          continue;
        }
      }
      const destName = `${key}.json`;
      writePlan.push({ destName, data });
      inputsOut[key] = destName;
    }
    // orientation: "1080x1920" → 视频宽高(显式 --width/--height 优先)
    if (key === "orientation") {
      const m = /^(\d+)x(\d+)$/.exec(inputsOut[key]);
      if (m) {
        if (!widthArg) width = Number(m[1]);
        if (!heightArg) height = Number(m[2]);
      }
    }
  }
  if (missing.length || errors.length) {
    if (missing.length) {
      console.error(`❌ 类型 "${type.id}" 缺少必填输入:\n${missing.join("\n")}`);
    }
    if (errors.length) {
      console.error(`❌ 输入校验失败:\n${errors.join("\n")}`);
    }
    process.exit(1);
  }
}

fs.mkdirSync(dir, { recursive: true });
for (const { src, destName } of copyPlan) {
  fs.copyFileSync(src, path.join(dir, destName));
}
for (const { destName, data } of writePlan) {
  fs.writeFileSync(path.join(dir, destName), JSON.stringify(data, null, 2) + "\n");
}
// 旧式(无类型)路径:script 直接拷成 script.txt
if (!type) fs.copyFileSync(scriptPath, path.join(dir, "script.txt"));

// Manifest — the canonical source of truth
const manifest = {
  slug,
  createdAt: new Date().toISOString(),
  status: "draft", // draft | voiced | rendered | published
  script: type ? (inputsOut.script ?? null) : "script.txt",
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
if (type) {
  manifest.type = type.id;
  manifest.inputs = inputsOut;
}
fs.writeFileSync(
  path.join(dir, "task.json"),
  JSON.stringify(manifest, null, 2) + "\n",
);

// History log — append-only, human-readable
const now = new Date().toISOString();
fs.writeFileSync(
  path.join(dir, "history.md"),
  `# ${slug} — history\n\n- ${now} — task created (${width}×${height}${type ? `, type=${type.id}` : ""})\n`,
);

console.log(`✅ task scaffolded: ${dir}`);
if (type) {
  console.log(`   type: ${type.id}(${type.name})[${type.status}]`);
  console.log(
    `   inputs: ${
      Object.entries(inputsOut)
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(", ") || "(无)"
    }`,
  );
}
if (copyPlan.some((c) => c.destName === "script.txt") || !type) {
  console.log(`   script.txt copied from ${scriptPath ?? copyPlan.find((c) => c.destName === "script.txt")?.src}`);
}
console.log(`   task.json + history.md initialised`);

if (type) {
  console.log(`\nNext:`);
  console.log(
    `  node .agents/skills/fd-vaas-video-creator/scripts/task-render.mjs --slug ${slug}`,
  );
  console.log(`  pipeline: ${type.pipeline.join(" → ")}`);
} else {
  console.log(`\nNext:`);
  console.log(`  1. TTS  : generate voiceover -> voiceover.mp3 + captions-raw.json`);
  console.log(`  2. fix  : fix-tts-timings.mjs --in captions-raw.json --out captions.json`);
  console.log(`  3. update task.json (tts.*)`);
  console.log(`  4. render: --props='{"audioSrc":"...","captionsSrc":"...", ...}'`);
  console.log(`  5. update task.json (render.*)`);
  console.log(
    `  （或一键: node .agents/skills/fd-vaas-video-creator/scripts/task-render.mjs --slug ${slug}）`,
  );
}

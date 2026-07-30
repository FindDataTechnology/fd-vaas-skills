#!/usr/bin/env node
/**
 * generate-covers.mjs
 *
 * 一条命令生成「公司风格统一封面」全套(横/竖/YouTube/视频号),复用 fd-cover-image
 * 的 generate-cover.mjs(Remotion BrandCover 模板)。同一套 title/subtitle/tags/template/logo
 * 渲染出多个尺寸 -> 视觉统一,只是按平台要求出不同画幅。
 *
 * 生成完回写 task.json 的 render.covers(相对 task 目录的路径,和 render.output 同约定),
 * publish.mjs 会按平台从中挑对应的封面文件上传。同时写 render.poster 做向后兼容。
 *
 * 默认值从 .env 读(公司风格统一在此配),CLI 参数可覆盖:
 *   COVER_TEMPLATE   brand | title-only | gradient   (默认 brand)
 *   COVER_SUBTITLE   副标题(可空)
 *   COVER_TAGS       底部标签(可空)
 *   COVER_LOGO       Logo 路径,或 none                  (默认 downloads/common/icon.png)
 *
 * 用法:
 *   node generate-covers.mjs --slug <name> --title "主标题"
 *   node generate-covers.mjs --slug <name> --title "..." --subtitle "..." --tags "..."
 *   node generate-covers.mjs --slug <name> --title "..." --template gradient
 *
 * 单独跑(渲染后预览确认)或被 publish.mjs 自动调用都行。
 */
import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";

// ─── args ──────────────────────────────────────────────
const args = process.argv.slice(2);
const getArg = (k) => {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
};
const hasArg = (k) => args.includes(k);

const slug = getArg("--slug");
const cliTitle = getArg("--title");
const cliSubtitle = getArg("--subtitle");
const cliTags = getArg("--tags");
const cliTemplate = getArg("--template");
const cliLogo = getArg("--logo");

if (!slug || !cliTitle) {
  console.error(
    'Usage: --slug <name> --title "..." [--subtitle "..."] [--tags "..."] [--template brand] [--logo <path|none>]',
  );
  process.exit(1);
}

// ─── env loading (very small dotenv, no deps; 同 publish.mjs) ──
function loadEnv(file) {
  if (!fs.existsSync(file)) return {};
  const out = {};
  for (const raw of fs.readFileSync(file, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    const k = line.slice(0, eq).trim();
    let v = line.slice(eq + 1).trim();
    if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1);
    out[k] = v;
  }
  return out;
}

const VAAS = "/Users/chengsishi/VAAS";
const TASK_DIR = path.join(VAAS, "downloads/fd-videos", slug);
const manifestPath = path.join(TASK_DIR, "task.json");

if (!fs.existsSync(manifestPath)) {
  console.error(`❌ task.json not found: ${manifestPath}. 先跑 task-render.mjs。`);
  process.exit(1);
}
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

const env = loadEnv(path.join(VAAS, ".env"));

// ─── resolve unified style params (CLI > .env > 内置默认) ──
const title = cliTitle;
const subtitle = cliSubtitle ?? env.COVER_SUBTITLE ?? "";
const tags = cliTags ?? env.COVER_TAGS ?? "";
const template = cliTemplate ?? env.COVER_TEMPLATE ?? "brand";
const logo = cliLogo ?? env.COVER_LOGO ?? null; // null = 让 generate-cover.mjs 用默认 icon.png

const COVER_SCRIPT = path.join(
  VAAS, ".agents", "skills", "fd-cover-image", "scripts", "generate-cover.mjs",
);

if (!fs.existsSync(COVER_SCRIPT)) {
  console.error(`❌ generate-cover.mjs not found: ${COVER_SCRIPT}`);
  process.exit(1);
}

// ─── 封面规格:文件名 + 传给 generate-cover.mjs 的尺寸参数 ──
// 同一套 title/subtitle/tags/template/logo,只是画幅不同 -> 公司风格统一
const SPECS = [
  // 横版 1920×1080:抖音横封面、B站
  { name: "cover-horizontal.jpg", sizeArgs: ["--orientation", "horizontal"] },
  // 竖版 1080×1440:抖音竖封面、小红书、快手
  { name: "cover-vertical.jpg", sizeArgs: ["--orientation", "vertical"] },
  // YouTube 缩略图 1280×720
  { name: "cover-youtube.jpg", sizeArgs: ["--size", "1280x720"] },
  // 视频号封面 1080×1260
  { name: "cover-weixin.jpg", sizeArgs: ["--size", "1080x1260"] },
];

// ─── 生成单张封面的公共参数 ─────────────────────────────
function buildCoverArgs(spec) {
  const a = ["--title", title, "--template", template, "--output", path.join(TASK_DIR, spec.name)];
  if (subtitle) a.push("--subtitle", subtitle);
  if (tags) a.push("--tags", tags);
  if (logo) a.push("--logo", logo);
  a.push(...spec.sizeArgs);
  return a;
}

console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 生成公司风格统一封面
📹 任务: ${slug}
📝 标题: ${title}
📐 模板: ${template}${subtitle ? `\n💬 副标题: ${subtitle}` : ""}${tags ? `\n🏷️  标签: ${tags}` : ""}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

const produced = {};
let failed = false;
for (const spec of SPECS) {
  const argv = buildCoverArgs(spec);
  console.log(`▶ 生成 ${spec.name}`);
  const res = spawnSync("node", [COVER_SCRIPT, ...argv], {
    cwd: VAAS,
    stdio: "inherit",
  });
  if (res.status !== 0) {
    console.error(`❌ ${spec.name} 渲染失败 (exit ${res.status})`);
    failed = true;
    continue;
  }
  produced[spec.name] = path.join(TASK_DIR, spec.name);
}

if (failed) {
  console.error("\n⚠️  部分封面生成失败,task.json 未更新。请检查上面的错误。");
  process.exit(1);
}

// ─── 回写 task.json: render.covers + render.poster ─────
// 路径相对 task 目录,和 render.output 约定一致(publish.mjs 拼 TASK_DIR)
manifest.render = manifest.render ?? {};
manifest.render.covers = {
  douyin_h: "cover-horizontal.jpg",
  douyin_v: "cover-vertical.jpg",
  bilibili: "cover-horizontal.jpg",
  xiaohongshu: "cover-vertical.jpg",
  kuaishou: "cover-vertical.jpg",
  weixin: "cover-weixin.jpg",
  youtube: "cover-youtube.jpg",
};
// 向后兼容:旧逻辑读 render.poster
manifest.render.poster = "cover-horizontal.jpg";
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 封面已生成并回写 task.json
   ${Object.entries(produced)
     .map(([n, p]) => `${n}: ${(fs.statSync(p).size / 1024).toFixed(0)} KB`)
     .join("\n   ")}
   render.covers 已写入 ${path.relative(VAAS, manifestPath)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

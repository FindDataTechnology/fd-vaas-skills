#!/usr/bin/env node
/**
 * publish.mjs - fd-vaas-publish-docs 主入口
 *
 * 本 skill 的浏览器自动化由 references/<platform>.md 的 heredoc 驱动(你/Claude 跑)。
 * 本脚本只做确定性的事,不碰浏览器:
 *   1. 读 article.md + meta.json(downloads/fd-docs/<slug>/)或 CLI 直传
 *   2. 读 .env + <task>/.publish.env,合并偏好
 *   3. 按平台适配:标题截断、正文限长、标签限数、摘要生成
 *   4. PLAN:把适配内容写到 .adapted/<platform>/,打印计划 + export 行(--dry-run 只打印不写)
 *   5. RECORD(--record):把已发布的平台回写 meta.json distribution[] + history.md
 *
 * 用法:
 *   node publish.mjs --slug <name> --plan
 *   node publish.mjs --slug <name> --dry-run
 *   node publish.mjs --title "..." --body "$(cat a.md)" --tags "a,b" --platforms zhihu,weixin --plan
 *   node publish.mjs --slug <name> --record --platforms zhihu,weixin --title "..."
 *
 * 参数优先级:CLI --flag > <task>/.publish.env > <VAAS>/.env > 内置默认。
 */
import fs from "fs";
import path from "path";

// ─── args ──────────────────────────────────────────────
const args = process.argv.slice(2);
const getArg = (k) => {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--") ? args[i + 1] : null;
};
const hasArg = (k) => args.includes(k);

const slug = getArg("--slug");
const cliTitle = getArg("--title");
const cliBody = getArg("--body");
const cliTags = getArg("--tags");
const cliCover = getArg("--cover");
const cliSummary = getArg("--summary");
const cliPlatforms = getArg("--platforms");
const planMode = hasArg("--plan");
const dryRun = hasArg("--dry-run");
const recordMode = hasArg("--record");

// ─── env loading (tiny dotenv, no deps) ────────────────
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

// ─── 平台规格表(与 SKILL.md「平台差异化默认」一致) ───
// bodyMax=0 表示无硬上限(只 warn);tagMax=0 表示该平台不吃标签
const PLATFORMS = {
  zhihu:       { name: "知乎",         editor: "https://zhuanlan.zhihu.com/write",                                              titleMax: 100, bodyMax: 50000, tagMax: 5,  cover: "optional" },
  weixin:      { name: "微信公众号",     editor: "https://mp.weixin.qq.com/",                                                     titleMax: 64,  bodyMax: 20000, tagMax: 0,  cover: "required" },
  xiaohongshu: { name: "小红书",        editor: "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image",   titleMax: 20,  bodyMax: 1000,  tagMax: 10, cover: "required" },
  xueqiu:      { name: "雪球",          editor: "https://xueqiu.com/zhuanlan/publish",                                           titleMax: 50,  bodyMax: 0,     tagMax: 10, cover: "optional" },
  eastmoney:   { name: "东方财富号",     editor: "https://mp.eastmoney.com/collect/pc_article/index.html#/",                titleMax: 30,  bodyMax: 0,     tagMax: 10, cover: "optional" },
  tonghuashun: { name: "同花顺财经号",   editor: "https://media.10jqka.com.cn/",                                                  titleMax: 30,  bodyMax: 0,     tagMax: 10, cover: "optional" },
  toutiao:     { name: "今日头条",        editor: "https://mp.toutiao.com/profile_v4/graphic/publish",                            titleMax: 30,  bodyMax: 0,     tagMax: 10, cover: "optional" },
  baijiahao:   { name: "百家号",         editor: "https://baijiahao.baidu.com/builder/rc/edit",                                  titleMax: 40,  bodyMax: 0,     tagMax: 10, cover: "required" },
  weibo:       { name: "微博",          editor: "https://weibo.com/newblog",                                                    titleMax: 140, bodyMax: 10000, tagMax: 10, cover: "optional" },
};

// ─── helpers ──────────────────────────────────────────
function truncate(s, max) {
  if (!max || !s || s.length <= max) return s ?? "";
  return s.slice(0, max - 1) + "…";
}
function stripMd(md) {
  return (md || "")
    .replace(/^---[\s\S]*?---/m, "")   // front matter
    .replace(/`{1,3}[^`]*`{1,3}/g, "") // inline/code
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "") // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1") // links -> text
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/[*_>#~-]/g, "")
    .replace(/\n{2,}/g, "\n")
    .trim();
}
function summarize(md, n = 120) {
  const t = stripMd(md);
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}

// ─── RECORD 模式:回写 distribution[] + history.md ──────
if (recordMode) {
  if (!slug) {
    console.error("❌ --record 需要 --slug <name>(回写到 downloads/fd-docs/<slug>/meta.json)");
    process.exit(1);
  }
  const recPlatforms = (cliPlatforms ?? "")
    .split(",").map((s) => s.trim()).filter(Boolean);
  if (!recPlatforms.length) {
    console.error("❌ --record 需要 --platforms zhihu,weixin,...(本次成功发布的平台)");
    process.exit(1);
  }
  const TASK_DIR = path.join(VAAS, "downloads/fd-docs", slug);
  const metaPath = path.join(TASK_DIR, "meta.json");
  if (!fs.existsSync(metaPath)) {
    console.error(`❌ meta.json not found: ${metaPath}`);
    process.exit(1);
  }
  const meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
  meta.distribution = meta.distribution ?? [];
  const now = new Date().toISOString();
  for (const p of recPlatforms) {
    const spec = PLATFORMS[p];
    if (!spec) { console.error(`⚠️  未知平台 ${p},跳过`); continue; }
    meta.distribution.push({
      platform: p,
      name: spec.name,
      title: cliTitle ?? meta.title ?? "",
      uploadedAt: now,
      editor: spec.editor,
    });
    console.log(`✅ 记录 ${p} (${spec.name})`);
  }
  fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2) + "\n");

  const historyPath = path.join(TASK_DIR, "history.md");
  const summary = recPlatforms.join(", ");
  fs.appendFileSync(historyPath, `- ${now} - publish-docs: ${summary}\n`);
  console.log(`\n已回写 ${metaPath} 的 distribution[](${meta.distribution.length} 条)`);
  process.exit(0);
}

// ─── PLAN / DRY-RUN 模式:加载文档 + 适配 ───────────────
let TASK_DIR = null;
let meta = {};
let title = cliTitle;
let body = cliBody;
let tags = cliTags;
let cover = cliCover;
let summary = cliSummary;
let platformsArg = cliPlatforms;

if (slug) {
  TASK_DIR = path.join(VAAS, "downloads/fd-docs", slug);
  const metaPath = path.join(TASK_DIR, "meta.json");
  if (!fs.existsSync(metaPath)) {
    console.error(`❌ meta.json not found: ${metaPath}\n   先建 downloads/fd-docs/${slug}/{article.md,meta.json}`);
    process.exit(1);
  }
  meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
  if (!body) {
    const art = path.join(TASK_DIR, "article.md");
    if (fs.existsSync(art)) body = fs.readFileSync(art, "utf8");
  }
  title = title ?? meta.title;
  tags = tags ?? (Array.isArray(meta.tags) ? meta.tags.join(",") : meta.tags);
  cover = cover ?? meta.cover;
  summary = summary ?? meta.summary;
  platformsArg = platformsArg ?? (Array.isArray(meta.platforms) ? meta.platforms.join(",") : meta.platforms);
}

if (!title || !body) {
  console.error(
    "Usage:\n" +
    "  --slug <name> --plan                                # 读 downloads/fd-docs/<slug>/\n" +
    "  --title \"...\" --body \"...\" [--tags a,b] [--platforms zhihu,weixin] --plan\n" +
    "  --slug <name> --dry-run                             # 只看计划\n" +
    "  --slug <name> --record --platforms zhihu,weixin --title \"...\"   # 回写发布结果"
  );
  process.exit(1);
}

// 合并 env:项目根 .env < task-local .publish.env
const rootEnv = loadEnv(path.join(VAAS, ".env"));
const taskEnv = TASK_DIR ? loadEnv(path.join(TASK_DIR, ".publish.env")) : {};
const env = { ...rootEnv, ...taskEnv };

const platforms = (platformsArg ?? env.PLATFORMS_DOCS ?? "zhihu")
  .split(",").map((s) => s.trim()).filter(Boolean);
const globalTags = tags ?? env.DOC_TAGS ?? "";

// cover 解析成绝对路径
function resolveCover(c) {
  if (!c) return "";
  if (path.isAbsolute(c) && fs.existsSync(c)) return c;
  const abs = TASK_DIR ? path.join(TASK_DIR, c) : path.join(process.cwd(), c);
  return fs.existsSync(abs) ? abs : "";
}
const coverAbs = resolveCover(cover);

// ─── 按平台适配 ────────────────────────────────────────
function adapt(p) {
  const spec = PLATFORMS[p];
  if (!spec) return null;
  const P = p.toUpperCase();
  // 用 _DOC_TAGS 后缀,避免和视频 skill(fd-vaas-publish)的 *_TAGS 在同一个 .env 里撞车
  const platTags = env[`${P}_DOC_TAGS`] ?? globalTags;
  const tagList = platTags.split(",").map((s) => s.trim()).filter(Boolean).slice(0, spec.tagMax);
  const t = truncate(title, spec.titleMax);
  const sum = summary || summarize(body, 120);
  let b = body;
  let bodyWarn = "";
  if (spec.bodyMax && body.length > spec.bodyMax) {
    b = body.slice(0, spec.bodyMax - 1) + "…";
    bodyWarn = `⚠️ 正文 ${body.length} > ${spec.bodyMax} 已截断`;
  }
  const needCover = spec.cover === "required";
  const coverWarn = needCover && !coverAbs ? `⚠️ 需要封面图但未提供` : "";
  return {
    spec, title: t, body: b, summary: sum,
    tags: tagList, cover: coverAbs,
    bodyWarn, coverWarn,
  };
}

const plan = platforms.map((p) => ({ platform: p, ...(adapt(p) || {}) })).filter((x) => x.spec);

if (!plan.length) {
  console.error("❌ 没有有效平台。--platforms 或 .env PLATFORMS_DOCS 至少给一个有效值。");
  console.error("   可选:zhihu,weixin,xiaohongshu,xueqiu,eastmoney,tonghuashun");
  process.exit(1);
}

// ─── 输出计划 ──────────────────────────────────────────
console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 文档分发计划${dryRun ? "(dry-run,不写 .adapted 不真发)" : ""}
📰 标题: ${title}
🎯 平台: ${plan.map((p) => p.platform).join(", ")}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);

const adaptedDir = TASK_DIR ? path.join(TASK_DIR, ".adapted") : path.join(process.cwd(), ".adapted");

for (const item of plan) {
  const { platform, spec, title: t, body: b, summary: s, tags: tl, cover: c, bodyWarn, coverWarn } = item;
  console.log(`\n▶ ${platform} (${spec.name})  ${spec.editor}`);
  console.log(`  标题(${t.length}/${spec.titleMax}): ${t}`);
  console.log(`  正文(${b.length}${spec.bodyMax ? "/" + spec.bodyMax : ""}字)  摘要: ${s.slice(0, 40)}…`);
  console.log(`  标签(${tl.length}${spec.tagMax ? "/" + spec.tagMax : ""}): ${tl.join(",") || "(无)"}`);
  console.log(`  封面: ${c || "(无)"} ${spec.cover}`);
  if (bodyWarn) console.log(`  ${bodyWarn}`);
  if (coverWarn) console.log(`  ${coverWarn}`);

  if (dryRun) continue;

  // 写 .adapted/<platform>/
  const dir = path.join(adaptedDir, platform);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "title.txt"), t);
  fs.writeFileSync(path.join(dir, "body.md"), b);
  fs.writeFileSync(path.join(dir, "tags.txt"), tl.join(","));
  fs.writeFileSync(path.join(dir, "cover.txt"), c || "");
  fs.writeFileSync(path.join(dir, "summary.txt"), s);

  // 打印 heredoc 要用的 export 行(正文从文件读,避免 shell 转义)
  console.log(`  ── heredoc 环境变量 ──`);
  console.log(`  export DOC_TITLE="$(cat ${path.join(dir, "title.txt")})" \\`);
  console.log(`         DOC_BODY="$(cat ${path.join(dir, "body.md")})" \\`);
  console.log(`         DOC_TAGS="$(cat ${path.join(dir, "tags.txt")})" \\`);
  console.log(`         DOC_COVER="$(cat ${path.join(dir, "cover.txt")})" \\`);
  console.log(`         DOC_SUMMARY="$(cat ${path.join(dir, "summary.txt")})"`);
}

console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
if (dryRun) {
  console.log("🔎 dry-run 完成。确认无误后去掉 --dry-run 重新跑出 .adapted/,再按 references/<platform>.md 跑 heredoc。");
} else {
  console.log("✅ 适配内容已写入 .adapted/<platform>/。");
  console.log("   下一步:对每个平台先跑 references/probe.md 核选择器(首次必做),");
  console.log("   再按 references/<platform>.md 的 heredoc 发布(用上面打印的 export 行)。");
  console.log("   发完逐平台回写:node publish.mjs --slug <name> --record --platforms <已发> --title \"...\"");
}
console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
process.exit(0);

#!/usr/bin/env node
/**
 * publish.mjs - fd-vaas-publish-docs 主入口
 *
 * 两条运行时:
 *   --runtime ego(默认):只做 plan/dry-run/record,打印 heredoc export 行,你用 ego-browser 手跑 references/<p>.md
 *   --runtime patchright:plan 写 .adapted/<p>/ 后,逐平台 spawnSync `python3 platforms/<p>.py`(stealth Playwright)
 *
 * 本脚本只做确定性的事:
 *   1. 读 article.md + meta.json(downloads/fd-docs/<slug>/)或 CLI 直传
 *   2. 读 .env + <task>/.publish.env,合并偏好
 *   3. 按平台适配:标题截断、正文限长 + mdToPlain(保留代码块)、标签限数、摘要、封面按平台挑
 *   4. PLAN:写 .adapted/<platform>/{title.txt,body.md,body.txt,tags.txt,cover.txt,summary.txt}
 *      patchright 模式再 spawnSync 每平台 .py(读 .adapted/,--confirm-file sentinel 给 Claude 非交互确认)
 *   5. RECORD(--record):回写 meta.json distribution[] + history.md
 *
 * 用法:
 *   node publish.mjs --slug <name> --plan
 *   node publish.mjs --slug <name> --runtime patchright --platforms zhihu
 *   node publish.mjs --slug <name> --dry-run
 *   node publish.mjs --slug <name> --record --platforms zhihu,weixin --title "..."
 *
 * 参数优先级:CLI --flag > <task>/.publish.env > <VAAS>/.env > 内置默认。
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";
import { loadEnv, truncate, stripMd, mdToPlain, summarize, limitTags } from "../../_shared/publish/publish-common.mjs";

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
const runtime = getArg("--runtime") || "ego"; // "ego"(打印 heredoc) | "patchright"(spawnSync .py)
const autoPublish = hasArg("--auto-publish");
const headless = hasArg("--headless");

// VAAS 仓库根 = 本脚本上四级(.agents/skills/<skill>/scripts/)，可用 VAAS_ROOT 环境变量覆盖
const VAAS = process.env.VAAS_ROOT ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");

// ─── 平台规格表(与 SKILL.md「平台差异化默认」一致) ───
// bodyMax=0 无硬上限(只 warn);tagMax=0 不吃标签;markdown=true 正文走 markdown(知乎渲染)
const PLATFORMS = {
  zhihu:       { name: "知乎",         editor: "https://zhuanlan.zhihu.com/write",                                              titleMax: 100, bodyMax: 50000, tagMax: 5,  cover: "optional" },
  weixin:      { name: "微信公众号",     editor: "https://mp.weixin.qq.com/ → appmsg?t=media/appmsg_edit&action=edit&type=77&token=<T>",  titleMax: 64,  bodyMax: 20000, tagMax: 0,  cover: "required" },
  xiaohongshu: { name: "小红书",        editor: "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image",   titleMax: 20,  bodyMax: 1000,  tagMax: 10, cover: "required" },
  douyin:      { name: "抖音图文",      editor: "https://creator.douyin.com/creator-micro/content/post/image",                   titleMax: 20,  bodyMax: 1000,  tagMax: 10, cover: "required" },
  kuaishou:    { name: "快手图文",      editor: "https://cp.kuaishou.com/article/publish/image",                                 titleMax: 20,  bodyMax: 0,     tagMax: 10, cover: "required" },
  // ⚠️ 2026-08-11 probe:xueqiu 旧入口 /zhuanlan/publish 已 404(真实入口待登录后重 probe);
  // tonghuashun media.10jqka.com.cn 302 跳 t.10jqka.com.cn/newcircle/creation/adviserEnterGuide/(投顾入驻引导)。
  // 两者 editor 字段保留作登录入口,发文入口以 references/<p>.md 为准。
  xueqiu:      { name: "雪球",          editor: "https://xueqiu.com/",                                                           titleMax: 50,  bodyMax: 0,     tagMax: 10, cover: "optional" },
  eastmoney:   { name: "东方财富号",     editor: "https://mp.eastmoney.com/collect/pc_article/index.html#/",                titleMax: 30,  bodyMax: 0,     tagMax: 10, cover: "optional" },
  tonghuashun: { name: "同花顺财经号",   editor: "https://media.10jqka.com.cn/",                                                  titleMax: 30,  bodyMax: 0,     tagMax: 10, cover: "optional" },
  toutiao:     { name: "今日头条",        editor: "https://mp.toutiao.com/profile_v4/graphic/publish",                            titleMax: 30,  bodyMax: 0,     tagMax: 10, cover: "optional" },
  baijiahao:   { name: "百家号",         editor: "https://baijiahao.baidu.com/builder/rc/edit",                                  titleMax: 40,  bodyMax: 0,     tagMax: 10, cover: "required" },
  weibo:       { name: "微博",          editor: "https://weibo.com/newblog",                                                    titleMax: 140, bodyMax: 10000, tagMax: 10, cover: "optional" },
};

// ─── 上游覆盖的图文平台(vendored social-auto-upload 有 Note 实现) ───
// 原则:上游有就走 note_adapter.py(复用上游 XiaoHongShuNote/DouYinNote/KSNote,
// cookie 与视频发布共享);不在此表的平台才用自己的 heredoc/patchright 逻辑。
const UPSTREAM_NOTE = new Set(["xiaohongshu", "douyin", "kuaishou"]);
const NOTE_ADAPTER = path.join(VAAS, ".agents", "skills", "fd-vaas-publish-docs", "scripts", "note_adapter.py");

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
  const dbWriter = path.join(VAAS, "data", "db_writer.py");
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
    // 统一库:记录文章分发 + 平台变体(标题)
    if (fs.existsSync(dbWriter)) {
      spawnSync("python3", [
        dbWriter, "distribute", slug, p,
        spec.editor, cliTitle ?? meta.title ?? "",
        process.env.DOC_SCHEDULE ?? "", "article"
      ], { stdio: "inherit" });
    }
    console.log(`✅ 记录 ${p} (${spec.name})`);
  }
  fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2) + "\n");

  const historyPath = path.join(TASK_DIR, "history.md");
  const summary = recPlatforms.join(", ");
  fs.appendFileSync(historyPath, `- ${now} - publish-docs: ${summary}\n`);
  if (fs.existsSync(dbWriter)) {
    spawnSync("python3", [dbWriter, "history", slug, "publish-docs", summary], { stdio: "inherit" });
  }
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
    "  --slug <name> --runtime patchright --platforms zhihu # patchright 发布\n" +
    "  --title \"...\" --body \"...\" [--tags a,b] [--platforms zhihu,weixin] --plan\n" +
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

// 按平台挑封面:公众号用 cover-weixin.jpg;小红书用 xhs-1..4.jpg(多张);其余用 cover-h.jpg/meta.cover
function resolveCoverForPlatform(p) {
  if (!TASK_DIR) {
    if (!cover) return "";
    const abs = path.isAbsolute(cover) ? cover : path.join(process.cwd(), cover);
    return fs.existsSync(abs) ? abs : "";
  }
  const exists = (f) => {
    const a = path.isAbsolute(f) ? f : path.join(TASK_DIR, f);
    return fs.existsSync(a) ? a : "";
  };
  if (p === "weixin") return exists("cover-weixin.jpg") || exists(cover) || exists("cover-h.jpg");
  if (p === "xiaohongshu") {
    const xhs = [1, 2, 3, 4].map((n) => exists(`xhs-${n}.jpg`)).filter(Boolean);
    if (xhs.length) return xhs.join(",");
    return exists(cover) || exists("cover-h.jpg");
  }
  if (p === "douyin" || p === "kuaishou") {
    const dy = [1, 2, 3, 4].map((n) => exists(`${p}-${n}.jpg`)).filter(Boolean);
    if (dy.length) return dy.join(",");
    // 图文图片平台无关:没有 <p>-*.jpg 就复用 xhs-*.jpg
    const xhs = [1, 2, 3, 4].map((n) => exists(`xhs-${n}.jpg`)).filter(Boolean);
    if (xhs.length) return xhs.join(",");
    return exists(cover) || exists("cover-h.jpg");
  }
  return exists(cover) || exists("cover-h.jpg");
}

// 上游图文平台(xiaohongshu/douyin)统一走 note_adapter.py 的参数组装
function buildNoteArgv(dir) {
  return [
    NOTE_ADAPTER,
    "--platform", path.basename(dir),
    "--title", fs.readFileSync(path.join(dir, "title.txt"), "utf8").trim(),
    "--note-file", path.join(dir, "body.txt"),
    "--tags", fs.readFileSync(path.join(dir, "tags.txt"), "utf8").trim(),
    "--images", fs.readFileSync(path.join(dir, "cover.txt"), "utf8").trim(),
  ];
}

// ─── 按平台适配 ────────────────────────────────────────
function adapt(p) {
  const spec = PLATFORMS[p];
  if (!spec) return null;
  const P = p.toUpperCase();
  // 用 _DOC_TAGS 后缀,避免和视频 skill(fd-vaas-publish)的 *_TAGS 在同一个 .env 里撞车
  const platTags = env[`${P}_DOC_TAGS`] ?? globalTags;
  const tagList = limitTags(platTags, spec.tagMax);
  const t = truncate(title, spec.titleMax);
  const sum = summary || summarize(body, 120);
  let b = body;
  let bodyWarn = "";
  if (spec.bodyMax && body.length > spec.bodyMax) {
    b = body.slice(0, spec.bodyMax - 1) + "…";
    bodyWarn = `⚠️ 正文 ${body.length} > ${spec.bodyMax} 已截断`;
  }
  const coverPath = resolveCoverForPlatform(p);
  const needCover = spec.cover === "required";
  const coverWarn = needCover && !coverPath ? `⚠️ 需要封面图但未提供` : "";
  return {
    spec, title: t, body: b, bodyPlain: mdToPlain(b), summary: sum,
    tags: tagList, cover: coverPath,
    bodyWarn, coverWarn,
  };
}

const plan = platforms.map((p) => ({ platform: p, ...(adapt(p) || {}) })).filter((x) => x.spec);

if (!plan.length) {
  console.error("❌ 没有有效平台。--platforms 或 .env PLATFORMS_DOCS 至少给一个有效值。");
  console.error("   可选:zhihu,weixin,xiaohongshu,douyin,kuaishou,xueqiu,eastmoney,tonghuashun,toutiao,baijiahao,weibo");
  process.exit(1);
}

// ─── 输出计划 ──────────────────────────────────────────
console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 文档分发计划${dryRun ? "(dry-run,不写 .adapted 不真发)" : ""}  [runtime: ${runtime}]
📰 标题: ${title}
🎯 平台: ${plan.map((p) => p.platform).join(", ")}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);

const adaptedDir = TASK_DIR ? path.join(TASK_DIR, ".adapted") : path.join(process.cwd(), ".adapted");

for (const item of plan) {
  const { platform, spec, title: t, body: b, bodyPlain, summary: s, tags: tl, cover: c, bodyWarn, coverWarn } = item;
  console.log(`\n▶ ${platform} (${spec.name})  ${spec.editor}`);
  console.log(`  标题(${t.length}/${spec.titleMax}): ${t}`);
  console.log(`  正文(${b.length}${spec.bodyMax ? "/" + spec.bodyMax : ""}字)  摘要: ${s.slice(0, 40)}…`);
  console.log(`  标签(${tl.length}${spec.tagMax ? "/" + spec.tagMax : ""}): ${tl.join(",") || "(无)"}`);
  console.log(`  封面: ${c || "(无)"} ${spec.cover}`);
  if (bodyWarn) console.log(`  ${bodyWarn}`);
  if (coverWarn) console.log(`  ${coverWarn}`);

  // patchright 模式即使 --dry-run 也要写 .adapted/(供检查);ego 模式 dry-run 跳过
  if (dryRun && runtime !== "patchright") continue;

  // 写 .adapted/<platform>/
  const dir = path.join(adaptedDir, platform);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "title.txt"), t);
  fs.writeFileSync(path.join(dir, "body.md"), b);
  fs.writeFileSync(path.join(dir, "body.txt"), bodyPlain);
  fs.writeFileSync(path.join(dir, "tags.txt"), tl.join(","));
  fs.writeFileSync(path.join(dir, "cover.txt"), c || "");
  fs.writeFileSync(path.join(dir, "summary.txt"), s);

  // ego 模式打印发布入口(上游图文平台给 note_adapter 命令,其余给 heredoc export 行)
  if (runtime !== "patchright") {
    if (UPSTREAM_NOTE.has(platform)) {
      console.log(`  ── 上游图文(note_adapter.py,cookie 与视频发布共享) ──`);
      console.log("  " + ["python3", ...buildNoteArgv(dir).map((a) => (a.includes(" ") ? `"${a}"` : a))].join(" "));
    } else {
      console.log(`  ── heredoc 环境变量 ──`);
      console.log(`  export DOC_TITLE="$(cat ${path.join(dir, "title.txt")})" \\`);
      console.log(`         DOC_BODY="$(cat ${path.join(dir, "body.md")})" \\`);
      console.log(`         DOC_TAGS="$(cat ${path.join(dir, "tags.txt")})" \\`);
      console.log(`         DOC_COVER="$(cat ${path.join(dir, "cover.txt")})" \\`);
      console.log(`         DOC_SUMMARY="$(cat ${path.join(dir, "summary.txt")})"`);
    }
  }
}

// ─── patchright 运行时:逐平台 spawnSync .py ────────────
if (runtime === "patchright" && !dryRun) {
  const PYTHON = env.PYTHON || "python3";
  const PLATFORMS_DIR = path.join(VAAS, ".agents", "skills", "fd-vaas-publish-docs", "scripts", "platforms");
  console.log(`\n🚀 patchright 运行时:逐平台 spawnSync (${PYTHON}) 串行`);
  console.log(`   路由:xiaohongshu/douyin/kuaishou → note_adapter.py(上游 Note 实现);其余 → platforms/<p>.py(自有逻辑)`);
  console.log(`   发布前确认(仅自有逻辑平台):Claude 看到「等待确认」后问你,你说确认 -> touch /tmp/vaas-doc-<platform>.go 放行\n`);
  for (const item of plan) {
    const { platform, spec } = item;
    const dir = path.join(adaptedDir, platform);

    // 上游图文平台 → note_adapter.py(复用 vendored 上游 Note 实现)
    if (UPSTREAM_NOTE.has(platform)) {
      const argv = buildNoteArgv(dir);
      if (headless) argv.push("--headless");
      console.log(`\n▶▶ ${platform} (${spec.name}) [上游 Note]`);
      console.log("  " + [PYTHON, ...argv.map((a) => (a.includes(" ") ? `"${a}"` : a))].join(" "));
      const res = spawnSync(PYTHON, argv, {
        cwd: VAAS,
        stdio: "inherit",
        env: { ...process.env, VAAS_ROOT: VAAS },
      });
      console.log(`${res.status === 0 ? "✅" : "❌"} ${platform} exit ${res.status}`);
      continue;
    }

    // 自有逻辑平台 → platforms/<p>.py
    const script = path.join(PLATFORMS_DIR, `${platform}.py`);
    if (!fs.existsSync(script)) { console.error(`⚠️  无 ${script},跳过 ${platform}`); continue; }
    const bodyFile = spec.markdown ? path.join(dir, "body.md") : path.join(dir, "body.txt");
    const argv = [
      script,
      "--title", fs.readFileSync(path.join(dir, "title.txt"), "utf8").trim(),
      "--body-file", bodyFile,
      "--tags", fs.readFileSync(path.join(dir, "tags.txt"), "utf8").trim(),
      "--cover", fs.readFileSync(path.join(dir, "cover.txt"), "utf8").trim(),
      "--summary", fs.readFileSync(path.join(dir, "summary.txt"), "utf8").trim(),
      "--confirm-file", `/tmp/vaas-doc-${platform}.go`,
      "--preview", path.join(dir, "preview.png"),
    ];
    if (spec.markdown) argv.push("--markdown");
    if (autoPublish) argv.push("--auto-publish");
    if (headless) argv.push("--headless");

    console.log(`\n▶▶ ${platform} (${spec.name})`);
    console.log("  " + [PYTHON, ...argv.map((a) => (a.includes(" ") ? `"${a}"` : a))].join(" "));
    const res = spawnSync(PYTHON, argv, {
      cwd: VAAS,
      stdio: "inherit",
      env: { ...process.env, VAAS_ROOT: VAAS },
    });
    console.log(`${res.status === 0 ? "✅" : "❌"} ${platform} exit ${res.status}`);
  }
}

console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
if (dryRun) {
  console.log("🔎 dry-run 完成。确认无误后去掉 --dry-run 重新跑出 .adapted/,再发布。");
} else if (runtime === "patchright") {
  console.log("✅ patchright 发布流程结束。发完逐平台回写:");
  console.log("   node publish.mjs --slug <name> --record --platforms <已发> --title \"...\"");
} else {
  console.log("✅ 适配内容已写入 .adapted/<platform>/。");
  console.log("   下一步:上游图文平台(xiaohongshu/douyin/kuaishou)直接跑上面打印的 note_adapter.py 命令;");
  console.log("   自有逻辑平台先跑 references/probe.md 核选择器(首次必做),");
  console.log("   再按 references/<platform>.md 的 heredoc 发布(用上面打印的 export 行)。");
  console.log("   或:node publish.mjs --slug <name> --runtime patchright --platforms <p>");
  console.log("   发完逐平台回写:node publish.mjs --slug <name> --record --platforms <已发> --title \"...\"");
}
console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
process.exit(0);

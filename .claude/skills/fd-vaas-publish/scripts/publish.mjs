#!/usr/bin/env node
/**
 * publish.mjs
 *
 * fd-vaas-publish 主入口。做的事:
 *   1. 读 slug 的 task.json,拿到 mp4 路径 + slug + 已发布记录
 *   2. 读 skill-global .env + task-local .publish.env(如存在),合并偏好
 *   3. 按 PLATFORMS 逐个平台 shell out `sau <platform> upload-video ...`
 *   4. 每成功一次,append 到 task.json 的 distribution[]
 *
 * fd-vaas-publish 自己不做任何上传逻辑 —— 那是 social-auto-upload 的事。
 * 这里只做偏好合并 + 命令行组装。
 *
 * 用法:
 *   node publish.mjs --slug finddata-intro --title "..." --desc "..."
 *   node publish.mjs --slug finddata-intro --title "..." --desc "..." \
 *      --platforms douyin,xiaohongshu \
 *      --tags "开源,AI,数据" \
 *      --schedule "2026-07-20 21:30"
 *
 *   # dry-run: 打印出会跑的 sau 命令,不真发
 *   node publish.mjs --slug finddata-intro --title "..." --dry-run
 *
 * 参数优先级:CLI --flag > <task>/.publish.env > <skill>/.env > 内置默认。
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
const cliDesc = getArg("--desc");
const cliNote = getArg("--note");
const cliPlatforms = getArg("--platforms");
const cliTags = getArg("--tags");
const cliSchedule = getArg("--schedule");
const dryRun = hasArg("--dry-run");

if (!slug || !cliTitle) {
  console.error(
    "Usage: --slug <name> --title \"...\" [--desc \"...\"] [--note \"...\"] \\\n" +
    "        [--platforms douyin,xhs,...] [--tags a,b,c] [--schedule 'YYYY-MM-DD HH:MM'] [--dry-run]",
  );
  process.exit(1);
}

// ─── env loading (very small dotenv, no deps) ──────────
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
const SKILL_DIR = path.join(VAAS, ".claude/skills/fd-vaas-publish");
const TASK_DIR = path.join(VAAS, "downloads/fd-videos", slug);
const manifestPath = path.join(TASK_DIR, "task.json");

if (!fs.existsSync(manifestPath)) {
  console.error(`❌ task.json not found: ${manifestPath}. Run new-task.mjs + task-render.mjs first.`);
  process.exit(1);
}
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

// Config: project-root .env (shared with TTS/seedream/etc.) < task-local .publish.env
const rootEnv = loadEnv(path.join(VAAS, ".env"));
const taskEnv = loadEnv(path.join(TASK_DIR, ".publish.env"));
const env = { ...rootEnv, ...taskEnv }; // task-local overrides project-root

// ─── resolve values ────────────────────────────────────
const platforms = (cliPlatforms ?? env.PLATFORMS ?? "douyin")
  .split(",").map((s) => s.trim()).filter(Boolean);
const globalTags = cliTags ?? env.TAGS ?? "";
const schedule = cliSchedule ?? env.SCHEDULE ?? "";
const headless = (env.HEADLESS ?? "true").toLowerCase() !== "false";
const sauDir = env.SAU_PROJECT_DIR ?? path.join(VAAS, "social-auto-upload");
const mp4 = path.join(TASK_DIR, manifest.render?.output ?? `${slug}.mp4`);

if (!fs.existsSync(mp4)) {
  console.error(`❌ mp4 not found: ${mp4}`);
  process.exit(1);
}

// ─── per-platform config ───────────────────────────────
function platformConfig(p) {
  const P = p.toUpperCase();
  const remap = { XIAOHONGSHU: "XIAOHONGSHU", DOUYIN: "DOUYIN", BILIBILI: "BILIBILI",
                  KUAISHOU: "KUAISHOU", TENCENT: "TENCENT", YOUTUBE: "YOUTUBE" };
  const key = remap[P] ?? P;
  return {
    account: env[`${key}_ACCOUNT`] ?? "main",
    tags: env[`${key}_TAGS`] ?? globalTags,
    tid: env[`${key}_TID`], // bilibili only
    shortTitle: env[`${key}_SHORT_TITLE`],
    visibility: env[`${key}_VISIBILITY`], // youtube
    descMax: env[`${key}_DESC_MAX`] ? parseInt(env[`${key}_DESC_MAX`]) : null,
  };
}

// ─── build sau args per platform ───────────────────────
function truncate(s, max) {
  if (!max || !s || s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}

function buildSauArgs(p) {
  const cfg = platformConfig(p);
  const common = ["--account", cfg.account, "--file", mp4, "--title", cliTitle];

  // All video uploads (upload-video) use --desc. --note only applies to
  // upload-note (xhs/douyin/kuaishou 图文). We only support upload-video here.
  const body = truncate(cliDesc ?? cliNote ?? "", cfg.descMax);

  const argv = [...common];
  if (body) argv.push("--desc", body);
  if (cfg.tags) argv.push("--tags", cfg.tags);
  if (schedule) argv.push("--schedule", schedule);

  // Cover / thumbnail: if the task dir has cover.jpg, pass it to platforms
  // that accept a thumbnail. Douyin's publish loop will hang forever if the
  // video needs a cover and none is provided — its recommendCover selector
  // is stale. Passing --thumbnail-landscape bypasses that whole trap.
  const cover = manifest.render?.poster
    ? path.join(TASK_DIR, manifest.render.poster)
    : null;
  if (cover && fs.existsSync(cover)) {
    if (p === "douyin") {
      argv.push("--thumbnail-landscape", cover);
    } else if (p === "tencent" || p === "kuaishou" || p === "xiaohongshu") {
      argv.push("--thumbnail", cover);
    }
  }

  // platform-specific
  if (p === "bilibili") {
    if (!cfg.tid) throw new Error("bilibili requires BILIBILI_TID in .env");
    argv.push("--tid", String(cfg.tid));
  }
  if (p === "tencent" && cfg.shortTitle) {
    argv.push("--short-title", cfg.shortTitle);
  }
  if (p === "youtube" && cfg.visibility) {
    argv.push("--visibility", cfg.visibility);
  }
  return { platform: p, argv, account: cfg.account };
}

// ─── run ──────────────────────────────────────────────
const results = [];
for (const p of platforms) {
  let job;
  try {
    job = buildSauArgs(p);
  } catch (e) {
    console.error(`⚠️  ${p}: ${e.message}`);
    results.push({ platform: p, ok: false, error: e.message });
    continue;
  }

  const cmdArgs = ["sau", p, "upload-video", ...job.argv];
  if (!headless) cmdArgs.push("--headed");
  console.log(`\n▶ ${p} (${job.account}):`);
  console.log("  " + cmdArgs.map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" "));

  if (dryRun) {
    results.push({ platform: p, account: job.account, ok: null, dryRun: true });
    continue;
  }

  const res = spawnSync(cmdArgs[0], cmdArgs.slice(1), {
    cwd: sauDir,
    stdio: "inherit",
    env: { ...process.env },
  });
  const ok = res.status === 0;
  results.push({
    platform: p,
    account: job.account,
    ok,
    error: ok ? null : `exit ${res.status}`,
  });
}

// ─── update manifest ───────────────────────────────────
if (!dryRun) {
  manifest.distribution = manifest.distribution ?? [];
  for (const r of results) {
    if (!r.ok) continue;
    manifest.distribution.push({
      platform: r.platform,
      account: r.account,
      uploadedAt: new Date().toISOString(),
      scheduled: schedule || null,
      title: cliTitle,
    });
  }
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

  const historyPath = path.join(TASK_DIR, "history.md");
  if (fs.existsSync(historyPath)) {
    const now = new Date().toISOString();
    const summary = results.map((r) => `${r.platform}:${r.ok ? "ok" : "fail"}`).join(", ");
    fs.appendFileSync(historyPath, `- ${now} — publish: ${summary}\n`);
  }
}

// ─── summary ───────────────────────────────────────────
console.log("\n─── summary ───");
for (const r of results) {
  const badge = r.dryRun ? "🔎 dry" : r.ok ? "✅" : "❌";
  console.log(`  ${badge} ${r.platform.padEnd(12)} ${r.account.padEnd(15)} ${r.error ?? ""}`);
}
const failCount = results.filter((r) => r.ok === false).length;
process.exit(failCount > 0 ? 1 : 0);

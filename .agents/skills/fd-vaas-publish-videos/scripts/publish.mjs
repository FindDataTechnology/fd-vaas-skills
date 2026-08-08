#!/usr/bin/env node
/**
 * publish.mjs - 优化版
 *
 * fd-vaas-publish 主入口。做的事:
 *   1. 读 slug 的 task.json,拿到 mp4 路径 + slug + 已发布记录
 *   2. 读 skill-global .env + task-local .publish.env(如存在),合并偏好
 *   3. 按 PLATFORMS 逐个平台调上传脚本（按平台 OS 派发运行时）:
 *        macOS  -> node  .agents/skills/fd-vaas-publish-videos/scripts/platforms/<platform>.mjs  (ego-browser)
 *        Windows-> python .agents/skills/fd-vaas-publish-videos/scripts/platforms/<platform>.py   (patchright)
 *      两套脚本 CLI 参数一致，下面的参数组装逻辑共用。env.PYTHON 可覆盖 Windows 解释器。
 *   4. 每成功一次,append 到 task.json 的 distribution[]
 *
 * 支持平台:
 *   - douyin, bilibili, youtube, kuaishou, weixin, xiaohongshu
 *
 * 用法:
 *   node publish.mjs --slug finddata-intro --title "..." --desc "..."
 *   node publish.mjs --slug finddata-intro --title "..." --desc "..." \
 *      --platforms douyin,xiaohongshu \
 *      --tags "开源,AI,数据" \
 *      --schedule "2026-07-20 21:30"
 *   node publish.mjs --slug finddata-intro --title "..." --dry-run
 *
 * 参数优先级:CLI --flag > <task>/.publish.env > <skill>/.env > 内置默认。
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
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
const noCover = hasArg("--no-cover");
const coverOnly = hasArg("--cover-only");

if (!slug || !cliTitle) {
  console.error(
    "Usage: --slug <name> --title \"...\" [--desc \"...\"] [--note \"...\"] \\\n" +
    "        [--platforms douyin,xhs,...] [--tags a,b,c] [--schedule 'YYYY-MM-DD HH:MM']\n" +
    "        [--dry-run] [--no-cover] [--cover-only]",
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

// VAAS 仓库根 = 本脚本上四级(.agents/skills/<skill>/scripts/)，可用 VAAS_ROOT 环境变量覆盖
const VAAS = process.env.VAAS_ROOT ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const TASK_DIR = path.join(VAAS, "downloads/fd-videos", slug);
const manifestPath = path.join(TASK_DIR, "task.json");

if (!fs.existsSync(manifestPath)) {
  console.error(`❌ task.json not found: ${manifestPath}. Run new-task.mjs + task-render.mjs first.`);
  process.exit(1);
}
let manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

// Config: project-root .env (shared with TTS/seedream/etc.) < task-local .publish.env
const rootEnv = loadEnv(path.join(VAAS, ".env"));
const taskEnv = loadEnv(path.join(TASK_DIR, ".publish.env"));
const env = { ...rootEnv, ...taskEnv }; // task-local overrides project-root

// ─── resolve values ────────────────────────────────────
const platforms = (cliPlatforms ?? env.PLATFORMS ?? "douyin")
  .split(",").map((s) => s.trim()).filter(Boolean);
const globalTags = cliTags ?? env.TAGS ?? "";
const schedule = cliSchedule ?? env.SCHEDULE ?? "";
const mp4 = path.join(TASK_DIR, manifest.render?.output ?? `${slug}.mp4`);

if (!fs.existsSync(mp4)) {
  console.error(`❌ mp4 not found: ${mp4}`);
  process.exit(1);
}

// 平台脚本目录（实际 skill 目录是 fd-vaas-publish-videos；之前写成 fd-vaas-publish 是错的）
const PLATFORMS_DIR = path.join(VAAS, ".agents", "skills", "fd-vaas-publish-videos", "scripts", "platforms");

// macOS = ego-browser (.mjs)；Windows = patchright (.py)。两套脚本 CLI 参数完全一致，下面的参数组装逻辑共用。
// ego-browser 没有 Windows 版，Windows 走 patchright（stealth Playwright）+ 持久 profile 复用登录态。
const IS_WIN = process.platform === "win32";
const RUNTIME = IS_WIN ? (env.PYTHON || "python") : "node";
const SCRIPT_EXT = IS_WIN ? "py" : "mjs";
const ACCOUNT_LABEL = IS_WIN ? "patchright" : "ego-browser";

const newCliScript = (p) => path.join(PLATFORMS_DIR, `${p}.${SCRIPT_EXT}`);

const NODE = "node";

// ─── per-platform config ───────────────────────────────
function platformConfig(p) {
  const P = p.toUpperCase();
  return {
    tags: env[`${P}_TAGS`] ?? globalTags,
    shortTitle: env[`${P}_SHORT_TITLE`],
    visibility: env[`${P}_VISIBILITY`],
    descMax: env[`${P}_DESC_MAX`] ? parseInt(env[`${P}_DESC_MAX`]) : null,
  };
}

// ─── helpers ──────────────────────────────────────────
function truncate(s, max) {
  if (!max || !s || s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
function ensureSeconds(s) {
  return /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(s) ? s + ":00" : s;
}

// ─── 检测平台 CLI 是否存在 ─────────────────────────
function getCliType(p) {
  if (fs.existsSync(newCliScript(p))) {
    return 'new';
  }
  return null;
}

// ─── 封面解析:按平台从 render.covers 取,fallback 到 render.poster ──
// keys 按优先级传;'poster' 是特殊键,读 render.poster。文件不存在就跳到下一个候选。
function pickCover(keys) {
  const covers = manifest.render?.covers;
  for (const k of keys) {
    const rel = k === "poster" ? manifest.render?.poster : covers?.[k];
    if (rel) {
      const f = path.join(TASK_DIR, rel);
      if (fs.existsSync(f)) return f;
    }
  }
  return null;
}

// ─── build command per platform ───────────────────────
function buildCommand(p) {
  const cfg = platformConfig(p);
  const body = truncate(cliDesc ?? cliNote ?? "", cfg.descMax);

  const cliType = getCliType(p);
  
  if (!cliType) {
    throw new Error(
      `暂无 ${p} 上传脚本: .agents/skills/fd-vaas-publish/scripts/platforms/${p}.mjs`
    );
  }

  // 所有平台都使用 ego-browser CLI
  const argv = [newCliScript(p), "--file", mp4, "--title", cliTitle];
  if (body) argv.push("--desc", body);
  if (cfg.tags) argv.push("--tags", cfg.tags);
  
  // 封面按平台挑对应画幅:douyin 横+竖;B站/YouTube 横;小红书/快手/视频号 竖
  if (p === 'douyin') {
    const ch = pickCover(['douyin_h', 'bilibili', 'poster']);
    const cv = pickCover(['douyin_v', 'xiaohongshu', 'kuaishou', 'weixin']);
    if (ch) argv.push("--cover-horizontal", ch);
    if (cv) argv.push("--cover-vertical", cv);
  } else if (p === 'bilibili') {
    const c = pickCover(['bilibili', 'douyin_h', 'poster']);
    if (c) argv.push("--cover", c);
  } else if (p === 'xiaohongshu') {
    const c = pickCover(['xiaohongshu', 'douyin_v']);
    if (c) argv.push("--cover", c);
  } else if (p === 'kuaishou') {
    const c = pickCover(['kuaishou', 'douyin_v']);
    if (c) argv.push("--cover", c);
  } else if (p === 'weixin') {
    const c = pickCover(['weixin', 'douyin_v']);
    if (c) argv.push("--cover", c);
  } else if (p === 'youtube') {
    const c = pickCover(['youtube', 'douyin_h', 'poster']);
    if (c) argv.push("--thumbnail", c);
  }
  
  if (schedule && (p === 'douyin' || p === 'kuaishou')) {
    argv.push("--schedule", p === 'kuaishou' ? ensureSeconds(schedule) : schedule);
  } else if (schedule) {
    console.log(`  ⚠️  ${p} 暂不支持 --schedule，已忽略`);
  }
  
  if (p === 'youtube' && cfg.visibility) {
    argv.push("--visibility", cfg.visibility);
  }
  
  if (dryRun) {
    argv.push("--dry-run");
  }
  
  return { cmd: RUNTIME, args: argv, cwd: VAAS, account: ACCOUNT_LABEL, cliType: IS_WIN ? 'py' : 'new' };
}

// ─── 封面:缺了就自动用公司风格模板补一套(发布时自动补全) ──
const GENERATE_COVERS = path.join(
  VAAS, ".agents", "skills", "fd-vaas-video-creator", "scripts", "generate-covers.mjs",
);
const hasCovers = !!manifest.render?.covers && Object.keys(manifest.render.covers).length > 0;

if (coverOnly) {
  // 只生成封面,不发布(渲染后预览确认用)
  console.log("🎨 仅生成封面,不发布 …\n");
  const r = spawnSync("node", [GENERATE_COVERS, "--slug", slug, "--title", cliTitle], {
    cwd: VAAS, stdio: "inherit",
  });
  process.exit(r.status === 0 ? 0 : 1);
}

if (!hasCovers && !noCover) {
  console.log("🖼️  未检测到封面(task.json 无 render.covers),自动生成公司风格统一封面 …\n");
  const r = spawnSync("node", [GENERATE_COVERS, "--slug", slug, "--title", cliTitle], {
    cwd: VAAS, stdio: "inherit",
  });
  if (r.status !== 0) {
    console.error("❌ 封面自动生成失败,终止发布。可加 --no-cover 跳过封面继续发布。");
    process.exit(1);
  }
  // 重新加载 manifest 拿到刚写入的 covers
  manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  console.log();
} else if (noCover) {
  console.log("🚫 已加 --no-cover,本次发布不上传封面\n");
}

// ─── run ──────────────────────────────────────────────
console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 开始多平台发布流程
📹 视频: ${mp4}
📝 标题: ${cliTitle}
🎯 平台: ${platforms.join(', ')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

const results = [];
for (const p of platforms) {
  let job;
  try {
    job = buildCommand(p);
  } catch (e) {
    console.error(`\n⚠️  ${p}: ${e.message}`);
    results.push({ platform: p, ok: false, error: e.message });
    continue;
  }

  const cliTypeLabel = ACCOUNT_LABEL;
  console.log(`\n▶ ${p} (${cliTypeLabel}):`);
  console.log("  " + [job.cmd, ...job.args].map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" "));

  if (dryRun) {
    results.push({ platform: p, account: job.account, ok: null, dryRun: true });
    continue;
  }

  // macOS: ego-browser 自动完成上传；Windows: patchright(.py) 自动完成上传
  // VAAS_ROOT 透传给 .py，让它能定位 .profiles/<platform> 登录态目录
  const res = spawnSync(job.cmd, job.args, {
    cwd: job.cwd,
    stdio: "inherit",
    env: { ...process.env, VAAS_ROOT: VAAS },
  });
  const ok = res.status === 0;
  results.push({
    platform: p,
    account: job.account,
    ok,
    cliType: job.cliType,
    error: ok ? null : `exit ${res.status}`,
  });
}

// ─── update manifest ──────────────────────────────────
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

    // Write to SQLite database
    const dbWriter = path.join(VAAS_ROOT, 'data', 'db_writer.py');
    if (fs.existsSync(dbWriter)) {
      spawnSync('python3', [
        dbWriter,
        'distribute',
        slug,
        r.platform,
        r.account,
        cliTitle,
        schedule || ''
      ], { stdio: 'inherit' });
    }
  }
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

  const historyPath = path.join(TASK_DIR, "history.md");
  if (fs.existsSync(historyPath)) {
    const now = new Date().toISOString();
    const summary = results.map((r) => `${r.platform}:${r.ok ? "ok" : "fail"}`).join(", ");
    fs.appendFileSync(historyPath, `- ${now} - publish: ${summary}\n`);

    // Write history to database
    const dbWriter = path.join(VAAS_ROOT, 'data', 'db_writer.py');
    if (fs.existsSync(dbWriter)) {
      spawnSync('python3', [
        dbWriter,
        'history',
        slug,
        'publish',
        summary
      ], { stdio: 'inherit' });
    }
  }
}

// ─── summary ───────────────────────────────────────────
console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
console.log("📊 发布总结");
console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
for (const r of results) {
  const badge = r.dryRun ? "🔎 dry" : r.ok ? "✅" : "❌";
  const cliLabel = IS_WIN ? 'py' : 'ego';
  console.log(`  ${badge} ${r.platform.padEnd(12)} [${cliLabel}] ${r.error ?? ""}`);
}
console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

const failCount = results.filter((r) => r.ok === false).length;
if (failCount > 0) {
  console.log(`\n⚠️  ${failCount} 个平台发布失败，请检查上述错误信息`);
  process.exit(1);
} else {
  console.log(`\n✅  所有平台发布流程已完成！`);
  if (!dryRun) {
    console.log(`    请在各平台创作者中心确认发布结果`);
  }
  process.exit(0);
}

#!/usr/bin/env node
/**
 * publish.mjs - 优化版
 *
 * fd-vaas-publish-videos 主入口。做的事:
 *   1. 读 slug 的 task.json,拿到 mp4 路径 + slug + 已发布记录
 *   2. 读 skill-global .env + task-local .publish.env(如存在),合并偏好
 *   3. 按 PLATFORMS 逐个平台调上传脚本（统一 py 运行时）:
 *        python platforms/sau_adapter.py --platform <p>  (vendored social-auto-upload, patchright)
 *        bilibili 仍走 platforms/bilibili.py（上游用 biliup 二进制，非 Playwright）
 *      CLI 参数组装逻辑共用。env.PYTHON 可覆盖解释器。
 *   4. 每成功一次,append 到 task.json 的 distribution[]
 *
 * 支持平台（路由/定时能力以 platform-registry.json 为准，见 check-registry-consistency.py）:
 *   - douyin, bilibili, youtube, kuaishou, weixin, xiaohongshu, weibo, baijiahao, alipay, hupu
 *
 * 确认闸（enforce-publish-confirmation-gate W1.2）:
 *   spawn 任何上传器之前必须持有确认凭据 —— 系统临时目录下哨兵文件
 *   vaas-video-<platform>.go（touch 即放行，与图文 vaas-doc-* 同形态）或 --confirm-file <path>。
 *   缺凭据 = 打印逐平台预览后 exit 非零，零上传请求发出；非交互无 TTY 同样失败关闭。
 *   --auto-publish 是显式旁路参数，回执/台账记录中会标注 auto_publish: true。
 *   VAAS_GATE_DIR 可覆盖哨兵基目录（Windows 节点用）。
 *
 * 用法:
 *   node publish.mjs --slug finddata-intro                  # 标题/描述从 task.json 读（pull-from-cloud 落盘即带）
 *   node publish.mjs --slug finddata-intro --title "..." --desc "..."
 *   node publish.mjs --slug finddata-intro --title "..." --desc "..." \
 *      --platforms douyin,xiaohongshu \
 *      --tags "开源,AI,数据" \
 *      --schedule "2026-07-20 21:30"
 *   node publish.mjs --slug finddata-intro --title "..." --dry-run
 *   node publish.mjs --slug finddata-intro --title "..." --confirm-file "$TMPDIR/vaas-video-douyin.go"
 *
 * 参数优先级:CLI --flag > <task>/.publish.env > <skill>/.env > 内置默认。
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";
import { loadEnv, truncate, ensureSeconds, resolvePython } from "../../_shared/publish/publish-common.mjs";
import { checkGate, defaultGateFile, GATE_PREFIX_VIDEO } from "../../_shared/publish/confirm-gate.mjs";

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
const cliRuntime = getArg("--runtime");
const cliConfirmFile = getArg("--confirm-file");
const dryRun = hasArg("--dry-run");
const noCover = hasArg("--no-cover");
const coverOnly = hasArg("--cover-only");
// W1.2:显式旁路参数,存在即生效,但回执必须标注 auto_publish(不做隐式/环境旁路)
const autoPublish = hasArg("--auto-publish");

if (!slug) {
  console.error(
    "Usage: --slug <name> [--title \"...\"] [--desc \"...\"] [--note \"...\"] \\\n" +
    "        [--platforms douyin,xhs,...] [--tags a,b,c] [--schedule 'YYYY-MM-DD HH:MM']\n" +
    "        [--dry-run] [--no-cover] [--cover-only] [--confirm-file <path>] [--auto-publish]",
  );
  process.exit(1);
}

// VAAS 仓库根 = 本脚本上四级(.agents/skills/<skill>/scripts/)，可用 VAAS_ROOT 环境变量覆盖
const VAAS = process.env.VAAS_ROOT ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const TASK_DIR = path.join(VAAS, "downloads/fd-videos", slug);
const manifestPath = path.join(TASK_DIR, "task.json");

// task.json 是本地创作链（已退役）的清单。托管出片经 pull-from-cloud 落盘时没有它，
// 但只要有 <slug>.mp4 就能发——用最小清单继续（发布只需要 render.output 与 distribution）。
const mp4Fallback = path.join(TASK_DIR, `${slug}.mp4`);
let manifest;
if (fs.existsSync(manifestPath)) {
  manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
} else if (fs.existsSync(mp4Fallback)) {
  console.warn(
    `⚠️  ${TASK_DIR} 无 task.json（托管出片常态）——以 ${slug}.mp4 为准继续；封面按缺省处理`,
  );
  manifest = { slug, render: { output: `${slug}.mp4` }, distribution: [] };
} else {
  console.error(
    `❌ 找不到可发布的产物：${mp4Fallback}\n` +
      `   托管出片后先拉回本机：python3 .agents/skills/fd-vaas-pull-from-cloud/scripts/pull_from_cloud.py \\\n` +
      `     --call-key <KEY> --asset <asset-id>     # 或 --url <生成响应里的 download_url>\n` +
      `   或把已有 mp4 放到 ${TASK_DIR}/${slug}.mp4`,
  );
  process.exit(1);
}

// Config: project-root .env (shared with TTS/seedream/etc.) < task-local .publish.env
const rootEnv = loadEnv(path.join(VAAS, ".env"));
const taskEnv = loadEnv(path.join(TASK_DIR, ".publish.env"));
const env = { ...rootEnv, ...taskEnv }; // task-local overrides project-root

// ─── resolve values ────────────────────────────────────
const platforms = (cliPlatforms ?? env.PLATFORMS ?? "douyin")
  .split(",").map((s) => s.trim()).filter(Boolean);
const globalTags = cliTags ?? env.TAGS ?? "";
const schedule = cliSchedule ?? env.SCHEDULE ?? "";
// 标题/描述可从清单回退（pull-from-cloud 落盘会写 task.json.title）——
// 让「拉回 → 发布」不必再手敲一遍标题。
const title = cliTitle ?? manifest.title ?? slug;
const desc = cliDesc ?? manifest.description ?? "";

const mp4 = path.join(TASK_DIR, manifest.render?.output ?? `${slug}.mp4`);

if (!fs.existsSync(mp4)) {
  console.error(`❌ mp4 not found: ${mp4}`);
  process.exit(1);
}

// 平台脚本目录（实际 skill 目录是 fd-vaas-publish-videos）
const PLATFORMS_DIR = path.join(VAAS, ".agents", "skills", "fd-vaas-publish-videos", "scripts", "platforms");

// 运行时：统一 py（vendored social-auto-upload，patchright）。legacy mjs 运行时已随
// .mjs 脚本删除（Phase 3）。--runtime / VAAS_PUBLISH_RUNTIME 仍接受但只认 py/auto（=py），
// 传 mjs 报错退出（legacy ego-browser 脚本已删）。
const runtimeChoice = (cliRuntime ?? env.VAAS_PUBLISH_RUNTIME ?? "py").toLowerCase();
if (runtimeChoice !== "py" && runtimeChoice !== "auto") {
  console.error(`❌ --runtime ${runtimeChoice} 已移除（legacy ego-browser 脚本已删）。只支持 py。`);
  process.exit(1);
}
const RUNTIME = resolvePython(env.PYTHON || process.env.PYTHON); // W5.2:python3/py/python 探测,不再硬编码
const SCRIPT_EXT = "py";
const ACCOUNT_LABEL = "patchright";

// ─── platform-registry.json:路由 + 定时能力单一可机读源(W3.1/W4.3)───────
// publish.mjs 不在此重复维护能力清单;注册表与 adapter/mjs 三方对账由
// fd-vaas-login/scripts/check-registry-consistency.py 在 CI 强制。
const REGISTRY_FILE = path.join(VAAS, ".agents", "skills", "_shared", "publish", "platform-registry.json");
const platformRegistry = (() => {
  try {
    return JSON.parse(fs.readFileSync(REGISTRY_FILE, "utf8")).platforms ?? {};
  } catch {
    return {}; // registry 缺失/坏:退回旧代码口径(见下 scheduleCapable),并在运行时警告
  }
})();

/** 平台是否支持定时发布:registry.videos.schedule 为准;registry 缺条目才 fallback 旧口径。 */
function scheduleCapable(p) {
  const v = platformRegistry[p]?.videos;
  if (v && typeof v.schedule === "boolean") return v.schedule;
  return usesAdapter(p) && p !== "youtube"; // legacy 兜底(与旧 :200-202 口径一致)
}

const newCliScript = (p) => path.join(PLATFORMS_DIR, `${p}.${SCRIPT_EXT}`);
// 薄适配层：py 运行时 5 个 Playwright 平台走 vendored upstream（social-auto-upload）
// bilibili 不在此列——上游 bilibili 用 biliup 二进制而非 Playwright，仍走本地 bilibili.py
const SAU_ADAPTER = path.join(PLATFORMS_DIR, "sau_adapter.py");
// py 运行时走适配层的平台（bilibili 除外——上游用 biliup 二进制，不在适配层内）
// 后 4 个 2026-10-14 随上游 0012d2c 接入：均为视频，无图文能力、不支持定时发布
const SAU_PLATFORMS = new Set([
  "xiaohongshu", "douyin", "kuaishou", "weixin", "youtube",
  "weibo", "baijiahao", "alipay", "hupu",
]);
const usesAdapter = (p) => SAU_PLATFORMS.has(p);

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

// ─── 检测平台 CLI 是否存在 ─────────────────────────
function getCliType(p) {
  if (usesAdapter(p)) {
    return fs.existsSync(SAU_ADAPTER) ? 'sau' : null;
  }
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
      `暂无 ${p} 上传脚本: .agents/skills/fd-vaas-publish-videos/scripts/platforms/${p}.${SCRIPT_EXT}`
    );
  }

  // py 运行时：5 个 Playwright 平台走 sau_adapter（vendored social-auto-upload）；
  // bilibili 仍用原 bilibili.py（上游走 biliup 二进制，不在适配层内）；
  // mjs 运行时：走 <platform>.mjs（ego-browser）
  const argv = usesAdapter(p)
    ? [SAU_ADAPTER, "--platform", p, "--file", mp4, "--title", title]
    : [newCliScript(p), "--file", mp4, "--title", title];
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
  
  // W4.3:定时参数按 registry 声明的能力下发。请求含 schedule 且平台不支持时,
  // 该已在批次组装阶段被剔除(见 run 段),不会进入子进程再中途拒绝;
  // registry 缺条目的极端情况下此处兜底提示。
  if (schedule && scheduleCapable(p)) {
    argv.push("--schedule", p === 'kuaishou' ? ensureSeconds(schedule) : schedule);
  } else if (schedule) {
    console.log(`  ⚠️  ${p} 不支持定时发布`);
  }
  
  if (p === 'youtube' && cfg.visibility) {
    argv.push("--visibility", cfg.visibility);
  }
  
  if (dryRun) {
    argv.push("--dry-run");
  }
  
  return { cmd: RUNTIME, args: argv, cwd: VAAS, account: ACCOUNT_LABEL, cliType: 'py' };
}

// ─── 封面:缺了就自动用公司风格模板补一套(发布时自动补全) ──
const GENERATE_COVERS = path.join(
  VAAS, ".agents", "skills", "fd-vaas-video-creator", "scripts", "generate-covers.mjs",
);
const hasCovers = !!manifest.render?.covers && Object.keys(manifest.render.covers).length > 0;

if (coverOnly) {
  // 只生成封面,不发布(渲染后预览确认用)
  console.log("🎨 仅生成封面,不发布 …\n");
  const r = spawnSync("node", [GENERATE_COVERS, "--slug", slug, "--title", title], {
    cwd: VAAS, stdio: "inherit",
  });
  process.exit(r.status === 0 ? 0 : 1);
}

if (!hasCovers && !noCover) {
  console.log("🖼️  未检测到封面(task.json 无 render.covers),自动生成公司风格统一封面 …\n");
  const r = spawnSync("node", [GENERATE_COVERS, "--slug", slug, "--title", title], {
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

// ─── 人工确认闸(W1.2:publish-local-handoff 铁律代码化)────────────────
// spawn 任何上传器之前,每个平台必须持有确认凭据:
//   系统临时目录哨兵 vaas-video-<platform>.go(touch 即确认),或 --confirm-file <path> 显式指定。
//   缺凭据 → 打印逐平台预览命令(等价 dry-run 输出)后 exit 1,零上传请求发出。
//   --auto-publish 是唯一显式旁路,存在即标记回执 auto_publish: true。
// 非 TTY 同样失败关闭:本闸只认文件存在性,不读 stdin,无「等待超时自动发布」路径。

// W4.3 批次组装剔除(先于闸):请求含 --schedule 而 registry 声明该平台不支持定时 →
// 跳过不 spawn(旧行为:把 --schedule 发给 no_strategy 平台,sau_adapter 跑到一半
// return 2 中断)。被跳过的平台自然不需要确认哨兵。
const scheduleSkipped = new Set(platforms.filter((p) => schedule && !scheduleCapable(p)));

const gateVerdicts = platforms
  .filter((p) => !scheduleSkipped.has(p))
  .map((p) => ({
    platform: p,
    verdict: checkGate(p, {
      confirmFile: cliConfirmFile ?? "",
      autoPublish,
      prefix: GATE_PREFIX_VIDEO,
      consume: false, // 预检不消费:批量确认齐了再逐平台放行时消费
    }),
  }));
if (!dryRun && !autoPublish) {
  const missing = gateVerdicts.filter((g) => !g.verdict.ok);
  if (missing.length) {
    console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏸️  确认闸未满足(${missing.length}/${platforms.length} 平台缺凭据):未发布,零上传请求发出
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👀 将要发布的命令(逐平台预览):`);
    for (const p of platforms) {
      try {
        const job = buildCommand(p);
        console.log(`  [${p}] ` + [job.cmd, ...job.args].map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" "));
      } catch (e) {
        console.log(`  [${p}] ⚠️ ${e.message}`);
      }
    }
    console.log(`\n✍️  补齐确认(人工复核上述内容后):`);
    for (const g of missing) {
      console.log(`   touch ${g.verdict.gateFile}`);
    }
    console.log(`   然后原命令重跑即放行(哨兵消费一次即失效)。`);
    console.log(`   或确属无人值守场景,显式加 --auto-publish(回执将标注 auto_publish,慎用)。`);
    process.exit(1);
  }
}

// ─── run ──────────────────────────────────────────────
console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 开始多平台发布流程
📹 视频: ${mp4}
📝 标题: ${title}
🎯 平台: ${platforms.join(', ')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

const results = [];
for (const p of platforms) {
  // W4.3(批次组装阶段剔除):见上方 scheduleSkipped——此处只负责记录结果,不 spawn。
  if (scheduleSkipped.has(p)) {
    console.log(`\n⏭️  ${p}: 不支持定时发布(--schedule 无法下发),本次批次已跳过(未启动上传器)`);
    results.push({ platform: p, ok: false, skipped: true, error: `跳过:不支持 --schedule(registry 未声明定时能力)` });
    continue;
  }

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

  // 确认哨兵在此消费(一次确认只放行一个平台一次,与 Python wait_for_file 语义一致)。
  // --auto-publish 显式旁路时不消费(没有哨兵可消费),记录标注 auto_publish: true。
  const gate = checkGate(p, { confirmFile: cliConfirmFile ?? "", autoPublish, prefix: GATE_PREFIX_VIDEO, consume: !autoPublish });
  if (!gate.ok) {
    console.error(`  ❌ ${p}: 确认闸拒绝(竞态或哨兵被消费),未 spawn 上传器`);
    results.push({ platform: p, ok: false, error: gate.reason });
    continue;
  }

  // 统一 patchright(py) 自动完成上传；bilibili 走 bilibili.py
  // VAAS_ROOT 透传给脚本，定位 VAAS 仓库根
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
    auto_publish: autoPublish === true, // 旁路必须可审计(spec:回执标注)
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
      title: title,
      // W1.2:显式旁路必须在台账标注(仅旁路时存在该字段;哨兵确认=人工已确认,不加标记)
      ...(r.auto_publish ? { auto_publish: true } : {}),
    });

    // Write to SQLite database
    const dbWriter = path.join(VAAS, 'data', 'db_writer.py');
    if (fs.existsSync(dbWriter)) {
      spawnSync(RUNTIME, [
        dbWriter,
        'distribute',
        slug,
        r.platform,
        r.account,
        title,
        schedule || ''
      ], { stdio: 'inherit' });
    }
  }
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

  const historyPath = path.join(TASK_DIR, "history.md");
  if (fs.existsSync(historyPath)) {
    const now = new Date().toISOString();
    const summary = results.map((r) => `${r.platform}:${r.skipped ? "skip" : r.ok ? "ok" : "fail"}`).join(", ");
    fs.appendFileSync(historyPath, `- ${now} - publish: ${summary}\n`);

    // Write history to database
    const dbWriter = path.join(VAAS, 'data', 'db_writer.py');
    if (fs.existsSync(dbWriter)) {
      spawnSync(RUNTIME, [
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
  const badge = r.dryRun ? "🔎 dry" : r.skipped ? "⏭ skip" : r.ok ? "✅" : "❌";
  const cliLabel = 'py';
  const apMark = r.auto_publish ? " [auto-publish]" : "";
  console.log(`  ${badge} ${r.platform.padEnd(12)} [${cliLabel}]${apMark} ${r.error ?? ""}`);
}
if (autoPublish && !dryRun) {
  console.log("  ⚠️ 本次以 --auto-publish 显式旁路人工确认闸(回执已标注 auto_publish)");
}
console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

const failCount = results.filter((r) => r.ok === false && !r.skipped).length;
const skipCount = results.filter((r) => r.skipped).length;
if (failCount > 0) {
  console.log(`\n⚠️  ${failCount} 个平台发布失败，请检查上述错误信息`);
  process.exit(1);
} else {
  if (skipCount > 0) {
    console.log(`\n⏭️  ${skipCount} 个平台因不支持 --schedule 被剔除(其余平台不受影响);要发它们请去掉 --schedule 即时发布。`);
  }
  console.log(`\n✅  所有平台发布流程已完成！`);
  if (!dryRun) {
    console.log(`    请在各平台创作者中心确认发布结果`);
  }
  process.exit(0);
}

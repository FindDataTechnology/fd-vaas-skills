#!/usr/bin/env node
/**
 * task-info.mjs
 *
 * 查询一个 task 的结构化信息。默认打印摘要;--json 输出原始 manifest;
 * --list 列所有 slug 的一句话摘要。
 *
 * 用法:
 *   node task-info.mjs --slug finddata-intro         # 人读摘要
 *   node task-info.mjs --slug finddata-intro --json  # 机读 manifest
 *   node task-info.mjs --list                        # 所有 slug 一览
 */
import fs from "fs";
import path from "path";

const ROOT = "/Users/chengsishi/VAAS/downloads/fd-videos";
const args = process.argv.slice(2);
const has = (k) => args.includes(k);
const val = (k) => {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
};

function listAll() {
  if (!fs.existsSync(ROOT)) {
    console.log("(no tasks yet — downloads/fd-videos/ not found)");
    return;
  }
  const slugs = fs
    .readdirSync(ROOT)
    .filter((d) => fs.statSync(path.join(ROOT, d)).isDirectory())
    .filter((d) => fs.existsSync(path.join(ROOT, d, "task.json")));
  if (slugs.length === 0) {
    console.log("(no tasks with task.json)");
    return;
  }
  console.log(`SLUG                             STATUS      DURATION  COMPOSITION`);
  console.log(`─────────────────────────────    ──────      ────────  ──────────────`);
  for (const slug of slugs) {
    const m = JSON.parse(
      fs.readFileSync(path.join(ROOT, slug, "task.json"), "utf8"),
    );
    const dur = m.render?.durationInFrames
      ? `${(m.render.durationInFrames / (m.video?.fps ?? 30)).toFixed(1)}s`
      : "-";
    console.log(
      `${slug.padEnd(32)} ${(m.status ?? "-").padEnd(11)} ${dur.padEnd(9)} ${m.render?.composition ?? "-"}`,
    );
  }
}

function showSlug(slug, asJson) {
  const dir = path.join(ROOT, slug);
  const manifestPath = path.join(dir, "task.json");
  if (!fs.existsSync(manifestPath)) {
    console.error(`❌ no task.json at ${dir}`);
    process.exit(1);
  }
  const m = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  if (asJson) {
    console.log(JSON.stringify(m, null, 2));
    return;
  }

  const files = fs.readdirSync(dir);
  console.log(`━━━ ${slug} ━━━`);
  console.log(`Status:      ${m.status}`);
  console.log(`Created:     ${m.createdAt}`);
  console.log(`Dimensions:  ${m.video.width}×${m.video.height} @ ${m.video.fps}fps`);
  if (m.tts) {
    console.log(`\nTTS`);
    console.log(`  Model:     ${m.tts.model}`);
    console.log(`  Voice:     ${m.tts.voice ?? "-"}`);
    console.log(`  Duration:  ${m.tts.audioDurationSec ?? "-"}s`);
    console.log(`  Tokens:    ${m.tts.tokenCount ?? "-"} (fixed Latin: ${m.tts.fixedLatinTokens ?? 0})`);
  }
  if (m.render) {
    console.log(`\nRender`);
    console.log(`  Composition:      ${m.render.composition ?? "-"}`);
    console.log(`  DurationInFrames: ${m.render.durationInFrames ?? "-"}`);
    console.log(`  Output:           ${m.render.output ?? "-"}`);
  }
  if (m.distribution && m.distribution.length > 0) {
    console.log(`\nDistribution`);
    for (const d of m.distribution) {
      console.log(`  ${d.platform}/${d.account} @ ${d.uploadedAt} → ${d.url ?? "-"}`);
    }
  } else {
    console.log(`\nDistribution: (none)`);
  }
  console.log(`\nFiles`);
  for (const f of files.sort()) {
    const size = fs.statSync(path.join(dir, f)).size;
    const kb = size < 1024 ? `${size}B` : size < 1024 * 1024 ? `${(size / 1024).toFixed(1)}K` : `${(size / 1024 / 1024).toFixed(1)}M`;
    console.log(`  ${f.padEnd(28)} ${kb}`);
  }
}

if (has("--list")) {
  listAll();
} else {
  const slug = val("--slug");
  if (!slug) {
    console.error("Usage: --slug <name> [--json]  |  --list");
    process.exit(1);
  }
  showSlug(slug, has("--json"));
}

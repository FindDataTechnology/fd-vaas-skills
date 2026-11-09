#!/usr/bin/env node
/**
 * audit-docs.mjs — 文档/代码口径一致性审计（五层）
 *
 * 为什么需要：大规模重构（如 2026-11-09 Remotion 退役）只改代码不改「说法」时，
 * 文档会继续教用户跑已删的命令、传不存在的参数、填无效的 env 键。这类漂移
 * 测试抓不到（不在执行路径上）、人眼也看不过来，只能机械核对。
 *
 * 五层检查（每层都真踩过坑）：
 *   ① 路径层：文档里写的相对路径是否实体存在（含技能目录相对解析）
 *   ② 命令层：文档教的脚本是否存在（退役词必须带「退役/已删/不再」上下文）
 *   ③ 参数层：文档里的 --flag 是否在其引用的脚本里实现
 *   ④ env 层 ：.env.example 的键是否被代码读取（动态键需白名单）
 *   ⑤ 自述层：活跃代码里的过时实现自述（如「走 Remotion 静帧」）
 *
 * 用法：
 *   node scripts/audit-docs.mjs            # 全量审计，有问题退出码 1
 *   node scripts/audit-docs.mjs --layer=env
 *
 * 设计原则：**宁可漏报不可误报**。误报会训练人忽略这个工具；因此动态键、
 * 跨脚本引用、退役说明都走白名单，宁可用人工复核兜底。
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const VAAS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const layerArg = process.argv.find((a) => a.startsWith("--layer="));
const ONLY = layerArg ? layerArg.split("=")[1] : null;

/** 会被审计的文档（真源性最强的那批） */
const DOCS = [
  "README.md",
  "README.en.md",
  "AGENTS.md",
  "deploy/README.md",
  "mcp-server/README.md",
  ".agents/skills/fd-vaas-video-creator/SKILL.md",
  ".agents/skills/fd-vaas-publish-videos/SKILL.md",
  ".agents/skills/fd-vaas-publish-docs/SKILL.md",
  ".agents/skills/fd-vaas-login/SKILL.md",
  ".agents/skills/fd-vaas-pull-from-cloud/SKILL.md",
  ".agents/skills/fd-vaas-brainstorm/SKILL.md",
  ".agents/skills/fd-vaas-storyboard/SKILL.md",
];

/** 文档里的相对路径可能相对仓根，也可能相对某个技能目录 */
const PATH_BASES = [
  "",
  "mcp-server",
  "deploy",
  ".agents/skills/fd-vaas-video-creator",
  ".agents/skills/fd-vaas-publish-videos",
  ".agents/skills/fd-vaas-publish-docs",
  ".agents/skills/fd-vaas-login",
  ".agents/skills/fd-vaas-pull-from-cloud",
];

/** 已知退役词：出现可以，但必须紧邻「退役/已删/已移除/不再」上下文 */
const RETIRED = ["new-task.mjs", "task-render.mjs", "fix-tts-timings", "remotion-app"];
const RETIRED_OK = ["退役", "已删", "已移除", "不再", "不支持", "无 `--", "缺 `--", "legacy", "retired"];

/** 文档 ↔ 其引用脚本（用于参数层比对；跨脚本引用必须列全，否则误报） */
const FLAG_SOURCES = {
  "README.md": [
    ".agents/skills/fd-vaas-publish-videos/scripts/publish.mjs",
    ".agents/skills/fd-vaas-publish-docs/scripts/publish.mjs",
    ".agents/skills/fd-vaas-publish-videos/scripts/platforms/bilibili.py",
    ".agents/skills/fd-vaas-publish-videos/scripts/platforms/sau_adapter.py",
  ],
  "README.en.md": [
    ".agents/skills/fd-vaas-publish-videos/scripts/publish.mjs",
    ".agents/skills/fd-vaas-publish-docs/scripts/publish.mjs",
    ".agents/skills/fd-vaas-publish-videos/scripts/platforms/bilibili.py",
    ".agents/skills/fd-vaas-publish-videos/scripts/platforms/sau_adapter.py",
  ],
  "AGENTS.md": [
    ".agents/skills/fd-vaas-publish-videos/scripts/publish.mjs",
    ".agents/skills/fd-vaas-publish-videos/scripts/platforms/bilibili.py",
    ".agents/skills/fd-vaas-publish-videos/scripts/platforms/sau_adapter.py",
  ],
  ".agents/skills/fd-vaas-publish-videos/SKILL.md": [
    ".agents/skills/fd-vaas-publish-videos/scripts/publish.mjs",
    ".agents/skills/fd-vaas-publish-videos/scripts/platforms/sau_adapter.py",
  ],
  ".agents/skills/fd-vaas-publish-docs/SKILL.md": [
    ".agents/skills/fd-vaas-publish-docs/scripts/publish.mjs",
    ".agents/skills/fd-vaas-publish-docs/scripts/platforms/probe.py",
  ],
  ".agents/skills/fd-vaas-pull-from-cloud/SKILL.md": [
    ".agents/skills/fd-vaas-pull-from-cloud/scripts/pull_from_cloud.py",
    ".agents/skills/fd-vaas-publish-docs/scripts/publish.mjs",
  ],
};

/** 非 CLI 参数（git/rsync/语义标记等），参数层跳过 */
const NON_CLI_FLAGS = new Set([
  "--delete", "--json", "--version", "--help", "--test", "--check", "--remote", "--deploy",
  "--troubleshooting", "--proxy-notes", "--ciyuan", "--volcengine", "--flag",
  "--variable-asset-authoring--syndication",
  "--ciyuan-",           // markdown 锚点残片（…volcengine--ciyuan-双档）
  "--flag", "--flags",   // 元描述：文档在讲「参数」这个概念本身（audit-docs 说明段）
]);

/**
 * 动态 env 键白名单：代码用 `${P}_TAGS` 这类拼接读取，静态 grep 看不到实例名。
 * 漏了这里会把真实可用的键误判成僵尸键（2026-11-10 差点删掉三个有效配置）。
 */
const DYNAMIC_ENV = [
  /^[A-Z]+_TAGS$/, /^[A-Z]+_DOC_TAGS$/, /^[A-Z]+_SHORT_TITLE$/,
  /^[A-Z]+_VISIBILITY$/, /^[A-Z]+_DESC_MAX$/,
];

/** 自述层：代码里出现这些组合 = 在描述已退役的实现 */
const SELF_CLAIM = [
  { re: /remotion\s*静帧|via Remotion|remotion 渲染/gi, why: "封面/静帧已迁 chromium（W6.5）" },
  { re: /scripts\/generators\//g, why: "本地生成器脚本已随 Remotion 退役" },
];

const problems = [];
const add = (layer, file, msg) => problems.push({ layer, file, msg });

function readMaybe(rel) {
  const p = path.join(VAAS, rel);
  return fs.existsSync(p) ? fs.readFileSync(p, "utf8") : null;
}

/** 递归收集源码（跳过 node_modules / .git / 归档 change） */
function walk(dir, out = []) {
  const abs = path.join(VAAS, dir);
  if (!fs.existsSync(abs)) return out;
  for (const ent of fs.readdirSync(abs, { withFileTypes: true })) {
    if (["node_modules", ".git", "__pycache__"].includes(ent.name)) continue;
    const rel = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      if (rel.includes("openspec/changes/archive")) continue;
      walk(rel, out);
    } else if (/\.(py|mjs|js|json|sh)$/.test(ent.name)) out.push(rel);
  }
  return out;
}

// ── ① 路径层 ──────────────────────────────────────────────
function auditPaths() {
  if (ONLY && ONLY !== "path") return;
  for (const doc of DOCS) {
    const s = readMaybe(doc);
    if (!s) continue;
    const re = /(?<![\w./-])((?:\.agents|scripts|mcp-server|deploy|render-plane|brand|data|tests)\/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)/g;
    for (const m of s.matchAll(re)) {
      const cand = m[0].replace(/[.,)]+$/, "");
      if (/[<>*]/.test(cand)) continue; // 模板占位
      if (!PATH_BASES.some((b) => fs.existsSync(path.join(VAAS, b, cand)))) {
        add("path", doc, `引用了不存在的路径：${cand}`);
      }
    }
  }
}

// ── ② 命令层 ──────────────────────────────────────────────
function auditCommands() {
  if (ONLY && ONLY !== "command") return;
  for (const doc of DOCS) {
    const s = readMaybe(doc);
    if (!s) continue;
    for (const word of RETIRED) {
      let idx = s.indexOf(word);
      while (idx !== -1) {
        const ctx = s.slice(Math.max(0, idx - 120), idx + word.length + 160);
        if (!RETIRED_OK.some((k) => ctx.includes(k))) {
          add("command", doc, `提到已退役的 ${word} 但未标注退役：…${ctx.slice(100, 180)}…`);
        }
        idx = s.indexOf(word, idx + 1);
      }
    }
  }
}

// ── ③ 参数层 ──────────────────────────────────────────────
function auditFlags() {
  if (ONLY && ONLY !== "flag") return;
  for (const [doc, scripts] of Object.entries(FLAG_SOURCES)) {
    const s = readMaybe(doc);
    if (!s) continue;
    const impl = scripts.map(readMaybe).filter(Boolean).join("\n");
    if (!impl) continue;
    // 参数层同样允许「写明已移除」的正当披露（如「旧 --tid 从未生效已移除」），
    // 否则修好的文档反而会被判红——披露必须紧邻退役语。
    for (const m of s.matchAll(/--[a-z][a-z0-9-]{2,}/g)) {
      const f = m[0];
      if (NON_CLI_FLAGS.has(f) || impl.includes(f)) continue;
      const ctx = s.slice(Math.max(0, m.index - 60), m.index + f.length + 60);
      if (RETIRED_OK.some((k) => ctx.includes(k))) continue;
      add("flag", doc, `文档写了 ${f}，但引用的脚本里没有实现（且未标注已移除）`);
    }
  }
}

// ── ④ env 层 ──────────────────────────────────────────────
function auditEnv() {
  if (ONLY && ONLY !== "env") return;
  const envExample = readMaybe(".env.example");
  if (!envExample) return;
  const keys = [...envExample.matchAll(/^([A-Z][A-Z0-9_]+)=/gm)].map((m) => m[1]);
  const code = [...walk("mcp-server"), ...walk("scripts"), ...walk(".agents/skills")].map(readMaybe).filter(Boolean).join("\n");
  for (const k of keys) {
    if (code.includes(k)) continue;
    if (DYNAMIC_ENV.some((re) => re.test(k))) continue;
    add("env", ".env.example", `${k} 无任何代码读取（动态键白名单未命中）`);
  }
}

// ── ⑤ 自述层 ──────────────────────────────────────────────
function auditSelfClaims() {
  if (ONLY && ONLY !== "selfclaim") return;
  const files = [...walk("mcp-server"), ...walk("scripts")];
  for (const f of files) {
    if (f.includes("/tests/")) continue;        // 测试里的负向断言与来源注记不算漂移
    if (f.endsWith("scripts/audit-docs.mjs")) continue; // 审计器自身的规则文本不是实现自述
    const s = readMaybe(f);
    if (!s) continue;
    for (const { re, why } of SELF_CLAIM) {
      for (const m of s.matchAll(re)) {
        const line = s.slice(0, m.index).split("\n").length;
        add("selfclaim", `${f}:${line}`, `${m[0]} → ${why}`);
      }
    }
  }
}

auditPaths();
auditCommands();
auditFlags();
auditEnv();
auditSelfClaims();

if (!problems.length) {
  console.log("✅ 文档/代码口径一致（路径 / 命令 / 参数 / env / 自述 五层）");
  process.exit(0);
}
console.log(`❌ 发现 ${problems.length} 处口径漂移：\n`);
for (const p of problems) console.log(`  [${p.layer}] ${p.file}\n      ${p.msg}`);
console.log("\n修复后重跑；确属「已退役说明」的，把退役词写进相邻上下文即可。");
process.exit(1);

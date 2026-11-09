#!/usr/bin/env node
/**
 * gen-echarts-theme.mjs — VAAS 品牌主题单一来源生成器。
 *
 * 解析 brand/theme.ts 的 COLORS / FONT_SANS / FONT_MONO 导出，
 * 生成 mcp-server/mcp_server/templates/echarts/echarts-theme.json：
 *   palette — echarts 系列色板（registerTheme 后未显式指定颜色的槽位按序取色）
 *   brand   — still_graphic 品牌 CSS wrapper 的变量（bg/text/muted/字体栈…）
 *   theme   — echarts registerTheme 的主题对象（坐标轴/图例/tooltip 配色）
 *
 * 用法:
 *   node scripts/gen-echarts-theme.mjs           # 重新生成 echarts-theme.json
 *   node scripts/gen-echarts-theme.mjs --check   # 漂移检查：与仓库内 JSON 不一致则 exit 1
 *
 * theme.ts 改动后必须重跑本脚本，否则 pytest 漂移测试（tests/test_echarts_theme.py）变红。
 * 依赖：无（纯 Node 内置模块，解析用正则，不装 typescript）。
 */

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const THEME_TS = join(REPO_ROOT, "brand", "theme.ts");
const OUT_JSON = join(REPO_ROOT, "mcp-server", "mcp_server", "templates",
  "echarts", "echarts-theme.json");
const ECHARTS_VERSION = "5.5.1";

// ── 解析 theme.ts ──────────────────────────────────────────────────────────

function stripComments(src) {
  return src.replace(/\/\/[^\n]*/g, "");
}

/** 提取 `export const NAME = { ... };` 的对象体（花括号配对，容忍嵌套）。 */
function objectLiteral(src, name) {
  const re = new RegExp(`export\\s+const\\s+${name}\\s*=\\s*\\{`);
  const m = re.exec(src);
  if (!m) throw new Error(`theme.ts: export const ${name} not found`);
  let depth = 0, i = m.index + m[0].length - 1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) break; }
  }
  if (depth !== 0) throw new Error(`theme.ts: unbalanced braces in ${name}`);
  return src.slice(m.index + m[0].length - 1, i + 1);
}

/** 对象体 → {key: value}（只认 `key: "literal"` 形态，这正是 theme.ts 的写法）。 */
function parseStringMap(literal) {
  const out = {};
  const re = /([A-Za-z_$][\w$]*)\s*:\s*"([^"]*)"/g;
  let m;
  while ((m = re.exec(literal)) !== null) out[m[1]] = m[2];
  return out;
}

/** `export const NAME = "..."`（容忍换行）→ 字符串。 */
function parseStringConst(src, name) {
  const re = new RegExp(`export\\s+const\\s+${name}\\s*=\\s*"([^"]*)"`);
  const m = re.exec(src);
  if (!m) throw new Error(`theme.ts: export const ${name} not found`);
  return m[1];
}

/**
 * 部署镜像装的是 fonts-noto-cjk 包（fontconfig 家族名 "Noto Sans CJK SC"），
 * theme.ts 的字体栈只写了 "Noto Sans SC"。echarts canvas/svg 文本不走 CSS
 * 回退链，家族名对不上就会掉到默认字体（CJK 变豆腐）。这里在生成边界把
 * "Noto Sans CJK SC" 插到 PingFang 之后：macOS 开发机命中 PingFang，部署机
 * 命中 Noto CJK，theme.ts 仍是单一来源。
 */
function withNotoCJK(stack) {
  if (stack.includes("Noto Sans CJK SC")) return stack;
  return stack.replace("'PingFang SC'", "'PingFang SC','Noto Sans CJK SC'");
}

function parseThemeTs() {
  const src = stripComments(readFileSync(THEME_TS, "utf8"));
  const colors = parseStringMap(objectLiteral(src, "COLORS"));
  const required = ["bg0", "surface", "surface2", "border", "text", "muted",
    "green", "blue", "purple", "orange", "red", "cyan"];
  const missing = required.filter((k) => !colors[k]);
  if (missing.length) throw new Error(`theme.ts COLORS missing keys: ${missing}`);
  return {
    colors,
    fontSans: withNotoCJK(parseStringConst(src, "FONT_SANS")),
    fontMono: parseStringConst(src, "FONT_MONO"),
  };
}

// ── 组装 echarts-theme.json ────────────────────────────────────────────────

function buildThemeDoc({ colors, fontSans, fontMono }) {
  // 数据系列色板：蓝为主accent，绿/紫/橙/红/青依次，muted 兜底第 7 色。
  const palette = [colors.blue, colors.green, colors.purple, colors.orange,
    colors.red, colors.cyan, colors.muted];

  const theme = {
    color: palette,
    backgroundColor: "transparent",
    textStyle: { color: colors.text, fontFamily: fontSans },
    title: {
      textStyle: { color: colors.text, fontWeight: 600, fontFamily: fontSans },
      subtextStyle: { color: colors.muted, fontFamily: fontSans },
    },
    legend: {
      textStyle: { color: colors.muted, fontFamily: fontSans },
      inactiveColor: colors.dim || colors.muted,
    },
    tooltip: {
      backgroundColor: colors.surface,
      borderColor: colors.border,
      borderWidth: 1,
      textStyle: { color: colors.text, fontFamily: fontSans },
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: colors.border } },
      axisTick: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.muted },
      splitLine: { show: false },
    },
    valueAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: colors.muted },
      splitLine: { lineStyle: { color: colors.surface2 } },
    },
    timeAxis: {
      axisLine: { lineStyle: { color: colors.border } },
      axisTick: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.muted },
      splitLine: { lineStyle: { color: colors.surface2 } },
    },
    logAxis: {
      axisLine: { lineStyle: { color: colors.border } },
      axisTick: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.muted },
      splitLine: { lineStyle: { color: colors.surface2 } },
    },
  };

  const brand = {
    bg: colors.bg0,
    bg1: colors.bg1 || colors.bg0,
    surface: colors.surface,
    border: colors.border,
    text: colors.text,
    muted: colors.muted,
    accent: colors.blue,
    fontSans,
    fontMono,
  };

  return {
    meta: {
      source: "brand/theme.ts",
      echarts: ECHARTS_VERSION,
      generator: "scripts/gen-echarts-theme.mjs",
      note: "generated — do not edit by hand; re-run the generator after theme.ts changes",
    },
    palette,
    brand,
    theme,
  };
}

// ── main ───────────────────────────────────────────────────────────────────

const doc = buildThemeDoc(parseThemeTs());
const rendered = JSON.stringify(doc, null, 2) + "\n";

const check = process.argv.includes("--check");
if (check) {
  const current = readFileSync(OUT_JSON, "utf8");
  if (current !== rendered) {
    console.error(
      `echarts-theme.json drifted from theme.ts — re-run:\n` +
      `  node scripts/gen-echarts-theme.mjs`);
    process.exit(1);
  }
  console.log("echarts-theme.json up to date with theme.ts");
} else {
  writeFileSync(OUT_JSON, rendered, "utf8");
  console.log(`wrote ${OUT_JSON}`);
}

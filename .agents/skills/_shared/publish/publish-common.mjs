/**
 * publish-common.mjs — 图文/视频两个发布 skill 共用的纯函数(unify-publish-lib 设计 D2)。
 *
 * 只放两个 publish.mjs 里真正重复、且无浏览器/env 副作用的纯逻辑,统一维护、可单测:
 *   - loadEnv: 极简 dotenv(无依赖),两个 skill 逐行相同
 *   - truncate: 标题按平台字数截断(超长加 …),中文/emoji 按码点计数
 *   - stripMd / mdToPlain: markdown → 纯文本(mdToPlain 保留代码块内容)
 *   - summarize: 从正文前 N 字生成摘要
 *   - ensureSeconds: 定时串补 :00 秒(视频 skill)
 *   - limitTags: 标签列表按平台上限截断
 *
 * 无 patchright / 浏览器 / .env 实际依赖,`node --test` 直接可跑。
 * 注意:封面挑选(pickCover / resolveCoverForPlatform)与 distribution[] 回写在两个
 * skill 里语义不同(manifest 封面 map vs 文件存在性;meta.json vs task.json),故
 * 未抽到此处——强行共享会引入行为差异,违背「对拍 diff 为空」的目标。
 */
import fs from "fs";

/** 极简 dotenv:读 key=value 行,跳过注释/空行,剥引号。文件不存在返回 {}。 */
export function loadEnv(file) {
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

/** 按字数截断(超长加 …,max 为 0 或 falsy 不截断)。 */
export function truncate(s, max) {
  if (!max || !s || s.length <= max) return s ?? "";
  return s.slice(0, max - 1) + "…";
}

/** markdown → 纯文本(去 front matter/代码/图片/链接/标题/强调),供摘要等用。 */
export function stripMd(md) {
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

/** markdown -> 纯文本,但保留代码块内容(安装命令等),给不吃 markdown 的平台用。 */
export function mdToPlain(md) {
  return (md || "")
    .replace(/^---[\s\S]*?---/m, "")
    .replace(/```[a-zA-Z]*\n([\s\S]*?)```/g, "$1") // 代码块:去围栏留内容
    .replace(/`([^`\n]+)`/g, "$1")                 // 行内代码
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")          // 图片
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")       // 链接
    .replace(/^#{1,6}\s+/gm, "")                   // 标题井号
    .replace(/^\s*[-*+]\s+/gm, "• ")               // 无序列表
    .replace(/^\s*\d+\.\s+/gm, "")                 // 有序列表
    .replace(/[*_~]{1,2}/g, "")                    // 粗斜体删除线
    .replace(/^>\s?/gm, "")                        // 引用
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** 从正文前 n 字生成摘要(超长加 …)。 */
export function summarize(md, n = 120) {
  const t = stripMd(md);
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}

/** 定时串补秒:已含 :ss 则原样,否则补 ":00"。 */
export function ensureSeconds(s) {
  return /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(s) ? s + ":00" : s;
}

/** 标签列表按平台上限截断:split/trim/去空后 slice(0, max)。max=0 → 空数组。 */
export function limitTags(tags, max) {
  return (tags ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, max);
}

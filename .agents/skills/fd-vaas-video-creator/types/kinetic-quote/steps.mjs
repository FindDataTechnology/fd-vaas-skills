import fs from "fs";
import path from "path";

/**
 * kinetic-quote 自定义 pipeline 步骤：extract-keywords
 *
 * 在 scene-align 之后运行。读 script.txt 里的 `**关键词**` 显式标记，按归一化
 * 文本匹配到 scene-align 产出的各段；无标记的段退化为该段最长连续中文词（≥2 字）。
 * 写 <slug>-keywords.json（每段一个 {keyword}）到 public，注入 ctx.renderProps.keywordsSrc。
 *
 * 匹配规则（spec）：
 *   - 显式标记优先：`**词**` 的「词」归一化后命中段文本 -> 该段关键词
 *   - 否则取段内最长 CJK 连续片段（≥2 字）
 *   - 都没有则 keyword=null（模板按普通文本渲染）
 */

function normalize(s) {
  return (s ?? "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

function findMarks(script) {
  const marks = [];
  const re = /\*\*(.+?)\*\*/g;
  let m;
  while ((m = re.exec(script)) !== null) marks.push(m[1].trim());
  return marks;
}

function extractKeywords(ctx) {
  const { taskDir, PUBLIC, slug, renderProps, type } = ctx;
  const minLen = Number(type?.defaults?.minKeywordLen ?? 2);
  const longestCjk = (text) => {
    const runs = text.match(new RegExp(`[一-鿿]{${minLen},}`, "g")) || [];
    if (!runs.length) return null;
    return runs.sort((a, b) => b.length - a.length)[0];
  };

  const scenesSrc = renderProps.scenesSrc;
  if (!scenesSrc) {
    console.error("❌ extract-keywords: 缺少 scenesSrc（scene-align 未运行？）");
    process.exit(1);
  }
  const scenesPath = path.join(PUBLIC, scenesSrc);
  if (!fs.existsSync(scenesPath)) {
    console.error(`❌ extract-keywords: scenes 文件不存在: ${scenesPath}`);
    process.exit(1);
  }
  const scenes = JSON.parse(fs.readFileSync(scenesPath, "utf8"));

  const scriptPath = path.join(taskDir, "script.txt");
  let marks = [];
  if (fs.existsSync(scriptPath)) {
    marks = findMarks(fs.readFileSync(scriptPath, "utf8"));
  }

  const keywords = scenes.map((scene, i) => {
    const normScene = normalize(scene.text);
    // 显式标记：归一化后命中段文本
    const hit = marks.find((mk) => {
      const nm = normalize(mk);
      return nm.length >= 1 && normScene.includes(nm);
    });
    if (hit) return { keyword: hit, source: "marked" };
    // 退化：段内最长 CJK 词
    const auto = longestCjk(scene.text || "");
    if (auto) return { keyword: auto, source: "auto" };
    return { keyword: null, source: "none" };
  });

  const pubName = `${slug}-keywords.json`;
  fs.writeFileSync(
    path.join(PUBLIC, pubName),
    JSON.stringify(keywords) + "\n",
  );
  ctx.renderProps.keywordsSrc = pubName;

  console.log("🔑 关键词：");
  keywords.forEach((k, i) => {
    const tag =
      k.source === "marked" ? "✏️标记" : k.source === "auto" ? "🤖自动" : "—";
    console.log(`   ${i + 1}. ${k.keyword ?? "（无）"}  [${tag}]`);
  });
  console.log("");
  return ctx;
}

export default { "extract-keywords": extractKeywords };

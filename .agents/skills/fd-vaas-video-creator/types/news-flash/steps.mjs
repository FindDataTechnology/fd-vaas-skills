import fs from "fs";
import path from "path";

/**
 * news-flash 自定义 pipeline 步骤：validate-structure
 *
 * 在 scene-align 之后、preflight 之前运行。校验 meta.json 的 points 数量与
 * scene-align 产出的口播「要点段」数量一致；不一致则渲染前报错并列出对照。
 *
 * 结构约定：标题卡(hook) -> 要点卡×N -> CTA(可选)。
 *   - hook = scenes[0]
 *   - cta = 末段（role==="cta" 时）
 *   - points_scenes = 中间段
 *   - 校验 points_scenes.length === meta.points.length
 */

function readMeta(taskDir, metaInput) {
  const p = path.join(taskDir, metaInput);
  if (!fs.existsSync(p)) {
    console.error(`❌ validate-structure: meta 清单不存在: ${p}`);
    process.exit(1);
  }
  let meta;
  try {
    meta = JSON.parse(fs.readFileSync(p, "utf8"));
  } catch (e) {
    console.error(`❌ validate-structure: meta.json 解析失败: ${e.message}`);
    process.exit(1);
  }
  if (!meta || typeof meta !== "object") {
    console.error("❌ validate-structure: meta 必须是对象 {headline, points[], source?}");
    process.exit(1);
  }
  if (!Array.isArray(meta.points) || meta.points.length === 0) {
    console.error("❌ validate-structure: meta.points 必须是非空数组");
    process.exit(1);
  }
  if (typeof meta.headline !== "string" || !meta.headline.trim()) {
    console.error("❌ validate-structure: meta.headline 必填且为非空字符串");
    process.exit(1);
  }
  return meta;
}

function validateStructure(ctx) {
  const { taskDir, PUBLIC, renderProps, task } = ctx;
  const metaInput = task.inputs?.meta;
  if (!metaInput) {
    console.error("❌ news-flash 缺少 meta 输入（--meta <meta.json>）");
    process.exit(1);
  }
  const meta = readMeta(taskDir, metaInput);

  const scenesSrc = renderProps.scenesSrc;
  if (!scenesSrc) {
    console.error("❌ validate-structure: 缺少 scenesSrc（scene-align 未运行？）");
    process.exit(1);
  }
  const scenes = JSON.parse(
    fs.readFileSync(path.join(PUBLIC, scenesSrc), "utf8"),
  );

  // 结构分解：hook + 中间要点段 + (可选 cta)
  const hasCta = scenes.length >= 2 && scenes[scenes.length - 1].role === "cta";
  const hook = scenes[0];
  const pointsScenes = hasCta ? scenes.slice(1, -1) : scenes.slice(1);
  const cta = hasCta ? scenes[scenes.length - 1] : null;

  const expected = meta.points.length;
  const actual = pointsScenes.length;
  if (actual !== expected) {
    console.error(
      `\n❌ 结构校验失败：meta 要点数（${expected}）≠ 口播要点段数（${actual}）\n`,
    );
    console.error("对照（meta.points[i]  vs  口播段文本）：");
    const max = Math.max(expected, actual);
    for (let i = 0; i < max; i++) {
      const pt = i < expected ? meta.points[i] : "—";
      const ptText = typeof pt === "string" ? pt : pt?.text ?? JSON.stringify(pt);
      const sc = i < actual ? pointsScenes[i].text : "—";
      console.error(
        `   ${i + 1}. [meta] ${String(ptText).slice(0, 24)}  |  [口播] ${String(sc).slice(0, 24)}`,
      );
    }
    console.error(
      `\n调整 meta.points 数量，或在口播稿里用 \`## 段名\` 增减段，使两者一致（hook + N 要点 + cta）。`,
    );
    process.exit(1);
  }

  console.log(
    `🩺 结构校验通过：hook + ${actual} 要点${hasCta ? " + cta" : ""} = ${scenes.length} 段\n`,
  );
  return ctx;
}

export default { "validate-structure": validateStructure };

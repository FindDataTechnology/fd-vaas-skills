import fs from "fs";
import path from "path";

/**
 * data-viz 自定义 pipeline 步骤：validate-data
 *
 * 在 scene-align 之后、preflight 之前运行。校验 data.json 的 charts 数与
 * scene-align 产出的口播「图表段」数量一致；不一致则渲染前报错并列出对照。
 *
 * 结构约定：hook 大字卡 -> 图表卡×N -> CTA(可选)。
 *   - hook = scenes[0]
 *   - cta = 末段（role==="cta" 时）
 *   - chart_scenes = 中间段
 *   - 校验 chart_scenes.length === data.charts.length
 */

const VALID_TYPES = new Set(["bar", "line", "pie"]);

function readData(taskDir, dataInput) {
  const p = path.join(taskDir, dataInput);
  if (!fs.existsSync(p)) {
    console.error(`❌ validate-data: data 清单不存在: ${p}`);
    process.exit(1);
  }
  let data;
  try {
    data = JSON.parse(fs.readFileSync(p, "utf8"));
  } catch (e) {
    console.error(`❌ validate-data: data.json 解析失败: ${e.message}`);
    process.exit(1);
  }
  if (!data || typeof data !== "object") {
    console.error("❌ validate-data: data 必须是对象 {title, charts[], source?}");
    process.exit(1);
  }
  if (typeof data.title !== "string" || !data.title.trim()) {
    console.error("❌ validate-data: data.title 必填且为非空字符串");
    process.exit(1);
  }
  if (!Array.isArray(data.charts) || data.charts.length === 0) {
    console.error("❌ validate-data: data.charts 必须是非空数组");
    process.exit(1);
  }
  for (let i = 0; i < data.charts.length; i++) {
    const c = data.charts[i];
    if (!c || typeof c !== "object" || !VALID_TYPES.has(c.type)) {
      console.error(
        `❌ validate-data: charts[${i}].type 必须是 bar/line/pie，得到: ${c?.type}`,
      );
      process.exit(1);
    }
    if (c.type === "line") {
      if (!Array.isArray(c.series) || c.series.length === 0) {
        console.error(`❌ validate-data: charts[${i}] (line) 需要 series:[{name,values}]`);
        process.exit(1);
      }
      for (let j = 0; j < c.series.length; j++) {
        const s = c.series[j];
        if (!s || typeof s.name !== "string" || !Array.isArray(s.values)) {
          console.error(`❌ validate-data: charts[${i}].series[${j}] 需要 {name,values[]}`);
          process.exit(1);
        }
      }
    } else {
      // bar / pie
      if (!Array.isArray(c.values) || c.values.length === 0) {
        console.error(`❌ validate-data: charts[${i}] (${c.type}) 需要 values[]`);
        process.exit(1);
      }
    }
    if (!Array.isArray(c.labels) || c.labels.length === 0) {
      console.error(`❌ validate-data: charts[${i}] 需要 labels[]`);
      process.exit(1);
    }
  }
  return data;
}

function validateData(ctx) {
  const { taskDir, PUBLIC, renderProps, task } = ctx;
  const dataInput = task.inputs?.data;
  if (!dataInput) {
    console.error("❌ data-viz 缺少 data 输入（--data <data.json>）");
    process.exit(1);
  }
  const data = readData(taskDir, dataInput);

  const scenesSrc = renderProps.scenesSrc;
  if (!scenesSrc) {
    console.error("❌ validate-data: 缺少 scenesSrc（scene-align 未运行？）");
    process.exit(1);
  }
  const scenes = JSON.parse(
    fs.readFileSync(path.join(PUBLIC, scenesSrc), "utf8"),
  );

  // 结构分解：hook + 中间图表段 + (可选 cta)
  const hasCta = scenes.length >= 2 && scenes[scenes.length - 1].role === "cta";
  const chartScenes = hasCta ? scenes.slice(1, -1) : scenes.slice(1);

  const expected = data.charts.length;
  const actual = chartScenes.length;
  if (actual !== expected) {
    console.error(
      `\n❌ 结构校验失败：data 图表数（${expected}）≠ 口播图表段数（${actual}）\n`,
    );
    console.error("对照（data.charts[i].title/type  vs  口播段文本）：");
    const max = Math.max(expected, actual);
    for (let i = 0; i < max; i++) {
      const ch = i < expected ? `${data.charts[i].title || ""} [${data.charts[i].type}]` : "—";
      const sc = i < actual ? chartScenes[i].text : "—";
      console.error(
        `   ${i + 1}. [data] ${String(ch).slice(0, 24)}  |  [口播] ${String(sc).slice(0, 24)}`,
      );
    }
    console.error(
      `\n调整 data.charts 数量，或在口播稿里用 \`## 段名\` 增减段，使两者一致（hook + N 图表 + cta）。`,
    );
    process.exit(1);
  }

  console.log(
    `🩺 结构校验通过：hook + ${actual} 图表${hasCta ? " + cta" : ""} = ${scenes.length} 段\n`,
  );
  return ctx;
}

export default { "validate-data": validateData };

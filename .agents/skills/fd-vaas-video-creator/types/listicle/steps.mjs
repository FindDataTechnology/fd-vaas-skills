import fs from "fs";
import path from "path";

/**
 * listicle 自定义 pipeline 步骤：validate-items
 *
 * 在 scene-align 之后、preflight 之前运行。校验 items.json 的条目数与
 * scene-align 产出的口播「条目段」数量一致；不一致则渲染前报错并列出对照。
 * 同时把条目配图（如有）拷进 public/，注入 ctx.renderProps.itemImages。
 *
 * 结构约定：hook 大字卡 -> 条目卡×N -> CTA(可选)。
 *   - hook = scenes[0]
 *   - cta = 末段（role==="cta" 时）
 *   - item_scenes = 中间段
 *   - 校验 item_scenes.length === items.length
 *   - rank 倒数：第 i 个条目 -> rank = items.length - i
 */

function readItems(taskDir, itemsInput) {
  const p = path.join(taskDir, itemsInput);
  if (!fs.existsSync(p)) {
    console.error(`❌ validate-items: items 清单不存在: ${p}`);
    process.exit(1);
  }
  let items;
  try {
    items = JSON.parse(fs.readFileSync(p, "utf8"));
  } catch (e) {
    console.error(`❌ validate-items: items.json 解析失败: ${e.message}`);
    process.exit(1);
  }
  if (!items || typeof items !== "object") {
    console.error("❌ validate-items: items 必须是对象 {title, items[], source?}");
    process.exit(1);
  }
  if (typeof items.title !== "string" || !items.title.trim()) {
    console.error("❌ validate-items: items.title 必填且为非空字符串");
    process.exit(1);
  }
  if (!Array.isArray(items.items) || items.items.length === 0) {
    console.error("❌ validate-items: items.items 必须是非空数组");
    process.exit(1);
  }
  for (let i = 0; i < items.items.length; i++) {
    const it = items.items[i];
    if (!it || typeof it !== "object" || typeof it.title !== "string" || !it.title.trim()) {
      console.error(`❌ validate-items: items.items[${i}] 必须有非空 title`);
      process.exit(1);
    }
  }
  return items;
}

function validateItems(ctx) {
  const { taskDir, PUBLIC, renderProps, task } = ctx;
  const itemsInput = task.inputs?.items;
  if (!itemsInput) {
    console.error("❌ listicle 缺少 items 输入（--items <items.json>）");
    process.exit(1);
  }
  const data = readItems(taskDir, itemsInput);

  const scenesSrc = renderProps.scenesSrc;
  if (!scenesSrc) {
    console.error("❌ validate-items: 缺少 scenesSrc（scene-align 未运行？）");
    process.exit(1);
  }
  const scenes = JSON.parse(
    fs.readFileSync(path.join(PUBLIC, scenesSrc), "utf8"),
  );

  // 结构分解：hook + 中间条目段 + (可选 cta)
  const hasCta = scenes.length >= 2 && scenes[scenes.length - 1].role === "cta";
  const itemScenes = hasCta ? scenes.slice(1, -1) : scenes.slice(1);

  const expected = data.items.length;
  const actual = itemScenes.length;
  if (actual !== expected) {
    console.error(
      `\n❌ 结构校验失败：items 条目数（${expected}）≠ 口播条目段数（${actual}）\n`,
    );
    console.error("对照（items.items[i].title  vs  口播段文本）：");
    const max = Math.max(expected, actual);
    for (let i = 0; i < max; i++) {
      const it = i < expected ? data.items[i].title : "—";
      const sc = i < actual ? itemScenes[i].text : "—";
      console.error(
        `   ${i + 1}. [items] ${String(it).slice(0, 24)}  |  [口播] ${String(sc).slice(0, 24)}`,
      );
    }
    console.error(
      `\n调整 items.items 数量，或在口播稿里用 \`## 段名\` 增减段，使两者一致（hook + N 条目 + cta）。`,
    );
    process.exit(1);
  }

  // 条目配图：拷进 public/，注入 itemImages 数组（无图位为 null）
  const itemImages = [];
  for (let i = 0; i < data.items.length; i++) {
    const img = data.items[i].image;
    if (!img) {
      itemImages.push(null);
      continue;
    }
    const src = path.join(taskDir, img);
    if (!fs.existsSync(src)) {
      console.error(`❌ validate-items: 条目 ${i + 1} 配图不存在: ${src}`);
      process.exit(1);
    }
    const pubName = `${ctx.slug}-itemimg-${i}${path.extname(img)}`;
    fs.copyFileSync(src, path.join(PUBLIC, pubName));
    itemImages.push(pubName);
  }
  ctx.renderProps.itemImages = itemImages;

  const rankFirst = data.items.length; // 倒数：第 1 个条目 = rank N
  console.log(
    `🩺 结构校验通过：hook + ${actual} 条目（rank ${rankFirst}→1）${hasCta ? " + cta" : ""} = ${scenes.length} 段\n`,
  );
  return ctx;
}

export default { "validate-items": validateItems };

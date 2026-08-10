import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";

/**
 * carousel 自定义 pipeline 步骤：generate-images
 *
 * 读 task.inputs.images（images.json 清单），把每一项解析为本地文件或 seedream 生成图，
 * 统一拷到 remotion-app/public/ 为 <slug>-img-<i>.<ext>，并把 public 文件名数组注入
 * ctx.renderProps.images（render 步聚会作为 props.images 传给 CarouselVideo）。
 *
 * 清单项可为：
 *   - "path/to/img.png"          字符串路径（相对任务目录 / CWD / 绝对）
 *   - {"path":"..."}             显式本地文件
 *   - {"prompt":"...","size?":"2K"}  调 seedream-wrapper 生成
 * 当 task.inputs.generate === "true" 时，找不到文件的纯字符串项会被当作 prompt 生成。
 *
 * 生成完毕打印清单（本地/生成）供用户确认，再继续后续 pipeline。
 */

function resolveImageFile(entry, { taskDir, cwd, skill }) {
  const p = typeof entry === "string" ? entry : entry?.path;
  if (!p) return null;
  if (path.isAbsolute(p)) return fs.existsSync(p) ? p : null;
  const candidates = [
    path.join(taskDir, p),
    path.join(cwd, p),
    skill ? path.join(skill, p) : null,
  ].filter(Boolean);
  for (const tp of candidates) if (fs.existsSync(tp)) return tp;
  return null;
}

function generateWithSeedream(prompt, { skill, size, outputFormat }) {
  const wrapper = path.join(skill, "scripts/generators/seedream-wrapper.js");
  const args = [
    wrapper,
    "create",
    "--prompt",
    prompt,
    "--size",
    size || "2K",
    "--output-format",
    outputFormat || "jpeg",
  ];
  console.log(`🤖 seedream 生成: ${prompt}`);
  const res = spawnSync("node", args, { encoding: "utf8" });
  if (res.status !== 0) {
    console.error(res.stdout || res.stderr);
    throw new Error(
      `seedream 生成失败 (prompt="${prompt.slice(0, 40)}…")；若未开通图像模型，请改用本地图片路径。`,
    );
  }
  const m = res.stdout.match(/已自动下载到本地:\s*(\S+)/);
  if (!m) {
    throw new Error(
      `seedream 输出未包含本地文件路径（prompt="${prompt.slice(0, 40)}…"）；可能仅返回了在线 URL。`,
    );
  }
  const local = m[1].trim();
  if (!fs.existsSync(local)) {
    throw new Error(`seedream 返回路径不存在: ${local}`);
  }
  return local;
}

async function generateImages(ctx) {
  const { task, taskDir, PUBLIC, slug, SKILL, type } = ctx;
  const generate = String(
    task.inputs?.generate ?? type?.defaults?.generate ?? "false",
  ) === "true";

  const imagesInput = task.inputs?.images;
  if (!imagesInput) {
    console.error("❌ carousel 缺少 images 输入（--images <清单.json>）");
    process.exit(1);
  }
  const specPath = path.join(taskDir, imagesInput);
  if (!fs.existsSync(specPath)) {
    console.error(`❌ images 清单不存在: ${specPath}`);
    process.exit(1);
  }
  let entries;
  try {
    entries = JSON.parse(fs.readFileSync(specPath, "utf8"));
  } catch (e) {
    console.error(`❌ images 清单 JSON 解析失败: ${e.message}`);
    process.exit(1);
  }
  if (!Array.isArray(entries) || entries.length === 0) {
    console.error("❌ images 清单必须是非空 JSON 数组");
    process.exit(1);
  }

  const cwd = process.cwd();
  const resolved = []; // {src:'local'|'generated', label, file}
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (e && typeof e === "object" && typeof e.prompt === "string") {
      const f = generateWithSeedream(e.prompt, {
        skill: SKILL,
        size: e.size,
        outputFormat: e.outputFormat,
      });
      resolved.push({ src: "generated", label: e.prompt, file: f });
      continue;
    }
    const found = resolveImageFile(e, { taskDir, cwd, skill: SKILL });
    if (found) {
      resolved.push({
        src: "local",
        label: typeof e === "string" ? e : e?.path,
        file: found,
      });
      continue;
    }
    if (generate && typeof e === "string") {
      const f = generateWithSeedream(e, { skill: SKILL });
      resolved.push({ src: "generated", label: e, file: f });
      continue;
    }
    const label = typeof e === "string" ? e : e?.path ?? JSON.stringify(e);
    console.error(
      `❌ 图片缺失且未开启补图: ${label}\n   改用 {"prompt":"…"} 显式生成，或加 --generate true 把字符串当 prompt。`,
    );
    process.exit(1);
  }

  // 打印补图清单供确认
  console.log("\n🖼️  图片清单：");
  resolved.forEach((r, i) => {
    const tag = r.src === "generated" ? "🤖生成" : "📁本地";
    console.log(`   ${i + 1}. ${tag}  ${r.label}`);
  });
  const genCount = resolved.filter((r) => r.src === "generated").length;
  if (genCount > 0) {
    console.log(
      `\n⚠️  已自动生成 ${genCount} 张图，渲染即将继续；如不符预期请 Ctrl+C 终止。\n`,
    );
  } else {
    console.log("");
  }

  // 拷到 public
  const pubNames = [];
  for (let i = 0; i < resolved.length; i++) {
    const r = resolved[i];
    const ext = path.extname(r.file) || ".jpg";
    const pubName = `${slug}-img-${i}${ext}`;
    fs.copyFileSync(r.file, path.join(PUBLIC, pubName));
    pubNames.push(pubName);
  }
  ctx.renderProps.images = pubNames;
  console.log(
    `✅ ${pubNames.length} 张图片就位 -> public/${pubNames[0]} …\n`,
  );
  return ctx;
}

export default { "generate-images": generateImages };

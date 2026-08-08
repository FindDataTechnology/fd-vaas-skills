#!/usr/bin/env node
/**
 * generate-cover.mjs
 *
 * fd-cover-image 主入口。用 Remotion 渲染封面图。
 * 封装 remotion still 调用，提供友好的 CLI 参数。
 *
 * 用法:
 *   node generate-cover.mjs --title "寻数科技" --subtitle "..." --tags "..." --output cover.jpg
 *   node generate-cover.mjs --title "..." --orientation vertical --output cover-v.jpg
 *   node generate-cover.mjs --title "..." --template title-only --size 1080x1080 --output cover.jpg
 */

import { spawnSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const VAAS = process.env.VAAS_ROOT ?? path.resolve(__dirname, "../../../..");
const REMOTION_APP = path.join(VAAS, "remotion-app");
const DEFAULT_LOGO = path.join(VAAS, "downloads/common/icon.png");

// ─── args ───
const args = process.argv.slice(2);
const getArg = (k) => {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
};

const title = getArg("--title");
const subtitle = getArg("--subtitle") || "";
const tags = getArg("--tags") || "";
const orientation = getArg("--orientation") || "horizontal";
const sizeArg = getArg("--size");
const template = getArg("--template") || "brand";
const logoPath = getArg("--logo") === "none" ? "" : (getArg("--logo") || DEFAULT_LOGO);
const output = getArg("--output");
const format = getArg("--format");

if (!title || !output) {
  console.error(`
Usage:
  node generate-cover.mjs --title <主标题> --output <输出路径> [options]

Required:
  --title <string>        主标题
  --output <path>         输出文件路径

Options:
  --subtitle <string>     副标题（绿色，主标题下方）
  --tags <string>         底部标签文字（灰色）
  --orientation <type>    horizontal | vertical | square  (default: horizontal)
  --size <WxH>            自定义尺寸，如 1080x1440 (覆盖 orientation)
  --template <name>       brand | title-only | gradient  (default: brand)
  --logo <path|none>      Logo 路径，或 none 不加Logo  (default: downloads/common/icon.png)
  --format <fmt>          jpeg | png  (default: 按后缀推断)
`);
  process.exit(1);
}

// ─── 计算尺寸 ───
let width, height;
if (sizeArg) {
  const [w, h] = sizeArg.split("x").map(Number);
  if (!w || !h) { console.error("❌ --size 格式错误，应为 WxH，如 1920x1080"); process.exit(1); }
  width = w; height = h;
} else {
  const sizes = {
    horizontal: [1920, 1080],
    vertical: [1080, 1440],
    square: [1080, 1080],
  };
  [width, height] = sizes[orientation] || sizes.horizontal;
}

// ─── 输出格式 ───
const outExt = path.extname(output).toLowerCase();
const imgFormat = format || (outExt === ".png" ? "png" : "jpeg");

// ─── 确保 Logo 复制到 remotion-app/public ───
const publicDir = path.join(REMOTION_APP, "public");
const logoPublicName = "cover-logo.png";
const logoPublicPath = path.join(publicDir, logoPublicName);

if (logoPath && fs.existsSync(logoPath)) {
  fs.copyFileSync(logoPath, logoPublicPath);
}

// ─── 构造 Remotion props ───
// 我们直接用 BrandCover composition，通过 props 控制
// 如果 template 不同，也映射到不同的 composition
const compositionId = template === "title-only"
  ? "BrandCoverTitleOnly"
  : template === "gradient"
  ? "BrandCoverGradient"
  : "BrandCoverHorizontal";

// 对于非标准尺寸，用 props 覆盖
const props = {
  title,
  subtitle,
  tags,
  orientation: sizeArg ? (width > height ? "horizontal" : "vertical") : orientation,
  logo: logoPath ? logoPublicName : "",
};

// ─── 调用 remotion still ───
console.log(`🎨 生成封面：${title}`);
console.log(`   尺寸: ${width}×${height}`);
console.log(`   模板: ${template}`);
console.log(`   输出: ${output}`);
console.log();

const res = spawnSync(
  "npx",
  [
    "remotion", "still",
    compositionId,
    "--output", output,
    "--image-format", imgFormat,
    ...(imgFormat === "jpeg" ? ["--jpeg-quality", "95"] : []),
    "--props", JSON.stringify(props),
    "--width", String(width),
    "--height", String(height),
  ],
  {
    cwd: REMOTION_APP,
    stdio: "inherit",
    env: { ...process.env },
  }
);

if (res.status !== 0) {
  console.error(`\n❌ 渲染失败 (exit ${res.status})`);
  process.exit(1);
}

console.log(`\n✅ 封面已生成: ${output}`);
const stats = fs.statSync(output);
console.log(`   文件大小: ${(stats.size / 1024).toFixed(0)} KB`);

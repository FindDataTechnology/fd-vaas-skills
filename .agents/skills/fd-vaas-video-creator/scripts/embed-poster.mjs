#!/usr/bin/env node
/**
 * embed-poster.mjs
 *
 * 给 mp4 嵌 poster(封面/海报图),就是别人在抖音/YouTube 列表里没点
 * 播放前看到的静图。技术上是往 mp4 里添加一条 disposition=attached_pic
 * 的 mjpeg stream,不重编原视频/音频。
 *
 * 三种玩法:
 *   1. --from-frame <sec>    从当前 mp4 t=<sec> 处截一帧当封面(推荐:视频
 *                             里 CoverOrg 淡入结束的那帧,~1.0s)
 *   2. --poster <path>       用已有 png/jpg 当封面(要求分辨率同 mp4 或成比例)
 *   3. --slug <name>         按 fd-vaas task 目录约定,自动改 <task>/<slug>.mp4
 *                             和 <task>/cover.jpg
 *
 * 用法:
 *   node embed-poster.mjs --slug finddata-intro --from-frame 1.0
 *   node embed-poster.mjs --slug finddata-intro --poster external-cover.png
 *   node embed-poster.mjs --mp4 out.mp4 --poster cover.jpg
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";

const args = process.argv.slice(2);
const getArg = (k) => {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1]
    : null;
};

const slug = getArg("--slug");
const mp4Arg = getArg("--mp4");
const posterArg = getArg("--poster");
const fromFrame = getArg("--from-frame");

let mp4Path, posterPath, taskDir;

if (slug) {
  taskDir = path.join(
    process.env.VAAS_ROOT ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../.."),
    "downloads/fd-videos",
    slug,
  );
  mp4Path = path.join(taskDir, `${slug}.mp4`);
  if (!fs.existsSync(mp4Path)) {
    console.error(`❌ mp4 not found: ${mp4Path}`);
    process.exit(1);
  }
  posterPath = posterArg
    ? path.resolve(posterArg)
    : path.join(taskDir, "cover.jpg");
} else if (mp4Arg && posterArg) {
  mp4Path = path.resolve(mp4Arg);
  posterPath = path.resolve(posterArg);
} else {
  console.error(
    "Usage: --slug <name> [--from-frame <sec>] [--poster <path>]  |  --mp4 <mp4> --poster <img>",
  );
  process.exit(1);
}

// If poster doesn't exist and --from-frame given, extract it
if (!fs.existsSync(posterPath)) {
  if (!fromFrame) {
    console.error(
      `❌ poster not found: ${posterPath}. Pass --from-frame <sec> to extract from mp4, or --poster <path>.`,
    );
    process.exit(1);
  }
  console.log(`📸 extracting frame at t=${fromFrame}s -> ${posterPath}`);
  const ex = spawnSync("ffmpeg", [
    "-y", "-ss", String(fromFrame), "-i", mp4Path, "-frames:v", "1",
    "-q:v", "2", posterPath,
  ], { stdio: "inherit" });
  if (ex.status !== 0) process.exit(ex.status);
}

// Embed poster into mp4 as attached_pic
console.log(`🎬 embedding poster into ${path.basename(mp4Path)}…`);
const tmp = mp4Path + ".tmp";
const em = spawnSync("ffmpeg", [
  "-y", "-i", mp4Path, "-i", posterPath,
  "-map", "0", "-map", "1", "-c", "copy",
  "-disposition:v:1", "attached_pic",
  tmp,
], { stdio: "inherit" });
if (em.status !== 0) process.exit(em.status);

fs.renameSync(tmp, mp4Path);

// If in a task dir, bump manifest + history
if (taskDir) {
  const manifestPath = path.join(taskDir, "task.json");
  if (fs.existsSync(manifestPath)) {
    const m = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    m.render = m.render ?? {};
    m.render.poster = path.basename(posterPath);
    fs.writeFileSync(manifestPath, JSON.stringify(m, null, 2) + "\n");
  }
  const historyPath = path.join(taskDir, "history.md");
  if (fs.existsSync(historyPath)) {
    const now = new Date().toISOString();
    fs.appendFileSync(
      historyPath,
      `- ${now} — embedded poster (${path.basename(posterPath)}) as attached_pic\n`,
    );
  }
}

console.log(`✅ poster embedded`);

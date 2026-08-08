/**
 * screen-recording 类型的自定义 pipeline 步骤
 *
 * ingest: 已录好的 mp4 入库（本类型不进 Remotion，无 tts/render 步骤）
 *   1. ffprobe 实测宽高/时长
 *   2. 归位为 <slug>.mp4（rename，不复制——task 目录只留一份）
 *   3. 回写 task.json: video 实测尺寸、render.{output,durationInFrames,source}、status=rendered
 *   4. history.md 追加（含可选 notes 备注）
 *
 * 幂等：重复执行时 src 已是 <slug>.mp4，跳过 rename，只刷新实测数据。
 */
import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";

export default {
  ingest(ctx) {
    const { task } = ctx;
    const rel = task.inputs?.video;
    if (!rel) {
      console.error("❌ task.json.inputs.video 缺失（--video 是必填输入）");
      process.exit(1);
    }
    const src = path.join(ctx.taskDir, rel);
    if (!fs.existsSync(src)) {
      console.error(`❌ 视频不存在: ${src}`);
      process.exit(1);
    }

    console.log("🔍 ffprobe…");
    const probe = spawnSync(
      "ffprobe",
      [
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration",
        "-of", "json",
        src,
      ],
      { encoding: "utf8" },
    );
    if (probe.status !== 0) {
      console.error("❌ ffprobe 失败: " + (probe.stderr || probe.stdout));
      process.exit(probe.status || 1);
    }
    const info = JSON.parse(probe.stdout);
    const stream = info.streams?.[0] ?? {};
    const durationSec = Number(info.format?.duration ?? 0);
    const width = stream.width ?? task.video.width;
    const height = stream.height ?? task.video.height;
    if (!durationSec) {
      console.error("❌ ffprobe 未返回时长，文件可能损坏");
      process.exit(1);
    }

    // 归位 <slug>.mp4（rename，幂等）
    const outName = `${ctx.slug}.mp4`;
    const out = path.join(ctx.taskDir, outName);
    if (path.resolve(src) !== path.resolve(out)) {
      fs.renameSync(src, out);
      task.inputs.video = outName;
    }

    // 回写 manifest
    task.video.width = width;
    task.video.height = height;
    const frames = Math.ceil(durationSec * ctx.fps);
    task.status = "rendered";
    task.render = {
      composition: null,
      durationInFrames: frames,
      output: outName,
      source: rel,
    };
    fs.writeFileSync(ctx.manifestPath, JSON.stringify(task, null, 2) + "\n");

    const now = new Date().toISOString();
    const notes = task.inputs?.notes ? ` — ${task.inputs.notes}` : "";
    fs.appendFileSync(
      path.join(ctx.taskDir, "history.md"),
      `- ${now} — ingested ${rel} → ${outName} (${width}×${height}, ${durationSec.toFixed(2)}s, ${frames}f)${notes}\n`,
    );

    ctx.log(`\n✅ ingested → ${out} (${width}×${height}, ${durationSec.toFixed(2)}s, ${frames}f)`);
    return ctx;
  },
};

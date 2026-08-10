# carousel — 图文轮播口播视频

一张图对应一个口播段，Ken Burns 缓推/拉 + 交叉淡入；图少于段时循环复用且相邻不重复。支持 seedream 自动补图。

## 适用场景

- 图文并茂的知识科普、产品要点、步骤教学
- 已有图片素材（截图/设计图/照片），配口播串联
- 缺图时可用 seedream 按 prompt 自动生成补齐

## 输入

| 输入 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `script` | file | 是 | 口播稿。用 `## 段落名` 标记分段 = 显式对齐画面切换；不标则按停顿自动分段 |
| `images` | json | 是 | 图片清单 JSON 数组，每项见下 |
| `orientation` | enum | 否 | `1080x1920`（默认竖屏）/ `1920x1080`（横屏） |
| `generate` | enum | 否 | `true`/`false`（默认）。为 `true` 时，清单里的纯字符串项若找不到文件，则把字符串当 prompt 调 seedream 生成 |

### images 清单项格式

```json
[
  "path/to/img.png",                       // 文件路径（相对任务目录 / CWD / skill 根 / 绝对）
  {"path": "path/to/img2.jpg"},            // 显式本地文件
  {"prompt": "一只橘猫戴墨镜坐海边", "size": "2K"}  // 调 seedream 生成
]
```

## pipeline

```
generate-images -> tts -> fix-tts-timings -> scene-align -> preflight -> render
```

`generate-images` 解析清单 → 本地图拷到 `public/`，seedream 项落盘后拷入 → 注入 `props.images`（public 文件名数组）；并打印补图清单（本地/生成）供确认。

## 示例

```bash
cd <VAAS 根目录>
node .agents/skills/fd-vaas-video-creator/scripts/new-task.mjs \
  --slug carousel-demo --type carousel \
  --script .agents/skills/fd-vaas-video-creator/types/carousel/example/script.txt \
  --images .agents/skills/fd-vaas-video-creator/types/carousel/example/images.json

node .agents/skills/fd-vaas-video-creator/scripts/task-render.mjs --slug carousel-demo
# -> downloads/fd-videos/carousel-demo/carousel-demo.mp4
```

`example/` 含 3 张示例图（img-1/2/3.png，ffmpeg 生成的纯色卡）+ script.txt（3 段 `##`）+ images.json。短音频用例：`script-short.txt` + `images-short.json`。

## 设计要点

- 画面层用堆叠 AbsoluteFill（非 Sequence）算每张图的全局帧透明度，实现相邻段真正交叉淡入；Ken Burns 缩放/平移随段进度推进，奇偶段方向交替。
- 图少于段时 `buildImagePlan` 循环复用且保证相邻段不重复（≥2 张图时）。
- 字幕/配音由 `shared.tsx` 的 `Subtitles` + `<Audio>` 复用，TikTok 风逐字高亮。
- `## ` 标记是 scene-align 的结构标记，pipeline 会在 TTS 前剥离这些行（不朗读）。

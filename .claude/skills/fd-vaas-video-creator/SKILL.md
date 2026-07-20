---
name: fd-vaas-video-creator
description: 把文案变成带逐字同步字幕的口播视频。流程:new-task → TTS(seed-tts-2.0 同时返回音频+官方逐字时间戳)→ fix-tts-timings(修正 Latin token 假时长)→ preflight → Remotion 渲染 → mp4(+.srt)。所有产物强制落在 downloads/fd-videos/<slug>/ 目录,由 task.json 结构化管理。视觉层支持已有素材/seedance 视频/seedream 图片/ppt 母带。当用户想做口播视频、配音视频、解说视频、文案转视频、给素材加配音和字幕、生成带字幕的短视频,或提到 TTS+字幕+视频、自动字幕、口播、朗读配画面,以及要为抖音/小红书/B站/视频号/YouTube 出片时,务必使用本 Skill。即使用户没明说"口播视频",只要意图是把一段文字变成有人声朗读+字幕的视频,就应触发。
compatibility: Node.js 18+;ffmpeg/ffprobe;Remotion 项目 VAAS/remotion-app;byted-ark-tts-skill;需安装 @remotion/captions(首次设置,见 references/setup.md);.env 配置 VolcEngine Ark key。
---

# FD VAAS 视频创作器

把一段**文案**变成一支成片**口播视频**:AI 配音 + 逐字同步字幕 + 画面,渲染成 mp4。这是 VAAS "需求→资源→分发" 主线里"资源"这一半的核心产出技能。

## 输出约定(硬性)

**每支视频 = `downloads/fd-videos/<slug>/` 目录**。所有素材/字幕/成片/manifest 都在一起。不要把 mp4 散落在根目录,也不要用 `-v2` `-final` `-fixed` 后缀迭代。详见 `references/task-directory.md`。

同一个 slug 改配音/微调 = 覆盖成片 + 追加 `history.md`;彻底换文案 = 新 slug。

## 为什么是这套流程

口播短视频(抖音/小红书/B站)有三要素:**人声、字幕、画面**。三个已部署的工具串起来:

- **豆包 TTS**(byted-ark-tts-skill,seed-tts-2.0)开启 `enable_subtitle` 后,在同一次调用里同时返回音频和官方逐字时间戳(sentence.words[]:每个字/词的 `startTime`/`endTime`)。wrapper 会落成 `captions.json`,格式已经对齐 `@remotion/captions` 的 `Caption[]`,且**在源头已经修正过 Latin token 的假 endMs**(见 `references/tts-timings-quirk.md`)。
- **fix-tts-timings.mjs**:防御性二次校验 —— 幂等,遇到修好的字幕不会改;遗留的老 captions.json 或第三方来源可以过一遍。
- **Remotion**:合成 画面 + 配音 + 字幕,渲染 mp4。

## 首次设置(一次性)

**按 `references/setup.md` 执行**。判断标志:`remotion-app/src/VoiceoverVideo.tsx` 存在,并在 `Composition.tsx` 里注册了 `id="VoiceoverVideo"`。

## 输入约定

开工前向用户确认(能从对话里提取就别再问):

| 项 | 必填 | 说明 |
|---|---|---|
| `slug` | ✅ | task 目录名,`[a-z0-9-]`,例如 `finddata-intro`。 |
| `script` 文案 | ✅ | 口播稿正文。以文件传入。 |
| 画面来源 | ✅ | 四选一:① 已有素材(路径)② seedance 视频 ③ seedream 图片 ④ 现有 IntroduceXxx 组合模板 / ppt 母带。 |
| `voice` 音色 | ❌ | 默认按文案语言自动推断。见 byted-ark-tts-skill。 |
| `orientation` 方向 | ❌ | 默认 `1080×1920` 竖屏。B 站/YouTube 用 `1920×1080`。 |
| 字幕样式 | ❌ | 默认 TikTok 绿色逐字高亮。见 `references/subtitle-styling.md`。 |
| 需要封面? | ❌ | **两种概念**,见 `references/cover-scene.md`:①**播放前 poster**(列表里没点前的静图,`embed-poster.mjs` 嵌进 mp4 attached_pic 流);②**片头 cover scene**(视频里的开头 60 帧动画卡)。经常同时用,poster 从 cover scene 截。 |

## 主流程(推荐:一键 pipeline)

```bash
SKILL=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-video-creator/scripts

# 1. 建 task 目录(拷 script + 初始化 task.json/history.md)
node $SKILL/new-task.mjs --slug <slug> --script /path/to/script.txt \
  [--width 1920 --height 1080] [--voice <id>]

# 2. 一键:TTS → fix-tts-timings → preflight → render → 回写 manifest
node $SKILL/task-render.mjs --slug <slug> \
  [--voice <id>] \
  [--composition VoiceoverVideo | IntroduceOrg | ...] \
  [--extra-props '{"videoSrc":"bg.mp4"}']
```

产物:`downloads/fd-videos/<slug>/<slug>.mp4` + 完整素材目录。

`task-render.mjs` 里跑的每一步都可以单独调,见下面"手工流程"。

## 查询已有 task

```bash
SKILL=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-video-creator/scripts

node $SKILL/task-info.mjs --list                      # 所有 slug 一览
node $SKILL/task-info.mjs --slug finddata-intro       # 单个 task 人读摘要
node $SKILL/task-info.mjs --slug finddata-intro --json # 机读 manifest
```

或者直接 `cat downloads/fd-videos/<slug>/task.json`。

## 手工流程(需要拆步调试时)

所有命令在 `VAAS/remotion-app/` 下执行,`SKILL` 同上。

### 1. TTS → 音频 + 原始字幕

```bash
cd /Users/chengsishi/VAAS/remotion-app
node scripts/generate-voiceover.mjs --file /path/to/script.txt [--voice <id>]
# 输出:public/voiceover-<ts>.mp3, public/captions-<ts>.json
```

### 2. 修正 Latin token 假时长(**必做**)

```bash
node $SKILL/fix-tts-timings.mjs \
  --in  public/captions-<ts>.json \
  --out public/captions-<ts>-fixed.json
```

背景见 `references/tts-timings-quirk.md`。跳过这步 = 字幕闪一下就消失,和声音对不上。

### 3. 算帧数

```bash
# 用 captions 最后一个 endMs 更稳(TTS 官方给的音频精确长度)
python3 -c 'import json,sys; c=json.load(open(sys.argv[1])); print(round(c[-1]["endMs"]/1000*30)+15)' \
  public/captions-<ts>-fixed.json
```

或用 ffprobe:`ceil(duration * fps) + 15`。

### 4. 体检(preflight)

```bash
node $SKILL/preflight.mjs \
  --audio public/voiceover-<ts>.mp3 \
  --captions public/captions-<ts>-fixed.json \
  --frames <n>
```

三项检查:mp3 时长 vs 帧数、caption 有无未修 Latin token、captions 是否超出音频。任何一项失败退出非 0。

### 5. Render

```bash
npx remotion render VoiceoverVideo /path/to/<slug>/<slug>.mp4 \
  --props='{"audioSrc":"voiceover-<ts>.mp3","captionsSrc":"captions-<ts>-fixed.json","durationInFrames":<n>,"videoSrc":"bg.mp4","width":1080,"height":1920}'
```

`--props` 字段(相对 `public/`,不带前导 `/`):

| 字段 | 必填 | 说明 |
|---|---|---|
| `audioSrc` | ✅ | 配音 |
| `captionsSrc` | ✅ | **修正后的** captions JSON |
| `durationInFrames` | ✅ | 第 3 步 |
| `videoSrc` / `imageSrc` / `images` | 视觉三选一 | 背景视频 / 单张图 / 图片轮播 |
| `width` `height` | ❌ | 默认 1080/1920 |
| `subtitleColor` `subtitleSize` | ❌ | 见 subtitle-styling.md |

### 6. .srt(可选)

```bash
node $SKILL/captions-to-srt.mjs \
  --json public/captions-<ts>-fixed.json \
  --out /path/to/<slug>/captions.srt
```

## 组合视频模板(IntroduceOrg 之类)

`remotion-app/src/Composition.tsx` 里除了参数化的 `VoiceoverVideo`,还预注册了带动画场景的组合模板(`IntroduceOrg` 含 5 幕 + 2s 封面, `IntroduceGov`, `IntroduceReport` 等)。这些模板把音频、字幕、场景动画一起打包,渲染时只需要给对应的 `--composition <id>` + 手工传 `audioSrc` prop。字幕文本/时间戳硬编码在 `src/SubtitleBar.tsx` 里(不像 `VoiceoverVideo` 那样从 JSON 加载),想复用一个模板换文案 = 改 `SubtitleBar.tsx` 或者新写一个 composition。

**判断**:一次性动画大片(需要视觉设计)走模板;标准口播 + 素材(视频/图片轮播)走 `VoiceoverVideo`。

## 分发(可选)

```bash
cd /Users/chengsishi/VAAS/social-auto-upload
sau douyin upload-video --account <name> \
  --file /Users/chengsishi/VAAS/downloads/fd-videos/<slug>/<slug>.mp4 \
  --title "…" --desc "…" --tags a,b
```

成功后手工更新 `task.json` 的 `distribution` 数组。

## 关键注意点(踩过的坑)

- **必跑 fix-tts-timings**:seed-tts-2.0 对 Latin token(英文名、URL、`Star、`)返回的 endMs 是假的(30-45ms),真实读音藏在 gap 里。修正规则见 `references/tts-timings-quirk.md`。
- **时长永远以配音为准**:别用文案字数估。用 captions 最后 `endMs` 或 ffprobe。`preflight.mjs` 强制体检。
- **画面静音**:配音是唯一音轨。背景视频原声被丢弃。
- **一支视频一个 slug 一个目录**:不许 `-v2`/`-final`/`-fixed` 后缀。修改用 history.md 记账。
- **字幕来自 TTS 官方,不用 ASR**:比 whisper 精度更高、更快、不依赖 1.5GB 模型下载。

## 故障排查

- **字幕闪一下就消失**:没跑 `fix-tts-timings.mjs`。
- **音画结尾对不齐**:`durationInFrames` 和 mp3 实测时长差得多。`preflight.mjs` 会挡下。
- **TTS 401/鉴权失败**:检查 `.env` 的 Volcengine key,见 byted-ark-tts-skill。
- **没生成 captions.json**:确认没传 `--no-subtitle`;确认用的模型是 `seed-tts-2.0`(1.0 不支持)。
- **render 报 `@remotion/captions` 找不到**:重跑 `references/setup.md`。
- **render 报 props 解析失败**:JSON 引号、路径不带前导 `/`、数组格式。
- **字幕对不齐(不是英文导致的)**:确认渲染用的 audio 和 captions 是**同一次 TTS 产出的一对**;混用不同批次会错位。

## 参考

- `references/task-directory.md` —— **task 目录结构 + task.json schema**
- `references/tts-timings-quirk.md` —— **seed-tts-2.0 Latin token 假 endMs 踩坑与修法**
- `references/cover-scene.md` —— 封面幕(2s 静音品牌卡)接法
- `references/setup.md` —— 首次设置(装 @remotion/captions、装合成组件)
- `references/voiceover-video-composition.tsx` —— VoiceoverVideo 源码
- `references/subtitle-styling.md` —— 字幕样式调参
- `scripts/new-task.mjs` —— 建 task 目录 + manifest
- `scripts/task-render.mjs` —— 一键 pipeline(TTS → 修字幕 → preflight → render → 回写)
- `scripts/fix-tts-timings.mjs` —— 修正 Latin token 假 endMs
- `scripts/preflight.mjs` —— 渲染前三方对齐体检
- `scripts/captions-to-srt.mjs` —— Caption JSON → .srt

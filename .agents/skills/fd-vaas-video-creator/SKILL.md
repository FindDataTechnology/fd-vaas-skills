---
name: fd-vaas-video-creator
description: >
  视频创作主技能,产出可直接发布的 mp4。支持两种视频类型:
  (1) 口播视频——文案转 AI 配音+逐字同步字幕+画面,流程:new-task → TTS(seed-tts-2.0)→
  fix-tts-timings → preflight → Remotion 渲染 → mp4(+.srt);
  (2) 录屏/网页操作视频——用浏览器打开目标页面,操作过程中用 cap 录屏,
  产出 mp4(可配麦克风解说)。所有产物强制落在 downloads/fd-videos/<slug>/ 目录,
  由 task.json 结构化管理。视觉层支持已有素材/seedance 视频/seedream 图片/ppt 母带。
  **内置三大生成器**:TTS 语音合成(tts-wrapper.js)、AI 图片生成(seedream-wrapper.js)、
  AI 视频生成(seedance-wrapper.js),均位于 scripts/generators/。
  当用户想做口播视频、配音视频、解说视频、文案转视频、给素材加配音和字幕、
  生成带字幕的短视频、录屏视频、网页录屏、操作演示视频、实操视频、屏幕录制、
  打开网站录下来、网页操作过程录制,以及要为抖音/小红书/B站/视频号/YouTube 出片时,
  务必使用本 Skill。即使用户没明说"视频",只要意图是产出一段可发布的视频内容,就应触发。
  当用户说"生成语音""配音""转语音""生成图片""画一张""生图""生成视频""做个视频"等
  单独生成需求时,也使用本 Skill 的生成器脚本。
compatibility: Node.js 18+;ffmpeg/ffprobe;Remotion 项目 VAAS/remotion-app;fd-browser-record skill(ego-browser + cap);需安装 @remotion/captions(首次设置,见 references/setup.md);.env 配置 VolcEngine Ark key;屏幕录制权限授予 Cap.app。
---

# FD VAAS 视频创作器

把一段**文案**变成一支成片**口播视频**:AI 配音 + 逐字同步字幕 + 画面,渲染成 mp4。这是 VAAS "需求→资源→分发" 主线里"资源"这一半的核心产出技能。

## 输出约定(硬性)

**每支视频 = `downloads/fd-videos/<slug>/` 目录**。所有素材/字幕/成片/manifest 都在一起。不要把 mp4 散落在根目录,也不要用 `-v2` `-final` `-fixed` 后缀迭代。详见 `references/task-directory.md`。

同一个 slug 改配音/微调 = 覆盖成片 + 追加 `history.md`;彻底换文案 = 新 slug。

**两种视频类型**,task.json 用 `type` 字段区分(没有 type 字段默认口播):
- `voiceover` — 口播视频(TTS + 字幕 + Remotion)
- `screen-recording` — 录屏/网页操作视频(ego-browser + cap)

## 为什么是这套流程

口播短视频(抖音/小红书/B站)有三要素:**人声、字幕、画面**。三个已部署的工具串起来:

- **豆包 TTS**(`scripts/generators/tts-wrapper.js`,seed-tts-2.0)开启 `enable_subtitle` 后,在同一次调用里同时返回音频和官方逐字时间戳(sentence.words[]:每个字/词的 `startTime`/`endTime`)。wrapper 会落成 `captions.json`,格式已经对齐 `@remotion/captions` 的 `Caption[]`,且**在源头已经修正过 Latin token 的假 endMs**(见 `references/tts-timings-quirk.md`)。
- **fix-tts-timings.mjs**:防御性二次校验 —— 幂等,遇到修好的字幕不会改;遗留的老 captions.json 或第三方来源可以过一遍。
- **Remotion**:合成 画面 + 配音 + 字幕,渲染 mp4。

## 首次设置(一次性)

**按 `references/setup.md` 执行**。判断标志:`remotion-app/src/VoiceoverVideo.tsx` 存在,并在 `Composition.tsx` 里注册了 `id="VoiceoverVideo"`。


## 注意事项
先写剧本，再向用户确认，用户通过了才可以进行渲染
剧本的画面要和内容保持一致，用适量的画面保证视频的表达更有利
用户制作口播视频的时候，用remotion生成页面，如果不是用户要求，不要用ai生图
remotion渲染视频前要注意使用正确的音频和字幕文件


## 输入约定


开工前向用户确认(能从对话里提取就别再问):

| 项 | 必填 | 说明 |
|---|---|---|
| `slug` | ✅ | task 目录名,`[a-z0-9-]`,例如 `finddata-intro`。 |
| `script` 文案 | ✅ | 口播稿正文。以文件传入。 |
| 画面来源 | ✅ | 四选一:① 已有素材(路径)② seedance 视频 ③ seedream 图片 ④ 现有 IntroduceXxx 组合模板 / ppt 母带。 |
| `voice` 音色 | ❌ | 默认按文案语言自动推断。见 `scripts/generators/tts-wrapper.js voices`。 |
| `orientation` 方向 | ❌ | 默认 `1080×1920` 竖屏。B 站/YouTube 用 `1920×1080`。 |
| 字幕样式 | ❌ | 默认 TikTok 绿色逐字高亮。见 `references/subtitle-styling.md`。 |
- `references/seedance-readme.md` -- Seedance 视频生成完整文档
- `references/seedance-model-matrix.json` -- Seedance 模型能力矩阵
- `references/seedream-readme.md` -- Seedream 图片生成完整文档
- `references/seedream-model-matrix.json` -- Seedream 模型能力矩阵
| 需要封面? | ❌ | **两种概念**,见 `references/cover-scene.md`:①**播放前 poster**(列表里没点前的静图,`embed-poster.mjs` 嵌进 mp4 attached_pic 流);②**片头 cover scene**(视频里的开头 60 帧动画卡)。经常同时用,poster 从 cover scene 截。 |

### 开工前必须检查的公开/共同资料(硬性)

做任何视频前,先扫一遍以下位置,**有现成素材优先复用,不要从零生造**:

1. **`downloads/common/`** —— 通用片尾、品牌图标、封面模板、公司介绍片等。如果用户提到「加片尾」「用通用片尾」,默认从这里取最新的 `company-introduce.mp4`(或目录里最新的片尾文件)。
2. **历史 task 目录** —— `downloads/fd-videos/` 下已有的视频,复用同品牌/同系列的:
   - 配音音色(保持人设一致)
   - 字幕样式(颜色 / 大小 / 位置)
   - 品牌视觉风格(配色 / 模板 / 封面格式)
   - CTA 话术
3. **项目 `AGENTS.md` 和 README** —— 产品名称标准写法、Slogan、定位描述,**脚本里的产品名和 Slogan 必须与官方表述完全一致**。
4. **Remotion 现有模板** —— `remotion-app/src/scenes*.tsx` 里有现成的场景组件(Gov / Report / Org / Brand 等),风格接近的直接复用或改造,不要重写一套视觉语言。

**原则:品牌一致性 > 创新。** 同一家公司/同一个 IP 的视频,听上去、看上去应该是一家的。

## 视频类型判断(开工前先选)

收到需求后,先判断走哪条线:

| 类型 | 典型需求 | 产出方式 | 关键工具 |
|---|---|---|---|
| **口播视频**(默认) | "把这段文案做成视频"、"配个音加字幕"、"讲解视频" | TTS + 字幕 + Remotion 渲染 | seed-tts-2.0 + Remotion |
| **录屏/网页操作视频** | "录个网页操作"、"操作演示"、"打开 XX 网站录下来"、"实操视频"、"屏幕录制" | 打开浏览器 → 操作 → cap 录屏 → 导出 mp4 | ego-browser + cap(通过 `fd-browser-record` skill) |

判断不清时问用户一句:"是口播配音视频还是录屏操作视频?"。不要硬套口播流程到录屏需求上。

**录屏视频直接调 `fd-browser-record` skill** —— 那个 skill 封装了浏览器操作 + cap 录屏的全部细节(权限处理、窗口匹配、后台录制、导出)。本 skill 负责 task 目录管理、产出物回写 task.json、以及和 publish 的衔接。

## 录屏视频流程

调用 `fd-browser-record` skill 完成录制,最终 mp4 纳入 task 目录,publish 流程和口播视频完全一致。

### 1. 建 task 目录

用 `new-task.mjs` 建目录。录屏视频**不需要文案文件**,但 `new-task.mjs` 强制要 `--script`,所以传一个占位说明文件:

```bash
# 先写一个操作说明文件(代替 script.txt,记录要录什么)
echo "操作演示:打开 example.com,展示首页内容" > /tmp/recording-plan.txt

SKILL=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-video-creator/scripts
node $SKILL/new-task.mjs --slug <slug> --script /tmp/recording-plan.txt \
  --width 1920 --height 1080
```

`script.txt` 里存的是录屏操作说明,不是口播稿。`task.json` 初始 status 是 `draft`。

### 2. 调用 fd-browser-record 录制

**加载 `fd-browser-record` skill** 后执行录制。把输出直接放进 task 目录:

```bash
TASK_DIR=/Users/chengsishi/VAAS/downloads/fd-videos/<slug>
BROWSER_RECORD=/Users/chengsishi/VAAS/.claude/skills/fd-browser-record/scripts/cap-record.sh

# 方式 A:录浏览器窗口(推荐,画面干净,只有网页)
# 先打开目标网页(ego-browser),再录 Chrome/浏览器窗口
bash "$BROWSER_RECORD" record-window \
  --match "Google Chrome" \
  --duration <秒数> \
  --output "$TASK_DIR/<slug>.mp4"

# 方式 B:录主屏(需要展示桌面/多窗口操作时用)
bash "$BROWSER_RECORD" record-screen \
  --duration <秒数> \
  --output "$TASK_DIR/<slug>.mp4"

# 方式 C:后台录制(操作时间不确定,操作完再停)
bash "$BROWSER_RECORD" record-window --match "Google Chrome" --detach \
  --output "$TASK_DIR/<slug>.cap"
# ... 用 ego-browser 做操作 ...
bash "$BROWSER_RECORD" stop \
  --cap-file "$TASK_DIR/<slug>.cap" \
  --export "$TASK_DIR/<slug>.mp4"
```

**录制时长默认值**:用户没说时长的话,根据操作复杂度估,默认 15 秒起。简单操作 15s,中等 30s,复杂流程 60s。宁愿多录不要少录,长了可以后剪。

### 3. 回写 task.json

录完后,用一段 Node 脚本更新 task.json,把录屏元数据写进去,status 设为 `rendered`:

```bash
node -e "
const fs = require('fs');
const path = require('path');
const dir = '/Users/chengsishi/VAAS/downloads/fd-videos/<slug>';
const task = JSON.parse(fs.readFileSync(path.join(dir, 'task.json'), 'utf8'));
task.status = 'rendered';
task.type = 'screen-recording';    // 标记视频类型
task.recording = {
  source: 'browser-window',        // browser-window | screen
  tool: 'cap',
  windowApp: 'Google Chrome',      // 录的哪个 App 的窗口(主屏录的话省略)
  targetUrl: 'https://example.com', // 操作的网页(如果有)
  durationSec: 15,                 // 实际时长
  output: '<slug>.mp4',
  capProject: '<slug>.cap',        // 如果保留了 .cap 工程
};
task.render = {
  composition: 'screen-recording',
  durationInFrames: 15 * 30,       // 估算值,精确值用 ffprobe
  output: '<slug>.mp4',
};
fs.writeFileSync(path.join(dir, 'task.json'), JSON.stringify(task, null, 2) + '\n');
// 追加 history
const history = fs.readFileSync(path.join(dir, 'history.md'), 'utf8');
fs.writeFileSync(path.join(dir, 'history.md'),
  history + '- ' + new Date().toISOString() + ' — recorded via cap (browser window, 15s) → <slug>.mp4\n');
console.log('✅ task.json updated (status=rendered, type=screen-recording)');
"
```

录屏视频的 `type` 字段是 `screen-recording`,和口播视频区分。publish 流程不关心这个字段,照样能发。

### 4. 后续流程(和口播视频一致)

- 加封面:用 `scripts/generate-covers.mjs --slug <name> --title "..."` 一键生成 6 平台统一公司风格封面(横/竖/YouTube/视频号共 4 张,自动回写 task.json render.covers),或用 `embed-poster.mjs` 嵌进 mp4;发布时 publish.mjs 发现没封面会自动补全
- 发布:走 `fd-vaas-publish-videos`,和口播视频一样按 slug 找到 mp4

## 主流程(口播视频 · 推荐:一键 pipeline)

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
- `references/seedance-readme.md` -- Seedance 视频生成完整文档
- `references/seedance-model-matrix.json` -- Seedance 模型能力矩阵
- `references/seedream-readme.md` -- Seedream 图片生成完整文档
- `references/seedream-model-matrix.json` -- Seedream 模型能力矩阵

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
- **时长永远以配音为准**:别用文案字数估。**用 ffprobe 实测音频时长**,不要用 captions 最后 `endMs`——seed-tts 音频尾部常有 1~1.5s 静音没被 caption 覆盖,`lastEndMs` < 实测时长,用它算帧会 preflight drift>0.5s 失败。帧数 = `ceil(audio_sec * fps) + 小余量`,保证 `frames/fps >= audio` 且 drift<0.5s。`preflight.mjs` 强制体检。
- **画面静音**:配音是唯一音轨。背景视频原声被丢弃。
- **一支视频一个 slug 一个目录**:不许 `-v2`/`-final`/`-fixed` 后缀。修改用 history.md 记账。
- **字幕来自 TTS 官方,不用 ASR**:比 whisper 精度更高、更快、不依赖 1.5GB 模型下载。
- **硬编码场景 composition 不能缩短 durationInFrames**:带固定 Sequence(如片头/CTA 用 `durationInFrames - N`)的 composition,传小于 N 的 props.durationInFrames 会让该场景算负值,Remotion 报 `durationInFrames must be positive, but got -X`。音频比原设计短时,**新建 composition** 按 captions 逐字时间戳重排场景边界,别改原 composition(历史视频可能重渲染)。
- **theme.ts COLORS 字段必须和场景用法一致**:场景里 `COLORS.textMuted` 之类若 theme.ts 没定义 -> `undefined` -> `color: undefined` 让文字回退浏览器默认**黑色**,深色背景上看不清。新增/改场景前先 `grep -oE 'COLORS\.\w+' src/scenes*.tsx | sort -u` 对照 `theme.ts`,缺的字段补上或改用已定义别名(`muted`/`bg0` 等)。
- **JSX 文本里裸 `>` 非法**:注释/说明文字里的 `->`(hyphen+大于号)会让 esbuild 报 `The character ">" is not valid inside a JSX element`。用中文箭头 `->` 或 `&gt;` 转义。重写场景时别把原文件的 `->` 误打成 `->`。
- **场景边界与口播对齐**:渲染前从 `captions.json` 逐字时间戳提取口播段落起止帧(写脚本匹配每段首字 token 的 startMs),映射到各 `<Sequence from= durationInFrames=>`,画面切换才和口播内容同步。`task-render.mjs` 只用 captions endMs 算总帧数,场景内部分段要自己提取对齐。

### 视频拼接 · 音频质量约束(硬性)

凡是用 ffmpeg 拼接多段视频(片头/正片/片尾/通用片尾等),**必须满足以下音频质量要求**,不许直接 `-c copy` 硬切：

1. **响度归一化**:所有片段统一到 `-16 LUFS`(TP -1.5, LRA 11),用 `loudnorm` 滤镜两遍 pass,保证各段音量一致。
2. **拼接处交叉淡入淡出**:
   - 前一段结尾做 `afade=t=out` 淡出(推荐 0.3~0.5s)
   - 后一段开头做 `afade=t=in` 淡入(推荐 0.1~0.2s)
   - 禁止硬切,避免爆音和音量跳变。
3. **音频格式统一**:
   - 采样率 `48000 Hz`,双声道 `stereo`
   - 编码 AAC,码率 ≥ 128kbps
   - 各段参数不一致时,用 `concat` filter 统一重编码,不能用 concat demuxer 直接 copy。
4. **推荐做法**:用 `filter_complex` 一步完成「响度归一 + 淡入淡出 + 拼接 + 重编码」,而不是分多步处理。
5. **拼接后验证**:跑一遍 `ffmpeg -i out.mp4 -af loudnorm=print_format=json -f null -`,确认整体响度在 -16±1 LUFS 范围内。

## 内置生成器(独立使用)

本 skill 内置三大 AI 生成器,位于 `scripts/generators/`。它们是口播视频流程的底层引擎,也可以**独立调用**满足单独的语音/图片/视频生成需求。

### 1. TTS 语音合成 (`tts-wrapper.js`)

豆包 TTS(seed-tts-2.0),文转语音 + 官方逐字时间戳。

```bash
GEN=/Users/chengsishi/VAAS/.agents/skills/fd-vaas-video-creator/scripts/generators

# 合成语音(自动推断音色)
node $GEN/tts-wrapper.js create --text "欢迎使用豆包语音合成"

# 从文件读取
node $GEN/tts-wrapper.js create --file /path/to/script.txt

# 指定音色 + 语速
node $GEN/tts-wrapper.js create --text "快点读" --speed 1.5

# 列出所有音色
node $GEN/tts-wrapper.js voices
```

关键参数:`--text`/`--file`(必填)、`--voice`(默认自动推断)、`--speed`(0.25~4.0)、`--format`(默认 mp3)、`--no-subtitle`(关闭逐字时间戳,默认开启)。默认开启 `enable_subtitle`,额外产出 `captions.json`(对齐 `@remotion/captions`)。

### 2. AI 图片生成 (`seedream-wrapper.js`)

豆包 Seedream,文生图/图生图/联网搜索增强/批量生成。同步出图,调用即返回。

```bash
node $GEN/seedream-wrapper.js create \
  --prompt "一只戴着墨镜的橘猫,坐在海边,日落,超写实" \
  --size 2K --output-format png
```

关键参数:`--prompt`(必填)、`--size`(2K/3K/4K 或自定义像素)、`--output-format`(png/jpeg)、`--watermark`(默认 false)、`--image`(参考图,图生图)、`--n`(批量生成数,最多 15)。Wrapper 根据参数自动路由模型(Agent 不需指定 `--model`)。

### 3. AI 视频生成 (`seedance-wrapper.js`)

豆包 Seedance,文生视频/图生视频/首尾帧控制。智能调度:短任务前台等,长任务自动异步。

```bash
node $GEN/seedance-wrapper.js create \
  --prompt "小猫在草地上奔跑,阳光明媚,高清" \
  --duration 5 --ratio 16:9
```

关键参数:`--prompt`(必填)、`--duration`(秒)、`--ratio`(16:9/9:16/1:1 等)、`--model`(自动路由,一般不指定)、`--first-frame`/`--last-frame`(首尾帧图片)、`--wait true`(强制同步等待)。模型矩阵见 `references/seedance-model-matrix.json`。

> 💡 生成器脚本的详细参数、模型列表、故障排查见各自 SKILL.md 原文,已合并到 `references/` 目录(`seedance-readme.md`、`seedream-readme.md`)。

## 故障排查

- **字幕闪一下就消失**:没跑 `fix-tts-timings.mjs`。
- **音画结尾对不齐**:`durationInFrames` 和 mp3 实测时长差得多。`preflight.mjs` 会挡下。
- **TTS 401/鉴权失败**:检查 `.env` 的 Volcengine key,见 `scripts/generators/tts-wrapper.js`。
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
- `references/seedance-readme.md` -- Seedance 视频生成完整文档
- `references/seedance-model-matrix.json` -- Seedance 模型能力矩阵
- `references/seedream-readme.md` -- Seedream 图片生成完整文档
- `references/seedream-model-matrix.json` -- Seedream 模型能力矩阵
- `scripts/new-task.mjs` —— 建 task 目录 + manifest
- `scripts/task-render.mjs` —— 一键 pipeline(TTS → 修字幕 → preflight → render → 回写)
- `scripts/fix-tts-timings.mjs` —— 修正 Latin token 假 endMs
- `scripts/preflight.mjs` —— 渲染前三方对齐体检
- `scripts/captions-to-srt.mjs` —— Caption JSON → .srt
- `scripts/generators/tts-wrapper.js` -- TTS 语音合成(豆包 seed-tts-2.0)
- `scripts/generators/seedream-wrapper.js` -- AI 图片生成(豆包 Seedream)
- `scripts/generators/seedance-wrapper.js` -- AI 视频生成(豆包 Seedance)

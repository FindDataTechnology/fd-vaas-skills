# 封面(Cover)· 两个不同的东西

短视频有两种"封面",别搞混:

| 概念 | 时机 | 别名 | 落地方式 |
|---|---|---|---|
| **播放前 poster** | 用户没点播放时列表里看到的那张海报 | thumbnail / attached_pic | mp4 里附一条 mjpeg attached_pic 流,`scripts/embed-poster.mjs` |
| **片头 cover scene** | 开播后的前 1-2 秒,视频里的第一个场景 | opening / brand card | Remotion 里加一个 Sequence,`VoiceoverVideo` 的 `coverImage`+`coverFrames` prop |

两者可以完全独立:视频里第一帧 ≠ 平台列表 poster。绝大多数平台不会自动把第一帧当 poster —— 有 attached_pic 就用 attached_pic,没有就用平台自己的算法(通常抽 t=0 或 t=1s 的帧)或人工上传的封面图。

## 播放前 poster(用户提到"封面"通常指这个)

```bash
export VAAS=<VAAS 仓库根目录,如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代
SKILL=$VAAS/.agents/skills/fd-vaas-video-creator/scripts

# 从视频里 t=1.0s 处截一帧作 poster(若已有 CoverOrg 淡入完的画面)
node $SKILL/embed-poster.mjs --slug finddata-intro --from-frame 1.0

# 或者用外部图(seedream 生成/PPT 导出/自己 P 的)
node $SKILL/embed-poster.mjs --slug finddata-intro --poster /path/to/cover.png

# 非 task 目录直接嵌
node $SKILL/embed-poster.mjs --mp4 out.mp4 --poster cover.jpg
```

**校验**:
```bash
ffprobe -v error -show_streams -select_streams v <mp4> | grep -E "codec_name|attached_pic"
# 期望:两条 v 流,第二条 mjpeg + DISPOSITION:attached_pic=1
```

**注意**:抖音/小红书上传时会自动读封面;YouTube API 需另用 thumbnails.set;B站在稿件页可手工换。不同平台细节见 `social-auto-upload/CLAUDE.md`。

## 片头 cover scene(视频里的开头)

短视频里的开头静止品牌卡,增加辨识度。约定:**开头 60 帧(2s)静止画,无配音、无字幕**,配音和其它场景整体后移。

### VoiceoverVideo(参数化模板,推荐)

`VoiceoverVideo` 支持 `coverImage` + `coverFrames` prop,一行 prop 就搞定,不改代码:

```bash
npx remotion render VoiceoverVideo out.mp4 --props='{
  "audioSrc":"voiceover.mp3",
  "captionsSrc":"captions.json",
  "durationInFrames": 2461,     // narration_frames + coverFrames
  "videoSrc":"bg.mp4",
  "coverImage":"cover.png",     // 相对 remotion-app/public/,不带前导斜杠
  "coverFrames": 60             // 可省,默认 60(2s @30fps)
}'
```

**要点**:
- `durationInFrames` 是**总长**(封面 + 讲解),不是讲解长度。少 60 帧就等于把讲解的末尾切掉。
- 封面期间音频和字幕不出现;讲解 Sequence 内部时间归零,你不需要给字幕时间戳加 offset。
- 封面图放 `remotion-app/public/`,画幅比例最好和视频一致(1920×1080 或 1080×1920)。可以用内置 `scripts/generators/seedream-wrapper.js` 生成。

### 组合模板里的接法(自定义封面组件)

需要动画封面(不只是静图)时,复制 `IntroduceOrg` 里的 `CoverOrg` 模式(见 `remotion-app/src/scenesOrg.tsx`):

```tsx
<AbsoluteFill>
  <Background />
  <Overlays durationInFrames={props.durationInFrames} accent={COLORS.green} />

  <Sequence from={0} durationInFrames={60} name="Cover">
    <CoverOrg />
  </Sequence>

  <Sequence from={60} name="Narration">
    <VoiceOver src={staticFile(props.audioSrc)} />
    <Sequence from={0} durationInFrames={510} name="Hook"><HookOrg /></Sequence>
    {/* ... 其它场景 ... */}
    <SubtitleBar />
  </Sequence>
</AbsoluteFill>
```

**关键**:`VoiceOver` + 场景 + `SubtitleBar` 都塞进外层 `<Sequence from={60}>`。Sequence 内部时间归零,字幕时间戳不用重算。

### 总时长要 +coverFrames

Composition 的 `durationInFrames` = `narration_frames + coverFrames`。task.json 里 `render.durationInFrames` 记录含封面的总帧数,`tts.audioDurationSec` 只算讲解本身。

## 一支视频常同时用两个

推荐做法:片头 cover scene 淡入到成型的品牌卡,再从那一帧截图当 poster,poster 和片头前 2 秒画面完全一致 —— 用户点开的瞬间不会有"卡片跳变"感。

```bash
# 1. 用 CoverOrg / coverImage 出片
node $SKILL/task-render.mjs --slug my-video --composition IntroduceOrg

# 2. 从 t=1.0s 截当 poster 嵌回去
node $SKILL/embed-poster.mjs --slug my-video --from-frame 1.0
```


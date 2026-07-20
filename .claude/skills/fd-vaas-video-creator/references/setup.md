# 首次设置(一次性)

本 Skill 需要装一个 Remotion 包(`@remotion/captions`),并把一个参数化合成组件装进 `remotion-app`。完成一次即可。

## 判断是否已设置

以下都满足则已设置,可跳过:

- `remotion-app/node_modules/@remotion/captions` 存在
- `remotion-app/src/VoiceoverVideo.tsx` 存在
- `remotion-app/src/Composition.tsx` 里注册了 `id="VoiceoverVideo"`

> ✂️ 不再需要 `@remotion/install-whisper-cpp` 或 whisper 模型 —— 逐字时间戳由豆包 TTS(`seed-tts-2.0` + `enable_subtitle`)直接返回。

## 步骤 1:安装 Remotion 包

```bash
cd /Users/chengsishi/VAAS/remotion-app
npx remotion add @remotion/captions
```

`npx remotion add` 会自动选与当前 remotion 版本匹配的版本。

## 步骤 2:装参数化合成组件

把本 Skill 的 `references/voiceover-video-composition.tsx` 复制为 `remotion-app/src/VoiceoverVideo.tsx`:

```bash
cp /Users/chengsishi/VAAS/.claude/skills/fd-vaas-video-creator/references/voiceover-video-composition.tsx \
   /Users/chengsishi/VAAS/remotion-app/src/VoiceoverVideo.tsx
```

## 步骤 3:注册合成

编辑 `remotion-app/src/Composition.tsx`:

1. 顶部加 import(放在其它 import 附近):

```tsx
import { VoiceoverVideo, type VoiceoverVideoProps } from "./VoiceoverVideo";
```

2. 在 `MyComposition` 的 `<>...</>` 里追加一个 `<Composition>`(与现有 IntroduceGov 等并列):

```tsx
<Composition
  id="VoiceoverVideo"
  component={VoiceoverVideo}
  durationInFrames={300}
  fps={30}
  width={1080}
  height={1920}
  defaultProps={{
    audioSrc: "voiceover.mp3",
    captionsSrc: "captions.json",
    durationInFrames: 300,
  }}
  calculateMetadata={({ props }) =>
    Promise.resolve({
      durationInFrames: props.durationInFrames,
      width: props.width ?? 1080,
      height: props.height ?? 1920,
    })
  }
/>
```

`calculateMetadata` 让 `durationInFrames`/`width`/`height` 从 `--props` 生效,这样每条视频的时长和方向都由 props 决定,无需改 React。

## 步骤 4:装脚本

`captions-to-srt.mjs`(把 caption JSON 转 .srt 软字幕)需要在 remotion-app 里:

```bash
cp /Users/chengsishi/VAAS/.claude/skills/fd-vaas-video-creator/scripts/captions-to-srt.mjs \
   /Users/chengsishi/VAAS/remotion-app/scripts/captions-to-srt.mjs
chmod +x /Users/chengsishi/VAAS/remotion-app/scripts/captions-to-srt.mjs
```

`generate-voiceover.mjs`(调 TTS + 拷贝 audio/captions 进 public/)已经在 `remotion-app/scripts/`,由 VAAS 项目托管,不用再拷。

## 步骤 5:验证

```bash
cd /Users/chengsishi/VAAS/remotion-app
npx remotion compositions   # 应列出 VoiceoverVideo(以及现有的 IntroduceGov 等)
```

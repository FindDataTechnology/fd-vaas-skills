# 🎤 Remotion Voice-over Integration

## ⚠️ Current Status

**The TTS API endpoint is being actively debugged.** The integration structure is complete, but we're still determining the exact format for the `Resource-Id` header required by the Volcengine Ark API.

**Known Information:**
- **Endpoint**: `POST https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional`
- **Model/Resource**: `seed-tts-2.0` (豆包语音合成模型2.0)
- **Auth**: Uses `X-API-Key` header with the same API key as image/video generation
- **Issue**: Getting error `"get resource id empty"` - investigating the exact header/parameter format

---

## Quick Start (Manual Workflow)

Since the automated TTS integration is pending:

1. **Generate your audio file** using any TTS service or record your own
2. **Place** in `remotion-app/public/your-voiceover.mp3`
3. **Add to your video** composition:

```tsx
import { VoiceOver, BackgroundMusic } from "./voiceover";

// Inside your component:
<VoiceOver src={require("../public/your-voiceover.mp3")} />
<BackgroundMusic src={require("../public/your-bgm.mp3")} volume={0.1} />
```

4. **Preview**: `npm run dev` - you'll hear the audio!

---

## Available Components

### `<VoiceOver>`
Main narration track with configurable timing:
- `src`: Audio file path (from `public/`)
- `startFrom`: Frame number to start (default: 0)
- `volume`: 0-1 (default: 1)
- `playbackRate`: 0.5-2 (default: 1)

### `<SceneVoiceOver>`
Scene-aligned audio for multi-part videos:
- `src`: Audio file
- `sceneStartFrame`: Starting frame of the scene
- `sceneDurationFrames`: Total scene duration
- `delayFrames`: Small delay before audio starts (avoids cut-in)

### `<BackgroundMusic>`
BGM with sensible defaults:
- `volume`: 0.15 by default (much lower than voice)
- `loop`: true by default

---

## Helper Functions

```tsx
import { calculateVoiceOverFrames, calculateSpeakingDuration } from "./voiceover";

// Estimate frames needed for Chinese text
const charCount = scriptText.length;
const framesNeeded = calculateVoiceOverFrames(charCount); // @ 30fps, 4.5 chars/sec

// Get duration in seconds
const durationSec = calculateSpeakingDuration(charCount);
```

---

## Available Voices

豆包 TTS supports the following voices:

| Voice ID | 名称 | 特点 |
|----------|------|------|
| `zh-CN-Yunxia` | 云夏 | ✅ 温柔甜美女声（默认） |
| `zh-CN-Yunxi` | 云希 | 成熟知性女声 |
| `zh-CN-Yunyang` | 云扬 | 活泼可爱女声 |
| `zh-CN-Yunye` | 云叶 | 文艺知性女声 |
| `zh-CN-Yunjian` | 云健 | 沉稳男声 |
| `zh-CN-Yunhao` | 云浩 | 阳光活力男声 |
| `zh-CN-Yunfan` | 云帆 | 磁性男声 |
| `en-US-Aria` | Aria | English female |
| `en-US-Davis` | Davis | English male |
| `ja-JP-Nanami` | Nanami | Japanese female |
| `ko-KR-SunHi` | SunHi | Korean female |

---

## TTS Integration Progress

### Completed
- ✅ Remotion audio component wrappers (`src/voiceover.tsx`)
- ✅ TTS skill structure (`voice-generator/`)
- ✅ npm script hooks in `package.json`
- ✅ API key resolution (reuses the same `.env` key as images/video)
- ✅ Request body formatting for the unidirectional endpoint
- ✅ Local file auto-save to 3-tier directories

### Pending
- 🔍 **Exact Resource-Id header format** - waiting on official documentation or working example

Once the API issue is resolved, the full automated workflow will be:

```bash
# Generate voiceover from text
npm run voiceover -- --text "欢迎使用我们的平台！" --voice zh-CN-Yunfan

# Generate from file
npm run voiceover -- --file scripts/example-script.txt

# List voices
npm run voiceover:voices
```

---

## Resources

- **Volcengine Ark Console**: https://console.volcengine.com/ark
- **TTS Model**: 豆包语音合成模型2.0 (`seed-tts-2.0`)
- **API Endpoint**: `https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional`

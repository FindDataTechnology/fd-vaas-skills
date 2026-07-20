# TTS 时间戳注意事项 · seed-tts-2.0

## 结论先给

**豆包 seed-tts-2.0 返回的 `sentence.words[]` 里,英文/字母/域名 token 的 `endTime` 是假的**,只标 30–45ms,但实际读音要 2–3 秒。中文汉字的 per-char 时间戳准。

**现状**:`byted-ark-tts-skill/scripts/tts.js` 的 `sentencesToCaptions()` **已在源头修正**,产出的 `captions.json` 直接可用。下面这些内容是根因存档 + 遗留 captions 的兜底修法。

## 现象

一次真实调用返回的 token(节选):

```json
{ "text": "FindDataTechnology，", "startMs": 9800,  "endMs": 9845 }   // dur=45ms
{ "text": "要",                    "startMs": 12635, "endMs": 12815 }  // 下一个字在 2.79s 之后
```

`FindDataTechnology,` 音频里实际读 2.79 秒,但接口标 45ms,`startMs → endMs → next.startMs` 中间那 2.79 秒是"gap",实际就是这个字母 token 的真时长。

其它同批命中的 token:

| Token | 接口 `endMs - startMs` | 真读音时长(到下一 token) |
|---|---|---|
| `FindDataTechnology，` | 45ms | 2790ms |
| `fd-cn-gov，` | 45ms | 2390ms |
| `fd-cn-report，` | 45ms | 2380ms |
| `github.com/FindDataOfficial，` | 45ms | 2940ms |
| `Star、` `Issue、` | 30ms | 70–1660ms |
| `DAAS，` | 30ms | 410ms |

## 原因(推测)

seed-tts-2.0 的对齐器是按声学帧+汉字 token 做的,Latin 段作为一个整体 token 输出,但对齐器只给了"这个 token 起始"的位置,`endMs` 用了一个占位常量(30/45ms)。中文单字有对应声学帧,`endMs` 就准。

## 修法(唯一正确姿势)

```bash
node .claude/skills/fd-vaas-video-creator/scripts/fix-tts-timings.mjs \
  --in  captions-raw.json \
  --out captions.json
```

规则:遍历 tokens,若 `endMs - startMs < 100ms` 且 `next.startMs - endMs > 100ms`,则 `endMs := next.startMs`。这样做的安全性:TTS 内相邻字之间没有真空隙,只有句间停顿(> 100ms 的 gap 才修),所以字幕不会被拖到下一句音频头上。

## 什么时候会踩坑

任何**中英混排**的口播稿(品牌名、URL、命令行、代码符号、CJK 顿号包着英文)。纯中文口播不受影响。

## 集成

- `task-render.mjs` 已自动跑修正,产出 `captions.json`(修正后)+ `captions-raw.json`(原始存档)。
- `preflight.mjs` 会拒绝任何未修正的 captions(有 `dur < 100 && gap > 100` 的 token 时直接失败)。
- 手动流程记得先修再渲染,或先修再喂 `captions-to-srt.mjs`。

## 什么时候不用修

- 只调 TTS 拿音频,不做字幕(`--no-subtitle`)。
- 纯中文文本、TTS 返回里没有 Latin token(实际很少见)。

# Task 目录约定

**每支视频 = 一个 `downloads/fd-videos/<slug>/` 目录。** 素材、字幕、成片、manifest 都在同一处,后续任何 agent / 人类都能凭 slug 找到全部信息。禁止把 mp4 散落在 `downloads/fd-videos/` 根目录里。

## 目录结构

```
downloads/fd-videos/<slug>/
├── task.json          # 结构化 manifest(唯一 source of truth)
├── script.txt         # 口播稿原文
├── voiceover.mp3      # TTS 产物
├── captions.json      # 修正后的逐字时间戳(见 tts-timings-quirk.md)
├── captions-raw.json  # TTS 原始返回,存档用
├── captions.srt       # 软字幕(可选,captions-to-srt.mjs 产出)
├── cover.png          # 封面图(可选,VoiceoverVideo 的 coverImage prop)
├── <slug>.mp4         # 最终成片
├── history.md         # 每次改动的 append-only 记录
└── _archive/          # (可选)历史迭代版本,不进 manifest,不算主产物
```

## task.json schema

```jsonc
{
  "slug": "finddata-intro",
  "createdAt": "2026-07-19T10:00:00.000Z",
  "status": "draft | voiced | rendered | published",
  "script": "script.txt",
  "video": { "width": 1920, "height": 1080, "fps": 30 },
  "tts": {
    "model": "seed-tts-2.0",
    "voice": "zh_female_gaolengyujie_uranus_bigtts",
    "audio": "voiceover.mp3",
    "captions": "captions.json",
    "captionsRaw": "captions-raw.json",
    "audioDurationSec": 79.51,
    "tokenCount": 252,
    "fixedLatinTokens": 8
  },
  "render": {
    "composition": "IntroduceOrg",
    "durationInFrames": 2461,
    "coverFrames": 60,
    "output": "finddata-intro.mp4",
    "props": { "audioSrc": "...", "captionsSrc": "...", "durationInFrames": 2461 }
  },
  "distribution": [
    { "platform": "douyin", "account": "main", "uploadedAt": "...", "url": "..." }
  ]
}
```

**规则**:
- 所有相对路径都相对 task 目录。
- `status` 单调向前:`draft → voiced → rendered → published`,不能回退(改文案就等于新 slug,或者在 history.md 里追记 revision)。
- `distribution` 每 push 一个平台 append 一条。

## history.md

Append-only,人类可读,记录每次改动的动机 + 结果。示例:

```markdown
# finddata-intro — history

- 2026-07-19T10:00:00Z — task created (1920×1080)
- 2026-07-19T16:44Z — rendered finddata-intro.mp4 (IntroduceOrg, 2401f, voice=高冷御姐)
- 2026-07-19T17:12Z — fix: Latin-token timings; re-render → 2401f
- 2026-07-19T17:35Z — add CoverOrg (60f cover, silent); re-render → 2461f
```

## Slug 规则

- `[a-z0-9][a-z0-9-]*`,不含空格/大写/下划线。
- 一个 slug 一次内容主题,不许 `-v2` `-final` `-fixed` 后缀。想换配音/微调时长/改画面 = **同一个 task 目录里覆盖 mp4**,history.md 记账。想彻底换文案 = 新 slug。

## 上手流程

```bash
SKILL=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-video-creator/scripts

# 1. 建 task 目录
node $SKILL/new-task.mjs --slug finddata-intro \
  --script /path/to/script.txt --width 1920 --height 1080

# 2. 一键跑完 TTS → 修字幕 → preflight → render → 回写 manifest
node $SKILL/task-render.mjs --slug finddata-intro \
  --voice zh_female_gaolengyujie_uranus_bigtts \
  --composition IntroduceOrg
```

产物:`downloads/fd-videos/finddata-intro/finddata-intro.mp4` + 完整目录。

## 查询/复用

任何时候要问"这支视频用的什么音色 / 多少帧 / 什么合成":

```bash
cat downloads/fd-videos/<slug>/task.json
```

要重跑同一个 slug(改画面/换音色):`--slug` 相同即可,`task-render.mjs` 会覆盖 mp4 并追加 history.md。旧版本要留档就先 `git add` 或手动拷走。

## 现存视频的历史包袱

`downloads/fd-videos/` 根目录下的 `finddata-intro*.mp4`(session 前遗留 + 本次 3 个)都不符合这个约定。清理策略两选一:
- 全部丢弃,只保留 `finddata-intro-with-cover.mp4`,重跑一次 `new-task` → `task-render` 进入新目录。
- 手工整理:建 `downloads/fd-videos/finddata-intro/` 把最新那个 mp4 拷进去,补一份 task.json。

推荐第一种,过程干净。

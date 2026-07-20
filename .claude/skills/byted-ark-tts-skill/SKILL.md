---
name: byted-ark-tts-skill
description: 豆包 TTS 语音合成 Skill - 火山方舟 API 专属版本。用于将文本转换为自然流畅的语音音频，支持多种中文/英文/日韩音色，可调节语速、输出格式等。当用户说"生成语音""语音合成""朗读这段文字""转语音""配音""做个音频文件"或任何需要文本转语音的场景时，务必使用本 Skill。无需反复确认。
compatibility: Requires Node.js 18+ and network access to VolcEngine Ark API.
metadata:
  author: volcengine/agentplan
  category: ai/audio-generation
  version: "1.0.0"
---

# Ark TTS Skill - 豆包语音合成

## 概述

豆包 TTS（文本转语音）Skill，基于火山方舟语音合成 API。

✨ **核心优势：**
- ✅ **OpenAI 兼容接口** — `POST /audio/speech` 标准格式，易于集成
- ✅ **多语言音色支持** — 中文（男女多种风格）、英语、日语、韩语
- ✅ **智能音色推断** — 根据文本语言自动选择最佳音色，Agent 无需猜测
- ✅ **官方逐字时间戳** — seed-tts-2.0 开启 `enable_subtitle`（默认开），同一次调用同时返回音频 + 每个字/词的 `startTime`/`endTime`，直接落成 `@remotion/captions` 兼容的 `captions.json`
- ✅ **语速调节** — 支持 0.25x 到 4.0x 超宽范围
- ✅ **多种输出格式** — mp3、opus、aac、flac、wav、pcm
- ✅ **本地自动保存** — 生成的音频（+ 字幕 JSON）自动下载到本地，三级目录 fallback
- ✅ **与 seedream/seedance 一致的架构** — 相同的 API Key 解析逻辑、错误处理、目录规范

## 触发条件

用户说以下关键词或意图时自动激活：
- 生成语音、语音合成、转语音、做个音频
- 朗读、念一下、读出来、配音、有声书
- 把这段文字变成声音、TTS、text to speech
- seedance、seedream 的姊妹技能，纯文本生成音频

---

## 🚀 核心命令与用法

### 1. 合成语音（`create` / `synth` / 直接传参数）

识别到合成需求时直接调用：

```bash
node scripts/tts-wrapper.js create \
  --text "欢迎使用豆包语音合成，今天天气真好！"
```

> 💡 **智能音色推断**：Agent 层不需要指定 `--voice`，Wrapper 会根据文本语言自动选择最合适的音色。用户有明确音色偏好时才传。

### 2. 列出所有支持的音色

```bash
node scripts/tts-wrapper.js voices [--model doubao-tts-2.5l-pro]
```

---

## 输入参数说明

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|-------|------|--------|------|------|
| `--text` / `--input` | string | - | ✅ | 要合成的文本内容（中文、英文、日语、韩语） |
| `--file` / `--input-file` | string | - | ❌ | 从本地文本文件读取内容（替代 --text，适合长文本） |
| `--voice` | string | *自动推断* | ❌ | 音色 ID，不指定时根据文本语言自动选择 |
| `--speed` | float | `1.0` | ❌ | 语速倍率 [0.25, 4.0] |
| `--format` / `--response-format` | string | `mp3` | ❌ | 输出格式：`mp3` / `opus` / `aac` / `flac` / `wav` / `pcm` |
| `--model` | string | `doubao-tts-2.5l-pro` | ❌ | TTS 模型名（一般不需要改） |
| `--api-key` | string | - | ❌ | 临时指定 API Key（默认读取项目 `.env`） |
| `--base-url` | string | - | ❌ | 自定义 API 入口地址 |
| `--no-subtitle` | flag | - | ❌ | 关闭逐字时间戳（默认开启）；开启时会额外产出 `captions.json` |

> 💡 **参数提取规则**（Agent 层必读）：
> - "快点读"、"慢一点"、"语速快一点" → `--speed` (1.5 / 0.8 等)
> - "用女生声音"、"男声" → 根据语气选对应 `--voice`
> - "读一下这个文件" → 把文件路径传给 `--file`
> - "保存为 wav 格式" → `--format wav`
> - **不要硬编码音色** — 让 Wrapper 自动推断，除非用户明确指定

---

## 🎤 音色速查表

### 中文女声（最常用）

| 音色 ID | 名称 | 特点 | 适用场景 |
|---------|------|------|---------|
| `zh-CN-Yunxia` | 云夏 | ✅ **默认推荐**，温柔甜美 | 通用场景、情感故事、客服 |
| `zh-CN-Yunxi` | 云希 | 成熟知性 | 新闻播报、有声读物 |
| `zh-CN-Yunyang` | 云扬 | 活泼可爱 | 儿童故事、动画配音 |
| `zh-CN-Yunye` | 云叶 | 文艺知性 | 散文、诗歌朗诵 |

### 中文男声

| 音色 ID | 名称 | 特点 | 适用场景 |
|---------|------|------|---------|
| `zh-CN-Yunjian` | 云健 | 沉稳磁性 | 新闻、纪录片、有声小说 |
| `zh-CN-Yunhao` | 云浩 | 阳光活力 | 广告、宣传片 |
| `zh-CN-Yunfan` | 云帆 | 温暖磁性 | 故事、播客 |

### 其他语言

| 音色 ID | 名称 | 语言 |
|---------|------|------|
| `en-US-Aria` | Aria | 美式英语女声 |
| `en-US-Davis` | Davis | 美式英语男声 |
| `ja-JP-Nanami` | Nanami | 日语女声 |
| `ko-KR-SunHi` | SunHi | 韩语女声 |

---

## 📚 典型场景示例

### 场景 1: 简单中文朗读（自动音色推断）

**用户输入：** "帮我把这段文字转成语音：今天天气晴朗，适合出去散步。"

**处理：**
```bash
node scripts/tts-wrapper.js create \
  --text "今天天气晴朗，适合出去散步。"
```

**Wrapper 自动选择** `zh-CN-Yunxia`（中文温柔女声）。

### 场景 2: 英文朗读 + 指定语速

**用户输入：** "用英语读一下这段，语速稍微快一点：The quick brown fox jumps over the lazy dog."

**处理：**
```bash
node scripts/tts-wrapper.js create \
  --text "The quick brown fox jumps over the lazy dog." \
  --speed 1.2
```

**Wrapper 自动选择** `en-US-Aria`（英文女声）。

### 场景 3: 指定音色 + 格式

**用户输入：** "用磁性男声给这段小说配音，保存为 wav 格式：夜深了，月光透过窗户洒进来..."

**处理：**
```bash
node scripts/tts-wrapper.js create \
  --text "夜深了，月光透过窗户洒进来，照亮了书桌上那本泛黄的日记..." \
  --voice zh-CN-Yunfan \
  --format wav
```

### 场景 4: 从文件读取长文本

**用户输入：** "[上传了 script.txt] 把这个文件的内容读出来"

**处理：**
```bash
node scripts/tts-wrapper.js create \
  --file "/path/to/script.txt"
```

### 场景 5: 查看可用音色

**用户输入：** "都有什么声音可以选？"

**处理：**
```bash
node scripts/tts-wrapper.js voices
```

---

## 📤 返回结果格式

### 生成成功：

```text
🎉 语音合成完成！

🤖 使用模型: seed-tts-2.0
🎤 音色: zh_female_gaolengyujie_uranus_bigtts (高冷御姐)
📝 文本长度: 42 字符
⚡ 速度倍率: 1.0x
🎵 格式: mp3
⏱️ API 耗时: 892ms
📦 文件大小: 62 KB
⏰ 预计时长: 4 秒

💾 本地文件路径:
   /Users/xxx/Desktop/Ark-TTS/20250715-143022/speech.mp3
📝 字幕文件路径 (18 个字/词，官方逐字时间戳):
   /Users/xxx/Desktop/Ark-TTS/20250715-143022/captions.json
⏱️ 官方音频时长: 4.21 秒
```

### 字幕 JSON 结构（`@remotion/captions` 兼容的 `Caption[]`）

```json
[
  { "text": "你", "startMs": 135, "endMs": 265, "timestampMs": 200, "confidence": 0.83 },
  { "text": "好,", "startMs": 265, "endMs": 675, "timestampMs": 470, "confidence": 0.95 }
]
```

字段来自豆包 API 的 `sentence.words[]`（`startTime`/`endTime` 单位为秒，已换算为毫秒）。可直接喂给 `@remotion/captions` 的 `createTikTokStyleCaptions`。

---

## 📥 文件保存位置

音频自动保存到以下位置（三级 fallback，与 seedream/seedance 一致）：

| 优先级 | 路径 | 适用场景 |
|-------|------|---------|
| 1 | `~/Desktop/Ark-TTS/<时间戳>/` | 桌面用户（Mac/Windows） |
| 2 | `~/Ark-TTS/<时间戳>/` | Linux 服务器、无头环境 |
| 3 | `./Ark-TTS/<时间戳>/` | 极端情况（home 目录不可写） |

---

## ❌ 错误处理

| 错误类型 | 处理方式 |
|----------|---------|
| API Key 未配置 / 401 鉴权失败 | 提示在 `.env` 的 `vol_agent_api_key` 配置有效 key，确认模型已开通 |
| 模型未开通 (ModelNotOpen) | 提示在火山方舟控制台开通对应的 TTS 模型 |
| 音色不存在 (InvalidVoice) | 自动列出所有可用音色供选择 |
| 缺少输入文本 | 提示用户提供要合成的文本内容 |

---

## ⚙️ 配置说明

### 🔑 API Key 配置

Wrapper 按以下优先级自动检测 API Key（与 seedream/seedance 完全一致）：

1. **`.env` 中的 `vol_agent_api_key`**（项目根 `VAAS/.env`，首选）
2. `--api-key` 参数（Agent 层临时传入）
3. 环境变量 `ANTHROPIC_AUTH_TOKEN`
4. Claude 配置文件 `~/.claude.json`
5. 通用环境变量名 `ARK_API_KEY` / `API_KEY` 等

> 💡 **重要说明**：TTS 使用的是标准 API v3 入口 (`/api/v3/audio/speech`)，与图像生成的 `/api/plan/v3` 不同。但同一个 API Key 只要开通了对应模型权限，就能同时用于两者。

---

## 🤖 Agent 层执行规范

### 关键要点

1. **不需要硬编码音色** — 除非用户明确指定，否则不传 `--voice`，让 Wrapper 自动推断
2. **不要手动检测语言** — Wrapper 内置简单语言检测，会自动选音色
3. **长文本用文件** — 超过 500 字建议用 `--file` 参数从文件读取
4. **渲染本地路径** — 生成后把 `💾 本地文件路径:` 后面的路径原样展示给用户

### 参数提取原则

- 用户说"快一点" / "慢一点" → 转换为合理的 `--speed` 值（1.2-1.5 / 0.7-0.8）
- 用户说"用女声" / "用男声" → 从音色表里选最匹配的默认款
- 用户上传了文件 → 把绝对路径传给 `--file`
- 不要把文本内容截断后传 — API 支持长文本合成

---

## 📋 支持的原生 API 接口

| 接口 | 路径 | 方法 |
|------|------|------|
| 语音合成（HTTP Chunked，音频+字幕） | `POST /api/v3/plan/tts/unidirectional` | ✅ 已实现 |

> 💡 响应是 HTTP Chunked 流：每块要么是 `{"code":0,"data":"<base64音频>"}`，要么是 `{"code":0,"sentence":{"text":..,"words":[{word,startTime,endTime,confidence}]}}`（当 `enable_subtitle:true`）。wrapper 会自动拼接音频块并把 `sentence.words` 转成 `@remotion/captions` 的 `Caption[]`。

# tasks

## 1. tts.js 出口契约与合成字幕

- [x] 1.1 出口归一：`synthesizeSpeechViaLiteLLM` 结果补 captions 逻辑——bridge 无 captions 时，对落盘音频 ffprobe 实测时长，按口播文本 token 切分（中文按字、标点并入前字、Latin 词元整体一个 token）线性缩放生成 Caption[]，写 captions.json，元数据 `captions_source: synthetic`；官方路径标记 `official`。验证：单测——mock 音频 10.0s / 文本 50 token → captions 末帧 endMs=10000±50，captions_source=synthetic
- [x] 1.2 错误分类：`parseChunkedResponse` 识别无 data 字段的非零 code JSON 块 → 直接返回 {error_code, error_message, hint}；InvalidSubscription 的 hint 含「续订方舟或切 TTS_PROVIDER=ciyuan」。验证：单测——喂 InvalidSubscription 分块样例，断言不再出现 DECODE_FAILED
- [x] 1.3 `--output-dir`：tts-wrapper.js / tts.js 增加该参数，优先级高于三级 fallback；结果 local_path/captions_path 如实返回。验证：单测——指定临时目录合成（mock）后产物落在指定目录

## 2. task-render 管线接线

- [x] 2.1 stepTts 传 `--output-dir <taskDir>/_tts`，产物从该目录取（findLatestArkTTS 仅在未指定时启用）；captions_source 写入 task.json tts 段。验证：跑一次 ciyuan 档 task-render，task 目录出现 voiceover.mp3 + captions.json + manifest 含 provider/captions_source
- [x] 2.2 preflight 兼容确认：synthetic captions 过三方对齐门禁（不改 preflight 代码，只验证）。验证：2.1 的任务 preflight 无 drift 报错

## 3. 白名单与文档

- [x] 3.1 README 词元白名单补 2026-11-06 行（tencent-tts ✅ voice=101001；audio 车道按 protocol 路由、模型名不进 /v1/models；换模型先实调纪律）；`.env` 配置示例同步 TTS_PROVIDER=ciyuan 档三行。验证：文档段落存在且与 .env 实测组合一致
- [x] 3.2 voiceover 类型文档（types/voiceover/type.json 描述或 SKILL.md 渲染表）补一句字幕来源口径（official=官方逐字 / synthetic=实测时长推算）。验证：文档可见

## 4. 回归

- [x] 4.1 volcengine 档回归：TTS_PROVIDER 未设时走 Ark 直连官方逐字戳路径，行为与改前一致（captions_source=official）。验证：单测或本地小文本实调一次
- [x] 4.2 ciyuan 档端到端回归：用 add-solution-package 主片口播稿走标准 new-task → task-render（腾讯档），preflight 全过、成片时长与字幕对齐。验证：成片 mp4 + task.json captions_source=synthetic

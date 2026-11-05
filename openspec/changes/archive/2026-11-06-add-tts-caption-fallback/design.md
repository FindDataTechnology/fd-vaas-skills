## Context

现状（2026-11-06 实测 + 源码走读）：

- `task-render.mjs` stepTts：调 `tts-wrapper.js --text` → 在 `~/Desktop/Ark-TTS` 三级目录里找
  **最新时间戳子目录** → 要求其中有 `captions.json`，缺失即 exit 1。
- `tts.js`：volcengine 档 Ark 直连（分块 JSON：音频 b64 + sentence.words[]），官方逐字戳写
  captions.json；ciyuan 档经 `litellm-bridge.py` → `_ciyuan_tts.py`（`POST /v1/audio/speech`，
  OpenAI 音频形状）——只回音频，结果字典无 captions 字段，bridge 层注释明确「如实降级」。
- 生产实证（add-solution-package 三支片，2026-11-05/06）：火山方舟 InvalidSubscription 期间，
  宿主项目旁路脚本用「句切 + token 均分 + 实测时长缩放」合成字幕，preflight 全过、成片出货。
  词元腾讯 TTS（模型名任意、按 protocol 路由、音色 101001）实调可用。
- 关键事实：ffprobe 在 VAAS 是既有依赖（doctor 检查项）；voiceover 管线下游
  （fix-tts-timings / preflight / VoiceoverVideo）只消费 Caption[] 形状，不感知 provider。

## Goals / Non-Goals

**Goals:**
- ciyuan 档 TTS 在标准链路（new-task → task-render）下开箱可用，无需宿主旁路
- 字幕来源（official/synthetic）成为一等元数据，成片口径可审计
- 消除 Ark-TTS 桌面扫描的并发竞态
- 错误分类：订阅失效等可行动错误直出

**Non-Goals:**
（见 proposal.md Non-Goals：逐句模式、图像/视频多源化、ASR、Remotion 组件改动。）

## Decisions

### D1 合成字幕放 tts.js 出口层（JS），不放 Python bridge、不放管线层
- tts.js 是两个 provider 的共同出口：在此归一化「总是返回 captions（official 或 synthetic）」，
  下游（stepTts/fix-tts-timings/preflight/Remotion）零改动、零 provider 感知。
- 备选一（Python `_ciyuan_tts` 内做）：需在 Python 引 ffprobe 子进程，且 bridge 的 JSON 结果
  契约要扩字段——把「管线关心的事」塞进纯合成层，职责错位。
- 备选二（task-render 兜底）：字幕来源变成两处逻辑（wrapper 官方 + 管线合成），未来加第三个
  provider 时还要再想一遍；出口层一处归一后新 provider 只需「返回音频 + 实测时长」。
- 实现要点：bridge 结果无 captions 时，tts.js 对落盘音频跑 `ffprobe -show_entries format=duration`
  → 文本按 token 切分（中文按字、标点并入前字；Latin 词元作为一个 token）→ token 数均分
  单 token 时长 → 全体时间戳 × (实测时长/估算总时长) 线性缩放 → 末 token endMs 钉到实测总时长。

### D2 分段合成（2026-11-06 实测修正，推翻原「单次调用」决策）
- 腾讯 TTS 上游有单次请求长度墙：实调二分钉死 ~170 字（165 通 / 170 挂，>170 触发
  TextTooLong 502 且会熔断摘除上游账号约 5 分钟）。全文单次调用在真实口播稿（500-1600 字）
  上必然失败——分段不是优化，是接线必需。
- 策略：tts.js 出口层按句切分（与 captions token 切分同源）→ 段长 ≤150 字（安全余量）→
  逐段调用 → ffmpeg concat（0.22s 句间静音）→ 逐段实测时长对齐 captions（句级精确，
  优于全文缩放）→ 段间时长计入 captions 时间轴。
- 重试：每段 ≤3 次（1.5s/3s 退避）；任一段 3 次失败即整任务失败，不产出残缺音频。
- 旁路实证：add-solution-package 三支片即此方案（逐段合成 + 缩放对齐），preflight 全过。

### D3 stepTts 直传 `--output-dir`（task 目录），桌面扫描降级为 fallback
- `tts-wrapper.js` 增加 `--output-dir`（透传给 tts.js 的 resolveSaveDir 优先级最高位）。
- stepTts 传 task 目录下的 `_tts/` 暂存子目录；findLatestArkTTS 仅在未指定目录时启用（兼容旧调用）。
- 附带收益：不再往 ~/Desktop 堆产物。

### D4 错误分类在 parseChunkedResponse 内识别错误 JSON 块
- Ark 分块响应中的 JSON 对象若含非零 code/message 且无 data 字段 → 判定为错误块，
  直接以 {error_code, error_message, hint} 返回；InvalidSubscription 的 hint 指向
  「续订方舟或切 TTS_PROVIDER=ciyuan」。词元侧错误语义不变（已有车道标识）。

### D5 白名单与元数据
- README「词元车道实测白名单」补 2026-11-06 行：tencent-tts ✅（voice 101001），audio 车道按
  protocol 路由、模型名不进 /v1/models——换模型先实调的纪律保留。
- task.json tts 段新增 provider 与 captions_source；`.env` 配置示例同步（TTS_PROVIDER=ciyuan +
  TTS_MODEL=tencent-tts + TTS_VOICE=101001）。

## Risks / Trade-offs

- [合成字幕在句内停顿处略漂] → 线性缩放把误差摊到全片；实测三支片 preflight 全过。残余风险接受
  （字幕为推算的事实已在 captions_source 声明）。
- [ffprobe 依赖面扩大到 tts.js] → doctor 已把它列为准入项，且只用最基础的 duration 查询。
- [改 stepTts 触碰生产管线] → volcengine 档回归用既有 Ark-TTS 路径不动；以三支片素材做重渲回归。
- [旁路脚本退役的迁移成本] → 宿主 build-generic.cjs 保留 --preaudio 分支作为 fallback（一段
  时间双轨），待 VAAS 版验证后再删。

## Migration Plan

1. tts.js 出口契约 + 合成字幕 + 错误分类（volcengine 档行为不变，单测覆盖 synthetic 路径）
2. tts-wrapper.js `--output-dir` + stepTts 直传
3. README/白名单/.env 示例更新
4. 回归：用 add-solution-package 的主片素材走标准链路重渲一次（ciyuan 腾讯档），preflight 全过即收
5. 宿主旁路退役（另行小改，不在本 change 内）

回滚：revert 单提交即可；volcengine 主路径无行为变化，风险面只在 ciyuan 档。

## Open Questions

（无——①②③ 已随用户「继续」按推荐落定：出口层归一 / 单次调用 / 顺带范围含白名单与错误分类。）

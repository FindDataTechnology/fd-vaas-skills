# add-tts-caption-fallback

## Why

词元（ciyuan）TTS 档在 VAAS 语音管线中实际不可用：`task-render` 的 tts 步骤把「官方逐字时间戳
（captions.json）」当硬依赖，而词元 `/v1/audio/speech` 只回音频不回逐字戳，导致 `TTS_PROVIDER=ciyuan`
必然在 stepTts 处 exit。2026-11-05/06 生产实证（add-solution-package 三支片）：火山方舟订阅失效期间，
用「句切 + token 均分 + 按拼接音频实测时长线性缩放」的合成字幕走通了整条 voiceover 管线（preflight
门禁全过、成片出货）——证明逐字戳可以降级为合成，管线不需要为 provider 分叉。同时暴露三处伴生缺陷：
Ark 错误 JSON 被当音频解码（InvalidSubscription 报成 DECODE_FAILED）、tts 输出靠扫描桌面
Ark-TTS 最新目录（并发竞态）、词元音色/模型白名单过期（腾讯 TTS 2026-11-06 实调可用但不在册）。
用户拍板：这个能力应该长在 VAAS 里（「本来 vaas 的 tts 就应该支持萬星的多来源」），而不是宿主项目的旁路脚本。

## What Changes

- **MODIFIED `ciyuan-lane-providers`**（核心）：
  - 语音车道合成需求扩展：词元档返回音频后，若 provider 未提供逐字时间戳，TTS 出口层 SHALL 合成
    captions（文本 token 切分 × ffprobe 实测音频时长线性缩放），并标记 `captions_source: synthetic`；
    官方逐字戳存在时标记 `official`。voiceover 管线（fix-tts-timings / preflight / Remotion）只认
    Caption[] 形状，MUST NOT 因 provider 分叉。
  - 词元模型/音色白名单更新：`tencent-tts`（腾讯语音，audio 车道按 protocol 路由、模型名任意）
    2026-11-06 实调 ✅，默认音色 `101001`；qwen3-tts-flash 保留。
  - 错误分类：Ark 分块响应中的 JSON 错误块 SHALL 按其 code/message 直接暴露（如 InvalidSubscription
    给出可行动提示），MUST NOT 伪装成音频解码失败。
- **确定性输出目录**：`tts-wrapper.js` 增加 `--output-dir`；`task-render` stepTts 直传 task 目录；
  桌面 Ark-TTS 扫描降级为未指定目录时的 fallback，消除并发竞态。
- **manifest 元数据**：task.json 的 tts 段记录 `provider`、`captions_source`，保证成片口径可审计。
- **宿主旁路退役**：finddata collateral-solution 的 `tencent-tts.js`/`--preaudio` 旁路改为直接调用
  VAAS 标准链路（`new-task → task-render` 两条命令）。

## Capabilities

### New Capabilities

（无——全部归口既有 capability。）

### Modified Capabilities

- `ciyuan-lane-providers`：语音车道（TTS）合成需求扩展——合成字幕兜底契约、captions_source 元数据、
  错误分类（Ark 错误块直出）、白名单更新（tencent-tts 入册）。

## Impact

- **代码**：`.agents/skills/fd-vaas-video-creator/scripts/generators/tts.js`（统一出口 + 合成字幕 +
  错误分类 + --output-dir）、`scripts/litellm-bridge.py`/`scripts/_ciyuan_tts.py`（captions 缺失时
  返回实测时长信息供 JS 侧合成；不改 Python 依赖面）、`task-render.mjs`（stepTts 传 --output-dir、
  manifest 元数据）、`README.md`（白名单与配置示例更新）。
- **依赖**：ffprobe（doctor 已检查，合成字幕量时长用）；无新增第三方依赖。
- **受影响面**：既有 volcengine 档行为不变（官方逐字戳路径不动）；finddata collateral-solution 的
  出片脚本简化。
- **验证基线**：add-solution-package 三支片的口播稿与画面轨可作为重渲回归素材。

## Non-Goals

- 逐句合成模式（N 次 API 调用换句级对齐）——留作长文本超限时的后续可选，本次只做单次调用。
- 图像/视频车道的多源化改造（已有 ciyuan 路径，无生产痛点）。
- ASR 车道（上游账号未配置，另行处理）。
- 换字幕渲染或 Remotion 组件改动。

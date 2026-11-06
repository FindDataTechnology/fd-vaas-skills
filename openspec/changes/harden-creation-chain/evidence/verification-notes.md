# Verification evidence: harden-creation-chain（2026-11-06，主会话）

## 已落地（本会话，避开并行会话工作区）
- W1.1/W1.2 `task-render.mjs`：voice 重复键合并（`voice` + `voice_requested` 双记）；`audioMeasuredSec` 自 TTS_RESULT_JSON 实测提取，`audioDurationSec = ctx.audioMeasuredSec ?? captions-fallback`；`RESERVED_DEFAULT_KEYS` 增 `speed`（defaults 非渲染键不再漏进 props）；`findLatestArkTTS` 死码删除（repo 全域零引用复核）。
- W1.3 speed 贯通：CLI `--speed` > `type.defaults.speed` → TTS wrapper args；node --check 过。
- W2.3 `tts-wrapper.js` help 重写：voices 子命令实况口径，Azure 样例清退，模型默认随 .env provider 实况；`TTS_RESULT_JSON` 机器可读行已有（provider/captions_source/audio_duration_seconds）。
- W3.2（部分）`voiceover` type defaults.subtitlePosition="center"。
- W4.1 SKILL.md「算帧数」节统一 ffprobe 实测口径；README:105 scene-align 漂移修正 + 字幕注意节改双腿如实口径（official/synthetic）。
- W4.2 README.md 新增「双执行器路由」小节（Remotion vs HTML 链五行对照）+ video-creator/brainstorm SKILL 互指。
- W3.3（披露半）BGM 不对称在路由表披露；remotion-app/public 清理转挂账（并行会话工作区不触碰）。
- W4.3/W5.3 renderer 语义收敛已由 W0 归档的主 spec 承载；顺序依赖确认，strict 绿。

## 转挂账/并行会话区（不触碰）
- W2.1/W2.2：tts.js 直连腿（sentences 兜底 + fetch 重试）= 并行会话 whisper 对齐工作区，绝不触碰。
- W3.1：remotion-app 字体打包 + 双端出样片 = 并行会话工作区 + 需真机。
- W5.1：node:test 桩件 = tests/ 与并行会话测试文件同区。
- W5.2：全链真实出片一次留证 → 随部署批次（DEBT-IMGROLL-01）一并实证。
- generate-voiceover.mjs 手工路径改造 → 并入并行会话 tts.js 批次。

## 验证
- `node --check task-render.mjs` / `tts-wrapper.js` 过；pytest 380 全绿（本 change 不涉 python 面）；openspec validate --strict 绿。
- 与并行会话文件（tts.js、tests/tts-synthetic-captions.test.mjs、remotion-app/**）git status 零交集复核。

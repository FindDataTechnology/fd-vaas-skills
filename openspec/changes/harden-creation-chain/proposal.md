# Proposal: harden-creation-chain

## Why

本地创作链（`fd-vaas-video-creator` node 管线 + Remotion 渲染）是 VAAS 出片主力，刚完成词元 TTS 一等公民化（ffca3e1，7 单测），但 11-06 调研揭出一组「刚好会在真片上翻车」的账：`task-render.mjs:268` 用字幕末帧推算总帧数——正是 SKILL.md 自己警告会让 preflight drift 炸的做法（官方音 1s 尾部静音即失配，`:395-407` 一处重复 `voice` 键使 CLI `--voice` 可被静默吞掉；volcengine 直连腿无合成字幕兜底、不回传 `provider/captions_source`，task.json 记 null 再默认显示 official（与 ciyuan 腿的硬闸口径分叉）；`speed` 参数在管线全程蒸发；`audioDurationSec` 标的是字幕不是实测音频）。渲染侧同样寄身历史载体：全站零字体打包（system PingFang 栈在 Windows 节点即错字）、`subtitlePosition` 改了组件未提交未接线、Remotion 链无 BGM 而 HTML 链有——同一类型双执行器能力不对称却无文档路由。测试面一边倒：HTML 新链 15 个 pytest，node 链除 TTS helper 外 `new-task/task-render/preflight/registry` 全裸——恰恰是最脆的时长/门限算术区。无真实客户正是给主力管线补安全网的最佳窗口。

## What Changes

- **NEW** `local-creation-chain` capability：帧数由实测音频推导（字幕推算仅 synthetic 且已 tailPad=0 语义保留）、参数真实性记录（voice/speed 端到端不吞、requested/actual 双记、audioDurationSec 存实测值）、直连腿出口层同等保障（volcengine direct 补合成字幕兜底 + `captions_source` 元数据，与词元腿同形状）、渲染侧跨平台字体（打包字体栈替代系统 PingFang、subtitlePosition 入管线口径）、双执行器路由披露、创作链数学区回归测试。
- **MODIFIED** `video-types`「类型渲染器声明」：`renderer` 字段约束从「每个类型」收敛为「五个 HTML 渲染类型」；未声明者按 node 管线默认（voiceover/screen-recording 现实如此）——修复上批 change delta 的 over-reach（**依赖 deliver-hosted-surface W0 归档先行，该 requirement 方入主 spec**）。
- 顺手收的账（任务级）：`findLatestArkTTS` 死代码删除、tts-wrapper help 文本（Azure 音色残留误导）重写、SKILL.md 自相矛盾两处统一、README `scene-align` 旧口径修正、`generate-voiceover.mjs` 桌面扫描改任务目录落盘、`remotion-app/public/` 历史 captions 垃圾清理、BGM 不对称 v1 以文档披露为限（接线另账）。

## Capabilities

### New Capabilities

- `local-creation-chain`: 本地 node+Remotion 创作管线的行为契约——帧数/时长推导真值、参数端到端不吞、字幕兜底全 provider 同保障、跨平台字体、双执行器路由披露与回归测试。

### Modified Capabilities

- `video-types`：「类型渲染器声明」适用范围由全类型收敛为五 HTML 类型 + 未声明默认 node 管线。

## Impact

- **代码**：`.agents/skills/fd-vaas-video-creator/scripts/task-render.mjs`（帧推导、voice 键、audioDurationSec）、`generators/tts.js`（direct 腿 captions 兜底与元数据、speed 透传）、`new-task.mjs`（speed 入 defaults 预留键）、`remotion-app/src/types/*.tsx` + `shared.tsx`（字体打包、subtitlePosition 接线提交）、`scripts/generate-voiceover.mjs`。
- **测试**：新增 `tests/` node:test 桩件（帧推导/preflight 三规则/registry 校验/字幕换算），并入 add-ci-and-provisioning 的测试闸（node --test 面扩大）。
- **文档**：SKILL.md/README（中英）双执行器路由小节、矛盾点清理。
- **不碰**：MCP hosted python 腿（deliver-hosted-surface 域）、发布链（enforce-publish 域）、typed_scenes HTML builder。

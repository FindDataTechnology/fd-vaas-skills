# Proposal: adopt-hyperframes-video-renderer

## Why

VAAS 的视频渲染是自己手搓的一个迷你版 HyperFrames（`compose_video`：自研 seek 契约 HTML → headless chromium 逐帧 → ffmpeg 合成），而 HyperFrames（`heygen-com/hyperframes`，81k stars，Apache 2.0，2026-03 起每日在推，HeyGen 自家产品在产）正是这件事的成熟标准：HTML + seekable 动画 → 确定性 MP4，多轨时间轴，GSAP/Lottie/Three/WAAPI 适配器，CLI/Studio/lint 全套。维持自研渲染器 = 在没有动画生态、退化版「场景拼接 + 事后混音轨」模型、手写音轨混流上持续付工时，质量上限更低。且我有**多台机器可用**：视频渲染是重 CPU/RAM（Chrome 每 worker ~256MB、/dev/shm ≥256MB）的活，不该挤在 API 容器里——独立渲染面既是正确的架构分层，也让 API 面继续保持轻量（ADR-0004 的原始意图得以保留，而非推翻）。

## What Changes

- **BREAKING** 视频渲染引擎替换：`render_video`（storyboard 与 type 两模式）不再自行逐帧 seek，改为**提交作业给独立渲染面**（HyperFrames，钉版本）并取回成片；退役自制帧循环与手写 ffmpeg 视音合成。
- **BREAKING** 外置场景契约从自研 seek 契约（`window.__DURATION__`/`__SIZE__`/`seek(t)`/`data-stage`）换成 HyperFrames composition 格式（`data-composition-id`/`data-start`/`data-duration`/`data-track-index` + 适配器 / `window.__hf.seek`）；无用户，一次性切换。
- **NEW 渲染面（独立平面）**：无状态 HTTP 渲染服务，与 API 面解耦、可部署在任意机器、可多实例；VAAS 以 `VAAS_RENDER_URL` 显式契约调用（env 可重指），符合本仓「借用契约」纪律。API 镜像继续不含 Node/引擎（ADR-0004 增补而非推翻：视频渲染被显式委托给渲染面）。
- 五类型 builder 改为产出中性 composition spec；动画改用适配器生态（GSAP/Lottie/Three/CSS/`window.__hf`）；data-viz 的 ECharts 用 `window.__hf.seek` 自定义运行时。
- 音频升级：voiceover/BGM 从「成片后 ffmpeg 混流」改为 composition 的 audio track（`data-track-index` 原生多轨）。
- 保留在 Python（API 面）：`render_still`（chart/cover/graphic）、`render_document`（pdf/longimage）——HyperFrames 只做视频。
- 保留在 VAAS 层：计划哈希/重放、账本、租户隔离、签名下载、计价、MCP 工具面、skills。
- 安全：租户提交的 composition 在渲染面**按作业沙箱**运行（网络命名空间无外网、env 白名单、独立 tmpdir、硬超时、内存/shm 限额）；渲染进程不继承任何平台密钥。
- **Phase 0 gate 已实测通过**（详见 design「Gate 结论」）：系统 chromium 复用、`window.__hf.seek` 适配器钩子、fps/workers/quality/png-sequence 控制、双跑确定性（容器字节与帧级均一致）全部成立；`unshare -n` 需 CAP_SYS_ADMIN（放在专用渲染面是可接受前提）。

## Capabilities

### New Capabilities
- `hyperframes-video-renderer`: 渲染面契约——无状态作业 API、composition 生成、确定性门禁、按作业隔离、多实例派发、失败与重试。

### Modified Capabilities
- `presentation-plane`: `render_video` 的引擎契约改为渲染面委托；外置场景契约改为 composition 格式；`渲染底座统一` 改为「HTML 作者语言 + 两出口引擎（渲染面 / chromium）」；still/doc 两出口不变。
- `video-types`: 五类型改为产出 composition（`renderer` 字段语义 html→hyperframes）；结构与动效行为仍按既有 Scenario 验收。

## Impact

- **代码**：新增渲染面服务（Node + hyperframes，独立镜像/容器）；`mcp-server/tools/render.py`（video 分支改为作业提交，删自制帧循环/ffmpeg 分支）、`tools/typed_scenes/builders/*`（改产 composition）、`tools/_scene_guard.py`（composition 级校验）、`.agents/skills/fd-vaas-storyboard`（契约改 composition 格式）；`remotion-app/` 退役。
- **部署**：新增渲染面容器（独立机器/多实例，`VAAS_RENDER_URL` 指向）；API 镜像**不变重**；compose/部署文档加渲染面一节。
- **文档**：workspace `docs/adr/0004` 增补（渲染面独立，API 面保持无 Node）；`deploy/README.md`。
- **依赖/供应链**：渲染面新增 Node 22 + `hyperframes@0.9.26`（钉版本，npmmirror 构建）；Apache-2.0 归属。
- **风险**：上游 release 耦合（钉版本 + 双跑门禁）；渲染面可用性（多实例 + 重试 + 明确错误）；租户 composition 隔离（按作业沙箱）；五类型 re-author 工作量；GSAP/Lottie 等前端库需本地 vendor（脚手架默认引 CDN，必须替换）。
- **不变**：MCP 工具面（hosted 17 / stdio 23）、账本/计价/重放/租户隔离、publish 面（仅 stdio）、skills 分发。

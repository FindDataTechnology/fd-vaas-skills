# ADR-0004（增补）：视频渲染移交独立渲染面

- 状态：已采纳（2026-11-09）
- 原文：workspace `docs/adr/0004`（"托管镜像不含 Node/Remotion"）

## 背景

原 ADR-0004 决定托管镜像不含 Node/Remotion：Remotion 栈重（React 工具链 +
浏览器下载），且发布面本就必须留在本机（平台登录态不出本机）。该决定至今
仍然成立——**API 面保持无 Node**。

但「不自己造视频渲染器」的需求没有变：VAAS 曾自研 `compose_video`
（HTML seek 契约 → playwright 逐帧 → ffmpeg），是 HyperFrames 的手工复刻，
缺动画生态、音轨靠事后混流、时间轴模型退化。

## 决定

视频渲染移交**独立渲染面**（HyperFrames 0.9.26，钉版本）：

- 控制面（API，Python）：MCP 工具面、账本、计价、重放、租户、签名下载、
  静态出口（chromium 截图/打印）、凭证。**不含 Node**。
- 渲染面（Node + HyperFrames）：无状态 HTTP 作业服务，可多实例、可部署在
  任意机器，API 以 `VAAS_RENDER_URL(S)` 显式契约调用（env 可重指）。
- 隔离：渲染面容器接 internal 网络（无出网）+ 作业级 env 白名单 + 独立
  tmpdir + 硬超时；租户 composition 不触达宿主敏感路径。

## 后果

- 原 ADR-0004 的约束（API 镜像无 Node）**继续有效**，本增补只澄清「视频引擎
  不属 API 面」。
- 渲染重资源（Chrome ~256MB/worker、/dev/shm ≥512MB）不再挤占 API 容器；
  渲染面可按机器余量独立扩容。
- 引擎升级必须过双跑确定性门禁；引擎版本折入计划键（升级自动失效旧重放）。
- Remotion 残留：`skills/cover.py`（封面静帧）与 `skills/voiceover.py`
  （registry 的 voiceover 驱动）仍依赖 `remotion-app/`，暂保留；typed 视频
  管线（`new-task.mjs`/`task-render.mjs`）已不再被 `render_video` 使用。

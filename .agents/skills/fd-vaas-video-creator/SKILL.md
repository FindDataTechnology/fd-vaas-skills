---
name: fd-vaas-video-creator
description: VAAS 视频类型注册表（types/）。五种类型（carousel/listicle/data-viz/kinetic-quote/news-flash）的输入契约声明在此；**渲染由渲染面承担**，本技能不再含本地 Remotion 管线脚本。触发场景：需要查某类型的 inputs 契约、或新增/修改类型声明时。
compatibility: 无额外依赖（纯声明）；渲染走 render_video（渲染面）。
---

# FD VAAS 视频类型注册表

本目录只剩**类型契约**：`types/<type-id>/type.json`（id/name/description/inputs/
defaults/platforms + `renderer: "hyperframes"`）。

- 渲染：`render_video(type=<id>, script=..., inputs=...)` → 场景构建器产 composition
  → 独立渲染面（HyperFrames）出片。
- 本地 Remotion 管线（`new-task.mjs` / `task-render.mjs`）已于 2026-11-09 退役。
- 查契约：`templates_get(domain="video", id=<type>)`；列全部：`templates_list(domain="video")`。
- 新增类型：加 `types/<id>/type.json` + 在 `mcp-server/mcp_server/tools/typed_scenes/builders/`
  加一个 builder（导出 `BUILDER` 即自动注册），核心调度无改动。

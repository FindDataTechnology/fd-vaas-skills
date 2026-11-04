# Design: add-presentation-plane

## Context

W3 已把 chromium 逐帧管线打穿（compose_video 上产 sha-d1869347，seek 契约 + 计划级重放 + CJK 字体内置）。本 change 不新造底座，而是把它**升格为全模态底座**并完成工具面重切。无用户，一次性 breaking。

## Goals / Non-Goals

- **Goals**：orchestrate_* 退役；render_video/render_still/render_document 三出口；双层模板；BGM 混流；知识层 skills 化。
- **Non-Goals**：BGM 生成 API（registry 后挂）；docx 输出（v1 只做 pdf+长图；docx 写作链在 agent 侧已存在，版式底座先行）；Remotion 场景族源码改写（只解禁不改写）；finddata 根文档同步（另起会话）。

## 架构

```
                      ┌──────── 渲染底座：chromium + fonts-noto-cjk + theme.ts 品牌令牌 ────────┐
                      │  seek 契约 = 接口方言（__DURATION__/__SIZE__/seek(t)/data-stage）        │
                      │  安全边界：无外链、data: URI only、set_content + about:blank、无 file:// │
                      └───────┬──────────────────┬──────────────────┬─────────────────────────┘
                        单帧  │            帧序列 │            分页   │
              render_still    │      render_video │    render_document│
              chart|cover|graphic    storyboard|type     pdf|longimage
```

## 工具面映射（old → new）

| 现工具 | 处置 |
|---|---|
| `orchestrate_brainstorm` | **退役** → skill `fd-vaas-brainstorm`（brainstorm.py 的 JSON 模板内容迁入 SKILL.md） |
| `orchestrate_voiceover` | **退役** → 实现吸收进 `render_video` type 模式；编排知识入 skill |
| `compose_video` | **更名归位** → `render_video`（storyboard 模式为第一公民） |
| `generate_cover` | **折入** `render_still(kind=cover)`（内部仍走 CoverBrand 静帧） |
| `generate_video`（同步包装） | **移除**；异步对 `generate_video_submit` + `video_job_status` 是唯一契约 |
| `assets_find_logo` / `assets_list_common` | **折入** `assets_get`（common/logo 是资产树查询，不是独立工具） |
| `assets_list_compositions` / `assets_get_scene_templates` | **升级为** `templates_list` / `templates_get`（双层模板面） |
| `assets_validate_paths` | **折入** `render_video` 输入校验错误信息 |
| `generate_voice/image`、`generate_video_submit`、`video_job_status`、`models_voices`、`voiceover_assemble`、`reference_clips_check`、`assets_list/get/stats`、`registry_*`、`publish_*`（仅 stdio） | 保留 |

托管面 26 → **17**（generate 7 + render 3 + assets 3 + templates 2 + registry 2）；stdio 加 publish 6 = 23。

## 关键决策

1. **render_video 双模式一工具**，不拆两个工具：storyboard（新范式、可组合）与 type（五类型老管线、一站式）。type 模式内部仍走 new-task.mjs/task-render.mjs（video-types spec 契约不动），storyboard 模式走 W3 逐帧管线。互斥校验在入口。skill 指南给选型：需要控制/组合 → storyboard；要成品结构 → type。
2. **图表 substrate = ECharts-on-chromium**。理由：与帧序列同底座（字体/主题/沙箱全复用）；不引 matplotlib（第二套渲染口径，品牌分裂）。视频内图表**动画**继续用 Remotion data-viz 组件（已有，品牌色板原生）；render_still(chart) 的 spec 设计为同一份数据可两用：单帧图 + kenburns 输入。
3. **主题令牌单一来源**：echarts 主题从 theme.ts 构建期生成 `echarts-theme.json`，加漂移测试（theme.ts 改了 JSON 没重生成 → 测试红）。
4. **chart spec v1 契约**：`{echarts_option: {...}, size, format}`——透传 ECharts option + 主题覆盖注入（option 未显式指定的颜色取品牌色板）。两条靶子的第一版 schema 就这一个：文章配图（PNG）与视频 kenburns 输入（PNG 序列）都吃它。
5. **render_document**：md→HTML（python-markdown + 品牌 CSS wrapper）→ chromium；pdf = printToPdf，长图 = full-page 截图。版式模板目录制（`mcp_server/templates/doc/<id>/`：template.json + css），默认版式 + 公文/研报版式后补。docx 留给 pandoc 后置任务（不在验收线）。
6. **外置场景安全边界**：W3 的约束成文为硬校验——渲染前扫描 HTML 引用（http(s)/file 外链 → 拒绝并列出资源）；chromium 侧请求拦截兜底（非 data: 全断）。测试含「含外链被拒 + 不产部分产物」。
7. **BGM**：assets 树 type=bgm；种子曲库 3–5 条 CC0/已授权曲目随镜像（授权来源字段必填）；混流参数 `bgm: {asset_id|path, volume, fade_out}`，ffmpeg 侧复用 voiceover_assemble 的 `-t covered_s` 纪律（BGM 长于视频在视频时长处收尾）。
8. **skills 归宿**：`fd-vaas-brainstorm` / `fd-vaas-storyboard` 落 `.agents/skills/`（repo 内既有模式）；finddata 侧 vaas-presets pack 同步是外账（proposal Impact 已记）。
9. **定价**：render_video 按 second（沿用 W3 口径）、render_still 按张、render_document 按份；pricing.json 补条目，作用量不涉云成本（本地算力 0.0 计价）。

## Risks / Trade-offs

- **双模式一工具的参数面较宽** → storyboard 与 type 参数在 schema 层分离并互斥校验，错误信息各指各的文档。
- **ECharts vendor 进镜像**（~1MB）→ 换取零外链与版本钉死，值得。
- **type 模式内部仍做自己的 TTS**（老管线特性）→ 保留；skill 指南写明何时该走 storyboard + generate_voice 组合（需要音色控制/复用旁白时）。

## Migration Plan

一次性切换：镜像重发 + 网关注册表工具数更新。无存量调用方需迁移（trial 文档等 finddata 侧同步为外账）。回滚 = 回滚镜像 tag。

## Open Questions

无——三条裁决（底座方向 / 直接 breaking / 两靶子都做）均已由用户拍板（2026-11-04）。

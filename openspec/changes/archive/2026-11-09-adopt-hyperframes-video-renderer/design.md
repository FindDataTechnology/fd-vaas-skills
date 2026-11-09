# Design: adopt-hyperframes-video-renderer

## Context

VAAS 现有视频出口是一套自研的迷你 HyperFrames：builders 产自带 `window.seek(t)` 的场景页，`_render_html_frames` 用 playwright 逐帧截图，`_ffmpeg` 合成并混音轨。它能跑（342 测试、生产 E2E 全绿），但每一行都是对「HTML→确定性视频」的重复实现，且没有生态：GSAP/Lottie/Three 用不了，音轨靠事后混流，时间轴模型退化成「场景拼接」。

HyperFrames（81k stars，Apache 2.0，每日推送，HeyGen 在用）是这件事的标准答案，与 VAAS 哲学同构（HTML 作者语言、确定性、为 agent 设计）。且**渲染是重资源活**（Chrome 每 worker ~256MB、/dev/shm ≥256MB），不该挤在 API 容器：本仓有**多台机器**，把视频渲染独立成「渲染面」，API 面继续轻量。

## Gate 结论（Phase 0 已实测，2026-11-09）

| 未知 | 结论 | 证据 |
|---|---|---|
| 包/版本 | `hyperframes@0.9.26` 在 npmmirror 有；Node 22 从 npmmirror 装 | 安装 + `--version` |
| 系统浏览器复用 | ✅ `HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium` 生效 | `doctor` 输出 `Chrome env: /usr/bin/chromium` |
| FFmpeg/FFprobe 复用 | ✅ `HYPERFRAMES_FFMPEG_PATH` / `HYPERFRAMES_FFPROBE_PATH` | 环境变量清单 + doctor |
| 自定义适配器钩子 | ✅ `window.__hf = {duration, seek(t)}`（非 GSAP 运行时）；GSAP 走 `window.__timelines[id].seek(t)` | dist 源码 + 真渲染 |
| fps / 质量 / worker / 格式 | ✅ `-f`(1-240)、`-q`、`-w`、`--format`(mp4/webm/mov/gif/png-sequence/hls)、`--crf` | `render --help` |
| 确定性 | ✅ 容器字节 md5 一致；png-sequence 20 帧聚合 md5 一致 | mac 双跑实测 |
| 离线 | ✅ 最小 composition 无外网可渲 | 真渲染 |
| 遥测 | 有开关 `HYPERFRAMES_NO_TELEMETRY` | 环境变量清单 |
| 外链风险 | ⚠️ 脚手架默认从 cdn.jsdelivr.net 引 GSAP——**必须本地 vendor** | 脚手架 index.html |
| /dev/shm | ⚠️ 默认 64MB < Chrome 要求 256MB，渲染面须 `--shm-size=512m` | doctor + inspect |
| `unshare -n` | ⚠️ 默认容器无 CAP_SYS_ADMIN 会失败；**专用渲染面**加 cap 或内核 netns 即可（隔离的前提） | 容器内实测 |

## Goals / Non-Goals

- **Goals**：视频渲染委托独立渲染面（钉版本、离线、复用系统浏览器/FFmpeg）；VAAS 拥有中性 composition spec 与编译器；五类型 builder 声明式；多轨音频；按作业隔离；确定性门禁；退役 Remotion 与自制帧循环。
- **Non-Goals**：不把 HyperFrames 用于静态出口（still/doc 保持 Python/chromium）；不做 k8s 编排（渲染面先做 compose/多实例，k8s 留后）；不改 MCP 工具面（17/23）；不托管 HyperFrames Studio。

## 架构：控制面 / 渲染面

```
                   ┌─────────────────────────────┐   HTTP(作业)   ┌──────────────────────────────┐
   MCP 客户端 ────▶ │  VAAS API 面（Python，轻）    │ ─────────────▶ │  渲染面（Node + HyperFrames）  │
   (语音/图像/视频)  │  MCP 工具面 · 账本 · 计价     │ ◀───────────── │  无状态 · 可多实例 · 任意机器   │
                   │  重放 · 租户 · 签名下载       │   成片/状态    │  Chrome · FFmpeg · 按作业沙箱   │
                   │  render_still/render_document │                │  HyperFrames 0.9.26（钉死）    │
                   └──────────────┬──────────────┘                └──────────────────────────────┘
                                  │
                      ┌───────────┴───────────┐
                      │ bao(vault) · 词元 router │   ← API 面继续管凭证与生成
                      └───────────────────────┘
```

- **控制面（API）**：工具面、账本、计价、重放、租户、签名下载、静态出口（chromium 截图/打印）、凭证。**不含 Node**。
- **渲染面**：只做 composition→MP4。无状态（不碰账本），可水平扩；`VAAS_RENDER_URL` 显式契约可重指——符合本仓「借用契约」纪律。
- 本地 stdio 模式可指向同一或本地渲染面（`VAAS_RENDER_URL` 默认本机）。

## 作业契约

```
POST /v1/render
  { job_id: "幂等键", format: "mp4", fps: 10, quality: "looks",
    composition: { html: "...", assets: [ {name, sha256, bytes?} ] } }
→ 200 { artifact_url | bytes, engine: "hyperframes@0.9.26", duration_ms, warnings: [...] }
```

- 素材：VAAS 把 composition 用到的图片/音频作为 multipart 或 sha256 引用随作业上传；渲染面解包到独立 tmpdir（避免 base64 膨胀与共享卷）。
- 幂等：`job_id` = VAAS 计划哈希（type/script/inputs/voice/bgm **+ 引擎版本**），重复提交返回同结果。
- 无状态：渲染面不存任何业务数据；成片可流式返回，或写到 VAAS 提供的上传地址。

## 中性 composition spec（VAAS 拥有）

```python
CompositionSpec = {
  "size": [w, h], "duration_s": float, "fps": 10,
  "tracks": [
    {"index": 0, "kind": "visual",   "clips": [{"start":0,"duration":3,"html":"…","animation":{"type":"css|waapi|gsap|hf"}}]},
    {"index": 1, "kind": "subtitle", "clips": [{"start":0,"duration":1.2,"text":"句"}]},
    {"index": 2, "kind": "audio",    "clips": [{"start":0,"duration":12,"src":"voice.mp3","volume":1.0}]},
  ]}
```

编译器 `compile_composition(spec) -> hyperframes_html`：clip → `data-start/data-duration/data-track-index`；品牌令牌注入 `:root{--vaas-*}`；前端库本地 vendor；零外链扫描。

## Builder 契约 v2（声明式）

```python
class Builder:
    type_id: str
    def validate_inputs(inputs, segments) -> None        # 不变：结构对照前置、零产物
    def build(segments, inputs, size, theme) -> {"visual":[clip…], "subtitle":[clip…]}
```

- 视觉/CSS 复用现有；删各 builder 的 seek JS 与字幕查表，改 CSS 关键帧/WAAPI/GSAP/`window.__hf`
- data-viz：`window.__hf.seek(t)` 驱动 ECharts（自定义运行时，官方钩子）
- 音频由管线统一注入（builder 不碰）

## 隔离模型（渲染面按作业沙箱）

```
渲染面作业执行器
  ├─ 独立 tmpdir（解包 composition + 素材）
  ├─ 网络：作业进程无外网（专用渲染面容器加 CAP_SYS_ADMIN 以 unshare -n，或渲染面本身置于 internal 网络）
  ├─ env：白名单（HYPERFRAMES_* / PATH / HOME=tmp），剔除一切平台密钥
  ├─ 资源：--shm-size=512m、内存限额、硬超时（默认 600s）、进程组 kill
  └─ 产物：成功才返回；失败/超时零残留
```

- 渲染面是专用机器/容器，授予 CAP_SYS_ADMIN 以用 `unshare -n` 是可接受前提（它不是公网面）
- 若不想加 cap：渲染面容器整体接 `--network` internal-only，作业无外网即天然隔离（推荐，见下）

## 部署与容量（多机器）

- 渲染面 c 候选机：cheap-6（8c/7.9G，余 ~2.5G）最优；cheap-1（4c/3.9G 余 2.0G）次之；cheap-3 盘紧（89%）。**不绑定单机**：`VAAS_RENDER_URL` 可指向任一实例或 LB。
- 并发：单机 `-w 1` 起步（每 worker 一个 Chrome ~256MB），随内存加 worker；VAAS 侧作业队列 + 多实例派发。
- 渲染面镜像：Node 22 + `hyperframes@0.9.26` + chromium + ffmpeg + 字体；约 +2.5GB（含浏览器），放专用机。

## 确定性

- 口径：帧级 framemd5 为主（容器字节已实测可达）
- 门禁：引擎版本变更必过双跑；计划哈希折入引擎版本
- builders 禁随机源；`toLocaleString` 等 ICU 相关格式化列为已知漂移点

## 迁移阶段（每阶段可停）

```
Phase 0  gate ✅ 已完成（上表五问全部有答案）
Phase 1  渲染面服务（作业 API + 沙箱 + 钉版本 + 健康检查）——独立可测
Phase 2  spec + 编译器 + theme/vendor（离线单测）
Phase 3  五 builder 改声明式（视觉复用）
Phase 4  切流：render_video 提交作业 + 重放哈希 + 诊断；退役自制帧循环/ffmpeg/seek 契约
Phase 5  上产 + 生产 E2E（五类型 + still/doc 回归）；退役 Remotion；文档/ADR 增补
```

无运行时双引擎；回滚 = 镜像/渲染面 tag。

## Risks / Trade-offs

| 风险 | 处置 |
|---|---|
| 上游 release 耦合 | 精确钉版本 + 双跑门禁 + 渲染面版本回报 |
| 渲染面可用性 | 多实例 + 重试 + 明确错误 + 健康检查 |
| 隔离前提（CAP_SYS_ADMIN / internal 网络） | 优先 internal-only 网络方案；cap 方案备选 |
| 前端库 CDN 默认 | 全部本地 vendor + 编译期零外链扫描 |
| 五 builder 重写 + 视觉回归 | 行为级 Scenario + 抽帧目检；允许重排不丢结构 |
| 渲染面镜像大 | 专用机，不与 API 面共享镜像 |
| 作业传输体积 | 素材按 sha256 引用 + 流式回传，不 base64 |

## Open Questions

无阻塞项——Phase 0 五问已答。剩余为工程细节（多实例派发策略、internal 网络 vs cap 的最终选择），在 Phase 1 实现时定。

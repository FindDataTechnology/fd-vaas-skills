# Proposal: deliver-hosted-surface

## Why

用户 2026-11-06 裁决：hosted 17 工具面「做实」——镜像补重依赖兑现承诺，不做缩面。现状是托管面一张兑现不了的牌：canonical 镜像只装 fastmcp/pydantic/aiosqlite/dotenv（`deploy/mcp-server.Dockerfile:24`），无 ffmpeg、无 chromium、无 CJK 字体、无 mutagen，而 `render_still/render_document/voiceover_assemble` 与 `templates` 的 `runtime:"hosted"` 标注都假设这些底座在位（`presentation-plane` 已规定「无头浏览器 + 内置 CJK 字体 + 单一底座」）；词元 TTS 的 170 字长度墙分段与合成字幕兜底（`ciyuan-lane-providers` 已规定「MUST NOT 因 provider 分叉」）只落在了 node 技能腿（ffca3e1），hosted python 腿长文照撞墙、桥硬编码 `enable_subtitle=False`；图像/视频车道上游封号（acct 40 403→503）后无任何机器可读的 lane 健康面，发现工具照常 advertise。修好这三段，托管面才配得上「核心产品条线」定位。

## What Changes

- **镜像补底座**：hosted 镜像全量安装渲染底座依赖（playwright+chromium、ffmpeg、CJK 字体栈、音频时长测量），三出口 + type 模式（html 构建器族）在托管实例开箱即跑；本地 stdio 行为不变。
- **前置收账**：先归档 `add-typed-video-html-renderer`（20/20，W5.2 图像/视频腿受阻按先例记外挂账），其 presentation-plane/video-types delta 落主 spec 后本 change 在其上继续。
- **python 腿对齐词元出口层**：hosted `generate_voice` 获得 ≤150 字段合成、段间间隔与退避重试、合成字幕兜底（形状同官方戳、`captions_source` 元数据）；桥不再 `enable_subtitle=False`；默认音色不再 `alloy` 兜底（白名单缺失即显式报错）；`_ciyuan_tts` 的 speed 透传与 docstring 虚标修正。
- **车道健康一等可见**：`models_voices`/`registry.list_generators` 返回每条车道 `health`（active/degraded/down + 原因类别 + 最后验证时间）；down 车道调用返回 `lane_down` 分类（错误分类层由 fix-hosted-generation-correctness 提供），发现面不得把 down 车道标为可用。
- **上游修复（外依赖）**：词元图像/视频车道（acct 40 403 封禁）在 sub2api 侧解封或换账号；volcengine 备档 key 的 seedream 权限核对；修复以实调 E2E 为销账证据，车道状态翻 active。
- **标注诚实**：模板/类型目录的 `runtime` 标注与实例真实能力一致，目录缺失等静默 `[]` fail-open 改为显式错误。

## Capabilities

### New Capabilities

（无——全部落入既有 capability 的 delta。）

### Modified Capabilities

- `presentation-plane`：修订「渲染底座统一」——托管实例 SHALL 自带完整渲染底座，出口能力与标注一致（开箱可跑、不一致即报错改标）。
- `ciyuan-lane-providers`：修订「词元侧车道缺陷的记录与规避」——缺陷台账机器可读、down 车道不 advertise、修复以实调为凭；出口层分段/字幕能力覆盖全部合成腿（该义务已在「语音车道合成」条款内，本 change 以任务补齐 python 腿实现）。
- `generation-registry`：修订「方式可发现性」——生成方式清单 SHALL 携带车道健康状态。

## Impact

- **代码/镜像**：`deploy/mcp-server.Dockerfile` 与根 shim（双写同步，直至 add-ci-and-provisioning 落单源）、`scripts/litellm-bridge.py`、`scripts/_ciyuan_tts.py`、`mcp-server/mcp_server/generators/tts.py`、`tools/templates.py`（fail-open 与标注）、`tools/generate.py`/`registry.py`（health 字段）、`tests/test_hosted_surface.py` 与新增 health 测试。
- **外依赖**：sub2api（词元）账号修复——跨仓操作，挂账跟踪直至实调销账；期间 image/video 车道如实标 down。
- **验收**：hosted 实例上五类型 type 模式 voice_path 腿 + TTS 腿成片、render_still/render_document/voiceover_assemble 成片、长文（>170 字）generate_voice 成功且带 synthetic captions、探针输出车道健康全表；证据记入本 change 目录。
- **风险**：镜像体积显著增大（chromium+fonts 约 +500MB）——词元线部署节点磁盘此前有事故先例，上线前核对 cheap-2 余量并记入 deploy README。

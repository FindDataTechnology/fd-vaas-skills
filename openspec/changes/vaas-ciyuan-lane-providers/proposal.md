## Why

VAAS 的语音/图像/视频生成目前硬绑火山方舟（Volcengine Ark）直连，且多 Provider 切换
依赖 `litellm` 桥接层——这是我们自己的钱花在别人的网关上，而萬星·词元（`router.finddatatech.cloud`，
self-fork 的 sub2api）已经把语音（ASR+TTS）、图像、视频三条车道全部打通并按同一把 key
计费。本次把生成后端换成词元车道，钱与用量回到自家账本，顺带去掉 litellm 依赖
（litellm 对我们没有意义，词元本身就是网关）。

2026-10-16 实调取证（先用试用 key 摸底，再用新建的 VAAS 专用账号全量复验，均真实出结果）：

| 车道 | 端点 | 实测 | 结论 |
|---|---|---|---|
| TTS | `POST /v1/audio/speech` | `qwen3-tts-flash` + `Cherry` → HTTP 200，134444B RIFF/WAVE | ✅ 可用 |
| ASR | `POST /v1/audio/transcriptions` | `whisper-1` → 502 `lane_upstream_error (status 429)`；`qwen3-asr-flash` → 503 无可用上游账号 | ⚠️ **车道未配好**，非 VAAS 侧问题 |
| 图像 | `POST /v1/images/generations` | `gemini-3-pro-image` → 200 `data[0].b64_json`，解码得真 JPEG（1408×768，815KB） | ✅ 可用 |
| 图像 | 同上 | `gpt-image-1` / `gpt-image-2` → HTTP 200 但 **Content-Type: text/html**，返回 openai-next 网页 UI；两个不同 prompt 返回**同一个** `20260817` 日期的 URL（是 favicon 不是生成结果） | ❌ **词元侧缺陷**，须避开 |
| 视频 | `POST /v1/contents/generations/tasks` | `doubao-seedance-2-0-fast-260128` → 200 `queued` → 轮询 `succeeded` → 下载到真 MP4（2987184B，`ISO Media, MP4`） | ✅ 可用 |
| 视频 | 同上 | `doubao-seedance-1-0-pro`（现 .env 值）→ 503；`seedance-2-5` → 503；`veo3.1-fast`/`sora-2`/`kling-*` → 404 | ❌ 仅 seedance-2-0-fast 家族可路由 |

**关键约束（决定本次形状）**：词元的密钥按分组划能力——`sk-1756…`（组 3）管 chat+三车道，
`sk-0e0d…`（组 9）管图像+视频，**一把 key 通吃做不到**。VAAS 凭证链已按 kind 分路
（`pool/<line>/tts`、`/image`、`/video`），正好天然适配，无需改解析链结构。

## What Changes

- **新增 `ciyuan` provider 档位**：`litellm-bridge.py` 增一条 `provider == "ciyuan"` 分支，
  直连词元车道 HTTP API（`urllib`，零第三方依赖），与现有 `volcengine` 直连分支并列。
  - TTS → `POST /v1/audio/speech`
  - Image → `POST /v1/images/generations`，取 `data[].b64_json` 落盘
  - Video → `POST /v1/contents/generations/tasks` 创建 + `GET` 同路径轮询，终态取
    `content.video_url` 下载
- **移除 litellm 依赖**：删除 `litellm-bridge.py` 的 litellm 调用路径与
  `requirements.txt` 的 `litellm` 项；`provider` 只保留 `volcengine`（Ark 直连）与
  `ciyuan` 两档。**BREAKING**：`.env` 里 `*_PROVIDER` 若设为 `openai`/`elevenlabs`/`azure`
  等第三方值将不再被接受（原走 litellm），需改为 `ciyuan`。
- **凭证链增 `ciyuan` 档**：`credentials.py` 的 `_OPENAI_ENV` 改名/扩展为按 provider 取
  环境变量，新增 `CIYUAN_API_KEY` / `CIYUAN_BASE_URL` / `CIYUAN_TTS_MODEL` 等；vault
  记录的 `provider: "ciyuan"` 走新分支。凭证使用 **VAAS 专用词元账号**
  （`vaas@findmail.com`，user 94，$20 硬顶；key76 组3=TTS、key77 组9=图像视频），
  与伙伴试用账号（ciyuan-trial）严格隔离；台账登记见 paas `docs/registry-maintenance.md` §10-A④。
- **默认模型改为词元实测可用值**：`IMAGE_MODEL=gemini-3-pro-image`、
  `VIDEO_MODEL=doubao-seedance-2-0-fast-260128`、`TTS_MODEL=qwen3-tts-flash` +
  `TTS_VOICE=Cherry`（原 Ark 的 `doubao-seedream-*`/`doubao-seedance-1-0-pro` 在词元不可路由）。
- **文档更新**：README（中/英）的 Provider 配置表、`.env.example`、deploy README 的
  OpenBAO 路径说明（新增 ciyuan 档路径与「图像/视频一把 key、语音另一把」的分组口径）。
- **不在本次范围**：ASR 车道修复（词元侧未配上游账号，属词元 change）；`generate_voice`
  之外的语音能力。

## Capabilities

### New Capabilities

- `ciyuan-lane-providers`: 萬星·词元车道作为 VAAS 生成后端的契约——三条车道（语音/图像/
  视频）的端点、可用模型白名单、计费与失败口径，以及 provider 档位的选择规则。

### Modified Capabilities

- `generation-credentials`: 凭证解析需支持 `ciyuan` provider 档（新增环境变量映射与
  vault 记录形态），凭证来源标注新增 `ciyuan`。

## Impact

- 代码：`scripts/litellm-bridge.py`（增 ciyuan 分支、删 litellm 路径）、
  `mcp-server/mcp_server/credentials.py`（provider 档与 env 映射）、
  `mcp-server/mcp_server/generators/{tts,image,video}.py`（provider 标注从硬编码
  `volcengine` 改为按解析结果）。
- 依赖：**移除 `litellm`**；新增零依赖（词元车道走 stdlib `urllib`）。
- 配置：`.env` / `.env.example` / OpenBAO `secret/vaas/pool/<line>/{tts,image,video}`
  的 provider 与 model 字段。
- 对外行为：生成产物形状与工具签名不变；计费与用量改由词元账本承载（VAAS 侧
  `generation_usage` 仍按既有口径记录 units）。
- 风险：图像车道 `gpt-image-*` 返回 HTML 是词元侧缺陷，需在默认模型与文档里明确避开；
  若词元日后来修，本 change 的模型白名单需同步。

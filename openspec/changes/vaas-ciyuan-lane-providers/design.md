## Context

见 `proposal.md` 的 Why（含 2026-10-16 六项实调取证表）。此处只记实施形状的约束：

**现状**：`mcp-server/mcp_server/generators/{tts,image,video}.py` 一律 `prepare()` →
`run_bridge([... litellm-bridge.py ...])` → 解析 stdout JSON → `finish()`。桥接层
`scripts/litellm-bridge.py` 有三个 `cmd_*`，各自 `if provider == "volcengine": <直连> else: <litellm>`。
`credentials.py` 已有 `provider` 字段概念（`"volcengine"` / `"openai"` 两档）与
`subprocess_env()` 的分档 env 映射——**这是本次改造的天然落点**，解析链结构不用动。

**约束一（决定分路）**：词元密钥按分组划能力，组 3 = chat+三车道、组 9 = 图像+视频，
一把 key 通吃做不到。VAAS 凭证链已按 kind 分路（`pool/<line>/{tts,image,video}`），
因此「语音一把、图像/视频一把」的分组口径**零改造即达**，只是两条路径填不同的 key。

**约束二（决定不用 litellm）**：词元本身就是网关，litellm 在这里是多余的第三层。
实测三条车道都是简单的 HTTP + JSON（或二进制流），stdlib `urllib` 足够。

**约束三（来自实测，决定默认值）**：图像车道只有 `gemini-3-pro-image` 返回合规 JSON；
`gpt-image-*` 返回 HTML（两个不同 prompt 返回同一个 `20260817` 的 favicon URL）。
视频只有 `doubao-seedance-2-0-fast-260128` 可路由（现 .env 的 `doubao-seedance-1-0-pro` 是 503）。

## Goals / Non-Goals

**Goals:**
- 三条车道（TTS / 图像 / 视频）能经词元完成真实生成并落盘成 VAAS 产物。
- provider 选择由凭证记录驱动，代码不硬编码后端。
- 去掉 litellm 依赖，生成链路只依赖 stdlib。
- 默认模型取自实测可服务的白名单。

**Non-Goals:**
- 修词元侧的 ASR 车道（上游未配账号）——那是词元的 change。
- 修图像车道 `gpt-image-*` 返回 HTML 的缺陷——同上，本 change 只规避不修。
- 引入词元 chat 能力（VAAS 生成链路不调 chat）。
- 改 `generation_usage` 的表结构（沿用既有 units 口径，只加档位区分）。

## Decisions

**① 在 `litellm-bridge.py` 内新增 `ciyuan` 分支，而不是新建一套车道客户端。**
生成器与 `run_bridge` 的契约是「子进程 + stdout JSON」，沿用它可以让 tts/image/video
三个生成器的改动量趋近于零（只有 video 的异步两段需要少量扩展），也让本地模式继续
走 `.env`、托管模式继续走 vault env 注入。**备选**：在 Python 生成器里直接写 HTTP
调用——会让「本地/托管」两种模式各写一遍，且绕过既有的子进程环境隔离，否决。

**② 车道调用用 stdlib `urllib`，不引入 SDK。**
实测三条车道都是一发请求（视频两发：创建+轮询），无流式、无签名算法。词元的视频
轮询是「创建返回任务 ID → GET 同路径」，比现有 volcengine 的 Agent Plan 轮询更简单。
**备选**：装 openai SDK——为一个网关再装一层 SDK 与「去掉 litellm」的意图相悖，否决。

**③ `provider` 只保留 `volcengine` 与 `ciyuan` 两档，`openai` 档退役。**
现有 `_OPENAI_ENV` 那档的本意是「任何 OpenAI 兼容中转」，而词元正是那个中转——
把 `openai` 改名落地为 `ciyuan` 并绑定实测端点，语义更准。**BREAKING**：`.env` 里
`*_PROVIDER` 写 `openai`/`elevenlabs`/`azure` 等第三方值的部署会开始被明确拒绝
（此前走 litellm）。这些值当前无部署在用，且用户已明确 litellm 没有意义。

**④ 视频沿用现有异步两阶段（submit/poll）形状，不改为同步阻塞。**
`video.py` 已有 `generate()` 同步 + `submit()/poll()` 异步两条路径，后者是托管模式防
重复计费的关键（客户端超时重试的是状态查询而非付费提交）。词元的任务协议与既有
volcengine 异步形状同构，直接套用即可。**备选**：统一改成同步等待——会丢掉防重复
提交的性质，否决。

**⑤ 默认模型写进 `.env.example` 与文档，实测白名单写成常量注释。**
`gemini-3-pro-image` / `doubao-seedance-2-0-fast-260128` / `qwen3-tts-flash`+`Cherry`
是 2026-10-16 实测可服务的组合；同时把「`gpt-image-*` 返回 HTML」「seedance-1-0-pro
503」作为已知缺陷写进注释，避免后人再次踩坑。**备选**：运行时探测可用模型再选——
增加一次网络往返与失败模式，且词元 `/v1/models` 列的是「可识别」而非「可服务」，
实测已证明不可信，否决。

**⑥ 错误如实上抛，不做模型兜底重试。**
词元对不可路由模型返回 404/503、对未配上游的车道返回 `lane_upstream_unavailable`。
这些都不是「换个模型试试」能解决的，静默兜底会把配置错误伪装成随机失败。

## Risks / Trade-offs

- **[图像车道模型面窄]** 实测只有 `gemini-3-pro-image` 返回合规 JSON，且它是 Google 模型
  （VAAS 现默认用 doubao-seedream）。→  mitigation：默认值即取该模型，并把「哪些模型
  实测不可用」写进注释；若运营需要 doubao 系图像，需先在词元侧修 doubao-seedream 路由
  （当前 400 "requires an image model"）。
- **[ASR 不可用]** 语音车道上游未配账号（503 `no available upstream account`）。
  → mitigation：TTS 可用先落地；ASR 如实报错而非静默降级，并在文档标注为待词元侧配置。
  VAAS 的 `generate_voice` 是 TTS 路径，ASR 不在当前工具面内，影响可控。
- **[BREAKING：第三方 provider 值失效]** 写 `openai`/`elevenlabs` 等值的部署会开始被拒。
  → mitigation：当前无此类在用部署；报错信息明确列出受支持的两档与迁移方式。
- **[词元分组约束]** 一把 key 只能绑一个分组，运维配错分组会得到「模型不可路由」类错误。
  → mitigation：deploy README 写明「语音一把（组 3）、图像/视频一把（组 9）」的口径与
  路径示例。
- **[词元侧缺陷会变]** 图像 HTML 缺陷若被修复，本 change 的模型白名单会显得过窄。
  → mitigation：白名单以注释形式标注实测日期，不写成硬校验拒绝。

## Migration Plan

1. 代码落地（bridge 分支 + credentials 分档 + 默认值 + 文档）。
2. 本地验证：`.env` 配 VAAS 专用账号的两把 key（账号 `vaas@findmail.com` / user 94，
   key76 组3=TTS、key77 组9=图像视频；密码与全文在部署密钥件，台账见 paas
   `docs/registry-maintenance.md` §10-A④）+ ciyuan 档，实跑 TTS / 图像 / 视频三条真请求，
   确认产物落盘且非空（图像能解码、视频能 `file` 识别为 MP4）。
   **不用 ciyuan-trial 那两把 key**——那是伙伴共享试用额度。
3. 托管验证：向 OpenBAO 写 `pool/wanxing/{tts,image,video}` 三条 ciyuan 记录
   （tts 填 key76，image/video 填 key77），滚版后经 MCP 工具各调一次。
4. 回滚：把 vault 记录改回 `provider: volcengine` + 原 Ark key 即恢复原后端；
   代码回滚只需还原 bridge 与 credentials 两个文件。两条路径可独立回滚。

## Open Questions

- 运营是否要求图像走 doubao 系（seedream）而非 gemini？若需要，须先在词元侧修
  seedream 的路由（当前 400）。本 change 按实测可用值落地，不阻塞于此。
- 语音车道的上游账号何时由词元侧配好？配好后 ASR 即随之可用，VAAS 侧无需改代码
  （端点与协议已在本次落地）。

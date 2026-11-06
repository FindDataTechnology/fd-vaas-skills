# VAAS 生成面托管部署（示例与配方）

> 秘密与真实值全在私有侧（部署节点 compose / 部署编排）。本目录只放结构与示例；
> 决策依据见 VAAS 仓 `openspec/changes/vaas-mcp-platform-onboarding/design.md`
> 与工作区 `docs/adr/0004`、`docs/adr/0005`。

**参考布局**：实例跑在一台独立节点（下称 `<NODE>`，tailnet `<NODE_IP>`，compose 在
`<DEPLOY_DIR>/`），OpenBAO 留在 registry 栈内并把 8200 加绑 tailnet `<BAO_IP>`——
跨机经 tailnet 取凭证，网关代理可达，部署节点不与 registry 抢资源。

> **部署者注意**：下文所有形如 `<NODE>` / `<NODE_IP>` / `<BAO_IP>` 的都是占位符，
> 替换成你自己的环境值。**本仓库不提供生产坐标**（Git 历史里可能有历史值，仅供回溯，
> 不要照抄到新环境）。

## 布局

- `mcp-server.Dockerfile` — 生成面镜像（不含 Remotion/发布面；**源码树直跑，
  PYTHONPATH=/app/mcp-server**，勿改回 wheel 安装——VAAS_ROOT 相对解析依赖 /app 布局）
- `docker-compose.vaas.example.yml` — 每线一个服务实例（部署节点独立 compose）

## 环境变量（部署侧注入，均不入仓）

| 变量 | 用途 |
|---|---|
| `VAAS_HOSTED=1` | 托管模式开关（工具面收窄 + 身份强制 + vault 凭证） |
| `VAAS_LINE` | 线池命名（`wanxing` / `base`） |
| `VAAS_BEARER_TOKEN` | 服务静态 bearer（谦面注册的 egress 凭据同值） |
| `OPENBAO_ADDR` / `OPENBAO_TOKEN` | bootstrap：密钥库地址（跨机写你的密钥库地址，如 `http://<BAO_IP>:8200`）+ path 受限 policy token |
| `VAAS_PORT` / `VAAS_BIND` | 监听（默认 30950 / 0.0.0.0，宿主侧只绑 tailnet IP） |
| `VAAS_PUBLIC_URL` | 下载签名 URL 的对外基址（`http://<NODE_IP>:30950`） |
| `VAAS_PRICING_FILE` | 定价表路径（见 `mcp-server/pricing.example.json`） |
| `VAAS_DOWNLOAD_TTL` / `VAAS_ARTIFACT_TTL_DAYS` / `VAAS_CRED_TTL` | TTL 调参（默认 24h / 30d / 300s） |

## OpenBAO 路径约定（KV v2，mount `secret`）

凭证按 **kind**（tts / image / video）分池，`provider` 字段声明后端档位
（`volcengine` 火山方舟直连 | `ciyuan` 萬星·词元车道；缺失按 volcengine 兼容）：

```
secret/vaas/pool/<line>/<kind>             # 线池凭证 {api_key, base_url?, model?, provider?, voice?}
secret/vaas/service/default/<kind>         # 服务默认凭证（同上形状）
secret/vaas/service/default/download-hmac  # 下载签名密钥 {value}
```

### ciyuan 档记录示例（萬星·词元，2026-11-05 复核）

```jsonc
// secret/vaas/pool/wanxing/tts —— 组3 core（豆包/腾讯云语音，健康）
{"api_key": "sk-...", "base_url": "<CIYUAN_GATEWAY_BASE>",
 "model": "qwen3-tts-flash", "voice": "101001", "provider": "ciyuan"}

// secret/vaas/pool/wanxing/image —— 组9 image-video（上游账号 40 openai-next）
{"api_key": "sk-...", "base_url": "<CIYUAN_GATEWAY_BASE>",
 "model": "gemini-3-pro-image", "provider": "ciyuan"}

// secret/vaas/pool/wanxing/video —— 组9（同一把 key）
{"api_key": "sk-...", "base_url": "<CIYUAN_GATEWAY_BASE>",
 "model": "doubao-seedance-2-0-fast-260128", "provider": "ciyuan"}
```

> ⚠️ 词元密钥按「分组」锁能力：**语音一把（组3 core）、图像+视频一把（组9 image-video）**，一把通吃做不到。配错分组得到「模型不可路由」类错误，不是密钥错误。
> **voice 字段是数字音色 ID（如 101001），不是 "Cherry"**——ciyuan 车道音色以 `models_voices` 工具为准（`_ciyuan_tts.py` 有硬校验，错误音色直接拒，不让上游静默回落）。旧文档/示例里的 "Cherry" 是过时口径。
> **2026-11-05 实测**：voice 腿（qwen3-tts-flash + 101001）200 出 MP3 全链通；**image/video 腿 HTTP 503**（`No available compatible accounts` / `No eligible Seedance accounts`）——根因是组9 唯一上游账号（openai-next，acct 40）被上游 `403 site owner blocked access`，router 侧无健康图像/视频账号可调度。这是**上游订阅问题，非 router key 问题**（凭证链已实证解析到 driver）；解法=恢复/替换 openai-next 图像视频账号。
> 换模型前先实调——`/v1/models` 列的是「可识别」不是「可服务」。

## OpenBAO 运维（以 registry 栈所在节点为例）

- **生产模式**（2026-10-06 起）：file backend + `./openbao/data` 卷，**重启后 SEALED**。
- **解封配方**（root-only 文件含 unseal key 与 root token；栈 `.env` 的 OPENBAO_TOKEN
  必须同步为当前 root token）：
  `python3 -c "import json,urllib.request; init=json.load(open('/root/<OPENBAO_INIT_FILE>')); urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8200/v1/sys/unseal', method='PUT', data=json.dumps({'key': init['unseal_keys_b64'][0]}).encode()))"`
- **VAAS policy token**：`vaas-policy`（仅 `secret/data/vaas/*`），10 年期 orphan
  token；部署密钥在部署节点 `/root/<VAAS_DEPLOY_SECRETS_FILE>`（600）。
- 迁移回滚件：`/root/openbao-snapshot-20261006.json`（dev→file 当日全量导出，回填校验
  3/3 哈希一致）。
- 两个 compose 都改过：`docker-compose.yml` 与 **权威的 `docker-compose.prebuilt.yml`**
  （容器由它创建；重建用 `docker compose -f docker-compose.prebuilt.yml up -d
  --no-deps --force-recreate --no-build <svc>`，不要走默认 yml——它会尝试本地 build）。

## 存活与恢复（runbook）

- **健康探针**：容器 `/health`（`main.py` custom_route）+ compose `healthcheck`（示例见
  `docker-compose.vaas.example.yml`）。存活态可 `docker inspect -f '{{.State.Health.Status}}' vaas-wanxing`。
- **unhealthy 自愈**：compose 的 healthcheck 不自动重启，部署侧用 `deploy/health-watch.sh` 兜底
  （连续 unhealthy 达阈值即 `docker restart`，默认阈值 2 次、容器名 `vaas-wanxing`，env 可调）。
  挂 root crontab：`*/5 * * * * bash <DEPLOY_DIR>/health-watch.sh >> /var/log/vaas-health-watch.log 2>&1`。
- **进程级自愈**：`restart: unless-stopped` 覆盖崩溃/OOM；单容器单节点是已知单点（见下）。
- **密钥库重启后 SEALED**：VAAS 起来但取不到凭证 → `credential_unavailable`。先按上方「OpenBAO 运维」
  解封配方 unseal，再 `docker restart vaas-wanxing`（policy token TTL 缓存会自然失效）。
  root key 文件路径与 OPENBAO_TOKEN 同步口径见上节；本仓不落真值。
- **单点风险与备份责任**：实例是单容器单节点。数据面 = `vaas-data`(DB) + `vaas-downloads`(产物) 两个
  named volume，宿主 docker 卷目录，**备份归部署节点运维**（本仓不提供生产坐标、不代管数据）。
  重节点/迁移前 `docker compose ... down` 前先备份两卷；节点重启后确认容器已 `running` 且 `/health` 绿。
- **外依赖债务**：车道封禁/CI 停摆/真机复验等跨仓未销账项，统一登记在
  [`docs/debt-ledger.md`](../docs/debt-ledger.md)。
- **验证一次自愈生效**（上线后做一次，留时间线）：`docker kill` 主进程 → 观察 restart 策略拉起 →
  `/health` 回绿；人为使 healthcheck 失败（如临时错 port）→ 观察 health-watch.sh 到阈值重启。

## 謙面注册（`/vaas-wanxing` 先行）

1. registry server 注册：proxy_pass_url = `http://<NODE_IP>:30950/mcp`；egress 凭据 =
   `VAAS_BEARER_TOKEN` 同值；**`identity_forwarding: true`**（fork 补丁已实现：
   `~/code/mcp-gateway-registry` 分支 `fd-i18n-ui` commit `9e63c091`，2026-10-06，
   7537 tests passed；生产部署须先让 registry 栈滚到含此 commit 的镜像）。
2. Logto group 可见性：仅目标线租户 group 可见。
3. 网关保守限流（成本保险丝）。
4. 冒烟：客户 token 经网关 initialize/tools/list（无 publish 工具）→ 生成 →
   签名下载 → `/usage/summary` 出现该租户记录（凭证来源=pool）。

## 已知口径（2026-10-06）

- 在役 ARK key 为 **Agent Plan 专用**（视频/对话），不支持 seedream 图片模型
  （/api/plan/v3 404 UnsupportedModel；/api/v3 401）。图片生成要等一枚开了
  seedream 权限的**标准 Ark key** 入 vault（顺带完成旧 key 轮换）。

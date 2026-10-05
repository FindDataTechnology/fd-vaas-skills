# VAAS 生成面托管部署（示例与配方）

> 秘密与真实值全在私有侧（部署节点 compose / 部署编排）。本目录只放结构与示例；
> 决策依据见 VAAS 仓 `openspec/changes/vaas-mcp-platform-onboarding/design.md`
> 与工作区 `docs/adr/0004`、`docs/adr/0005`。

**在役布局（2026-10-06 定）**：实例跑 **cheap-2**（tailnet `100.64.0.16`，compose 在
`/opt/vaas-deploy/`），OpenBAO 留在 cheap-1 registry 栈内并把 8200 加绑 tailnet
`100.64.0.11`——跨机经 tailnet 取凭证，网关代理可达，部署节点不与 registry 抢资源。

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
| `OPENBAO_ADDR` / `OPENBAO_TOKEN` | bootstrap：密钥库地址（跨机用 `http://100.64.0.11:8200`）+ path 受限 policy token |
| `VAAS_PORT` / `VAAS_BIND` | 监听（默认 30950 / 0.0.0.0，宿主侧只绑 tailnet IP） |
| `VAAS_PUBLIC_URL` | 下载签名 URL 的对外基址（`http://100.64.0.16:30950`） |
| `VAAS_PRICING_FILE` | 定价表路径（见 `mcp-server/pricing.example.json`） |
| `VAAS_DOWNLOAD_TTL` / `VAAS_ARTIFACT_TTL_DAYS` / `VAAS_CRED_TTL` | TTL 调参（默认 24h / 30d / 300s） |

## OpenBAO 路径约定（KV v2，mount `secret`）

```
secret/vaas/pool/<line>/volcengine         # 线池凭证 {api_key, base_url?, model?}
secret/vaas/service/default/volcengine     # 服务默认凭证
secret/vaas/service/default/download-hmac  # 下载签名密钥 {value}
```

## OpenBAO 运维（cheap-1 /opt/mcp-gateway-registry）

- **生产模式**（2026-10-06 起）：file backend + `./openbao/data` 卷，**重启后 SEALED**。
- **解封配方**（root-only 文件含 unseal key 与 root token；栈 `.env` 的 OPENBAO_TOKEN
  必须同步为当前 root token）：
  `python3 -c "import json,urllib.request; init=json.load(open('/root/openbao-init-20261006.json')); urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8200/v1/sys/unseal', method='PUT', data=json.dumps({'key': init['unseal_keys_b64'][0]}).encode()))"`
- **VAAS policy token**：`vaas-policy`（仅 `secret/data/vaas/*`），10 年期 orphan
  token；部署密钥在部署节点 `/root/vaas-deploy-secrets.txt`（600）。
- 迁移回滚件：`/root/openbao-snapshot-20261006.json`（dev→file 当日全量导出，回填校验
  3/3 哈希一致）。
- 两个 compose 都改过：`docker-compose.yml` 与 **权威的 `docker-compose.prebuilt.yml`**
  （容器由它创建；重建用 `docker compose -f docker-compose.prebuilt.yml up -d
  --no-deps --force-recreate --no-build <svc>`，不要走默认 yml——它会尝试本地 build）。

## 謙面注册（`/vaas-wanxing` 先行）

1. registry server 注册：proxy_pass_url = `http://100.64.0.16:30950/mcp`；egress 凭据 =
   `VAAS_BEARER_TOKEN` 同值；**`identity_forwarding: true`**（fork 补丁已实现：
   `~/code/mcp-gateway-registry` 分支 `fd-i18n-ui` commit `9e63c091`，2026-10-06，
   7537 tests passed；生产部署须先让 cheap-1 栈滚到含此 commit 的镜像）。
2. Logto group 可见性：仅目标线租户 group 可见。
3. 网关保守限流（成本保险丝）。
4. 冒烟：客户 token 经网关 initialize/tools/list（无 publish 工具）→ 生成 →
   签名下载 → `/usage/summary` 出现该租户记录（凭证来源=pool）。

## 已知口径（2026-10-06）

- 在役 ARK key 为 **Agent Plan 专用**（视频/对话），不支持 seedream 图片模型
  （/api/plan/v3 404 UnsupportedModel；/api/v3 401）。图片生成要等一枚开了
  seedream 权限的**标准 Ark key** 入 vault（顺带完成旧 key 轮换）。

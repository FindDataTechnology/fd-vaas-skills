# VAAS 生成面托管部署（示例与配方）

> 秘密与真实值全在私有侧（cheap-1 compose / 部署编排）。本目录只放结构与示例；
> 决策依据见 VAAS 仓 `openspec/changes/vaas-mcp-platform-onboarding/design.md`
> 与工作区 `docs/adr/0004`、`docs/adr/0005`。

## 布局

- `mcp-server.Dockerfile` — 生成面镜像（不含 Remotion/发布面）
- `docker-compose.vaas.example.yml` — cheap-1 姊妹栈示例（每线一个服务实例）

## 环境变量（部署侧注入，均不入仓）

| 变量 | 用途 |
|---|---|
| `VAAS_HOSTED=1` | 托管模式开关（工具面收窄 + 身份强制 + vault 凭证） |
| `VAAS_LINE` | 线池命名（`wanxing` / `base`） |
| `VAAS_BEARER_TOKEN` | 服务静态 bearer（谦面注册的 egress 凭据同值） |
| `OPENBAO_ADDR` / `OPENBAO_TOKEN` | bootstrap：密钥库地址 + path 受限 policy token |
| `VAAS_PORT` / `VAAS_BIND` | 监听（默认 30950 / 0.0.0.0，仅内网） |
| `VAAS_PUBLIC_URL` | 下载签名 URL 的对外基址 |
| `VAAS_PRICING_FILE` | 定价表路径（见 `mcp-server/pricing.example.json`） |
| `VAAS_DOWNLOAD_TTL` / `VAAS_ARTIFACT_TTL_DAYS` / `VAAS_CRED_TTL` | TTL 调参（默认 24h / 30d / 300s） |

## OpenBAO 路径约定（KV v2，mount `secret`）

```
secret/vaas/pool/<line>/volcengine         # 线池凭证 {api_key, base_url?, model?}
secret/vaas/service/default/volcengine     # 服务默认凭证
secret/vaas/service/default/download-hmac  # 下载签名密钥 {value}
```

## 謙面注册（`/vaas-wanxing` 先行）

1. registry server 注册：proxy_pass_url 指向实例 `/mcp`；egress 凭据 =
   `VAAS_BEARER_TOKEN` 同值；**`identity_forwarding: true`**（fork 补丁，任务组 5）。
2. Logto group 可见性：仅目标线租户 group 可见。
3. 网关保守限流（成本保险丝）。
4. 冒烟：客户 token 经网关 initialize/tools/list（无 publish 工具）→ 生成 →
   签名下载 → `/usage/summary` 出现该租户记录（凭证来源=pool）。

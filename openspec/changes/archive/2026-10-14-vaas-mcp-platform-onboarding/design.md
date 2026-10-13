# Design — VAAS 生成面平台化

## Context

VAAS MCP 是 FastMCP 3.x 单体（stdio），本地 SQLite（`data/vaas.db`，assets/variants/distribution 等 9 表）+ `downloads/` 文件树；生成链为 tools → generators → `scripts/litellm-bridge.py`（子进程，env 驱动、env 优先于 `.env`）→ 火山方舟直连。謙面网关（mcp-gateway-registry fork，cheap-1 compose）默认把入站身份头全部剥离后才转发上游；registry 栈内有 OpenBAO 但为 dev 模式（内存存储，重启丢数据）。2026-10-06 烤问定案 29 条（D1–D29），本 design 是其工程化。

## Goals / Non-Goals

**Goals:**
- 生成面以 HTTP 托管模式上架謙面目录，萬星租户 agent 可经网关调用且互相不可见。
- 模型凭证收口：服务侧只见 bootstrap，真凭证住 OpenBAO，轮换免部署。
- 视频生成异步化，消除超时重试重复扣费。
- 平台侧可出「谁用了多少、按什么凭证、折多少钱」的账。

**Non-Goals:**
- 发布面上架（永不做，见工作区 ADR 0004）。
- BYOK / OBO / 控制台录键页（二期另立 change）。
- claim 动态选池、多实例物理隔离、sub2api 自动结算接线。
- 本地 stdio 单机体验的任何行为变化（发布、Remotion、ppt-master 照旧）。

## Decisions

### D-A 身份：opt-in 头转发，OBO 二期
默认网关不给上游任何调用者身份（`_forward_headers` 剥离 Authorization/Cookie，X-Internal-Token 显式不外发）。一期在 fork 的 `mcp_proxy` 跳加 `identity_forwarding` 注册旗：开启才把已验证 claims 的 `sub` 以 `X-Forwarded-User` 注入。信任模型 = 上游仅内网可达 + 静态 egress bearer + 网关同宿。备选：OBO 提前（Logto audience 应用接线重，一期不值）；不转发（跨租户 prompt 泄漏，不可接受）。二期 OBO 上线后同旗升级为 OBO 模式。

### D-B 凭证：VAAS 侧解析链 + OpenBAO 运行时拉取
解析器是 mcp-server 内一个模块（`credentials.py`）：托管模式下每次生成调用按 线池 → 服务默认 顺序解析（二期在头部插入 请求引用 → BYOK 两级），解析结果以 env 注入本次子进程，bridge 零改动。env 只住 `OPENBAO_ADDR` + 受限 policy token；凭证 TTL 缓存 300s，轮换免部署。备选：部署时 env 明文注入（轮换要重发）、网关侧统一模型网关（当前仅 VAAS 一个消费方，过早）。

### D-C 隔离：单实例 + owner 列逻辑过滤
`assets`/`generation_jobs`/`generation_usage` 加 `owner`；托管模式下内容库读写按 owner 过滤，缺失身份的变更请求 fail-closed 拒绝；`assets_list_common`/`assets_find_logo`/`assets_list_compositions` 为平台公共素材不过滤。备选：每租户一库一实例（v1 运维不成比例）。

### D-D 视频：提交/查询两工具
`generate_video_submit` 走 bridge `wait=false` 拿供应商 task id 落 `generation_jobs` 表即返；`video_job_status` 轮询并在完成时归档产物 + 写 assets。job TTL 24h（过期查不到），产物随 assets 走 30 天 GC。动因：分钟级同步调用在真实 MCP 客户端超时后重试 = 重复扣费。

### D-E 交付：自带签名下载端点
VAAS HTTP 服务加 `GET /download/{asset_id}`（HMAC 签名绑 asset_id+owner+exp，默认 24h，密钥住 vault `service/default/download-hmac`）。生成类工具响应直接带 download_url。不走网关鉴权（省 JWT 往返，签名即凭据）。

### F 计量：VAAS 侧用量表 × 定价文件
每次生成写 `generation_usage`（owner/tool/provider/model/units/unit_type/credential_source）；定价住 `pricing.json`（结构与读取口进代码，初值按火山牌价人工填）；只读端点 `GET /usage/summary` 按 owner×工具聚合折价。sub2api 自动结算接线留二期。

### D-G 注册与部署形态
谦面目录每线一条（`/vaas-wanxing` 试点，`/vaas-base` 待验收）；两实例同宿 cheap-1 compose（与网关、OpenBAO 同机，代理可达 + 内网绑定）；上游鉴权用静态 egress bearer；网关保守限流作成本保险丝。

### D-H 开源边界
解析器/异步/端点代码进公开仓 fd-vaas-skills（逻辑无秘密）；vault 路径、池凭证、bootstrap token、定价初值、注册配置全在私有部署侧。

## Risks / Trade-offs

- **X-Forwarded-User 头依赖内网 + bearer 双保险**：若未来上游暴露公网，头可被伪造 → 二期换 OBO 是既定路线；一期注册旗只对自-owned 服务开。
- **OpenBAO 生产化要动在役密钥后端**：dev 切 file 必须先全量导出现有 KV 再重 seed，窗口期栈服务会短暂拿不到 secret——安排在低峰，先演练回滚。
- **SQLite 单写者**：托管并发写有锁竞争 → v1 量级可承受；WAL 模式 + 短事务缓解，量大再迁 PG。
- **签名下载绕过网关审计**：下载行为只在本服务日志 → 可接受（产物已按 owner 隔离，链接默认 24h 过期）。
- **域内域名/端口**：入口端口为外部服务硬依赖的项目纪律（见 fd-open-data-mcp 先例）——VAAS 是新增入口，不涉及存量端口迁移，但注册后端点即运行时契约。

## Open Questions

无——烤问已收敛（2026-10-06 共识总账 D1–D29）。

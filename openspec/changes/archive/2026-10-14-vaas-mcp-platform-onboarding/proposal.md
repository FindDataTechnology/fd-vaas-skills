# VAAS 生成面平台化上线（謙面目录 × 萬星试点）

## Why

VAAS MCP 目前是本机 stdio 单租户服务：无调用者身份、无租户隔离、模型凭证散在 `.env`、视频生成分钟级同步调用易因客户端超时重试而重复扣费。要把生成面（generate/orchestrate/assets/registry 工具族）作为服务上架謙面目录并供萬星租户 agent 消费，必须补齐多租户归属、凭证解析链、托管传输与计价计量四块底座。发布面（publish_*）不在本 change 范围——见工作区 ADR 0004：发布面永不做多租户托管。

## What Changes

- **多租户归属**：`assets` 表新增 `owner` 列（存量行归服务内部所有），生成与内容库查询按 owner 逻辑隔离；平台品牌素材（公共 assets 查询）不过滤。
- **凭证解析链**：新增凭证解析模块——托管模式下一律经 OpenBAO 解析模型凭证（一期顺序：线池凭证 → 服务默认；env 只住 bootstrap），生成器按次以环境变量注入子进程；**key 永不过工具参数**。本地 stdio 模式保持 `.env` 行为不变。
- **视频异步化**：`generate_video` 拆为 `generate_video_submit`（即返 job id）+ `video_job_status`（轮询）；job 记录入库，TTL 24h，防超时重试重复扣费。
- **托管传输与端点**：MCP 服务器支持 HTTP 托管模式（本地 stdio 不变）；新增带签名过期 URL 的产物下载端点、健康检查、按 owner 汇总的只读计价用量端点。
- **registry fork 补丁**（跨仓，`~/code/mcp-gateway-registry`）：server 注册项新增 opt-in `identity_forwarding` 旗，开启后代理跳把已验证 claims 的 `sub` 以 `X-Forwarded-User` 注入上游请求。
- **OpenBAO 生产化**（部署任务）：registry 栈内 OpenBAO 从 dev 模式切 file backend + 数据卷 + path 受限 policy token；seed 萬星线池凭证与服务默认凭证。
- **部署与注册**：mcp-server 容器化，落 cheap-1 与网关同宿；謙面目录注册 `/vaas-wanxing`（试点）；`/vaas-base` 待萬星试点验收后照方抓药。
- 二期（BYOK + OBO + 控制台录键页）**不在本 change**，另立 change。

## Capabilities

### New Capabilities

- `generation-credentials`: 模型凭证解析链——vault bootstrap、解析优先序、按次注入、轮换与「key 永不过参数」约束。
- `generation-jobs`: 异步生成作业——视频提交/查询工具、job 状态机与 TTL。

### Modified Capabilities

- `material-store`: 新增租户归属与隔离要求（owner 列、查询过滤、存量迁移、公共素材例外）。
- `unified-mcp-interface`: 新增托管 HTTP 传输、签名下载端点、计价用量报表、托管模式身份要求。

# Tasks — vaas-mcp-platform-onboarding

## 1. 多租户归属（material-store）

- [x] 1.1 `assets` 表加 `owner` 列 + 索引，幂等迁移（存量行置服务内部所有者 `service`），`vaas-init-db` 与自举路径都生效；验证：对存量库与全新库各跑一次迁移，`.schema` 含 owner 且重跑无副作用
- [x] 1.2 内容库查询/写入函数加 owner 维度（insert/list/get/update 透传），本地模式 owner 缺省为 `service`；验证：pytest 单测覆盖 insert/list/get 的 owner 透传与缺省
- [x] 1.3 托管模式下 `assets_list`/`assets_get`/`assets_stats` 按 owner 过滤，公共素材三工具（list_common/find_logo/list_compositions）不过滤；验证：单测模拟双租户断言互不可见、公共素材完整
- [x] 1.4 新表 `generation_jobs` 与 `generation_usage`（含 owner 列）纳入建库自举与迁移；验证：全新库首次启动含两新表，旧库迁移幂等

## 2. 凭证解析链（generation-credentials）

- [x] 2.1 新增 `credentials.py`：OpenBAO KV v2 客户端（bootstrap env：`OPENBAO_ADDR`+`OPENBAO_TOKEN`）、路径约定（`vaas/pool/<line>/<provider>`、`vaas/service/default/<provider>`）、TTL 缓存 300s；验证：单测以假 vault HTTP 服务覆盖读路径/缓存/轮换
- [x] 2.2 解析器实现「线池 → 服务默认」两级优先序 + 本地模式直通 `.env`（行为不变）；验证：单测覆盖线池命中、线池缺失回落、本地模式无 vault 依赖
- [x] 2.3 generators（image/tts/video/cover）改为按次从解析器取凭证并以 env 注入子进程，响应/日志/DB 不落凭证明文；验证：单测断言子进程 env 注入正确 + 现有生成路径回归测试通过
- [x] 2.4 工具参数防夹带：生成类工具检测凭证明文形参数并拒绝；验证：单测断言带 key 形参的调用被拒且不入日志

## 3. 视频异步作业（generation-jobs）

- [x] 3.1 `generate_video_submit`：走 bridge `wait=false`，落 `generation_jobs`（owner/status/provider_task_id），即返 job id；验证：单测 mock 供应商受理，断言秒级返回与入库归属
- [x] 3.2 `video_job_status`：轮询供应商、完成时归档产物入 `assets`（带 owner）并返回下载地址；跨租户查询 fail-closed；验证：单测覆盖 运行中/成功/失败/跨租户 四态
- [x] 3.3 job TTL 24h（过期置 expired 且不可查，产物不受影响）+ 启动时清扫僵尸 job；验证：单测用注入时钟覆盖过期语义
- [x] 3.4 托管模式工具面收窄：`publish_*` 不注册、旧别名不注册，本地 stdio 全量保留；验证：托管模式 tools/list 不含 publish，本地模式含

## 4. 托管传输与端点（unified-mcp-interface）

- [x] 4.1 入口支持 `VAAS_TRANSPORT=http|stdio`（默认 stdio），HTTP 模式绑定内网地址 + `/health`；验证：本地起 HTTP 实例 curl /health 200，stdio 默认行为不变
- [x] 4.2 托管模式身份中间件：校验服务凭证（静态 bearer）+ 读取 `X-Forwarded-User`；变更类调用缺身份 fail-closed，registry_* 只读放行；验证：单测/curl 覆盖 缺身份 403、带身份成功、无凭证 401
- [x] 4.3 `GET /download/{asset_id}`：HMAC 签名（asset_id+owner+exp，密钥自 vault `service/default/download-hmac`），生成类工具响应附带 download_url；验证：单测覆盖 有效/过期/篡改/跨租户 四态 + 端到端取回文件内容一致
- [x] 4.4 用量记录（每次生成写 `generation_usage`）+ `GET /usage/summary`（服务凭证保护，按 owner×工具聚合×`pricing.json` 折价）；验证：单测断言 聚合口径、凭证来源拆分、定价变更即时生效
- [x] 4.5 产物 30 天保留 + 每周 GC（只删过期产物文件与资产，job 已过期不受影响）；验证：单测注入时钟验证 GC 只删过期项

## 5. registry fork 身份转发补丁（~/code/mcp-gateway-registry）

- [x] 5.1 server 注册 schema 加 opt-in `identity_forwarding` 布尔旗（默认 false）；验证：该仓 pytest 注册项 schema 测试
- [x] 5.2 `mcp_proxy` 跳：旗开且 claims 已验证时注入 `X-Forwarded-User: <sub>`，旗关行为不变；验证：该仓 pytest 覆盖 旗开注入/旗关剥离/未验证不注入
- [x] 5.3 补丁过该仓全量单测并出 diff 提交（私有侧部署编排引用该 commit）；验证：pytest 全绿 + commit hash 记录于部署说明

## 6. OpenBAO 生产化与凭证 seed（生产变更，低峰执行）

- [x] 6.1 cheap-1 上导出在役 KV 全量快照（dev 模式内存数据），演练回滚路径；验证：快照可完整列出全部既有路径
- [x] 6.2 切 file backend + 数据卷 + 重启，重 seed 快照并验证栈服务读回；验证：registry 栈健康检查通过 + 抽查 3 个既有 secret 读回一致
- [x] 6.3 签发 VAAS 专用 policy token（仅 `vaas/*` 路径）；验证：该 token 可读写 vaas/*、读不到其他路径
- [x] 6.4 seed 萬星线池凭证（新轮换的 ARK key，不回 `.env`）与服务默认凭证（含 download-hmac）；验证：经 policy token 读到且旧 key 已吊销失效

## 7. 容器化与部署（萬星试点）

- [x] 7.1 mcp-server Dockerfile（不含 Remotion 重依赖，生成面镜像）+ TCR 通道构建；验证：镜像在 cheap-1 可拉起 /health 200
- [x] 7.2 compose 服务（`vaas-wanxing`）：bootstrap env、内网端口、数据卷（vaas.db + downloads）；验证：容器启动自举建库、日志无凭证明文
- [x] 7.3 謙面注册 `/vaas-wanxing`：proxy_pass_url、静态 egress bearer、`identity_forwarding` 旗开、Logto group 可见性、保守限流；验证：经网关带客户 token initialize/tools/list 成功且不含 publish 工具
- [x] 7.4 端到端冒烟：经网关生成图片 → 返回下载地址 → 取回文件 → usage/summary 出现该租户记录且凭证来源=线池；验证：冒烟记录归档
- [ ] 7.5 `/vaas-base` 部署任务（**待萬星试点验收后执行**）：照 7.2–7.4 配方换线池路径与注册项；验证：同 7.4 冒烟

## 8. 跨切验收

- [x] 8.1 本地 stdio 全量回归：发布面/Remotion/ppt-master 链路行为与本 change 前一致；验证：既有测试全绿 + 一次真实封面生成
- [ ] 8.2 `openspec validate vaas-mcp-platform-onboarding --strict` 通过并归档；验证：validate 无 error

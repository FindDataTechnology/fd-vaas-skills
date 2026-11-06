# VAAS 外依赖债务台账（debt ledger）

> 契约出处：`openspec/specs/release-verification/`（「外依赖债务仓内台账」requirement，
> 随 change `add-ci-and-provisioning` 归档后入主 spec）。凡因跨仓/外部环境无法在单个
> change 内销账的债务，记在这里；**MUST NOT 以会话记忆作为唯一追踪载体**。
> 每条含：债务描述 / 挂靠 change / 销账证据标准 / 责任线。

| # | 债务 | 挂靠 | 销账证据标准 | 责任线 | 状态 |
|---|---|---|---|---|---|
| DEBT-CI-01 | 托管 CI 执行器不可用（FindDataTechnology 账号 GHA billing 停摆前科，11-06）；`.github/workflows/ci.yml` 已就位但未获得一次托管绿跑 | `add-ci-and-provisioning` W1.3 | 恢复后任意 push 的 run：test 全绿 + 注入红时 build-image 被 skip 的 run 链接 | VAAS 仓（运维侧账号） | 🟡 **首跑已触发（run 42212771183，push 3e3cb15）**：test 7 红（runner 缺 ffmpeg 4 项 + `_read_script` 把长中文内联稿当路径、Linux ENAMETOOLONG 3 项）、build-image 按 `needs` 正确 skip（注入门已实证）。两处已修（ci.yml 装系统 ffmpeg / `_read_script` 保守形状判定 + 回归测试），等第二次 push 的绿跑销账；本地等价闸 `scripts/ci-local.sh` 在岗 |
| DEBT-IMGROLL-01 | 单源 Dockerfile 的新镜像重建与上产（build-pool/快照通道，需推送 origin + 部署节点） | `add-ci-and-provisioning` W2.3 → `deliver-hosted-surface` W1/W5 合并滚 | 现网 `docker inspect` sha + `scripts/probe_hosted_surface.py` 全绿留证 | VAAS 部署（词元线节点） | ✅ **销账 2026-11-06**：现网镜像 `ccr.ccs.tencentyun.com/yizuo/vaas-mcp:sha-wave6-202611061854`（增量构建共享渲染底座层，磁盘 5.9G 余量约束下的等价格；canonical 单源 Dockerfile 与根 shim cmp IDENTICAL）；probe 6/6 PASS（17 工具面 + publish 拒 + lane health 10 块）+ 长文 voice E2E 4 段全绿。GHA 快照通道首跑另挂 DEBT-CI-01 |
| DEBT-HEALTH-01 | 托管实例 unhealthy→自愈实机演示（本机无 docker，runbook/脚本已就位） | `add-ci-and-provisioning` W4.3 | 部署节点时间线：kill 主进程→restart 拉起→/health 回绿 + health-watch 触发记录 | VAAS 部署 | ✅ **销账 2026-11-06**：compose 加 healthcheck（现网 `docker inspect`=healthy）；kill PID1 → T+5s starting restarts=1 → T+10s healthy + /health=200；health-watch.sh 已装 root crontab `*/5`，阈值分支仿真（count=1 wait → count=2 RESTART → healthy clear）通过 |
| DEBT-LANE-9-01 | 词元图像/视频车道 down：组9 唯一上游 acct 40（openai-next）被 403 封禁 → router 503 | `deliver-hosted-surface` W4.1 | sub2api 侧解封/换账号后 generate_image + generate_video_submit 实调 E2E，车道 health 翻 active | 萬星·词元（sub2api） | 🔴 现网 down，发现面标注先行 |
| DEBT-W75-01 | 生成面凭证池（W7.5 遗留，原追踪载体=会话记忆，本条即迁移收口）：hosted 凭证 vault 链路可用性与 key 轮换 | `2026-11-05-add-presentation-plane`（已归档外挂账）→ `deliver-hosted-surface` | hosted 实例经 OpenBAO 取到现役 key + 生成 E2E 证据；轮换记录入 secrets 侧 | VAAS + 谦面密钥运维 | 🟡 voice 腿已实证（11-05），image/video 腿并入 DEBT-LANE-9-01 |
| DEBT-WIN-01 | Windows 节点（<WIN_NODE_IP>）发布闸真机复验：确认哨兵/启动器改造的实机证据 | `enforce-publish-confirmation-gate` W5.3 | 真机扫码登录→带闸 dry-run→确认发布全流程记录 | VAAS + windows-admin | 🟡 本地/仿真验证先行 |
| DEBT-RELOGIN-01 | 发布面登录态过期批次：4 视频平台 cookie 临近 30 天门限、`.docs_state.json` 检查记录过期 | `enforce-publish-confirmation-gate` W6.1 | 重登重验后 login-manager 面板全绿 + registry lastVerified 刷新 | VAAS 本机运维 | 🟡 真发布前强制前置 |

## 已知坑（探针/工具类）

- **stdio JSON-RPC 拉活/列表探针必须增量读写**：一次性 pipe 喂 `initialize+initialized+tools/list`
  再关 stdin，server 在 EOF 后只回 initialize（fastmcp stdio 行为），tools/list 无声丢失。
  doctor.mjs 的拉活探针只验 initialize（不受影响）；全量列表探针脚本必须 Popen 逐行读、收到
  id=2 再关（11-06 实证，23 工具全面在列）。

## 使用纪律

- 归档任何 change 前：其中标记「外依赖/挂账」的条目必须已在本表登记（描述+挂靠+销账标准）。
- 每波收口时复核本表：能销的销（附证据链接/日期），新债进表。
- 本表只记坐标级事实，不落密钥/账号真值（公开仓纪律，见 `opensource-readiness`）。

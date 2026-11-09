# VAAS 外依赖债务台账（debt ledger）

> 契约出处：`openspec/specs/release-verification/`（「外依赖债务仓内台账」requirement，
> 随 change `add-ci-and-provisioning` 归档后入主 spec）。凡因跨仓/外部环境无法在单个
> change 内销账的债务，记在这里；**MUST NOT 以会话记忆作为唯一追踪载体**。
> 每条含：债务描述 / 挂靠 change / 销账证据标准 / 责任线。

| # | 债务 | 挂靠 | 销账证据标准 | 责任线 | 状态 |
|---|---|---|---|---|---|
| DEBT-CI-01 | 托管 CI 执行器不可用（FindDataTechnology 账号 GHA billing 停摆前科，11-06）；`.github/workflows/ci.yml` 已就位但未获得一次托管绿跑 | `add-ci-and-provisioning` W1.3 | 恢复后任意 push 的 run：test 全绿 + 注入红时 build-image 被 skip 的 run 链接 | VAAS 仓（运维侧账号） | ✅ **销账 2026-11-06（run 42223375665，push 5baff15：test ✅ + build-image ✅ 全绿）**。托管化路程四跑实弹：①run 42212771183 test 7 红（runner 缺 ffmpeg + `_read_script` 把长中文内联稿当路径 Linux ENAMETOOLONG），build-image 按 needs 正确 skip（注入门实证）；②run 42213979030 余 3 红（node 段 confirm_gate 缺 patchright 导入 + 并发会话测试硬编码本机 captions 路径）；③run 42220599370 test ✅，build-image 首次真跑暴露 Dockerfile ENV 续行符吞注释；④全绿。遗留一件：并发会话 `tests/tts-synthetic-captions.test.mjs:82` require 本机绝对路径 `@remotion/captions`，CI 以 runner 垫路兜底（ci.yml 注释在案），治本=测试改仓内相对路径+缺依赖时 skip，归 tts.js 归属批次。**CI 基建两课（四跑后钉死）**：①ubuntu-26 runner 的 apt 拉 ffmpeg 全家桶慢到撞超时 → 改 BtbN GitHub CDN 静态构建；②并发会话测试硬编码本机路径在 CI 永不可达 → runner 垫路兜底只是兜底，治本归归属批次 |
| DEBT-IMGROLL-01 | 单源 Dockerfile 的新镜像重建与上产（build-pool/快照通道，需推送 origin + 部署节点） | `add-ci-and-provisioning` W2.3 → `deliver-hosted-surface` W1/W5 合并滚 | 现网 `docker inspect` sha + `scripts/probe_hosted_surface.py` 全绿留证 | VAAS 部署（词元线节点） | ✅ **销账 2026-11-06**：现网镜像 `ccr.ccs.tencentyun.com/yizuo/vaas-mcp:sha-wave6-202611061854`（增量构建共享渲染底座层，磁盘 5.9G 余量约束下的等价格；canonical 单源 Dockerfile 与根 shim cmp IDENTICAL）；probe 6/6 PASS（17 工具面 + publish 拒 + lane health 10 块）+ 长文 voice E2E 4 段全绿。GHA 快照通道首跑另挂 DEBT-CI-01 |
| DEBT-HEALTH-01 | 托管实例 unhealthy→自愈实机演示（本机无 docker，runbook/脚本已就位） | `add-ci-and-provisioning` W4.3 | 部署节点时间线：kill 主进程→restart 拉起→/health 回绿 + health-watch 触发记录 | VAAS 部署 | ✅ **销账 2026-11-06**：compose 加 healthcheck（现网 `docker inspect`=healthy）；kill PID1 → T+5s starting restarts=1 → T+10s healthy + /health=200；health-watch.sh 已装 root crontab `*/5`，阈值分支仿真（count=1 wait → count=2 RESTART → healthy clear）通过 |
| DEBT-LANE-9-01 | 词元图像/视频车道 down：组9 唯一上游 acct 40（openai-next）被 403 封禁 → router 503 | `deliver-hosted-surface` W4.1 | sub2api 侧解封/换账号后 generate_image + generate_video_submit 实调 E2E，车道 health 翻 active | 萬星·词元（sub2api） | 🔴 现网 down，发现面标注先行。**11-06 深查（admin JWT + 实调 + usage_logs 取证）**：封锁已从硬 403 演变为**软 200-HTML**——images/generations 调度到 acct 40 返回 HTTP 200 + openai-next SPA 页面 + 计费 \$0.134/次零图片（usage_logs 277386-277389 三单取证）；video（ark-shape /v1/contents/generations/tasks）401 Invalid token。结论：上游账号本体被 openai-next 站点级封锁（browser signature），agent 侧无解，需用户在上游 openai-next 恢复/替换账号（1253774197@qq.com 名下）；替换后 VAAS lane_health.json 翻 active 即销账 |
| DEBT-RENDER-CAP-01 | 渲染面容量不足：cheap-2 仅 3.9G 内存（渲染面 doctor `Memory: 3.0 GB total · 0.5 GB available` = FAIL），渲染面单 worker（`VAAS_RENDER_MAX_CONCURRENCY=1`）；实测 12.5s 成片耗时 **287s**；渲染面上线初期 10/26 作业失败（早于 `sha-subtitle1`/data-s0 修复，现网无 OOM 记录） | `adopt-hyperframes-video-renderer`（已归档，11-09 上产） | 扩容或迁渲染面到更大内存节点后：doctor Memory=OK + 同片耗时显著下降 + 连续 20 作业零失败 | VAAS 部署（cheap-2） | 🟡 功能可用，性能/稳定性受限。**11-09 二次实测（现网 sha-layout3）**：12.2s/5 场景成片 1.04MB、682 kbps，单次实测落在 240s 内（另一次并发双跑曾撞 600s 渲染超时——两路同时打单 worker 所致，串行即过）；同片 PNG 序列逐帧 cover 19-22%、帧 YAVG 42.8-46.5（纯黑≈16），无近黑帧 |
| DEBT-RENDER-ENC-01 | 深色成片低码率下的压缩残影/色带：1080x1920、12.2s 仅 **682 kbps**（x264 CRF16 对大面积平坦深色本就压得低），深色渐变处可见前帧文字残影与轻微色带；渲染面只透传 `-q quality`，无 `--crf` / `--max-bitrate` 入口 | `adopt-hyperframes-video-renderer`（已归档） | 渲染面开放 crf/bitrate 透传（或对深色内容改用 `-q delivery`）后，同片重出：码率显著上升、残影消失（逐帧比对同一时间点无前帧文字） | VAAS 渲染面 | 🟡 待办。判据提示：本地 PNG 序列同帧干净、只有成片有残影 → 属编码侧，非版式侧 |
| DEBT-XLEDGER-01 | 对外台账剩余的**活体设施**批次（sync-external-ledgers 归档时转挂账）：①registry 服务端 metadata/描述 PATCH（W1.4，需 registry 管理面）②四技能包重传触发 plaza 再物化（W4.2）③plaza `mcp-vaas-wanxing.md` 物料重生成（W4.3）④万星发布套件 v6 的 17 工具声明过 pack 闸发版 + 发布后门/integrity 复核（W5.1/W5.2） | `sync-external-ledgers`（已归档，2026-11-09） | 每项执行后回读实证：registry 描述与 17 面一致、plaza 物料计数与文案跟上、pack 发版 400→201 且 commercial_tools/integrity 无漂移 | VAAS + 谦面（registry/plaza/市场） | 🟡 仓内可作部分已全部完成（注释 17 面/ catalog 描述 / MCP-REGISTRY sha 登记 / 试用面 / 坐标脱敏）；本条目只余需活体管理面的四项。**11-09 对账实况**（`scripts/reconcile_mcp_registry.py`）：29 条、实质漂移 13 条；`/vaas-wanxing` 工具数 **17/17 一致**（not-in-k8s，镜像 sha 已补登）；**registry 管理面不可达**（metadata 检查「kubectl/exec/token 任一失败」、Mongo DOCUMENTDB_* 不可达、脊柱投影 token 未配）→ W1.4 metadata PATCH 无法本批执行；其余漂移（`/wire-ops-mcp`、`/wire-build-mcp`、`/lex-ops-mcp`、`/fd-paper-trading`、`/fd-erp-ledger-mcp` 8→20、三条 `/fd-wire-cell-*` 不可达）**属其他产品线**，不在 VAAS 收口范围 |
| DEBT-W75-01 | 生成面凭证池（W7.5 遗留，原追踪载体=会话记忆，本条即迁移收口）：hosted 凭证 vault 链路可用性与 key 轮换 | `2026-11-05-add-presentation-plane`（已归档外挂账）→ `deliver-hosted-surface` | hosted 实例经 OpenBAO 取到现役 key + 生成 E2E 证据；轮换记录入 secrets 侧 | VAAS + 谦面密钥运维 | ✅ **销账 2026-11-07**：vault 链路全实证——cheap-2 本机 OpenBAO（file backend+自解封）→ pool/wanxing/{tts,image,video} 三池 credential_source=pool 读取成功（wave6 voice E2E 全链）；tts 池 key 健康（多次长文调用）；image/video 池 key 本体有效（上游封锁致不可用，归 DEBT-LANE-9-01 追踪，非凭证池缺陷）。轮换记录归 secrets 侧台账 |
| DEBT-WIN-01 | Windows 节点（<WIN_NODE_IP>）发布闸真机复验：确认哨兵/启动器改造的实机证据 | `enforce-publish-confirmation-gate` W5.3 | 真机扫码登录→带闸 dry-run→确认发布全流程记录 | VAAS + windows-admin | 🟡 本地/仿真验证先行 |
| DEBT-RELOGIN-01 | 发布面登录态过期批次：4 视频平台 cookie 临近 30 天门限、`.docs_state.json` 检查记录过期 | `enforce-publish-confirmation-gate` W6.1 | 重登重验后 login-manager 面板全绿 + registry lastVerified 刷新 | VAAS 本机运维 | 🟡 真发布前强制前置。**11-07 静态核实（免浏览器）**：视频侧 douyin/tencent/xiaohongshu 三份 account.json 均 23.8 天（⚠️ 距 30 天门限 ~6 天）、kuaishou_creator.json 23.8 天；**weibo/youtube/ks 三目录为空=从未落 cookie**；bilibili 走 biliup 本机态（~/.biliup 未发现）。图文 `.docs_state.json` 23.8 天前更新，其中 zhihu/weixin_mp/weibo/baijiahao/xueqiu last_verified=2026-08-12（~87 天）、toutiao=2026-10-14。**扫码清单（一次性做完）**：①视频重登 douyin+tencent(视频号)+xiaohongshu+kuaishou（4 份都在门限内）②视频首登 weibo+youtube ③图文复核 zhihu/weixin_mp/weibo/baijiahao/xueqiu 选择器+重验戳 ④完成后跑 login-manager 面板对全绿 |

## 已知坑（探针/工具类）

- **stdio JSON-RPC 拉活/列表探针必须增量读写**：一次性 pipe 喂 `initialize+initialized+tools/list`
  再关 stdin，server 在 EOF 后只回 initialize（fastmcp stdio 行为），tools/list 无声丢失。
  doctor.mjs 的拉活探针只验 initialize（不受影响）；全量列表探针脚本必须 Popen 逐行读、收到
  id=2 再关（11-06 实证，23 工具全面在列）。

## 使用纪律

- 归档任何 change 前：其中标记「外依赖/挂账」的条目必须已在本表登记（描述+挂靠+销账标准）。
- 每波收口时复核本表：能销的销（附证据链接/日期），新债进表。
- 本表只记坐标级事实，不落密钥/账号真值（公开仓纪律，见 `opensource-readiness`）。

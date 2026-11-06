# Tasks: add-ci-and-provisioning

## tasks

### W1 测试闸落地

- [x] W1.1 新增 `.github/workflows/ci.yml`：jobs = pytest(mcp-server/tests) + node:test(tests/、_shared/publish) + registry 一致性 + Dockerfile 漂移检查；build-push job `needs` 测试闸（红即 skip）
- [x] W1.2 新增 `scripts/ci-local.sh`：一条命令跑同一套四项检查，输出与 CI 语义一致；README/AGENTS.md 写明「合并前置=此脚本绿」
- [x] W1.3 拦截语义实证：注入一个故意红的用例验证 build 被挡（本地实证留证；GHA billing 停摆期间以 ci-local 实证为准，workflow 恢复后任意 push 补跑销账——记入 W5 债务台账）
  - 实证记录（11-06）：`mcp-server/tests/test_ci_red_probe.py` 故意红 → ci-local ❌ pytest + 整体 🔴；删除后回绿。workflow 已就位待执行器恢复（DEBT-CI-01）

### W2 镜像单源

- [x] W2.1 `deploy/mcp-server.Dockerfile` 为唯一 canonical；根 `Dockerfile` 删除或由 `scripts/gen-root-dockerfile.sh` 从 canonical 机械生成（build-pool 约定保留时选生成方案）；本次先把 W7.6 的 types COPY 漂移一并对平
  - 实证记录：生成后 `cmp -s` IDENTICAL（根 shim 缺 types COPY 的历史漂移即此消）
- [x] W2.2 漂移检查实现（diff 根 vs 生成物/canonical），挂入 W1 测试闸
- [x] W2.3 2026-11-06 部署节点实证：现役镜像已含 ffmpeg/ffprobe/chromium/CJK 底座与 mutagen/playwright（canonical 单源 Dockerfile 与根 shim cmp IDENTICAL）；受节点 5.9G 余量约束，采用 FROM 现役镜像的增量构建（清树 COPY 新源码 + 依赖复核 deps-ok），镜像 `sha-wave6-202611061854` 已滚现网，探针 6/6 不回退。build-pool 快照通道的 GHA 首跑仍挂 DEBT-CI-01

### W3 安装与自检覆盖 mcp 平面

- [x] W3.1 install.sh：mcp-server 依赖安装步骤（venv/uv 口径与 README 对齐）+ `.mcp.json` 模板生成/复制指引 + 汇总行更新
- [x] W3.2 doctor.mjs：新增 `import mcp_server` + stdio 拉起探活项（❌ 级）；技能链接清单补 `fd-vaas-login`（与 spec 既有条款对平）；ffmpeg 缺失改 ❌ 非零退出；uv/patchright 检查扩到全平台（补 spec 既有义务）
  - 顺手修：技能链接检查「缺项字符串当 ✅ 显示」的旧语义 bug（缺项现在真报 ⚠️）；stdio 拉活注意 EOF 竞态（配方入 docs/debt-ledger.md 坑节）
- [x] W3.3 fresh-clone 验证：干净目录跑 install.sh → doctor 全 ✅ → MCP 客户端列 23 工具留证
  - 实证记录（11-06）：工作树 rsync 模拟全新克隆 → install.sh exit 0、.mcp.json 生成、doctor 核心项全 ✅；stdio 增量探针 tools/list = 23 全名（publish 面在列，宿主形态即全量）；注：`git clone` HEAD 不含未提交改动，克隆法测新脚本无效，须 rsync 工作树或先提交
- [x] W3.4 README.md:173/README.en.md:173 断链修复（sync-upstream.sh 路径真实化或文案改写），「生成后端配置」小节复核

### W4 部署存活与恢复

- [x] W4.1 `docker-compose.vaas.example.yml` 加 healthcheck（进程存活 + `/health` 探活，实测 main.py custom_route 即 /health），restart 策略复核 + `deploy/health-watch.sh`（unhealthy→阈值重启，cron 挂法注释内）
  - 注：部署节点权威 compose 为 prebuilt（不在仓内），healthcheck 随下次滚版一并打（DEBT-IMGROLL-01 同批）
- [x] W4.2 OpenBAO SEALED 解封 runbook 入仓（命令级、路径与现行部署一致），deploy README 挂链；单实例单节点风险 + 备份责任在 deploy README 明示
- [x] W4.3 2026-11-06 部署节点实证：compose 加 healthcheck（start_period 20s）后 `docker inspect` = healthy；kill PID1 → T+5s running/starting restarts=1 → T+10s healthy + /health=200（时间线留证）；health-watch.sh 已装 root crontab `*/5 * * * *`，阈值分支仿真 count=1 wait → count=2 RESTART → healthy clear 通过

### W5 债务台账与仓库卫生

- [x] W5.1 新增 `docs/debt-ledger.md`：W7.5 凭证池、acct 40 封禁（deliver-hosted-surface W4）、GHA billing（W1.3）、Windows 真机复验（enforce-publish W5.3）入账，另收 IMGROLL/HEALTH/RELOGIN（描述/挂靠 change/销账证据标准/责任线）；AGENTS+deploy README 挂链
- [x] W5.2 `docs-e2e-evidence/` 迁出公开仓：git mv 至本 change 目录 `evidence/docs-e2e-evidence/`（随归档入 archive/）；本地根杂物为 gitignored 本机文件（vaas.db.bak/demand.md/.deepeval），不入公开仓、留本机待用户清理决定（删除生产库备份文件不应由本 change 代裁）
- [x] W5.3 ci-local 四检全绿 + 六 change strict 全绿；归档统一延后至 C1/C2 补证后同批（见 W2.3/W4.3 实证）
  - 待办：闸绿/strict/勾已在会话内完成；**归档等 W2.3/W4.3 上产补证同批收**（与 deliver-hosted-surface 一次滚版一次归档，避免镜像连滚）

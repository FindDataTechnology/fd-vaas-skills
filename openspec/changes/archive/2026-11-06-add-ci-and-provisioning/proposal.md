# Proposal: add-ci-and-provisioning

## Why

VAAS 的工程基建与产品承诺错位：仓里已有 337 个 pytest 函数 + node 单测，却**零 CI**（无 `.github/`，远端同）——测试只能靠人肉想起来才跑；`add-typed-video-html-renderer` 这种高风险重构全靠「213 测试绿」的口头声明。fresh-user 路径断在半路：`install.sh` 与 `doctor.mjs` 从不装/验 mcp-server 平面（pip 依赖、`.mcp.json`），本地用户按 README 装完后 23 工具面里有 12 个（stdio 全量）根本起不来。镜像双写漂移已实际发生：根 shim 缺 canonical 的 types COPY（W7.6 修的正是它），build-pool 通道从仓根构建就会出残废镜像。托管实例是单容器单节点、compose 无 healthcheck，OpenBAO 重启后 SEALED 靠人肉一行命令解封；W7.5 凭证池债务的追踪载体是「会话记忆」——台账纪律最脆的一环。把闸、装、探、账四件事补上，后面的 waves 才跑在安全网内。

## What Changes

- **NEW** `release-verification` capability：CI 闸（pytest 全量 + node:test + registry 一致性 + Dockerfile 漂移检查，任一红则镜像构建跳过）；GHA 额度停摆风险下同时提供等价本地入口脚本；单源 Dockerfile（根 shim 删除或由 canonical 生成，禁双写）；托管实例 healthcheck 与自愈重启；跨仓外依赖债务在仓内台账文件跟踪（替代会话记忆）。
- **MODIFIED** `opensource-readiness`「一键安装与自检」：install.sh/doctor SHALL 覆盖 mcp-server 平面（Python 依赖安装或显式引导、`.mcp.json` 模板生成、`import mcp_server` 自检项）；顺带把既有 spec 违约项修齐（doctor 技能清单含 `fd-vaas-login`、ffmpeg 缺失 ❌ 非零退出、patchright 全平台检查）。
- 仓库卫生顺手收：`docs-e2e-evidence/` 证据目录迁出公开仓（入 change 归档目录）、README:173 指向不存在的 `scripts/sync-upstream.sh` 修复、deploy README 磁盘余量与外依赖检查单。
- 不改测试内容本身（harden-creation-chain 负责加测试）、不改发布逻辑（enforce-publish-confirmation-gate 负责）。

## Capabilities

### New Capabilities

- `release-verification`: 变更验收与安全网契约——测试闸 CI/等价本地入口、镜像单源、托管实例存活自证、外依赖债务仓内台账。

### Modified Capabilities

- `opensource-readiness`: 修订「一键安装与自检」——安装/自检覆盖 mcp-server 平面；既有 ❌/清单/跨平台条款落地补齐。

## Impact

- **代码/配置**：`.github/workflows/`（新增）、`scripts/ci-local.sh`（新增）、`Dockerfile`（改生成或删除，`deploy/mcp-server.Dockerfile` 为唯一真源）、`install.sh`、`scripts/doctor.mjs`、`deploy/docker-compose.vaas.example.yml`（healthcheck）、`.gitignore`（docs-e2e-evidence 去向调整）、`README.md`/`README.en.md`（断链与安装小节）、`docs/debt-ledger.md`（新增）。
- **外依赖**：GHA 账号 billing 停摆中（scs001/FindDataTechnology 双账号前科 11-06）——workflow 就位即写，恢复后任意 push 补跑为证；期间以 ci-local.sh 为闸。挂账入债务台账。
- **验收**：本地跑 `scripts/ci-local.sh` 全绿留证；故意注入一个红测试验证拦截语义；fresh-clone 虚拟机/干净目录走一遍 install.sh 后 `import mcp_server` + doctor 全 ✅。

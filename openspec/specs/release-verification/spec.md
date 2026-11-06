# release-verification Specification

## Purpose
VAAS 变更验收与安全网的契约：测试闸对每次变更生效、托管镜像单源不漂移、托管实例存活可自证、跨仓外依赖债务在仓内台账可查不靠人记。

## Requirements

### Requirement: 变更测试闸

仓库 SHALL 在每次 push/PR 上运行统一测试闸：mcp-server pytest 全量、`node --test`（tests/ 与 `_shared/publish/`）、registry 一致性检查、Dockerfile 单源漂移检查；任一项红 MUST 阻断镜像构建产物发布。托管平台执行器不可用期间，仓库 SHALL 提供语义等价的本地入口（一条命令跑同一套检查），并以该入口的绿作为合并前置。闸的存在与运行方法 MUST 写入 README/AGENTS 使贡献者可发现。

#### Scenario: 红测试拦截出片

- **WHEN** 一次提交使任一 pytest 用例失败
- **THEN** 测试闸红且镜像构建步骤不执行
- **AND** 失败项与被测行为可定位（非整体超时假象）

#### Scenario: 执行器不可用时本地等价闸兜底

- **WHEN** 托管 CI 执行器因计费/配额停摆
- **THEN** 贡献者运行本地入口脚本得到同一套检查结论
- **AND** 停摆与兜底状态记入债务台账，执行器恢复后补跑留证

### Requirement: 镜像构建单源

托管镜像的 Dockerfile MUST 只有一份真源（canonical）：镜像根 shim 要么删除，要么由 canonical 机械生成，MUST NOT 人工双写；构建通道（含仓根约定）与 canonical 内容不一致时测试闸 MUST 失败。

#### Scenario: 漂移被拦

- **WHEN** 有人只改 canonical 而镜像根构建上下文缺同一条 COPY
- **THEN** 漂移检查失败并列出差集
- **AND** 不可能产出缺元数据的 hosted 镜像而不被发现

### Requirement: 托管实例存活自证

托管部署 SHALL 声明容器健康检查（存活 + 服务面探活），unhealthy 时由编排层自动重启；密钥库重启后 SEALED 一类需要人工介入的恢复路径 SHALL 有仓内 runbook（命令级、可复制执行），runbook 与部署文档 MUST 一致。单实例单节点风险 SHALL 在部署文档明示（数据备份责任归属）。

#### Scenario: 僵死自愈

- **WHEN** 托管容器内服务面僵死（进程在而端口不应答）
- **THEN** 健康检查失败触发容器重启，探活恢复
- **AND** 事件可通过部署侧日志定位

#### Scenario: 解封有章可循

- **WHEN** 部署节点重启、密钥库进入 SEALED
- **THEN** 运维按仓内 runbook 步骤完成解封，无需依赖会话记忆或口口相传
- **AND** runbook 标注的最小权限与凭据文件位置与现行部署一致

### Requirement: 外依赖债务仓内台账

跨仓/外部环境导致无法在单个 change 内销账的债务（上游账号封禁、CI 计费停摆、他节点真机复验等）SHALL 记入仓内债务台账文件：每条含债务描述、挂靠 change、销账证据标准与责任线；MUST NOT 以会话记忆作为唯一追踪载体。台账文件 MUST 可被 openspec validate 之外的常规检索发现（README/deploy 文档挂链）。

#### Scenario: 债务可盘可追

- **WHEN** 任一 change 归档时存在未销外依赖项
- **THEN** 债务台账新增条目且归档注记指向该条目
- **AND** 后续任意会话可从仓内读出当前全部未销账项

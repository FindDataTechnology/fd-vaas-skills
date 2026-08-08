# opensource-readiness Specification

## Purpose
TBD - created by archiving change opensource-readiness. Update Purpose after archive.
## Requirements
### Requirement: 渲染源码公开可用

公开仓库 SHALL 包含渲染一支口播视频所需的全部 Remotion 源码（`remotion-app/src/`、构建配置、渲染必需的品牌资产）。运行时产物（node_modules、out、生成的配音/字幕文件）MUST NOT 被跟踪。任何敏感信息（密钥、内部 URL、个人路径）MUST NOT 进入公开历史。

#### Scenario: 新用户克隆后可渲染

- **WHEN** 新用户 clone 公开仓库并完成依赖安装
- **THEN** `remotion-app/src/` 中 `VoiceoverVideo` composition 存在且可渲染
- **AND** 无需从 references 手工重建任何组件

#### Scenario: 运行时产物不入库

- **WHEN** 用户本地生成了配音 mp3、captions json、渲染产物
- **THEN** `git status` 不将这些文件列为变更
- **AND** `vaas.db`、`.profiles/`、`downloads/`、`*.bak` 均保持忽略

### Requirement: 一键安装与自检

仓库 SHALL 提供 `install.sh`（macOS/Linux）与 `scripts/doctor.mjs`（跨平台）。install.sh SHALL 完成依赖检查、remotion-app 依赖安装、`.env` 初始化、技能链接创建，并在结尾运行 doctor。doctor SHALL 按 ✅/⚠️/❌ 三级报告，❌ 项 MUST 附带修复命令，存在 ❌ 时退出码 MUST 非 0。doctor MUST NOT 打印任何密钥值。

#### Scenario: 缺依赖时给出可行动报告

- **WHEN** 一台缺 ffmpeg 的机器运行 `node scripts/doctor.mjs`
- **THEN** 报告中 ffmpeg 项为 ❌ 并附安装命令
- **AND** 退出码非 0
- **AND** 补齐后重跑全部 ✅，退出码为 0

#### Scenario: Windows 技能可用

- **WHEN** Windows 用户 clone 仓库并运行安装/自检流程
- **THEN** `.claude/skills/` 下技能以目录复制形式存在（而非断掉的软链接）
- **AND** `/fd-vaas-video-creator` 等命令可被 Claude Code 发现

### Requirement: 快速上手路径

README SHALL 在顶部提供「5 分钟第一支视频」路径：安装 → 填 key → 两条命令渲染，不依赖阅读完整文档。平台支持矩阵 SHALL 标注每个平台的验证状态（✅ 实机验证 / ⚠️ 推断未验证）。

#### Scenario: 用户按快速路径出片

- **WHEN** 用户只阅读 README 快速路径小节
- **THEN** 能完成从安装到产出 `<slug>.mp4` 的全流程
- **AND** 所需命令在该小节内完整给出

#### Scenario: 用户预判平台风险

- **WHEN** 用户查看平台支持矩阵
- **THEN** 每个平台显示验证状态
- **AND** ⚠️ 平台附指向 `probe.md` 验证流程的说明


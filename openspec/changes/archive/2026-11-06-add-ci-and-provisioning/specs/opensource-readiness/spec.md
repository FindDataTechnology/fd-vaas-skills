# opensource-readiness (delta)

## MODIFIED Requirements

### Requirement: 一键安装与自检

仓库 SHALL 提供 `install.sh`（macOS/Linux）与 `scripts/doctor.mjs`（跨平台）。install.sh SHALL 完成依赖检查、remotion-app 依赖安装、`.env` 初始化、技能链接创建，并在结尾运行 doctor。doctor SHALL 按 ✅/⚠️/❌ 三级报告，❌ 项 MUST 附带修复命令，存在 ❌ 时退出码 MUST 非 0。doctor MUST NOT 打印任何密钥值。

依赖检查 MUST 反映「统一 py 运行时」架构：视频发布在全平台（含 macOS）走 vendored social-auto-upload 上游（patchright），因此 install.sh MUST 在所有平台检查 `python3` 与 `uv`/patchright，MUST NOT 再把 patchright 列为 Windows-only。ego-browser/cap/officecli 在 macOS 上 MUST 降级为可选项警告（仅录屏与部分图文自有逻辑平台需要）。技能链接清单 MUST 与 `.claude/skills/` 暴露的子集保持一致，包含 `fd-vaas-login`。install.sh 内所有指向 README 小节的引用 MUST 指向真实存在的锚点（如「前置条件」）。安装汇总 MUST 引导用户下一步完成平台登录（`/fd-vaas-login` 登录管理页）。

安装与自检 MUST 覆盖 MCP 服务器平面：install.sh SHALL 安装 mcp-server 的 Python 依赖（或给出文档化的一条命令安装引导并在汇总中显示），SHALL 生成 `.mcp.json` 或提供可直接复制的模板；doctor SHALL 验证 `mcp_server` 可导入且 stdio 服务器可拉起（轻量探活，不发起付费生成），该项缺失或损坏报 ❌。ffmpeg 等渲染必需依赖缺失 MUST 报 ❌（非 warn）并附修复命令。

#### Scenario: 缺依赖时给出可行动报告

- **WHEN** 一台缺 ffmpeg 的机器运行 `node scripts/doctor.mjs`
- **THEN** 报告中 ffmpeg 项为 ❌ 并附安装命令
- **AND** 退出码非 0
- **AND** 补齐后重跑全部 ✅，退出码为 0

#### Scenario: Windows 技能可用

- **WHEN** Windows 用户 clone 仓库并运行安装/自检流程
- **THEN** `.claude/skills/` 下技能以目录复制形式存在（而非断掉的软链接）
- **AND** `/fd-vaas-video-creator` 等命令可被 Claude Code 发现

#### Scenario: macOS 缺 patchright 被检出

- **WHEN** macOS 机器未安装 patchright/uv 运行 `./install.sh`
- **THEN** 输出包含 patchright 缺失警告及安装命令（不再被当作 Windows-only 跳过）
- **AND** ego-browser 缺失仅产生「可选工具」级别警告

#### Scenario: 技能链接清单含登录技能

- **WHEN** 全新克隆上运行 `./install.sh`
- **THEN** `.claude/skills/fd-vaas-login` 被创建（软链或复制）
- **AND** 汇总输出引导用户运行登录管理页完成各平台扫码登录

#### Scenario: 装完即可拉起 stdio 服务器

- **WHEN** 全新克隆按 install.sh 完成后运行 `node scripts/doctor.mjs`
- **THEN** mcp-server 平面自检项为 ✅（依赖可导入、stdio 可拉起）
- **AND** 用户按 README 接入 `.mcp.json` 后 23 工具面立即可列出

# Delta Spec: opensource-readiness

## MODIFIED Requirements

### Requirement: 一键安装与自检

仓库 SHALL 提供 `install.sh`（macOS/Linux）与 `scripts/doctor.mjs`（跨平台）。install.sh SHALL 完成依赖检查、remotion-app 依赖安装、`.env` 初始化、技能链接创建，并在结尾运行 doctor。doctor SHALL 按 ✅/⚠️/❌ 三级报告，❌ 项 MUST 附带修复命令，存在 ❌ 时退出码 MUST 非 0。doctor MUST NOT 打印任何密钥值。

依赖检查 MUST 反映「统一 py 运行时」架构：视频发布在全平台（含 macOS）走 vendored social-auto-upload 上游（patchright），因此 install.sh MUST 在所有平台检查 `python3` 与 `uv`/patchright，MUST NOT 再把 patchright 列为 Windows-only。ego-browser/cap/officecli 在 macOS 上 MUST 降级为可选项警告（仅录屏与部分图文自有逻辑平台需要）。技能链接清单 MUST 与 `.claude/skills/` 暴露的子集保持一致，包含 `fd-vaas-login`。install.sh 内所有指向 README 小节的引用 MUST 指向真实存在的锚点（如「前置条件」）。安装汇总 MUST 引导用户下一步完成平台登录（`/fd-vaas-login` 登录管理页）。

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

### Requirement: 快速上手路径

README SHALL 在顶部提供「5 分钟第一支视频」路径：安装 → 填 key → 两条命令渲染，不依赖阅读完整文档。平台支持矩阵 SHALL 标注每个平台的验证状态（✅ 实机验证 / ⚠️ 推断未验证），且验证状态 MUST 与 `.agents/skills/_shared/publish/platform-registry.json` 一致。README（zh 与 en 双版本）对分发架构的描述 MUST 与代码现状一致：视频发布 = vendor 上游 + `sau_adapter.py` 薄适配层（统一 py/patchright 运行时，cookie 登录态），bilibili = 本地 `bilibili.py`（biliup）；图文 = 上游优先（`note_adapter.py`，11 平台）+ 自有逻辑（ego-browser 或 `--runtime patchright`）。README MUST NOT 再出现「social-auto-upload 已移除」「macOS 走 ego-browser .mjs 发布视频」等过时表述，MUST 介绍 `/fd-vaas-login` 登录管理页作为统一登录入口，MUST 反映 `fd-vaas-video-creator` 的类型注册表（`new-task --type`，口播/录播之外的 carousel、kinetic-quote、news-flash、listicle、data-viz 等）。

#### Scenario: 用户按快速路径出片

- **WHEN** 用户只阅读 README 快速路径小节
- **THEN** 能完成从安装到产出 `<slug>.mp4` 的全流程
- **AND** 所需命令在该小节内完整给出

#### Scenario: 用户预判平台风险

- **WHEN** 用户查看平台支持矩阵
- **THEN** 每个平台显示验证状态
- **AND** ⚠️ 平台附指向 `probe.md` 验证流程的说明

#### Scenario: 新用户理解登录方式

- **WHEN** 新用户阅读 README 的登录/前置条件小节
- **THEN** 得知视频发布登录 = `/fd-vaas-login` 扫码，cookie 存于 `upstream/cookies/<platform>_uploader/account.json`
- **AND** 不会找到 cookie 文件「已废弃」或「macOS 免登录复用 Chrome」之类的矛盾表述

#### Scenario: 双语 README 一致

- **WHEN** 对比 README.md 与 README.en.md 的架构、平台矩阵、技能清单小节
- **THEN** 两者信息等价（仅语言不同）

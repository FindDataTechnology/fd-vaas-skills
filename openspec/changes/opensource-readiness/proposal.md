# 开源可用性：clone 即可用

## Summary

让公开仓库 `FindDataTechnology/fd-vaas-skills` 达到「新用户 clone → 跑 install.sh → doctor 自检 → 5 分钟渲出第一支口播视频」的水平。签入渲染源码与 MCP 服务器，收敛 .gitignore，升级安装脚本，提供自检工具与快速上手路径。

## Motivation

**当前问题（按严重度）：**

1. **渲染核心不在公开仓库**：`remotion-app/` 整个被 .gitignore，公开用户没有 `VoiceoverVideo` 等 composition，装完渲不出任何视频——只能靠 `references/setup.md` 手工重建，这是阻塞级缺陷。
2. **已归档的成果未签入**：`openspec/`（3 条主 spec）、`mcp-server/`（统一 MCP 服务器，spec 已归档为完成态）在 git 里是 untracked，公开仓库与本地真相源不一致。
3. **install.sh 太薄**：只做 clone + npm install + cp .env，不检查 ffmpeg/ego-browser/cap/officecli/python，不验证 API key，不建技能软链接。
4. **没有自检工具**：新用户卡住时不知道缺什么，只能通读 400 行 README 排错。
5. **`.claude/skills` 是软链接**：Windows git 默认不创建软链接，Windows 用户 clone 后技能全部失联。
6. **README 缺快速路径**：内容全但长，没有「最小可跑」的 5 分钟路线；平台支持矩阵也没标注哪些验证过、哪些是推断。

**目标：**
- 公开仓库自包含：渲染源码、spec、MCP 服务器全部可追踪
- 安装可自检：install.sh + doctor 给出「绿了 / 缺什么 / 怎么补」的明确报告
- 上手有快路径：README 顶部一条 5 分钟第一支视频的路线

## Requirements

### 核心功能

1. **签入渲染源码**
   - `.gitignore` 不再忽略整个 `remotion-app/`，改为只忽略运行时产物（`node_modules/`、`out/`、`.remotion/`、`public/voiceover-*`、`public/captions-*` 等生成物）
   - 签入 `remotion-app/src/`（全部 composition、theme、ui）、`package.json`、`tsconfig.json`、remotion 配置
   - **签入前审计**：grep 源码中的内部 URL / 密钥 / 私人信息；`public/` 下只签入渲染必需的品牌资产（logo 等），不签入生成物
   - 品牌场景（scenesVAAS/Gov/Org 等）默认随 src 公开——它们本就是公开发布视频的内容；审计中若发现敏感信息则脱敏后再签入

2. **签入已归档成果**
   - `openspec/`（config + 主 specs + changes/archive）全部签入
   - `mcp-server/` 签入（排除 `__pycache__`、本地 db、测试产物）
   - `vaas.db`、`data/`、`*.bak`、`.profiles/` 保持忽略；`.gitignore` 增加 `*.bak` 与 `.env.bak` 模式

3. **install.sh 升级为 bootstrap**
   - 检查并报告：Node 18+、git、ffmpeg/ffprobe、Python 3.10–3.12 + uv（Windows）、ego-browser（macOS）、cap、officecli
   - `npm install` remotion-app；若 `VoiceoverVideo` 未注册则执行 `references/setup.md` 的安装步骤
   - 重建 `.claude/skills` 链接：**macOS/Linux 用软链接，Windows 用目录复制**（git 克隆下来的断链也由此修复）
   - 缺 `.env` 时从 `.env.example` 复制并提示填 key
   - 结尾自动调用 doctor，输出可行动的下一步

4. **doctor 自检脚本**（`scripts/doctor.mjs`）
   - 逐项检查：运行时依赖、`.env` 关键变量（Ark key 存在性，不打印值）、remotion-app 依赖与 composition 注册、技能链接完整性、ego-browser/patchright 可用性
   - 输出分级：✅ 通过 / ⚠️ 可选缺失（影响哪些功能）/ ❌ 阻塞缺失（附修复命令）
   - 退出码：有 ❌ 则非 0，供 install.sh 和 CI 使用

5. **README 快速路径 + 验证状态透明化**
   - 顶部新增「5 分钟第一支视频」小节：install → 填 key → 一条 new-task + task-render 命令
   - 平台支持矩阵每行加验证状态列：✅ 实机验证 / ⚠️ 推断未验证（图文 9 平台、patchright Windows 链路）
   - README.en.md 同步

### 非目标（Non-goals）

- 不重构 remotion-app 代码本身（composition 重写属于 video-type-registry 的事）
- 不改发布链路、不改 skill 内部逻辑
- 不做 CI/CD（doctor 的退出码设计为未来 CI 留口，但本变更不建流水线）
- 不提交任何真实生成物、登录态、数据库内容

## Technical Approach

- **.gitignore 收敛**：把 `remotion-app/` 整条忽略改为精确忽略其子路径；新增 `*.bak`、`.env.bak`
- **软链接跨平台**：install.sh 内检测 `process.platform`（脚本层用 `uname`/`%OS%`），Windows 下 `robocopy /E` 或 `xcopy` 复制 `.agents/skills/<name>` 到 `.claude/skills/<name>`；已存在的正确链接跳过，实现幂等
- **doctor 实现**：纯 Node 脚本，无新依赖；每项检查返回 `{level, name, detail, fix}`，汇总打印；检查项写成数组便于扩展
- **组合注册检查**：doctor 读取 `remotion-app/src/Composition.tsx`（或 Root.tsx）确认 `VoiceoverVideo` id 存在

## Success Criteria

1. 全新 macOS 机器：clone → install.sh → 填入 Ark key → 按 README 快速路径渲出第一支口播视频，全程不读 README 快速路径以外的文档
2. `node scripts/doctor.mjs` 在一台缺 ffmpeg 的机器上给出 ❌ + 安装命令；补装后再跑全绿
3. Windows clone 后跑 install.sh，`.claude/skills` 下技能以复制形式可用
4. `git ls-files` 包含 `remotion-app/src/`、`openspec/`、`mcp-server/`；不包含任何 `.bak`、`vaas.db`、生成物、`.profiles/`

## Risks & Mitigations

| 风险 | 影响 | 缓解 |
|------|------|------|
| remotion-app 源码含敏感信息 | 泄露内部 URL/命名 | 签入前专项审计任务（grep 密钥模式 + 人工过一遍 scenes*.tsx）；发现问题先脱敏 |
| 品牌场景公开后被模仿 | 品牌视觉被抄 | 可接受：视频本身已公开；品牌一致性靠 downloads/common 素材（不公开）维持 |
| Windows 复制 skills 后与 .agents 漂移 | 用户改了副本没改真相源 | README/AGENTS 强调真相源在 `.agents/skills/`；install.sh 幂等可复制刷新 |
| install.sh 变复杂后跨平台分叉 | bash 在 Windows 不可用 | install.sh 保持 bash（macOS/Linux）；Windows 另给 `install.ps1` 或文档说明用 Git Bash/WSL——本变更选：文档说明 + doctor.mjs 跨平台（Node 层做主要检查） |

## Open Questions

1. `data/`（dashboard 数据）是否也有该签入的 schema/种子文件？实施时审计后决定
2. README 快速路径是否同时给英文版完整同步，还是英文版先只放快速路径 + 链接？（倾向：完整同步，避免双语漂移）

## Dependencies

- 无新外部依赖；doctor 用 Node 18+ 内置 API

## Timeline Estimate

- gitignore 收敛 + 审计 + 签入：1 小时
- install.sh 升级 + doctor.mjs：2-3 小时
- README 快速路径 + 验证状态：1 小时
- 真机验证（最好找一台干净机器/新目录模拟）：1 小时
- **总计：5-6 小时**

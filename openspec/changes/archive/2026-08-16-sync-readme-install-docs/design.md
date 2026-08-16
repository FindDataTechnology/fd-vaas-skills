# Design: sync-readme-install-docs

## Context

入口三件套（README.md / README.en.md / install.sh）最后一次大改是 `opensource-readiness`（2026-08 上旬），随后三轮重构改变了被描述的现实：

1. **`unify-publish-runtime`（Phase 2/3）**：视频发布从「macOS=ego-browser .mjs / Windows=patchright .py 双运行时」翻转为**统一 py 运行时**——上游 social-auto-upload 被 vendor 进 `fd-vaas-publish-videos/scripts/upstream/`，`sau_adapter.py` 把 CLI 翻译成上游 `<Platform>Video(...).main()`；各平台手写 `.mjs`/`.py` 已删除；bilibili 例外（上游用 biliup 二进制，走本地 `bilibili.py`）。登录态从「ego 继承 Chrome / patchright profile」变为 **cookie `upstream/cookies/<platform>_uploader/account.json`**。
2. **`unify-publish-lib`**：图文发布变为「上游优先」——小红书/抖音图文/快手图文走 `note_adapter.py`（与视频共享 cookie），图文平台 9 → 11；自有逻辑平台（知乎/公众号/雪球/东财/同花顺/头条/百家/微博）保留 ego-browser heredoc，新增 `--runtime patchright`；平台路由与验证状态的单一事实源是 `_shared/publish/platform-registry.json`。
3. **`fd-vaas-login`**：新登录管理技能（Python stdlib HTTP server，:8766），统一查看/触发各平台扫码登录。已在 `.claude/skills/` 有软链，但 install.sh 的链接清单和 README 的技能清单都没有它。
4. **video-creator 类型注册表**：`new-task --type` + pipeline interpreter，类型含 voiceover、screen-recording、carousel、kinetic-quote、news-flash、listicle、data-viz；口播流水线新增 scene-align 步骤。

约束：纯文档/安装脚本变更，不改任何 skill 源码；所有事实以各 SKILL.md、platform-registry.json、scripts/upstream/ 现状为准；双语 README 必须同步。

## Goals / Non-Goals

**Goals:**
- README 双版本的架构图、主线流程、平台矩阵、技能清单、前置条件、登录说明、坑与排错与代码一致。
- install.sh 的依赖检查、技能链接清单、结尾引导与新架构一致，且所有对 README 小节的引用指向真实锚点。
- 平台验证状态与 platform-registry.json 对齐（不手写猜测）。

**Non-Goals:**
- 不改 doctor.mjs 的检查逻辑（除非引用到已删文件；如有则顺手修）。
- 不重写写 SKILL.md 正文（它们是事实源，不是被同步对象）。
- 不补做「weixin/bilibili/youtube 实机验证」——只如实标注状态。
- 不动 AGENTS.md（如需同步另开变更）。

## Decisions

### D1: 事实源优先级 —— SKILL.md > registry > git log

每处 README 表述必须能回溯到 `.agents/skills/<skill>/SKILL.md` 或 `_shared/publish/platform-registry.json` 的原文。平台验证状态表直接从 registry 渲染，不从旧 README 表格继承（旧表整体过时）。理由：本次漂移的根因就是文档凭记忆写、没有对照事实源。

### D2: install.sh 依赖检查改为「按用途分组」而非「按 OS 二分」

现状是 `if WINDOWS → patchright; elif Darwin → ego/cap/officecli`，新架构下这是错的（macOS 发视频也要 patchright）。改为：

- **核心**：Node 18+、git、ffmpeg/ffprobe（不变）
- **发布运行时（全平台）**：python3、uv、patchright（缺失 → 警告 + 安装命令）
- **可选工具（macOS）**：ego-browser（录屏 + 图文自有平台）、cap、officecli——缺失只 info/warn「可选」
- Linux：发布 py 运行时可用；录屏类不可用（不变）

备选方案「保持 OS 二分、只在 macOS 分支加 patchright」被否：分支会随图文 `--runtime patchright` 普及继续腐烂，按用途分组更贴近真实依赖关系。

### D3: 登录叙事统一为「/fd-vaas-login 扫码 → cookie 共享」

README 的登录小节、install.sh 的结尾引导、5 分钟快速路径之后的「下一步」全部指向同一入口：`python3 .agents/skills/fd-vaas-login/scripts/login-manager.py`（或 Claude Code 里 `/fd-vaas-login`）。ego-browser 的「复用 Chrome 登录态」表述收敛到它仅剩的两个用途（fd-browser-record 录屏、图文自有逻辑平台默认运行时），不再出现在视频发布路径上。

### D4: 双语同步策略 —— 先定稿中文，再整段翻译对齐

README.md 为权威版本；README.en.md 按节对照重写（不是逐行 diff，因为漂移面太大）。完成后用节标题清单做一致性抽查（两文件的 ## 小节集合必须相同）。

### D5: 「架构变更」提示块反转措辞

README 现存的「架构变更（重要）：social-auto-upload 已移除」块替换为新的变更说明：分发栈已改为 vendor 上游 + 薄适配层（第二次架构翻转），并明确旧表述（sau 已移除、macOS ego 双运行时）作废。保留这类提示块的传统——它是老读者唯一的迁移信号。

## Risks / Trade-offs

- [文档再次漂移] → 在坑与排错/平台矩阵中显式指向 platform-registry.json 与各 SKILL.md 作为事实源，提醒「改状态用 probe.py 回写，别手改文档」；tasks 里安排对照校验步骤。
- [install.sh 改动破坏 macOS 现有用户] → 依赖检查只增警告不增硬性失败（沿用脚本「只警告不中断」原则）；技能链接逻辑幂等，重跑安全。
- [README 变长] → 只更新漂移小节，不新增概念性章节；平台矩阵保持表格化不扩写。
- [验证状态如实标注后显得「全是 ⚠️」] → 可接受，如实 > 好看；registry 里 ✅ 的（小红书视频/图文等）照实标 ✅。

## Migration Plan

无需迁移。纯文档 + 安装脚本变更，合并即生效。install.sh 幂等，老用户重跑只会补齐 fd-vaas-login 链接和新警告。

## Open Questions

- AGENTS.md 是否也存在同样漂移？（初步看有「sau 已移除」同类表述的可能——本变更不动它，tasks 里记录为后续项。）

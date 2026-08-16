# Proposal: sync-readme-install-docs

## Why

README.md / README.en.md / install.sh 与代码现状严重脱节。最近三轮重构（`unify-publish-runtime` Phase 2/3、`unify-publish-lib`、`fd-vaas-login` portal）把分发栈改了个遍，但面向新用户的入口文档还写着旧架构——README 甚至声称「`social-auto-upload/` 已移除，不要再引用它」，而代码恰恰把上游 vendor 了回来作为唯一上传实现。新用户照 README 装会装错运行时（macOS 不装 patchright）、找不到登录入口、对平台矩阵的验证状态产生错误预期。

## What Changes

- **README.md / README.en.md 全面对齐现状**：
  - 分发架构改写为「vendor + 薄适配层」：上游 social-auto-upload vendored 在 `fd-vaas-publish-videos/scripts/upstream/`，`sau_adapter.py` 统一 py 运行时（patchright），bilibili 走本地 `bilibili.py`（biliup）；删除「sau 已移除」「macOS=ego-browser .mjs / Windows=patchright .py 双运行时」等过时表述。
  - 登录态改写：视频发布 = cookie（`upstream/cookies/<platform>_uploader/account.json`），由新技能 **`/fd-vaas-login`**（登录管理 Web 页 :8766，扫码/状态总览）统一管理；ego-browser 只剩录屏（fd-browser-record）和图文自有逻辑平台两条用途。
  - 图文平台 9 → 11（新增抖音图文、快手图文），「上游优先」路由（xiaohongshu/douyin/kuaishou 走 `note_adapter.py`，与视频共享 cookie），自有逻辑平台支持 `--runtime patchright`。
  - `fd-vaas-video-creator` 补充类型注册表：除口播/录屏外新增 carousel、kinetic-quote、news-flash、listicle、data-viz 等类型，`new-task --type` + pipeline interpreter + scene-align。
  - 技能一览/仓库结构/前置条件/坑与排错同步（新增 fd-vaas-login、`_shared/`、platform-registry.json；前置条件改为全平台需要 Python+patchright）。
- **install.sh 刷新**：
  - `SKILLS_TO_LINK` 增加 `fd-vaas-login`（与 `.claude/skills/` 现有软链一致）。
  - 依赖检查不再按 Windows/macOS 二分 patchright——视频发布全平台走 py 运行时，macOS 也检查 `python3`/`uv`/patchright；ego-browser 降级为「录屏 + 部分图文平台」可选项。
  - 修正失效引用（警告信息指向的 README「依赖工具」节不存在，实为「前置条件」）。
  - 汇总页「下一步」补充登录引导（`python3 .agents/skills/fd-vaas-login/scripts/login-manager.py` 或 `/fd-vaas-login`）。

## Capabilities

### New Capabilities

（无——本变更只改文档与安装脚本，不引入新行为契约。）

### Modified Capabilities

- `opensource-readiness`：「一键安装与自检」要求的依赖检查范围变化（patchright/uv 从 Windows-only 变为全平台必需；技能链接清单新增 fd-vaas-login）；「快速上手路径」隐含的平台矩阵与登录说明需按 vendor+adapter 架构重写。

## Impact

- **文档**：`README.md`、`README.en.md`（约 30 处实质性更新）。
- **脚本**：`install.sh`（依赖检查逻辑、技能清单、结尾引导）。
- **代码**：无。不触碰任何 skill 源码；所有描述以 `.agents/skills/*/SKILL.md`、`scripts/upstream/`、`_shared/publish/platform-registry.json` 现状为准。
- **风险**：低（纯文档）；主要风险是描述与 SKILL.md 再次漂移——tasks 里安排逐条对照校验。

# unify-publish-lib

## Why

图文（`fd-vaas-publish-docs`）和视频（`fd-vaas-publish-videos`）两个发布 skill 在「浏览器自动化工具」和「编排脚手架」上各有一份几乎相同的实现，正在分叉漂移：

- `scripts/platforms/lib/browser_utils.py` 存在**两份**。videos 版是 docs 版的**过期子集**：16 个通用函数（`Browser`/`is_logged_in`/`wait_for_login`/`click_by_text`/`safe_fill`/`upload_file`/`with_retry`/`StepRunner`/`default_profile_dir`…）逐行相同，但 videos 版缺了 `Browser.__enter__` 的剪贴板授权，以及 docs 侧 12 个图文专用 helper（`paste_text`/`paste_html`/`fill_hidden`/`upload_images`/`publish_and_verify`…）。改一个 bug 要同步两处，且 videos 版已经悄悄落后。
- 两个 `publish.mjs` 里的 `loadEnv`/`truncate`/`mdToPlain`/`summarize`/`.publish.env` 合并、`distribution[]` 回写是同一套逻辑各写一遍（约 370 行 × 2），纯函数被埋在 spawnSync 副作用脚本里，**无法单测**——而「标题超长/标签超限/正文截断」正是最高发的 bug 区。
- `README-PUBLISH-OPTIMIZATION.md` 引用的 `bilibili-upload`/`youtube-upload`/`douyin-upload` skill 目录早已删除，纯属误导。
- 平台健康度（哪个平台走上游/自有、选择器是否实机验证、最后验证日期）散落在 memory、SKILL.md 表格、各 references 底部，**没有单一可机读的登记处**，选择器漂移只能靠人肉发现。

## What Changes

- **单一 `browser_utils.py`**：videos/docs 两份收敛成一份 canonical 共享模块，两个 skill 的 `.py` 都从这里 import。canonical 取 docs 的超集版本（含剪贴板授权 + 图文 helper），videos 的 `bilibili.py` 改为指向共享位置。
- **抽出共享纯函数模块 `publish-common.mjs`**：标题截断、`mdToPlain`、摘要、标签限数、封面挑选、`.publish.env` 合并、`distribution[]` 回写等纯逻辑抽到一个可测模块，两个 `publish.mjs` 共用，并加最小单测（`node:test`）。
- **删除/更正 stale 文档**：`README-PUBLISH-OPTIMIZATION.md` 归档或重写为指向现行架构。
- **平台健康登记表**：单一可机读源（JSON + 由它渲染到 SKILL.md 的表格），记录「平台 → 路由（note_adapter/自有）→ 选择器验证状态 + 最后验证日期」。probe 流程回写它，SKILL.md 和登录面板状态（`.docs_state.json`）都从它读。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `publish-runtime`: 新增「单一浏览器自动化共享库」「共享编排纯函数」「平台健康登记」需求——两个发布 skill 的浏览器原语与内容适配逻辑 SHALL 各自只有一份 canonical 实现，平台健康状态 SHALL 有单一可机读源。

## Impact

- **代码**：新增共享模块（`browser_utils.py` 单份 + `publish-common.mjs` + `platform-registry.json`）；videos 的 `lib/browser_utils.py` 删除/改为 shim；两个 `publish.mjs` 改为 import 共享模块；docs 9 个 `platforms/*.py` 与 videos 的 `bilibili.py` 的 `sys.path` 指向共享位置。
- **依赖**：无新增（`node:test` 是 Node 内置；patchright 已在用）。
- **文档**：两个 SKILL.md 的「参考」与「选择器验证状态」段改为引用单一登记表；删除/重写 `README-PUBLISH-OPTIMIZATION.md`。
- **兼容性**：非破坏性。函数签名不变，平台脚本行为不变；登录态/profile 目录不变。

## Non-Goals（本次明确不做）

- **不删除 vendored 上游**（videos 的 `scripts/upstream/`）。SKILL.md 已给出强证据：上游 `wait_for_url("**/publish/success?**")` 命中 success 页才报成功、`sync-upstream.sh` 免费拿上游 bugfix、小红书视频已实发验证。删它是回退，不是收敛。
- **不收敛 docs 的双运行时**（`--runtime ego` heredoc vs `--runtime patchright` .py）。理由见 design.md「Runtime convergence 为何暂缓」。本次只消除「双运行时」里可共享的那一半（lib + 纯函数），让「保留双轨」变便宜；要不要进一步单轨是后续独立决策。

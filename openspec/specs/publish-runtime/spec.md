# Publish Runtime

统一发布运行时与浏览器自动化共享层。fd-vaas-publish-videos 与 fd-vaas-publish-docs 共用单一浏览器原语库与单一编排纯函数模块；视频发布在所有操作系统上走单一 patchright 运行时。

### Requirement: 单一浏览器自动化共享库

`browser_utils.py` SHALL 在仓库里只有一份 canonical 实现，fd-vaas-publish-docs 与 fd-vaas-publish-videos 两个 skill 的平台脚本 MUST 从同一份共享模块 import，MUST NOT 各自维护副本。canonical 版本 SHALL 是包含全部通用原语 + 图文 helper 的超集（含 `Browser.__enter__` 的剪贴板 `grant_permissions`）。

#### Scenario: 两个 skill 共用同一份原语

- **WHEN** 任一 skill 的 `.py` 平台脚本 import `browser_utils`
- **THEN** 它从单一共享路径解析到同一份模块（非 skill 内各自 `lib/` 副本）
- **AND** videos 的 `bilibili.py` 与 docs 的 9 个 `platforms/*.py` 得到相同的行为（含剪贴板授权）

#### Scenario: 修一处 bug 两处生效

- **WHEN** 在共享 `browser_utils.py` 修复某原语（如 `click_by_text` 文本匹配）
- **THEN** docs 与 videos 的下次运行都拿到修复
- **AND** 无需在第二个 skill 里重复同步

### Requirement: 共享编排纯函数

内容适配（标题截断、`mdToPlain` 保代码块、摘要、标签限数、封面挑选）、`.publish.env` 分层合并、`distribution[]` 回写等纯逻辑 SHALL 抽到单一可测模块（`publish-common.mjs`），两个 `publish.mjs` MUST 共用，SHALL 有最小单元测试覆盖（Node 内置 `node:test`，零外部依赖）。

#### Scenario: 纯函数可单测

- **WHEN** 运行 `node --test`
- **THEN** 标题截断/正文去符号/标签限数/封面挑选的用例通过
- **AND** 无 `patchright`/浏览器/`.env` 实际依赖

#### Scenario: 两个编排器行为一致

- **WHEN** 对同一个 slug 分别用改前/改后的 `publish.mjs --dry-run`
- **THEN** 两份输出 diff 为空（标题/正文/标签/封面/命令组装一致）

### Requirement: 平台健康登记

平台「路由（upstream-note / own）+ 选择器验证状态 + 最后验证日期」SHALL 有单一可机读源 `platform-registry.json`，两个 SKILL.md 的平台表格与选择器验证状态 MUST 由它渲染而非手写；`probe.py` 跑完 MUST 回写对应平台的 `selectorStatus` 与 `lastVerified`。

#### Scenario: 选择器漂移可追溯

- **WHEN** 某平台选择器失效（`probe.py` 发现）
- **THEN** `platform-registry.json` 该平台 `selectorStatus` 更新为 `broken` 并记录日期
- **AND** SKILL.md 反映该状态，不再靠人肉 memory 记录

#### Scenario: 单一源与运行态分离

- **WHEN** 登录面板读写登录检测结果
- **THEN** 它继续用运行态 `.docs_state.json`，不写 `platform-registry.json`
- **AND** registry 只存半静态的路由 + 选择器事实

### Requirement: 单一上传运行时

fd-vaas-publish-videos SHALL 在所有操作系统上使用 patchright（`.py`）作为唯一上传运行时。`publish.mjs` MUST NOT 按 OS 分派不同运行时。平台脚本 SHALL 只保留 `.py` 一套，`.mjs`（ego-browser）脚本 SHALL 删除。

#### Scenario: macOS 走 patchright

- **WHEN** 用户在 macOS 执行 `publish.mjs --slug <x> --platforms <p>`
- **THEN** 平台上传走 `<platform>.py`（patchright）
- **AND** 不启动 ego-browser

### Requirement: 浏览器自动化用 Playwright 真原语

平台脚本 SHALL 通过 `browser_utils.py` 使用 `locator()`/`set_input_files()`/`fill()`/auto-wait 等 Playwright 原语。文本输入（描述/正文）MUST 使用真实键盘事件（`type_text`，即 `page.keyboard.type`），MUST NOT 依赖 `document.execCommand('insertText')`。

#### Scenario: 描述填写不被静默丢弃

- **WHEN** 平台脚本填写 React contenteditable 描述框
- **THEN** 使用 `type_text`（真实键盘事件）
- **AND** 描述内容出现在发布表单中（不静默丢失）

### Requirement: 持久登录态（storage_state）

py 运行时 5 个 Playwright 平台（xiaohongshu/douyin/kuaishou/weixin/youtube）SHALL 使用 vendored 上游的 `cookies/<platform>_uploader/account.json`（storage_state JSON）持久化登录态，跨次运行复用。首次 SHALL 支持扫码登录（`sau_adapter.py --login`，上游 `<platform>_setup` QR 流程）；已有 `.profiles/<platform>/` 持久登录态可经 `sau_adapter.py --migrate-profile` 导出为 storage_state。bilibili 仍用本地 `bilibili.py` + `.profiles/bilibili/`。

#### Scenario: 首次登录后免登

- **WHEN** 用户首次在某平台扫码登录（`--login`）或从 `.profiles/` 迁移（`--migrate-profile`）
- **THEN** 登录态写入 `cookies/<platform>_uploader/account.json`
- **AND** 后续运行不再要求登录

### Requirement: 死代码清理

`lib/browser-utils.mjs`（无任何 `.mjs` import 的工具库）SHALL 删除。`publish.mjs` 中的死变量（如未使用的 `NODE`）和 stale 引用（`fd-vaas-publish` 不带 `-videos`）SHALL 清理。

#### Scenario: 无死引用

- **WHEN** 删除 `.mjs` 与 `lib/browser-utils.mjs` 后
- **THEN** `publish.mjs` 与所有 `.py` 运行无 import/ReferenceError
- **AND** `grep` 无 `execCommand.*insertText` 用于文本输入

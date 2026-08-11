# publish-runtime Spec Delta

## ADDED Requirements

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

# unify-publish-runtime

## Summary

把 fd-vaas-publish-videos 的双运行时（macOS=ego-browser `.mjs` / Windows=patchright `.py`）统一为**单一 patchright `.py` 运行时**。删除 6 个 `.mjs` 脚本 + 死代码 `lib/browser-utils.mjs`（411 行，无任何 import），`publish.mjs` 简化为全平台派发 `.py`。

这是用户「上传整体解决方案」的落地——根因是 ego-browser 的 nodejs 模式**不是 Playwright**：没有 `locator()`/auto-wait/`set_input_files()`，所有 DOM 交互靠手搓 `querySelector` + 已废弃的 `execCommand`，所以「老出问题」。而 `.py`（patchright = stealth Playwright）已经是 social-auto-upload 那套稳定原语的忠实移植，只是 macOS 一直没用到它。

## Motivation

用户问：**为什么 social-auto-upload 能稳定多平台上传，我的代码老出问题？**

诊断结论（两个 agent + 实测）：

**social-auto-upload 稳定的根因** = 它用 Playwright 真原语：`locator()` 自动重试/自动等待、`set_input_files()` 走原生文件选择、`fill()` 触发真实 input 事件、`userDataDir` 持久化登录态。这些原语对 React/Shadow DOM/异步渲染有天然容错。

**fd-vaas-publish-videos 不稳定的根因** = macOS 跑的 `.mjs` 用 ego-browser nodejs 模式，它**不是 Playwright**：没有 Page 句柄、没有 `locator()`、没有 auto-wait。每个 `.mjs` 把一整个 `egoScript` 模板字符串 pipe 给 ego-browser stdin，所有 DOM 操作都是 `document.querySelector` + `execCommand('insertText')`（已废弃，在 React contenteditable 上**静默失败**——抖音描述填不上就是这么来的）。

**关键事实**：`.py` 脚本就是 social-auto-upload 那套稳定原语的忠实移植——`browser_utils.py` 的 `upload_file` 用 `.first.set_input_files()`、`click_by_text` 带 `offsetParent` 可见性判断、`wait_for_login` 轮询、`launch_persistent_context` 复用 `.profiles`。`.py` 已经在 Windows 上稳定跑，只是 macOS 一直被路由到脆弱的 `.mjs`。

所以「整体解决方案」不是重写，是**砍掉脆弱的那半边，让 macOS 也走已经稳定的 `.py`**。

### 重新引入 social-auto-upload（vendor + 薄适配层）—— 前提修正 2026-08-11

初版结论是「不重新引入」，理由是「`.py` 已是等价实现」。**Phase 1 验证证伪了这一点**：用我们手写的 `xiaohongshu.py` 跑 dataviz-demo→小红书，脚本退出 0 但实际未发布成功——根因是我们的移植**漏了上游的 `set_thumbnail` 封面上传步骤**，且原始声明/发布点击的容错也不如上游。结论：手写 `.py` 不是「等价实现」而是「不完整移植」，逐平台对齐代价 > vendor 上游。

改用 **vendor + 薄适配层**（用户选择「Vendor + 薄适配层」）：
- `scripts/upstream/`：vendored social-auto-upload（`uploader/` + `utils/` + `conf.example.py`），canonical，不手改
- `scripts/sync-upstream.sh`：clone + rsync --delete 重新同步，记录 SHA 到 `.upstream-version`；`--check` 看 diff、`<sha>` 钉版本、`--remote` 用 fork —— 这就是用户要的「快速和开源项目同步」机制
- `scripts/platforms/sau_adapter.py`：薄适配层，把 VAAS CLI（`--file/--title/--desc/--tags/--cover*/--schedule`）翻译成上游 `<Platform>Video(**kwargs).main()`；额外提供 `--login/--login-check/--migrate-profile`
- `scripts/upstream/conf.py`：我们自己的 conf（BASE_DIR 指向 vendor 根，headed 默认，YT_PROXY 从 env），sync 不覆盖
- `publish.mjs`：py 运行时 5 个 Playwright 平台（xiaohongshu/douyin/kuaishou/weixin/youtube）走 `sau_adapter.py`；bilibili 仍走本地 `bilibili.py`（上游 bilibili 用 biliup 二进制，非 Playwright）

cookie 用 `storage_state`（JSON 文件）而非持久 profile 目录；可 `--migrate-profile` 从已有 `.profiles/<platform>/` 导出，不丢现有登录态。

## Requirements / Solution

1. **单一运行时**：`publish.mjs` 全平台派发 `.py`（patchright），删除 OS 分支。`RUNTIME = env.PYTHON || "python3"`，`SCRIPT_EXT = "py"`。
2. **patchright 真原语**：所有平台脚本 MUST 用 `browser_utils.py` 的 locator/fill/set_input_files/auto-wait，MUST NOT 用 `execCommand` 做文本输入（描述/正文一律 `type_text` 真实键盘事件——xhs `.py` 已验证的范式）。
3. **持久登录态**：每平台一个 `.profiles/<platform>/`（`launch_persistent_context`），跨次复用。首次需扫码登录一次。
4. **删除死代码**：6 个 `.mjs` + `lib/browser-utils.mjs`（411 行，无任何 `.mjs` import）。
5. **渐进切换**：先加 `--runtime` flag / `VAAS_PUBLISH_RUNTIME` env 让 macOS 可灰度切 `.py`（Phase 1），验证后再把默认翻成 `py` 并删 `.mjs`（Phase 2-3）。

### 已知需回填的 .py 缺陷（Phase 2 逐平台对齐时修）

- `douyin.py` 描述填写仍用 `execCommand`（与 `.mjs` 同 bug）→ 改 `type_text`（Phase 1 先修，因为它是验证平台之一）
- bilibili `.mjs` vs `.py` shadow-DOM 处理**互相矛盾** → 以 `.py` 为准对齐
- kuaishou 封面上传路径核对

### 登录态迁移代价（用户决策点）

当前 `.profiles/` 实测：

| 平台 | patchright 登录态 | 切 .py 后 |
|---|---|---|
| xiaohongshu | ✓ | 直接可用 |
| weixin | ✓ | 直接可用 |
| douyin | ✗ | 需扫码 1 次 |
| bilibili | ✗ | 需扫码 1 次 |
| kuaishou | ✗ | 需扫码 1 次 |
| youtube | ✗ | 需扫码 1 次（+代理） |

这是切 `.py` 的唯一代价——4 个平台在 patchright Chrome 里重新扫码登录一次，之后持久免登。

## Technical Approach

三阶段（渐进，可回退）：

- **Phase 1 去风险**（spike）：patchright 在 macOS 能启动 ✓（已 smoke pass）；`xiaohongshu.py` dry-run 能开页 ✓（已验证）；回填 `douyin.py` 描述修复；`publish.mjs` 加 runtime flag + 修 stale 报错。用一个真实平台（建议 xiaohongshu，有登录态）跑通 `.py` 全自动发布，证明 macOS 上 `.py` 可替代 ego-browser。
- **Phase 2 切换**：`publish.mjs` 默认翻 `.py`；逐平台对齐 `.py` 与 `.mjs` 行为，回填缺陷；更新 SKILL.md/文档；4 个缺登录态的平台扫码登录。
- **Phase 3 清理**：删 6 `.mjs` + `lib/browser-utils.mjs` + 死变量；commit。

## Success Criteria

1. macOS 上 `publish.mjs --slug <x> --platforms xiaohongshu` 走 `.py` 全自动发布成功（上传+填表+点发布+URL 验证），无需 ego-browser。
2. 6 个平台脚本只剩 `.py` 一套；`lib/browser-utils.mjs` 删除后无 import 报错。
3. `publish.mjs` 无 OS 分支、无 stale `fd-vaas-publish` 引用、无 ReferenceError。
4. 描述/正文在所有平台用真实键盘事件填写（grep 无 `execCommand insertText` 用于文本输入）。

## Risks & Mitigations

| 风险 | 缓解 |
|---|---|
| 4 平台需重新扫码登录 | 一次性；登录态持久化后免登 |
| `.py` 在某平台有未发现缺陷 | Phase 1 只验 1 平台；Phase 2 逐平台对齐+实发 |
| 删 `.mjs` 后想回退 | git 历史可恢复；Phase 2 默认翻之前 `.mjs` 仍在 |

## Open Questions

1. douyin 当前卡住的 ego 发布窗口（描述没填、没点发布）怎么收尾？建议关掉 ego 窗口，Phase 2 用 `.py` 重发（需重新扫码登录 douyin）。

## Timeline Estimate

- Phase 1：2 小时（flag + douyin.py 回填 + 1 平台实发验证）
- Phase 2：3-4 小时（默认翻 .py + 逐平台对齐 + 4 平台扫码 + 文档）
- Phase 3：0.5 小时（删文件 + grep + commit）

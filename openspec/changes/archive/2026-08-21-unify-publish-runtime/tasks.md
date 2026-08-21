# Tasks

> 渐进三阶段：Phase 1 去风险（可回退）→ Phase 2 切默认 → Phase 3 删死代码。每阶段独立可交付。

## Phase 1: 去风险（spike）

- [x] patchright 在 macOS 启动验证（smoke: `launch_persistent_context` headless 能开 about:blank）✓ 已 pass
- [x] `xiaohongshu.py --dry-run` 在 macOS 开页验证 ✓ 已 pass（publish 页打开，脚本跑到 handoff）
- [x] `publish.mjs` 加 `--runtime` flag + `VAAS_PUBLISH_RUNTIME` 环境变量（`auto|mjs|py`，默认 `auto=macOS mjs / Windows py`），让 macOS 可灰度切 `.py`
- [x] `publish.mjs` 修 stale 报错（line 172 `fd-vaas-publish` → `fd-vaas-publish-videos`）+ 删死变量 `const NODE = "node"`
- [x] `douyin.py` 回填描述修复：`execCommand('insertText')` → `type_text` 真实键盘事件（参照 `xiaohongshu.py`：定位 contenteditable → Backspace/Ctrl+a/Delete 清空 → `type_text`）；import 补 `type_text`
- [x] ~~选 xiaohongshu 用手写 `.py` 跑全自动发布~~ → **失败**：退出 0 但实际未发布（漏上游 `set_thumbnail` 封面步骤），证伪「`.py` 等价实现」前提，改 vendor 上游
- [x] vendor social-auto-upload 到 `scripts/upstream/`（uploader/+utils/+conf.example.py）+ 生成我们的 `conf.py`
- [x] `scripts/sync-upstream.sh`（clone+rsync--delete+记 SHA；--check/--remote/<sha>）= 用户要的「快速同步」机制
- [x] `scripts/platforms/sau_adapter.py`（CLI→上游构造；--login/--login-check/--migrate-profile）
- [x] `publish.mjs` buildCommand 派发 5 个 Playwright 平台走 sau_adapter（bilibili 仍走 bilibili.py）；dry-run 已 pass
- [x] `.gitignore` 加 upstream cookies/logs/.upstream-version（运行态登录态，永不提交）
- [x] 用 vendored 上游（含 set_thumbnail）重跑 dataviz-demo→xiaohongshu 实发验证 ✓ 2026-08-11 跑通：上游走完 cookie 检查→上传→填表→**set_thumbnail（旧 .py 漏的步骤）**→原创声明→`wait_for_url("**/publish/success?**")` 命中→「视频发布成功」。证伪「.py 等价实现」，vendor 修复了失败

## Phase 2: 切换默认

- [x] `publish.mjs` 默认 `RUNTIME` 翻 `py`（`auto` 分支改 `USE_PY = true`，macOS 不再默认走 mjs）✓ 2026-08-11 commit 26fdcb3，dry-run 验证 xiaohongshu/bilibili/douyin 全走 py 运行时
- [ ] 逐平台对齐：5 个 Playwright 平台 py 运行时已走 vendored upstream（canonical，无需与 .mjs 对齐）；bilibili 仍走本地 bilibili.py（上游用 biliup 二进制），需真机验证 shadow-DOM 上传
- [ ] douyin / kuaishou / youtube 扫码登录建立 cookie（`sau_adapter.py --platform <p> --login` → `cookies/<p>_uploader/account.json`；weixin 已 migrate-profile；youtube 需 `VAAS_YT_PROXY` 代理）—— 需用户在场扫码，非自治
- [x] 更新 fd-vaas-publish-videos SKILL.md / 文档：单一运行时说明、cookies/ 登录模型、sync-upstream.sh 用法、ego-browser 段落降级为 legacy ✓ 2026-08-11 重写完成 (commit 05d73c7，已 push)

## Phase 3: 清理死代码

- [x] 删 6 个 `.mjs`（douyin/bilibili/kuaishou/weixin/xiaohongshu/youtube）✓ 2026-08-11
- [x] 删 `lib/browser-utils.mjs`（411 行）✓ 2026-08-11
- [x] `publish.mjs` 删 `--runtime` 的 `mjs` 选项 + `IS_WIN` 分支（此时已全 py）✓ 2026-08-11 — `--runtime` 只认 py/auto，传 mjs 报错退出；`RUNTIME = env.PYTHON || "python3"`
- [x] grep 确认：无残留 `.mjs` import、无 `execCommand.*insertText` 用于文本输入、无 stale `fd-vaas-publish`（不带 `-videos`）引用 ✓ 2026-08-11 — scripts/ 下无 .mjs import（exit 1=clean）；execCommand 仅存 browser_utils.py:157,163（bilibili.py 用的 safe_fill，刻意保留）；bare `fd-vaas-publish` 全清
- [x] commit + push ✓ 2026-08-11

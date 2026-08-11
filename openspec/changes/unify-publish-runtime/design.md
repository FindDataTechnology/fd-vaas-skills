# Design: unify-publish-runtime

## 诊断：为什么 .mjs 脆弱 / .py 稳定

```
                   social-auto-upload (稳定)
                            │  Playwright 真原语
                            ▼
            ┌───────────────────────────────────────┐
            │  locator()     → 自动重试/等待         │
            │  set_input_files() → 原生文件选择      │
            │  fill()        → 真实 input 事件       │
            │  userDataDir   → 持久登录态            │
            └───────────────────────────────────────┘
                            │  忠实移植
                            ▼
              browser_utils.py (319 行, LIVE)
              ┌─ upload_file:  .first.set_input_files()
              ├─ click_by_text: offsetParent 可见性判断
              ├─ wait_for_login: 轮询 body.innerText
              └─ launch_persistent_context(.profiles/<platform>)
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
       6 个 .py (Windows 跑, 稳定)   publish.mjs 派发
              ▲                            │
              │                  IS_WIN ? py : mjs
              │                            ▼
              │                   6 个 .mjs (macOS 跑, 脆弱)
              │                   ┌─ ego-browser nodejs ≠ Playwright
              │                   ├─ 无 Page 句柄 / locator / auto-wait
              │                   ├─ 一个大 egoScript 模板字符串 pipe stdin
              │                   └─ querySelector + execCommand(已废弃)
              │                            │
              └────────────────────────────┘
              lib/browser-utils.mjs (411 行, 死代码, 无 import)
```

**根因一句话**：macOS 一直被路由到没有 Playwright 原语的 ego-browser `.mjs`，所以「老出问题」；`.py` 已经是稳定实现，只是 macOS 没用它。

## 目标架构

```
publish.mjs ──(全平台)──> <platform>.py ──> browser_utils.py ──> patchright
                              │                  │                  │
                              └ .profiles/<platform>/ 持久登录态 ◀──┘
```

- 单一运行时：`RUNTIME = env.PYTHON || "python3"`，`SCRIPT_EXT = "py"`
- 删 6 `.mjs` + `lib/browser-utils.mjs`

## 迁移路径（渐进，可回退）

| 阶段 | 动作 | 可回退性 |
|---|---|---|
| Phase 1 | `publish.mjs` 加 `--runtime`/`VAAS_PUBLISH_RUNTIME`；默认仍 auto（macOS=mjs）。回填 `douyin.py` 描述修复。验证 1 平台 `.py` 全自动发布。 | ✅ flag 关掉即回退 |
| Phase 2 | 默认翻 `py`；逐平台对齐 `.py` 行为；4 平台扫码登录；更新文档。 | ✅ `.mjs` 还在 |
| Phase 3 | 删 6 `.mjs` + `lib/browser-utils.mjs` + 死变量。 | git 可恢复 |

## 关键决策

### 1. 文本输入一律真实键盘事件

`execCommand('insertText')` 在 React/Slate contenteditable 上静默失败（douyin 描述、weixin 摘要都中过）。xhs `.py` 的范式：

```
click_selector 定位 contenteditable
→ Backspace / Ctrl+a / Delete 清空
→ type_text（page.keyboard.type，真实 input 事件）
```

所有平台描述/正文统一走这个范式，`browser_utils.py` 已有 `type_text`/`press_key`。

### 2. 重新引入 social-auto-upload（vendor + 薄适配层）

**前提修正（2026-08-11）**：初版决策「不重新引入，`.py` 已是等价实现」被 Phase 1 验证证伪——手写 `xiaohongshu.py` 退出 0 但未真正发布（漏上游 `set_thumbnail` 封面步骤）。手写移植逐平台对齐代价 > vendor 上游，故改 vendor。用户拍板「Vendor + 薄适配层」。

```
publish.mjs ──(py, 5 平台)──> sau_adapter.py ──> vendored upstream/uploader/<platform>_uploader
       │                              │                          │
       └ (py, bilibili)──> bilibili.py(本地)        conf.py(我们的) + cookies/(JSON storage_state)
                                                    ↑
                                    sync-upstream.sh: clone+rsync--delete, 记 SHA 到 .upstream-version
```

- 上游 `uploader/`+`utils/` 是 canonical，不手改；本地适配全在 `sau_adapter.py` / `conf.py`
- 同步机制（用户要的「快速和开源项目同步」）：`sync-upstream.sh`（rsync --delete 保字节一致；conf.py 由脚本重新生成、保留本地覆盖；`--check`/`--remote`/`<sha>`）
- cookie 用 `storage_state` JSON（`cookies/<platform>_uploader/account.json`），可从 `.profiles/<platform>/` `--migrate-profile` 导出
- bilibili 例外：上游走 biliup 二进制（非 Playwright），不在适配层，仍用本地 `bilibili.py`

### 3. Phase 1 只验 1 平台，不全量切

用 xiaohongshu（有登录态、`.py` 已能开页）跑通全自动发布即可证明架构；其余平台对齐放 Phase 2。这样 Phase 1 完全可回退（flag 默认关），不碰现有 ego-browser 流程。

### 4. publish.mjs 的 `--runtime` flag 设计

```
优先级: CLI --runtime > env VAAS_PUBLISH_RUNTIME > 默认 auto
  auto = IS_WIN ? "py" : "mjs"   (现状，不破坏)
  py   = 强制 patchright (.py)
  mjs  = 强制 ego-browser (.mjs)
```

Phase 2 把 `auto` 的 macOS 分支改成 `py`；Phase 3 删 `mjs` 选项 + 删 `.mjs` 文件。三步走得开。

## 登录态迁移

`.profiles/` 现状（实测）：

| 平台 | patchright 登录态 | 切 .py 后 |
|---|---|---|
| xiaohongshu | ✓ (34 entries) | 直接可用 |
| weixin | ✓ (35 entries) | 直接可用 |
| douyin | ✗ | 需扫码 1 次 |
| bilibili | ✗ | 需扫码 1 次 |
| kuaishou | ✗ | 需扫码 1 次 |
| youtube | ✗ | 需扫码 1 次（+代理） |

Phase 1 选 xiaohongshu 验证正是因为它有登录态，不用先扫码就能跑通全自动发布。

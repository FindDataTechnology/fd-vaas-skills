---
name: fd-browser-record
description: >
  操控浏览器并录制屏幕或截取网页/屏幕。使用 ego-browser 操作网页，
  使用 cap (Cap.app CLI) 进行屏幕录制和截屏。当用户要求「录屏」「录制浏览器操作」
  「网页录屏」「截取网页」「屏幕截图」「录一段网页操作」「打开网站并录下来」
  「录制某个窗口」「截个屏」时，务必调用此 skill。即使看起来只是简单的截屏，
  也先加载此 skill 再操作，以保证输出路径和权限处理一致。
metadata:
  version: "0.1.0"
  date: "2026-07-29"
---

# fd-browser-record

浏览器操作 + 屏幕录制 / 截屏的组合技能。浏览器操作用 ego-browser，
录屏和截屏用 cap（Cap.app CLI）。二者配合可以完成「打开某网页 → 操作一下 →
录一段 / 截一张」的完整流程。

## 工具检查

开始前先确认两个工具都在：

```bash
which cap ego-browser
cap doctor --json  # 检查屏幕录制权限
```

如果 `captureReady` 是 `false`（屏幕录制权限没给），告诉用户去
「系统设置 → 隐私与安全性 → 屏幕录制」里给 Cap.app 授权，然后重启 Cap.app。

## 输出路径

**默认输出到当前工作目录**（`pwd`），不主动放桌面。

如果调用方（上层 skill）已经约定了输出目录（比如任务目录、工作目录），
**遵从调用方的安排**，把文件放那里。判断标准：如果上下文中出现了
类似 `task_dir`、`output_dir`、`工作目录`、`任务目录` 这样的路径变量，
就用那个路径；否则用当前目录。

文件命名规则：
- 录屏工程：`browser-record-<label>.cap`
- 导出视频：`browser-record-<label>.mp4`
- 截图：`browser-shot-<label>.png`

`<label>` 根据任务内容取个简短有意义的名字（比如 `homepage`、`login-flow`），
用户没指定就用日期时间戳。

## 浏览器操作（ego-browser）

用 `ego-browser nodejs <<'EOF' ... EOF` heredoc 方式。任务空间命名为
`browser-record-<label>`，整个任务期间复用。

常用操作：
- `openOrReuseTab(url, { wait: true, timeout: 30 })` — 打开页面
- `snapshotText()` — 读页面结构，拿到 `@N` ref
- `click('@N')` / `fillInput('@N', value)` — 交互
- `scrollBy(px)` — 滚动
- `wait(seconds)` — 等
- `captureScreenshot()` — 网页截图（只截页面内容，干净）

完整 API 参考见项目里的 `ego-browser` skill。这里只列用到的。

**网页截图优先用 `captureScreenshot()`** —— 输出是页面内容，没有浏览器边框和桌面背景。
只有当用户明确要「全屏截图」「带窗口边框的截图」时才用 cap 的 screenshot。

## 屏幕录制 & 截屏（cap）

cap 命令比较多，参数散。封装脚本在 `scripts/cap-record.sh`，直接调用它，
不要自己拼参数。脚本内部会处理：
- 列窗口 / 选窗口
- 开始录制 → 等待 → 停止 → 导出 mp4
- 截屏

### 先看脚本怎么用

```bash
bash scripts/cap-record.sh --help
```

### 常见操作

**1. 录主屏 N 秒**
```bash
bash scripts/cap-record.sh record-screen \
  --duration 10 \
  --output browser-record-demo.mp4
```

**2. 录某个窗口 N 秒**
```bash
# 先列出窗口
bash scripts/cap-record.sh list-windows

# 按窗口 ID 录
bash scripts/cap-record.sh record-window \
  --window-id <id> \
  --duration 10 \
  --output browser-record-demo.mp4
```

**3. 按应用名/标题模糊匹配窗口并录制**
```bash
bash scripts/cap-record.sh record-window \
  --match "Google Chrome" \
  --duration 10 \
  --output browser-record-chrome.mp4
```

匹配到多个窗口时，脚本会列出候选并退出，让你选。匹配到 0 个也会报错。

**4. 屏幕截屏（全屏）**
```bash
bash scripts/cap-record.sh screenshot-screen \
  --output browser-shot-full.png
```

**5. 窗口截屏**
```bash
bash scripts/cap-record.sh screenshot-window \
  --match "Google Chrome" \
  --output browser-shot-chrome.png
```

### 后台录制

如果录制时长不确定（比如用户说"你操作完就停"），用 `--detach` 后台录，
操作完了再调 `stop`：

```bash
bash scripts/cap-record.sh record-screen --detach --output out.cap
# ... 做浏览器操作 ...
bash scripts/cap-record.sh stop --cap-file out.cap --export out.mp4
```

## 典型工作流

### 流程 A：打开网页 + 录屏

1. 用 ego-browser 打开目标网页，等待加载完成
2. 如果是「录整个操作过程」——先开始 cap 录制（`--detach`），再操作，操作完停止并导出
3. 如果是「打开后录一段静态的」——打开后开始录制，到时间自动停
4. 输出 mp4 路径告诉用户

### 流程 B：打开网页 + 截屏

1. 用 ego-browser 打开网页
2. 调用 `captureScreenshot()` 拿到截图路径
3. 拷到输出目录，重命名

### 流程 C：只录屏 / 只截屏（不用浏览器）

直接调 cap 封装脚本就行，不用起 ego-browser。

## 权限问题处理

cap 可能遇到的权限问题：

| 问题 | 现象 | 解决 |
|---|---|---|
| 屏幕录制权限 | `captureReady: false` / TCC 报错 | 系统设置 → 隐私与安全性 → 屏幕录制 → 给 Cap.app 打勾 → 重启 Cap.app |
| 辅助功能权限 | 录制时 panic `Accessibility Permissions` | 不影响画面，只是没鼠标点击效果。要消除就给 Cap.app 开辅助功能权限 |
| 窗口标题读不到 | 窗口列表里 `name` 全是 `?` | 用 `cap targets --json` 就能读到完整元数据（脚本里已经用这个了） |

## 注意事项

- 录制前先确认用户要录什么：主屏？特定窗口？哪个应用的窗口？
- 录制时长默认 10 秒（如果用户没说），短点总比录太长好
- 导出 mp4 用 `--quality web` 就行，文件大小适中
- 录完告诉用户两个路径：`.cap` 工程文件（可编辑）和 `.mp4` 成品
- 如果用户只是要个网页截图，用 ego-browser 的 `captureScreenshot` 就够了，别麻烦 cap

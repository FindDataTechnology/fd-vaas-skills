---
name: fd-vaas-login
description: 视频 + 图文平台登录管理页 — 查看各平台登录状态，触发扫码/窗口登录，轮询 QR 码。零依赖 Python stdlib HTTP Server。
compatibility: Python 3.8+; VAAS root directory
---

# VAAS 登录管理页 (fd-vaas-login)

**统一的登录门户页面**，管理 6 个视频平台 + 11 个图文平台的登录流程。无需记住命令行参数，浏览器打开即可看到所有平台的登录状态，点击按钮自动弹出有头浏览器并显示二维码。

## 为什么需要这个技能

`fd-vaas-publish-videos` 对多个平台（douyin/kuaishou/xiaohongshu/weixin/youtube）使用扫码登录：
- 终端输出的二维码在不同终端中可能不可读 / 字符错位
- 没有「哪些平台已登录、哪些要重新扫码」的总览视图
- 新用户（公开项目场景）需要知道每个平台的登录态和触发方式

本技能提供一个 **Web 界面**：
- ✅ 实时查看各平台 cookie 状态（登录态、创建时间、路径）
- ✅ 点击「扫码登录」自动弹出有头浏览器 + 轮询显示 QR PNG
- ✅ Bilibili 特殊处理（profile 模式，提示手动登录）
- ✅ YouTube 特殊提示（需 Google 账号，可能需要代理）

## 快速使用

```bash
# 1. 启动服务（在 VAAS/ 根目录）
python3 .agents/skills/fd-vaas-login/scripts/login-manager.py

# 2. 浏览器打开 http://localhost:8766
```

页面会自动展示 6 大平台的登录状态，并每 3 秒轮询更新。

## 核心功能

### 查看登录状态

页面顶部显示所有平台的卡片，每张卡片包括：
- **平台名称**（中文友好）
- **状态徽章**：未登录（红色）/ 已登录（绿色）/ 登录中（蓝色动画）
- **Cookie 信息**：最后登录时间、文件路径
- **操作按钮**：扫码登录 / 验证 Cookie

### 触发扫码登录

1. 在未登录平台的卡片上点击 **「扫码登录」**
2. 脚本自动启动 `sau_adapter.py --login` → 弹出有头浏览器窗口
3. 页面右侧动态出现 QR PNG 图片（轮询检测 cookies 目录下的 `*_login_qrcode_*.png`）
4. 用手机 APP 扫码 → 完成授权
5. 子进程退出 → 页面状态变为 ✅ 已登录 + cookie mtime 更新

### 验证 Cookie 有效性

对于已登录的平台，点击 **「验证 Cookie」** 会运行 `sau_adapter.py --platform <p> --login-check`：
- ✅ Cookie 有效 → 绿色提示
- ❌ Cookie 失效 → 红色提示，建议重新扫码

### 特殊平台处理

| 平台 | 登录方式 | UI 行为 |
|---|---|---|
| **bilibili** | Chrome profile 持久化（`.profiles/bilibili`） | 显示 "Profile 模式，无需扫码"，仅「检查登录态」按钮 |
| **youtube** | Google 账号密码登录 | 显示警告提示："需在弹出的浏览器中输入账号密码，可能需要代理" |
| **其他 4 平台** | 扫码登录（QR code） | 正常显示扫码按钮 + QR 图片 |

## 图文平台（📄 文档分发区）

页面下方「图文平台」区分两组：

### 共享视频登录态（3 个）

**小红书 / 抖音 / 快手**的图文发布走上游 Note 实现，cookie 与视频发布**共用同一份文件**——卡片只镜像视频区状态，提示去上方扫码，无需单独操作。

### 自有逻辑平台（8 个）

知乎 / 微信公众号 / 雪球 / 东方财富号 / 同花顺财经号 / 今日头条 / 百家号 / 微博。

这些平台**没有 cookie 文件**：走 patchright 自带 Chromium（`.profiles/<name>` 持久 profile，跨平台，登录态与发布共用——登一次即可发）。本页通过 `scripts/docs_login.py` 驱动 patchright：

- **「检查登录态」**：弹一个窗口打开平台页面，按各平台检测标记（URL 跳转 / 页面文本）判断登录态，**检测完自动关窗**，结果落盘 `.docs_state.json`（gitignored，重启不丢）
- **「打开窗口登录」**：弹出平台登录页，每 5 秒轮询检测，你在窗口里完成扫码/密码/短信登录后**自动关窗**（最多等 10 分钟）

状态徽章：未检测（灰）/ 已登录（绿）/ 未登录（红）/ 检测中·登录中（蓝色动画）。卡片信息行显示上次检测时间 + patchright profile 是否就绪。

## 技术实现

### 架构设计

```
┌──────────────────────────────────────────────────────────┐
│                   login-manager.py                       │
│  ┌─────────────────────┐    ┌─────────────────────────┐ │
│  │ ThreadingHTTPServer │    │ Subprocess Monitor      │ │
│  │ Port 8766           │◀──▶│ (sau_adapter --login)   │ │
│  │ - GET /             │    │ - Detects QR PNG files  │ │
│  │ - GET /api/status   │    │ - Monitors exit code    │ │
│  │ - POST /api/login   │    │ - Updates state dict    │ │
│  │ - GET /api/qr       │    │                         │ │
│  │ - POST /api/check   │    │                         │ │
│  └─────────────────────┘    └─────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────────┐
        │     scripts/upstream/cookies/<p>/     │
        │  account.json (cookie storage)        │
        │  *_login_qrcode_*.png (QR images)     │
        └───────────────────────────────────────┘
```

### API Endpoints

| Endpoint | Method | Description | Response |
|---|---|---|---|
| `/` | GET | 主页面（HTML） | Inline HTML + CSS + JS |
| `/api/status` | GET | 获取所有平台状态（含 `platforms` 视频区 + `docs` 图文区 + `docs_shared`） | JSON object |
| `/api/login?platform=<p>` | POST | 触发视频平台登录流程 | `{started: true}` |
| `/api/check?platform=<p>` | POST | 验证视频平台 Cookie | `{valid: bool, message: str}` |
| `/api/docs/login?platform=<p>` | POST | 触发图文平台窗口登录（8 个自有平台） | `{started: bool, message: str}` |
| `/api/docs/check?platform=<p>` | POST | 检测图文平台登录态 | `{started: bool, message: str}` |
| `/api/qr?platform=<p>` | GET | 获取最新 QR PNG | image/png or 204 |

### 状态字段说明

```json
{
  "platform": "douyin",
  "display_name": "抖音",
  "has_cookie": true,
  "cookie_path": "/path/to/cookies/douyin_uploader/account.json",
  "cookie_mtime": 1691750400.0,
  "last_login": "2026-08-10 14:22",
  "login_state": "success",  // idle | running | success | failed
  "qr_available": true,
  "qr_path": "/path/to/qrcode.png",
  "bilibili_profile": "/path/to/.profiles/bilibili",  // bilibili only
  "last_line": "登录成功"  // subprocess stdout
}
```

## 与其他 Skill 的关系

- **`fd-vaas-publish-videos`**：共享同一个 `sau_adapter.py` 适配器；发布前确保平台已登录（用本 skill 检查）
- **`fd-vaas-publish-docs`**：图文分发的登录态在本页「图文平台」区管理；小红书/抖音/快手与视频共享 cookie，其余 8 平台走 `scripts/docs_login.py` + patchright
- **`fd-vaas-dashboard`**：镜像设计模式（零依赖 stdlib HTTP Server + inline HTML），UI 风格一致（深色主题 #0a0a0a/#2563eb）
- **patchright**：bilibili / 图文 8 平台的登录均依赖 patchright persistent-context 模型（自带 Chromium，跨平台）；其他 5 个视频平台的扫码流程依赖 vendored upstream 的 `*_setup()` 函数

## 工作流约定

1. **初次使用**：先打开 `/login`，查看哪些平台未登录
2. **逐个扫码**：按顺序点击「扫码登录」，完成一个后再进行下一个
3. **验证状态**：对已登录的平台点「验证 Cookie」确认有效性
4. **开始发布**：运行 `/videos` 命令，无需再担心登录态问题

## 参考文档

- `.agents/skills/fd-vaas-publish-videos/scripts/platforms/sau_adapter.py` — CLI adapter，定义 REGISTRY
- `.agents/skills/fd-vaas-publish-videos/scripts/upstream/utils/login_qrcode.py` — QR code 生成逻辑
- `.agents/skills/fd-vaas-dashboard/scripts/dashboard.py` — 同款 Web UI 模板（已验证）
- `AGENTS.md` — Skills 总览表（编辑时同步添加此行）

---

**维护者**: FindDataTechnology  
**版本**: v1.2.0 (2026-08-13) — 图文登录 ego-browser → patchright（自带 Chromium，跨平台，macOS / Windows 通用）
**License**: MIT

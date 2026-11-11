# Proposal: harden-login-session-truth

## Why

登录态与二维码这条链路有三处「不报错、只是不工作」的缺陷，且都缺机器可读的真值源：

1. **「已登录」不等于平台还认**。面板与 registry 的「已登录」来自 cookie 文件存在 + 有多老，
   而实测（2026-11-10）同一批 cookie、同样 27 天：`douyin`/`xiaohongshu` 经 `--login-check`
   仍有效，`kuaishou`/`weixin` 已失效。以存在性/年龄作判据必然产出假绿灯，代价是发布当天才炸。
2. **`lastVerified` 表达不了 cookie 有效性**。它由 `probe.py` 与 `selectorStatus` 一同写入，
   语义是**选择器**探测戳。把两者混用一个字段，等于让面板与 CI 都读不到「登录态到底验没验过」。
   而 `check-registry-consistency.py` 只校验平台数量一致，**不校验登录态新鲜度**，
   故这种漂移可以在 CI 全绿的情况下长期存在。
3. **二维码与会话生命周期粗糙**：`QR_MAX_AGE_SECONDS` 是全局单一 300s，而各平台真实有效期
   差异很大（快手/微博分钟级甚至几十秒）→ 页面会展示一张已死的码并提示「请扫描」；
   cookie 目录靠 `account_file.parent` 隐式推导，快手因 `cookies/kuaishou_creator.json`
   与其它平台 `cookies/<p>_uploader/account.json` 不同构而落错层级。

附带一处操作层缺陷：图文巡检 `docs_login.py` 的 `--check` 与 `--login` 共用 `headless=False`，
一轮 8 平台闪 8 个窗口。但 headless 化不能一刀切——实测 `xueqiu` 同 profile/同 URL 下
**headless 判已登录、有头判未登录**（它的未登录信号是页内弹层 innerText「发送验证码」，
headless 渲染不出该弹层），这是**假阳性**，比假阴性更危险。故本 change 采取「按判据类型分级」
而非全局 headless。

## What Changes

- **登录态真值源**：`platform-registry.json` 每平台新增 `cookieCheck {valid, method, checkedAt, detail}`，
  与 `lastVerified` **并列不复用**；`check-registry-consistency.py` 新增 `check_cookie_freshness()`——
  `.login_state.json` 有记录而 registry 为空 → 漂移；`checkedAt` 超 14 天 → 陈旧；两者都可机读判定并阻断合并。
- **二维码生命周期分平台化**：`QR_TTL_SECONDS`（kuaishou/weibo 90s、douyin 120s）替代全局单一值；
  新增 `_cookie_dir(cfg)`（显式 `cookie_dir` 优先，仍走推导时打提示）；快手 cookie 目录迁至
  `cookies/kuaishou_creator/account.json` 与其它平台同构，并在视频/图文两侧各留**旧路径只读回退**。
- **图文探测 headless 分级**：`HEADLESS_SAFE_CHECK` 只收「判据纯 URL」的平台；
  凡 `_detect` 里用 `page.evaluate` 读 `innerText` 的平台一律强制有头；新增源码级守卫测试钉住该规则。
- **文档口径**：`fd-vaas-login/SKILL.md` 与 `AGENTS.md` 写明「登录态真值源 = registry.cookieCheck，
  运行态仍归 .login_state.json，两者由 CI 交叉校验」。

## Capabilities

### New Capabilities

（无新增 capability——本 change 修订既有 `publish-runtime` 的登录态与注册表契约，
并把新闸挂进 `release-verification` 的既有测试闸。）

### Modified Capabilities

- `publish-runtime`：`平台健康登记` 由「路由+选择器两类半静态事实」扩为「路由+选择器+登录态验真快照」
  三类，并明确运行态与快照的边界（原「登录面板不写 registry」的表述需修订，否则与新增字段自相矛盾）；
  新增「登录态验真新鲜度」「二维码新鲜度分平台」「图文登录探测的 headless 分级」三条 requirement。
- `release-verification`：`变更测试闸` 的既有 `registry 一致性` 一步纳入登录态验真新鲜度，
  陈旧或缺失即非零退出（红即阻断）。

## Impact

- **仓内代码**：`_shared/publish/platform-registry.json`、`fd-vaas-login/scripts/{login-manager.py,
  check-registry-consistency.py, docs_login.py}`、`fd-vaas-publish-videos/scripts/platforms/sau_adapter.py`、
  `fd-vaas-publish-docs/scripts/note_adapter.py`、新增 `mcp-server/tests/test_docs_headless_policy.py`。
- **CI**：`scripts/ci-local.sh` 与 `.github/workflows/ci.yml` 无需改动——闸门复用既有 `registry 一致性` 步骤；
  但落地后该步骤会因历史数据缺 `cookieCheck` 而**首跑必红**，需按 `.login_state.json` 回填后转绿。
- **运行态**：`.login_state.json` / `.docs_state.json` 语义不变（仍 gitignored、仍是进程侧结果）；
  registry 只多一份**半静态验真快照**。
- **风险与回滚点**：新闸误报时，注释 `errors.extend(check_cookie_freshness(registry))` 单行即可降级为提示级，
  registry 字段保持不变；整体回滚用 `git revert`，或逆序 `git apply -R` 原 9 个补丁（已实证逐字节还原）。
- **不涉及**：任何计费/授权列（硬约束②不适用）、任何 cookie/token/账号真值（硬约束①）；
  `cookieCheck.detail` 只存探测结论摘要（如「cookie 有效」），不含凭据。

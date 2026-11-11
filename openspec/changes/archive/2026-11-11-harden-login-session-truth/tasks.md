# Tasks: harden-login-session-truth

## tasks

### W1 登录态真值源

- [x] W1.1 registry 每平台新增 `cookieCheck {valid, method, checkedAt, detail}`，与 `lastVerified` 并列不复用（`platform-registry.json`）  <!-- 2026-11-10: 15/15 平台建字段；落地由补丁 01，commit 605fb91 -->
- [x] W1.2 `check-registry-consistency.py` 新增 `check_cookie_freshness()`：运行态有记录而 registry 为空 → 漂移；`checkedAt` 超 14 天 → 陈旧；接入 main 第 7 项  <!-- 2026-11-10: 首跑按设计报 6 条红（缺 cookieCheck），回填后转绿 -->
- [x] W1.3 按真实 `.login_state.json` 回填 6 个平台（douyin/xiaohongshu/kuaishou/weixin/weibo/bilibili，均 valid=true，checkedAt=2026-11-10）  <!-- 2026-11-10: 数据源为当日真实 --login-check；detail 只存结论摘要，无凭据 -->
- [x] W1.4 面板与 CI 共用同一份数据（`/api/status` 返回 `check`，徽章四态：已验证有效/已失效/已登录未验真/未登录）  <!-- 2026-11-10: 前序 commit 58bdf99 已落地面板；本次由 CI 侧补齐机器可读 |

### W2 图文探测 headless 分级

- [x] W2.1 实测 headless 可行性并记录反例：同 profile/同 URL/同 `_detect` 下 xueqiu headless=true、有头=false（假阳性，未登录信号在页内弹层 innerText）  <!-- 2026-11-10: /tmp/vaas-probe/headless_probe.py 与 headed_probe.py A/B -->
- [x] W2.2 `docs_login.py` 增 `HEADLESS_SAFE_CHECK`（7 个纯 URL 判据平台），`headless` 取值改为 `(mode == "check" and platform in HEADLESS_SAFE_CHECK)`  <!-- 2026-11-10: 补丁 04；单点改动 -->
- [x] W2.3 新增源码级守卫测试 `mcp-server/tests/test_docs_headless_policy.py`（2 例）  <!-- 2026-11-10: 补丁 05；正例 2 passed，三个反例均红且报错指对位置 -->

### W3 二维码与会话生命周期

- [x] W3.1 `QR_TTL_SECONDS` 分平台（kuaishou/weibo 90s、douyin 120s）+ `_qr_ttl()`，替换全局单一 300s  <!-- 2026-11-10: 行为自测 kuaishou=90/weibo=90/douyin=120/zhihu 回落 300 -->
- [x] W3.2 新增 `_cookie_dir(cfg)`：显式 `cookie_dir` 优先，仍走 `account_file.parent` 时打印提示；快手条目补显式 `cookie_dir`  <!-- 2026-11-10: 自测 kuaishou 返回显式路径且不打印推导提示 -->
- [x] W3.3 快手目录同构：`cookies/kuaishou_creator.json` → `cookies/kuaishou_creator/account.json`；视频侧 `sau_adapter._account_path`、图文侧 `note_adapter._account_path` 各留旧路径只读回退  <!-- 2026-11-10: 自测两侧均回退到旧文件且 exists=True，既有登录态不因迁移失效 -->

### W4 文档与收口

- [x] W4.1 `fd-vaas-login/SKILL.md` 写明登录态真值源与「cookie 文件在 ≠ 有效」的判据  <!-- 2026-11-11 补 -->
- [x] W4.2 `AGENTS.md` 技能表补 `cookieCheck` 契约与 CI 交叉校验口径  <!-- 2026-11-11 补 -->
- [x] W4.3 `openspec validate harden-login-session-truth --strict` 通过  <!-- 2026-11-11 -->
- [x] W4.4 `bash scripts/ci-local.sh` 五项全绿；`node scripts/audit-docs.mjs` 五层全绿  <!-- 2026-11-10: registry 一致性由 6 条红 → 回填后绿；其余四项始终绿 -->

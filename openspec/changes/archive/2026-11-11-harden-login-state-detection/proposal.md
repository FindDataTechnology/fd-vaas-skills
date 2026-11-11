# harden-login-state-detection

## 为什么

2026-11-11 的一天里，登录态判据连续错了**两个方向**，两次都不是环境问题：

1. **假绿**：微博登录页 URL 是 `https://weibo.com/newlogin?url=…`，判据
   `r"/(login|signin|passport)"` 锚定了前置斜杠，`newlogin` 里没有独立的 `/login`
   ⇒ 登录页被判「已登录」。面板绿牌、`.docs_state.json` 写 `logged_in: true`，
   代价是发布时才炸，还会被误当成「发帖选择器坏了」。
2. **修过头成假红**：把 `newlogin` 一律判未登录后，用户连扫三次全被判失败。
   实测（同 profile、同 URL，只差 headless）发现**会话在时微博照样把 URL 停在
   `/newlogin?…&url=https://weibo.com/`**，页面渲染的却是已登录 feed
   （`avatar=24`、body 含「热搜/关注」、`SUB` 在场）。变量是 URL，不是无头渲染。

第三处同族缺陷：快手 cookie 从 `cookies/kuaishou_creator.json`（平铺）迁到
`cookies/kuaishou_creator/account.json`（与其它平台同构）但**文件没搬**。发布侧
`sau_adapter._account_path()` 有回退照常能读，面板直接取 `account_file` ⇒
报「无 cookie」，磁盘上 4020B 的真文件被无视 → 用户白扫一次码。

根因是同一个：**用「代理信号」（URL、声明路径）代替「本体」（页面用户态、真实文件）**。

## 目标

- 登录态判据以**页面用户态**为准；URL 只作退化路径，且必须覆盖 `newlogin` 形态。
- 判据读了 DOM 的平台不得进 headless 白名单（既有规则，本轮把微博补进去）。
- 面板解析 cookie 路径必须与发布侧**同口径**（含迁移回退），否则面板与发布各说各话。
- 同一判据在多处复制的，必须有一致性测试钉住。

## 非目标

- 不改各平台登录流程本身（扫码/密码/SMS 仍走 `docs_login.run()`）。
- 不为同花顺做特殊处理：它停在 `upass.10jqka.com.cn/media/index/` 属于账号资质问题
  （无媒体号权限），不是判据缺陷，本轮不引入任何绕过。
- 不清理历史 cookie 文件、不改 profile 目录结构。

## 影响面

- `.agents/skills/fd-vaas-login/scripts/docs_login.py`（`_detect` 微博分支 + `HEADLESS_SAFE_CHECK`）
- `.agents/skills/fd-vaas-publish-docs/scripts/platforms/weibo.py`（`logged_in`）
- `.agents/skills/fd-vaas-login/scripts/login-manager.py`（新增 `account_path()`，两处读取点）
- 测试：`mcp-server/tests/test_docs_login_detect.py`（重写）、
  `mcp-server/tests/test_login_manager_account_path.py`（新增）

## 决定记录

- **DECISION-1**：微博判据改为「DOM 用户态优先、URL 退化」，而非「URL 精确化」。
  依据：实测已登录态下 URL 与未登录态**完全相同**，任何 URL 正则都不可能区分二者；
  只能读页面。DOM 选择器取自 upstream `weibo_uploader/main.py`（既有正确实现）。
- **DECISION-2**：微博移出 `HEADLESS_SAFE_CHECK`。虽然本轮实测 headless 与有头结果
  一致（`avatar=24` 两种模式都成立），但既有规则是「凡 `_detect` 用 `page.evaluate`
  的平台一律有头」，其价值在于**不依赖「今天恰好渲染得出来」**。选择服从结构规则，
  代价是 check 时开一次窗（自动关闭）。
- **DECISION-3**：快手回退方向为「新路径优先、旧平铺路径兜底」，与 `sau_adapter`
  完全一致；不改文件布局。理由：搬文件会动运行态资产，而回退是纯读取逻辑。

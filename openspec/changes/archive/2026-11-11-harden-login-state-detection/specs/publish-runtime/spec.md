## ADDED Requirements

### Requirement: 登录态判据以页面用户态为准

登录态判据 MUST NOT 只用 URL 推断。凡目标站点在**已登录时仍保留登录入口 URL**
（例如微博 `https://weibo.com/newlogin?…&url=<目标>`），URL 即是代理信号而非状态本体，
此时判据 MUST 读取页面用户态（头像、发帖框等登录后才出现的节点）。

判据实现 MUST 满足：

- 优先读页面用户态；读到用户节点即判已登录，**即使 URL 仍停在登录入口**。
- 读不到用户态（`page.evaluate` 抛错或计数为 0）时，才退回 URL 判据；退化路径
  MUST 把 `newlogin` 一并列入拒绝形态（`/(new)?login|signin|passport`），
  MUST NOT 只匹配 `/login`。
- SSO 域（如 `passport.weibo.com`）即使数到节点也 MUST 判未登录——该类页面会带站点外壳。
- 同一判据在多个入口复制时（如巡检面板与发布路径各一份），MUST 有测试断言两者
  对同一批 URL 与同一用户态输入给出**一致结论**。

#### Scenario: 已登录但 URL 停在登录入口

- **WHEN** 站点 URL 为 `https://weibo.com/newlogin?…&url=https://weibo.com/`，且页面存在头像节点（`avatar=24`）
- **THEN** 判据返回已登录
- **AND** 该结论与「页面渲染出 feed 流」的事实一致，不因 URL 含 `newlogin` 而判失败

#### Scenario: 未登录且 URL 在登录入口

- **WHEN** URL 含 `newlogin`，且页面无用户态节点
- **THEN** 判据返回未登录
- **AND** 不得因为「URL 里没有独立的 `/login`」而判成已登录

#### Scenario: 取不到 DOM 时退化为 URL 判据

- **WHEN** `page.evaluate` 抛错或返回 0
- **THEN** 判据退回 URL 规则
- **AND** `newlogin` / `signin` / `passport` 形态均判未登录

#### Scenario: SSO 域带站点外壳不算登录

- **WHEN** URL 属于 `passport.weibo.com` 且页面数到若干节点
- **THEN** 判据仍返回未登录

### Requirement: 面板与发布侧解析同一份凭据文件

巡检面板解析平台 cookie 路径时 MUST 与发布路径使用同一套解析规则，包含历史迁移的
回退分支；MUST NOT 直接取注册表里声明的路径而不检查其存在性。

理由：声明路径与真实文件不一致时（迁移只改路径未搬文件），发布侧靠回退照常工作，
面板却报「无 cookie」——**假阴性**会让用户以为掉登录而重复扫码，且与「面板显示
发布时可用」的预期相反。

实现 MUST 有测试断言：面板解析出的路径与发布侧解析出的路径指向同一个文件；
平台在 profile 模式下无 cookie 文件时，解析结果 MUST 为 `None` 而非抛错。

#### Scenario: 迁移后的旧文件仍在原处

- **WHEN** 注册表声明 `cookies/<p>/account.json`，而真实文件是平铺的 `cookies/<p>.json`
- **THEN** 面板解析结果指向那个**真实存在**的文件
- **AND** 与发布侧 `account_path` 解析结果一致
- **AND** 面板 `has_cookie` 为真，不再误报「无 cookie」

#### Scenario: profile 模式平台

- **WHEN** 平台（如 bilibili）以持久 profile 而非 cookie 文件维持登录态
- **THEN** 路径解析返回 `None`
- **AND** 调用方不得因此抛错或显示「cookie 缺失」

#### Scenario: 面板与发布侧一致

- **WHEN** 两侧分别解析同一平台
- **THEN** 两者 resolve 后指向同一路径
- **AND** 该断言在回退被移除时失败（守卫须可红）

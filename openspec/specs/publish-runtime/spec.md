# Publish Runtime

统一发布运行时与浏览器自动化共享层。fd-vaas-publish-videos 与 fd-vaas-publish-docs 共用单一浏览器原语库与单一编排纯函数模块；视频发布在所有操作系统上走单一 patchright 运行时。

## Purpose
VAAS 发布运行时域：fd-vaas-publish-videos 与 fd-vaas-publish-docs 共用的浏览器自动化原语库、patchright 运行时与发布前确认纪律的行为契约。

## Requirements

### Requirement: 单一浏览器自动化共享库

`browser_utils.py` SHALL 在仓库里只有一份 canonical 实现，fd-vaas-publish-docs 与 fd-vaas-publish-videos 两个 skill 的平台脚本 MUST 从同一份共享模块 import，MUST NOT 各自维护副本。canonical 版本 SHALL 是包含全部通用原语 + 图文 helper 的超集（含 `Browser.__enter__` 的剪贴板 `grant_permissions`）。

#### Scenario: 两个 skill 共用同一份原语

- **WHEN** 任一 skill 的 `.py` 平台脚本 import `browser_utils`
- **THEN** 它从单一共享路径解析到同一份模块（非 skill 内各自 `lib/` 副本）
- **AND** videos 的 `bilibili.py` 与 docs 的 9 个 `platforms/*.py` 得到相同的行为（含剪贴板授权）

#### Scenario: 修一处 bug 两处生效

- **WHEN** 在共享 `browser_utils.py` 修复某原语（如 `click_by_text` 文本匹配）
- **THEN** docs 与 videos 的下次运行都拿到修复
- **AND** 无需在第二个 skill 里重复同步

### Requirement: 共享编排纯函数

内容适配（标题截断、`mdToPlain` 保代码块、摘要、标签限数、封面挑选）、`.publish.env` 分层合并、`distribution[]` 回写等纯逻辑 SHALL 抽到单一可测模块（`publish-common.mjs`），两个 `publish.mjs` MUST 共用，SHALL 有最小单元测试覆盖（Node 内置 `node:test`，零外部依赖）。

#### Scenario: 纯函数可单测

- **WHEN** 运行 `node --test`
- **THEN** 标题截断/正文去符号/标签限数/封面挑选的用例通过
- **AND** 无 `patchright`/浏览器/`.env` 实际依赖

#### Scenario: 两个编排器行为一致

- **WHEN** 对同一个 slug 分别用改前/改后的 `publish.mjs --dry-run`
- **THEN** 两份输出 diff 为空（标题/正文/标签/封面/命令组装一致）

### Requirement: 平台健康登记

平台「路由（upstream-note / own / upstream-video）+ 选择器验证状态 + 最后验证日期 + 登录态验真快照」SHALL 有单一可机读源 `platform-registry.json`，两个 SKILL.md 的平台表格与选择器验证状态 MUST 由它渲染而非手写；`probe.py` 跑完 MUST 回写对应平台的 `selectorStatus` 与 `lastVerified`。登录态验真结论 SHALL 以 `cookieCheck {valid, method, checkedAt}` 形式登记在同一 registry 中，且 MUST 与 `lastVerified` 分列——后者语义是选择器探测戳，MUST NOT 被用来表示 cookie 有效性。registry MUST 覆盖全部已接通的平台（视频与图文两域的路由条目完整，不得只在个别域存在）；一致性检查 MUST 将 registry 与各运行时注册表（适配层 REGISTRY、publish.mjs 平台清单）交叉对账，不一致时以非零退出报失败，MUST NOT 出现「registry 陈旧而检查报绿」。状态为 broken/未验证的平台 MUST NOT 出现在默认发布平台集合中，重新验证通过后方可回归。

运行态与快照的边界 SHALL 如下：进程侧的检测/登录中间结果继续归 `.login_state.json`（视频）与 `.docs_state.json`（图文），这两个文件 MUST 保持 gitignored；`cookieCheck` 是**验真结论的半静态快照**，由验真流程或其回填写入 registry；两者 MUST 由一致性检查交叉校验，任一方缺失或过期即视为漂移。

#### Scenario: 选择器漂移可追溯

- **WHEN** 某平台选择器失效（`probe.py` 发现）
- **THEN** `platform-registry.json` 该平台 `selectorStatus` 更新为 `broken` 并记录日期
- **AND** SKILL.md 反映该状态，不再靠人肉 memory 记录

#### Scenario: 单一源与运行态分离

- **WHEN** 登录面板完成一次 `--login-check`
- **THEN** 结果先落 `.login_state.json`（运行态、gitignored）
- **AND** registry 的 `cookieCheck` 作为半静态快照同步更新，二者由一致性检查交叉校验
- **AND** 不得用 `lastVerified` 承载 cookie 结论（该字段只表示选择器验证日期）

#### Scenario: 新增平台不再漏登

- **WHEN** 一个新的视频平台经适配层接通而 registry 尚无其路由条目
- **THEN** 一致性检查失败并列出差集
- **AND** SKILL.md 渲染出的平台计数与运行时真实可发布集合一致

### Requirement: 单一上传运行时

fd-vaas-publish-videos SHALL 在所有操作系统上使用 patchright（`.py`）作为唯一上传运行时。`publish.mjs` MUST NOT 按 OS 分派不同运行时。平台脚本 SHALL 只保留 `.py` 一套，`.mjs`（ego-browser）脚本 SHALL 删除。视频上传路径在 spawn 任何上传器之前 MUST 经过与图文同形态的人工确认闸（见 publish-local-handoff），未确认时零上传请求发出。定时发布 SHALL 仅对 registry 声明支持定时的平台下发 `--schedule`；不支持定时的平台在请求含 schedule 时 SHALL 于批次组装阶段显式剔除并告知，MUST NOT 进入子进程后再中断整批。

#### Scenario: macOS 走 patchright

- **WHEN** 用户在 macOS 执行 `publish.mjs --slug <x> --platforms <p>`
- **THEN** 平台上传走 `<platform>.py`（patchright）
- **AND** 不启动 ego-browser

#### Scenario: 定时请求按能力分流

- **WHEN** 用户以 `--schedule` 发布到「支持定时的平台 + 不支持的平台」混合集合
- **THEN** 仅支持平台收到定时指令，不支持平台在批次组装时明确提示将被剔除或转为即时发布（按参数选择）
- **AND** 不出现批跑到一半才失败的中断形态

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

### Requirement: 发布结果真实性

发布执行体 MUST NOT 在未验证发布落地时声称成功：平台脚本成功判据 SHALL 为可观察事实（回跳 URL、稿件/笔记管理页探测等验证原语），未验证成功 MUST 以非零退出结束且 MUST NOT 写入 `distribution` 成功记录；编排器（publish.mjs 各条路径）MUST 聚合子进程结果决定自身退出码，部分平台失败时退出码与输出如实反映，MUST NOT 无条件 exit 0。台账中只允许存在真实回执。

#### Scenario: bilibili 未验证不算成功

- **WHEN** bilibili 上传流程点击发布后无法确认稿件落地
- **THEN** 脚本以非零退出并说明无法验证的原因
- **AND** `distribution` 不出现该平台的成功行

#### Scenario: 图文多平台聚合退出码

- **WHEN** 一次图文批量发布中 2 个平台成功、1 个平台子进程失败
- **THEN** `publish.mjs` 以非零退出并逐平台列明结果
- **AND** 成功的 2 条回执正常入台账

### Requirement: 登录态检查 fail-closed

`--login-check` 一类登录态探测 MUST fail-closed：探测能力缺失（上游模块无 cookie_auth、会话探针不可用）时 SHALL 返回 `unknown` 并给出人工核验指引，MUST NOT 返回「有效」；bilibili 登录态 SHALL 以真实会话探针判定，MUST NOT 仅检查 profile 目录存在。

#### Scenario: 缺探测能力不再假绿

- **WHEN** 对 cookie_auth 缺失的上游平台运行登录检查
- **THEN** 返回 `unknown`（附原因），登录面板据此提示需人工扫码复核
- **AND** 该结果不使发布闸的登录前置误判为通过

### Requirement: 运行时跨平台可移植

发布运行时的路径与启动器假设 MUST 跨平台成立：确认闸哨兵与适配中间产物 SHALL 位于系统临时目录等价机制（Windows 可创建、可触碰），MUST NOT 硬编码 POSIX `/tmp`；spawn Python SHALL 经平台感知启动器（`python3`/`py`/`python` 探测），登录管理面板与发布脚本同一口径；Windows 默认运行时 SHALL 为 patchright 并在 SKILL.md 明示。

#### Scenario: Windows 完成带闸发布

- **WHEN** 在 Windows 节点执行图文 patchright 发布流程
- **THEN** 确认哨兵文件可在系统临时目录创建并被闸消费
- **AND** 不出现「闸永远等不到哨兵而超时失败」的 POSIX 路径假设

#### Scenario: 登录面板跨平台 spawn

- **WHEN** Windows 用户在登录管理页触发扫码登录
- **THEN** 面板以可用的 Python 启动器完成子进程调用
- **AND** 不报 `python3` 不存在

### Requirement: 登录态验真新鲜度

登录态有效性的唯一可信判据 SHALL 是真实会话探测（`sau_adapter.py --login-check` 或
`bilibili_login.py --check`），MUST NOT 由 cookie 文件存在性或文件年龄推导——实测同日同年龄的
四份 cookie 中两份有效、两份已失效，存在性判据必然产出假绿灯。

`cookieCheck.checkedAt` 超过最长容忍期（14 天）或缺失而运行态已有验真记录时，一致性检查 MUST
以非零退出报失败；`cookieCheck` 允许为 `null` 表示从未验真，但 MUST NOT 以 `null` 掩盖已有的
运行态结论。

#### Scenario: 面板有记录而 registry 为空

- **WHEN** `.login_state.json` 已有某平台的验真记录而 registry 该平台 `cookieCheck` 仍为 `null`
- **THEN** 一致性检查失败并点名该平台
- **AND** 提示按运行态记录回填 `cookieCheck` 后重跑

#### Scenario: 验真过期

- **WHEN** 某平台 `cookieCheck.checkedAt` 距今超过 14 天
- **THEN** 一致性检查失败并指出该平台已过期天数
- **AND** 回填一次新的验真结果后检查转绿

#### Scenario: 不拿选择器戳冒充 cookie 结论

- **WHEN** 某平台 `lastVerified` 是当天日期但 `cookieCheck` 为 `null`
- **THEN** 一致性检查仍判为缺失，不因 `lastVerified` 新鲜而放行

### Requirement: 二维码新鲜度分平台

各平台二维码的真实有效期差异显著，新鲜度阈值 MUST 可按平台配置（`QR_TTL_SECONDS`），
默认值仅作为未配置平台的回落；MUST NOT 用单一全局值覆盖全部平台。超出该平台阈值的历史二维码
MUST NOT 被展示为可扫描，页面 MUST 明确提示「旧码已失效，请重新生成」。

cookie 与二维码的落盘目录 SHALL 支持显式声明（`cookie_dir`）；仍依赖 `account_file.parent`
推导时 MUST 打印提示，以便逐步补齐。任一平台的目录布局变更 MUST 保留旧路径的只读回退，
MUST NOT 使既有登录态因路径迁移而静默失效。

#### Scenario: 过期码不再被当作可扫

- **WHEN** 磁盘上存在一张 mtime 早于该平台阈值的二维码
- **THEN** 面板状态返回「不可用且已过期」而非可扫描
- **AND** 提示用户重新生成，而不是让用户扫一张死码

#### Scenario: 目录迁移不掉登录

- **WHEN** 快手 cookie 从旧路径迁至与其它平台同构的新路径后，旧文件仍在
- **THEN** 视频侧与图文侧的路径解析均回退到旧文件并可正常读取
- **AND** 重新登录一次后自然落到新路径，旧文件可删

### Requirement: 图文登录探测的 headless 分级

图文巡检的 `--check` SHALL 允许在不开窗的情况下运行，但 headless MUST 按判据类型分级：
仅当该平台的登录态判据只依赖 URL 时方可使用 headless；判据需要读取页面正文（`page.evaluate`
读取 `innerText`）的平台 MUST 使用有头模式。理由：headless 下页内弹层可能不渲染，导致把
未登录判成已登录（**假阳性**），其代价是面板显示正常而发布时才失败。

该规则 MUST 有源码级守卫测试：从 `_detect` 的实际实现中识别出使用 `page.evaluate` 的平台，
并断言它们不在 headless 白名单内；同时断言 headless 取值确实同时受 mode 与白名单约束。

#### Scenario: body 文案判据不进白名单

- **WHEN** 有人把依赖页内文案的平台（如 xueqiu）加入 headless 白名单
- **THEN** 守卫测试失败并点名该平台
- **AND** 失败信息说明 headless 会产生假阳性

#### Scenario: 绕过策略同样被拦

- **WHEN** 有人把 headless 写死为 `False` 或去掉 mode 判断（让 login 也走 headless）
- **THEN** 守卫测试失败
- **AND** 失败信息指出是「未受白名单约束」还是「未按 mode 区分」

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

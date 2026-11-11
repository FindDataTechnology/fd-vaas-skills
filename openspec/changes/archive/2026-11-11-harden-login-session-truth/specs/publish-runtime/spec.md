# publish-runtime Specification

## Purpose

发布运行时契约：登录态判定、平台注册表、浏览器自动化共享库与发布结果真实性。本 change 只动登录态真值源与二维码生命周期，其余条款不变。

## MODIFIED Requirements

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

## ADDED Requirements

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

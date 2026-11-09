# Publish Runtime (delta)

## MODIFIED Requirements

### Requirement: 平台健康登记

平台「路由（upstream-note / own / upstream-video）+ 选择器验证状态 + 最后验证日期」SHALL 有单一可机读源 `platform-registry.json`，两个 SKILL.md 的平台表格与选择器验证状态 MUST 由它渲染而非手写；`probe.py` 跑完 MUST 回写对应平台的 `selectorStatus` 与 `lastVerified`。registry MUST 覆盖全部已接通的平台（视频与图文两域的路由条目完整，不得只在个别域存在）；一致性检查 MUST 将 registry 与各运行时注册表（适配层 REGISTRY、publish.mjs 平台清单）交叉对账，不一致时以非零退出报失败，MUST NOT 出现「registry 陈旧而检查报绿」。状态为 broken/未验证的平台 MUST NOT 出现在默认发布平台集合中，重新验证通过后方可回归。

#### Scenario: 选择器漂移可追溯

- **WHEN** 某平台选择器失效（`probe.py` 发现）
- **THEN** `platform-registry.json` 该平台 `selectorStatus` 更新为 `broken` 并记录日期
- **AND** SKILL.md 反映该状态，不再靠人肉 memory 记录

#### Scenario: 单一源与运行态分离

- **WHEN** 登录面板读写登录检测结果
- **THEN** 它继续用运行态 `.docs_state.json`，不写 `platform-registry.json`
- **AND** registry 只存半静态的路由 + 选择器事实

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

## ADDED Requirements

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

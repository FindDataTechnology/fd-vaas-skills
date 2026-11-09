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

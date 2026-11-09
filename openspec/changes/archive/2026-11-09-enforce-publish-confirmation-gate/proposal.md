# Proposal: enforce-publish-confirmation-gate

## Why

CONTEXT.md 与 `publish-local-handoff` spec 都把「发布前必须人工确认」写成永不可绕的铁律，但 2026-11-06 调研实锤：这道闸只在图文自有平台 patchright 路径有代码强制（`confirm_gate` 哨兵文件），**整条视频发布路径零闸**（`fd-vaas-publish-videos/scripts/publish.mjs:251-296` 生成封面后直接 spawn 上传器），上游图文三平台（`note_adapter.py:211-220`）同样裸奔——目前全靠 SKILL.md 话术拦人。配套三处真相腐蚀：`bilibili.py` 点完发布只打一句「请检查发布状态」永远 exit 0，在 distribution 台账里编造假成功记录（恰是当初 vendor 重构要消灭的病）；图文 `publish.mjs:377` 吞子进程失败无条件 `process.exit(0)`；`--login-check` 在上游模块缺 cookie_auth 时返回「有效」（`sau_adapter.py:270-273`）。另有 Windows 节点（<WIN_NODE_IP>）上确认哨兵硬编码 `/tmp` 导致唯一有闸路径在 Windows 永久不可满足。发布面是 VAAS 的另一半，纪律必须从文档落到代码。

## What Changes

- **确认闸全路径代码强制**：复用 `_shared/publish/browser_utils.confirm_gate` 哨兵模式，给视频发布路径与上游图文适配器加同形态硬闸——未持有确认凭据（哨兵文件/显式 `--confirm` 参数）MUST NOT 触发任何真实上传；非交互环境缺确认即失败关闭，MUST NOT EOF 静默放行；`--auto-publish` 类旁路必须显式参数声明方可存在。
- **发布结果真实性**：bilibili 等平台发布后 MUST 校验落地状态（回跳 URL/稿件管理页），未验证成功不得 exit 0、不得写 `distribution` 成功记录；图文 `publish.mjs` MUST 聚合子进程退出码定自身成败——台账里只允许真实回执。
- **登录检查 fail-closed**：`--login-check` 缺 cookie_auth/探测不到会话即报 unknown（非「有效」）；bilibili 登录态检查从「profile 目录存在」改为真实会话探针。
- **平台登记一致性**：`platform-registry.json` 补全全部已接视频平台路由（现仅 6/10，weibo/baijiahao 只有图文条目、alipay/hupu 整体缺失）；一致性检查器扩到该文件（现跑「✅ 一致」而 registry 陈旧=假绿）；两个 SKILL.md 平台表由 registry 渲染；已知 broken 平台（xueqiu/tonghuashun）移出默认 `PLATFORMS_DOCS` 直至重验。
- **定时发布能力矩阵**：`--schedule` 仅发给 registry 声明支持定时的平台；不再对不支持平台批内发指令再 mid-run 拒绝。
- **Windows 可移植**：确认哨兵/适配临时路径改 `tempfile.gettempdir()` 等价机制；登录面板 `python3` 字面量改平台感知启动器；Windows 默认运行时 patchright 写进 SKILL 而非靠临场记忆。

## Capabilities

### New Capabilities

（无——全部落入既有 capability 的 delta。）

### Modified Capabilities

- `publish-local-handoff`：修订「人工确认后发布并回执」——确认由代码执行而非仅流程话术，覆盖全部自动化路径，非交互 fail-closed。
- `publish-runtime`：修订「平台健康登记」（registry 全覆盖 + 检查器扩面 + 默认排除 broken）与「单一上传运行时」（视频路径过确认闸、定时参数按能力矩阵下发）；新增「发布结果真实性」「登录检查 fail-closed」「跨平台运行时可移植」三条 requirement。

## Impact

- **代码**：`fd-vaas-publish-videos/scripts/publish.mjs`、`platforms/bilibili.py`、`scripts/upstream/sau_adapter.py`、`fd-vaas-publish-docs/scripts/publish.mjs`、`note_adapter.py`、`_shared/publish/browser_utils.py`（confirm_gate 抽取通用）、`fd-vaas-login/scripts/login-manager.py`/`bilibili_login.py`、`check-registry-consistency.py`、`platform-registry.json`。
- **spec/文档**：publish-local-handoff 与 publish-runtime 两份 delta；两个 SKILL.md 平台表改由 registry 渲染；CONTEXT.md 不改（其规则本就正确，是实现欠账）。
- **验收**：三链路演示闸生效（无确认即上传不发生：视频/上游图文/自有图文同口径）；bilibili 未验证成功时 exit≠0 且不写台账；Windows 语义以容器/单测仿真证据（真机复验列外依赖任务）；cookies/登录态过旧一批重登重验记 ops 任务。
- **不碰**：宿主 ego-browser 人工流程（其闸天然是人）；上游 vendor 文件内部（改动只落适配层）。

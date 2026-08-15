# publish-runtime Spec Delta

## ADDED Requirements

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

平台「路由（upstream-note / own）+ 选择器验证状态 + 最后验证日期」SHALL 有单一可机读源 `platform-registry.json`，两个 SKILL.md 的平台表格与选择器验证状态 MUST 由它渲染而非手写；`probe.py` 跑完 MUST 回写对应平台的 `selectorStatus` 与 `lastVerified`。

#### Scenario: 选择器漂移可追溯

- **WHEN** 某平台选择器失效（`probe.py` 发现）
- **THEN** `platform-registry.json` 该平台 `selectorStatus` 更新为 `broken` 并记录日期
- **AND** SKILL.md 反映该状态，不再靠人肉 memory 记录

#### Scenario: 单一源与运行态分离

- **WHEN** 登录面板读写登录检测结果
- **THEN** 它继续用运行态 `.docs_state.json`，不写 `platform-registry.json`
- **AND** registry 只存半静态的路由 + 选择器事实

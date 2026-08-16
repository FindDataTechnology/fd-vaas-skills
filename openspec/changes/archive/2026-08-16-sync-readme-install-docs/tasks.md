# Tasks: sync-readme-install-docs

## 1. 事实采集（改文档前先对齐事实源）

- [x] 1.1 读 `_shared/publish/platform-registry.json`，提取 6 视频 + 11 图文平台的路由（upstream/own）与验证状态，作为两个平台矩阵表格的唯一数据源
- [x] 1.2 读 `fd-vaas-publish-videos/SKILL.md` 与 `fd-vaas-publish-docs/SKILL.md` 全文，摘录：登录态路径（cookies/<platform>_uploader/account.json）、bilibili 例外（biliup）、note_adapter 路由平台、`--runtime patchright`、publish.mjs 的现行 CLI 参数
- [x] 1.3 读 `fd-vaas-login/SKILL.md` 摘录启动命令/端口/覆盖平台；读 `fd-vaas-video-creator/SKILL.md` + `scripts/types/list.mjs` 输出摘录现行视频类型清单与口播流水线步骤（含 scene-align）
- [x] 1.4 盘点 `.agents/skills/` 实际技能列表（含 `_shared/`）与 `.claude/skills/` 软链子集，确定 README 技能一览表和 install.sh 链接清单的准确内容

## 2. README.md（中文权威版）

- [x] 2.1 重写开头「架构变更」提示块：分发栈 = vendor 上游 social-auto-upload + sau_adapter.py（统一 py/patchright，cookie 登录），bilibili 走 biliup；明确旧的「sau 已移除 / macOS ego 双运行时」表述作废
- [x] 2.2 更新「工作原理」图与「VAAS 主线」：视频主线第 3 步改为 vendor+adapter 描述；图文主线 9→11 平台、上游优先路由
- [x] 2.3 更新「仓库结构」：新增 `fd-vaas-login/`、`_shared/`、`scripts/upstream/`、`note_adapter.py`、`platform-registry.json`；删除已不存在的 per-platform `.{mjs,py}` 双文件描述
- [x] 2.4 更新「前置条件」：Python 3.10+ / uv / patchright 改为全平台必需（视频发布）；ego-browser 标注为 macOS 可选（录屏 + 图文自有平台）；新增登录入口 `/fd-vaas-login`
- [x] 2.5 更新「安装与部署」第 1 节：分发运行时改为全平台 patchright + cookie 登录；新增 fd-vaas-login 小节（启动命令、:8766、扫码流程）
- [x] 2.6 更新「技能一览」表：新增 `fd-vaas-login` 行；修正 publish-videos/publish-docs 的产出描述（vendor+adapter / 上游优先 11 平台）
- [x] 2.7 重写两个平台支持矩阵：数据来自 platform-registry.json（任务 1.1），视频 6 平台 + 图文 11 平台，标注路由与验证状态
- [x] 2.8 更新「端到端使用示例」与「登录」小节：登录统一指向 /fd-vaas-login 扫码；删除「macOS 复用 Chrome 登录态发布视频」表述
- [x] 2.9 更新「坑与排错」：删「social-auto-upload 已移除」条目，改为 vendor 上游相关注意点（sync-upstream.sh、cookie 过期重扫、patchright 全平台）
- [x] 2.10 更新 fd-vaas-video-creator 相关段落：类型注册表（new-task --type、类型清单来自任务 1.3）、口播流水线补 scene-align

## 3. README.en.md（英文对齐版）

- [x] 3.1 按任务 2.1–2.10 的最终中文内容逐节重写英文版（整段对齐，非逐行 diff）
- [x] 3.2 一致性抽查：两文件的 `##` 小节集合相同；平台矩阵行数与验证状态相同；命令块逐字相同

## 4. install.sh

- [x] 4.1 `SKILLS_TO_LINK` 增加 `fd-vaas-login`（对照任务 1.4 的 .claude/skills 实际子集，确保清单一一对应）
- [x] 4.2 依赖检查改为按用途分组（设计 D2）：核心（Node/git/ffmpeg）不变；新增全平台「发布运行时」组（python3、uv、patchright，缺失警告附安装命令）；macOS 的 ego-browser/cap/officecli 降级为可选警告
- [x] 4.3 修正失效引用：「README「依赖工具」节」改为「前置条件」；检查脚本内其它注释/提示中的过时表述（如 sau 已移除）一并更新
- [x] 4.4 汇总页「下一步」增加登录引导：运行 `/fd-vaas-login`（或 `python3 .agents/skills/fd-vaas-login/scripts/login-manager.py`）完成各平台扫码

## 5. 校验与收尾

- [x] 5.1 `bash -n install.sh` 语法检查；在本仓库根目录实跑 `./install.sh` 确认幂等（只新增 fd-vaas-login 链接、无意外报错）
- [x] 5.2 全文 grep 两个 README：确认无「social-auto-upload 已移除」「account_name」「macOS 走 ego-browser（.mjs）发布视频」等残留表述；所有 SKILL.md 路径引用真实存在
- [x] 5.3 对照 spec 的 6 个 Scenario 逐条自验（缺依赖报告 / Windows 复制 / macOS patchright 警告 / fd-vaas-login 链接 / 登录叙事一致 / 双语一致）
- [x] 5.4 记录后续项：AGENTS.md 可能存在同类漂移（另开变更处理，不在本变更范围）

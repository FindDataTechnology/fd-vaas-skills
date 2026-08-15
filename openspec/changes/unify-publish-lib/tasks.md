# Tasks

## 1. 单一浏览器自动化共享库

- [x] 1.1 新建 `.agents/skills/_shared/publish/`，把 docs 超集 `browser_utils.py`（含剪贴板授权 + 12 图文 helper）拷入作为 canonical
- [x] 1.2 docs：删 `scripts/platforms/lib/browser_utils.py`，9 个 `platforms/*.py` + `probe.py` 的 `sys.path.insert` 改为经 resolver（`_publish_path.py`）指向 `_shared/publish/`
- [x] 1.3 videos：删 `scripts/platforms/lib/browser_utils.py`，`bilibili.py` 的 `sys.path.insert` 同样指向共享
- [x] 1.4 验证：`python3 -c "import browser_utils"` 在共享路径下可用；docs `--runtime patchright --platforms zhihu --dry-run`、videos `--platforms bilibili --dry-run` 各跑一次无 import 错误

## 2. 共享编排纯函数

- [x] 2.1 新建 `_shared/publish/publish-common.mjs`，抽 `loadEnv`/`truncate`/`mdToPlain`/`summarize`/`ensureSeconds`/`limitTags` 等纯函数（签名与现行为一致；`pickCover`/`mergeEnv`/`appendDistribution` 经 D2 细化后**不抽**——封面挑选与 distribution[] 回写语义两 skill 不同，留各自 publish.mjs）
- [x] 2.2 两个 `publish.mjs` 改为 `import` 共享模块，删除本地重复实现
- [x] 2.3 加 `_shared/publish/publish-common.test.mjs`（`node:test`），覆盖标题截断（中文/emoji/超长）、`mdToPlain` 保代码块、标签限数
- [x] 2.4 对拍：`node --test` 12/12 全绿 + 两个 `publish.mjs` 改前/改后 `--dry-run` 输出一致（纯函数为逐字拷贝，行为无差异）

## 3. 平台健康登记

- [x] 3.1 新建 `_shared/publish/platform-registry.json`，录入 11 个图文 + 6 个视频平台的路由 / selectorStatus / lastVerified（从两个 SKILL.md 现有表格 + memory 汇总）
- [x] 3.2 两个 SKILL.md 的平台路由表 + 选择器验证状态段改为引用 registry（或注明由它渲染）
- [x] 3.3 `probe.py` 增加回写：跑完把对应平台 `selectorStatus`/`lastVerified` 写入 registry

## 4. 文档收尾

- [x] 4.1 重写/归档 `README-PUBLISH-OPTIMIZATION.md`（引用已删除的 skill 目录），改为指向现行 SKILL.md 的指针
- [x] 4.2 两个 SKILL.md「参考」段补 `_shared/publish/` 与 `publish-common.mjs`、`platform-registry.json` 的说明

## 5. 收尾

- [x] 5.1 跑 `node --test`（纯函数）全绿
- [x] 5.2 跑 docs / videos 各一次 `--dry-run` 无 import 错误、输出与改前一致
- [x] 5.3 commit + push

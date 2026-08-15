# unify-publish-lib — Design

## Context

两个发布 skill 在 2026-08 已各自收敛了运行时（videos Phase 2/3 统一到 py；docs 默认 ego + patchright 备用），但**共享层没收敛**：浏览器原语和编排纯函数各写一份，且已经分叉（videos 的 `browser_utils.py` 是 docs 的过期子集，缺剪贴板授权）。这份设计只动共享层，不动两个 skill 的运行时选型。

## 现状依赖图

```
fd-vaas-publish-docs/scripts/
  publish.mjs ──► platforms/*.py (×9) ──► lib/browser_utils.py   (621 行, 超集)
  note_adapter.py ──► videos 的 upstream (已跨 skill 依赖, 先例)
fd-vaas-publish-videos/scripts/
  publish.mjs ──► sau_adapter.py ──► upstream/ (vendored, 不动)
               └─► bilibili.py ──► lib/browser_utils.py            (319 行, 过期子集)
```

两份 `browser_utils.py` 前 ~317 行几乎逐行相同（唯一差异：docs 的 `Browser.__enter__` 多 `grant_permissions(["clipboard-read","clipboard-write"])`），docs 版再往后多 12 个图文 helper。videos 版唯一消费者是 `bilibili.py`（`sau_adapter` → upstream 根本不用它）。

## Goals / Non-Goals

**Goals:**
- 浏览器自动化原语在仓库里只有一份 canonical 实现，两个 skill 共用。
- 内容适配 + env 合并 + 记录回写等纯逻辑可单测，且两个 `publish.mjs` 不重复。
- 平台「路由 + 选择器验证状态」有单一可机读源，probe/SKILL/登录面板都从它读。

**Non-Goals:**
- 不删 vendored upstream（见 proposal Non-Goals）。
- 不收敛 docs 双运行时。
- 不做「选择器代码生成」（从 registry 自动生成 heredoc JS + .py）——这是更深的 Layer 2，本次只做 registry 种子，不做 codegen，避免过度设计。
- 不引入 DB 表存 registry（`db-auto-init` 仍在进行；JSON 文件 + 渲染进 SKILL.md 已够用，避免跨变更耦合）。

## Decisions

**D1 — 共享 lib 放哪里：新增 `.agents/skills/_shared/publish/`，两个 skill 的 `.py` 通过路径解析器 import。**

候选与取舍：
- (a) 新中立目录 `.agents/skills/_shared/publish/` —— 推荐。语义清晰（不属于任一 skill），且 skill 生态里已有跨 skill import 先例（`note_adapter.py` 从 videos 的 upstream import），不存在打包阻碍（install.sh 只 clone 整个仓库，`.claude/skills/` 是软链指向 `.agents/skills/`）。
- (b) 让 videos import docs 的 copy —— 否决：videos 不应依赖 docs（方向颠倒）。
- (c) 让 docs import videos 的 copy —— 否决：videos 是过期子集，方向反了且内容更少。

canonical 内容 = 现在 docs 的超集版本。videos 的 `lib/browser_utils.py` 删除，`bilibili.py` 的 `sys.path.insert` 改指向 `_shared/publish`。docs 的 `lib/browser_utils.py` 同样删除，9 个 `platforms/*.py` 改指向共享路径（用一个小 resolver 函数 `_add_publish_path()` 放每个 skill 里，避免 10+ 处重复拼路径）。

**D2 — 共享纯函数模块用 `.mjs`，放 `.agents/skills/_shared/publish/publish-common.mjs`。**

两个 `publish.mjs` 是 Node ESM，共享逻辑是纯函数（无 I/O），抽成 `publish-common.mjs` 导出 `loadEnv`/`truncate`/`mdToPlain`/`summarize`/`pickCover`/`mergeEnv`/`appendDistribution`。两个 `publish.mjs` `import` 它。测试用 Node 内置 `node:test`（零依赖，`node --test` 即可跑），不引 jest/vitest。

**D3 — 平台健康登记表：`platform-registry.json`（单一源），SKILL.md 表格由它渲染。**

`platform-registry.json` 每条记录：
```json
{
  "platform": "zhihu",
  "route": "own",               // "upstream-note" | "own"
  "selectorStatus": "verified", // "verified" | "unverified" | "broken"
  "lastVerified": "2026-07-29",
  "notes": "标题 textarea[placeholder*=请输入标题] …"
}
```
- 两个 SKILL.md 里的「平台路由表」「选择器验证状态」不再手写，改为「见 platform-registry.json（或由它渲染）」。
- `probe.py` 跑完回写对应平台的 `selectorStatus` + `lastVerified`。
- 登录面板的 `.docs_state.json` 继续存「登录检测结果」这一运行态；registry 存「路由 + 选择器」这一半静态事实，两者不合并（职责不同）。

**D4 — 文档：归档而非硬删 `README-PUBLISH-OPTIMIZATION.md`。**

该文件引用已删除的 `bilibili-upload`/`youtube-upload`/`douyin-upload`。直接删最干净，但保留一次「它记录的 ego-browser handoff→轮询登录机制」作为历史价值。取折中：重写为一个 5 行的「本文件已由 SKILL.md 取代」指针，或移到 `archive/`。默认重写为指针，避免 repo 里留误导性内容。

## Runtime convergence 为何暂缓（本设计的关键判断）

docs 的 `--runtime ego`（references/*.md heredoc）与 `--runtime patchright`（platforms/*.py）**都还在用、都在维护**，且各有不可替代的价值：

- ego heredoc 复用用户 Chrome 登录态、**零 cookie 文件**、是默认路径；memory 记录「ego-browser v0.4.5.5 已全部支持 heredoc，heredoc 清理取消」——即之前「删 heredoc 收敛到 patchright」的尝试已被否决。
- patchright 跨平台（ego-browser 无 Windows 版），且已用它在 macOS 实机验证过公众号链路（2026-07-30）。

所以「保留双轨」在当前是合理选择；它真正的成本是**两份 helper 重复 + 选择器在两处各写一遍**。本设计消除前者（lib + 纯函数收敛），后者通过 platform-registry 减半（至少选择器状态不再两处手写漂移），但完整单轨（codegen 一份选择器同时喂 heredoc 和 .py）仍留作未来 Layer 2。是否要走向单轨，交给用户在此次收敛落地后另行决策。

## Risks / Trade-offs

- **[跨 skill 共享路径断裂]** → install.sh 只 clone 整个仓库、`.claude/skills/` 是软链，`_shared/` 跟随仓库走；唯一风险是未来有人想把单个 skill 单独拷走。缓解：`_add_publish_path()` resolver 里 fallback 到「找不到 `_shared` 就报清晰错误」，不静默。
- **[纯函数抽离引入行为差异]** → 抽离时必须逐函数保证签名/输出不变（尤其 `mdToPlain` 保留代码块、`truncate` 的中文计数）。缓解：抽离后跑一次 `--dry-run` 对拍（旧 vs 新 `publish.mjs` 输出 diff 为空）。
- **[canonical 取 docs 超集会不会拖累 videos]** → videos 只 import 自己用的 16 个函数，多余的图文 helper 只是代码存在，不运行。无运行时开销。
- **[platform-registry.json 与 `.docs_state.json` 职责重叠]** → 明确 registry = 半静态「路由 + 选择器」，`.docs_state.json` = 运行态「登录检测结果」，不合并；二者在登录面板里各读各的。

## Migration Plan

1. 建 `_shared/publish/`，把 docs 超集 `browser_utils.py` 拷入，删两个 skill 各自的 `lib/browser_utils.py`，改 `sys.path` 指向共享 + resolver。
2. 抽 `publish-common.mjs`，两个 `publish.mjs` 改 import，`node --test` 跑纯函数单测。
3. `--dry-run` 对拍：改前后两个 `publish.mjs` 的输出 diff 为空。
4. 建 `platform-registry.json`，两个 SKILL.md 表格改为引用；`probe.py` 加回写。
5. 重写/归档 `README-PUBLISH-OPTIMIZATION.md`。
6. 回归：docs `--runtime patchright --platforms zhihu --dry-run`、videos `--platforms bilibili --dry-run` 各跑一次无 import 错误。

## Open Questions

- **`_shared/` 目录名与位置**：`_shared/publish/` vs 顶层的 `scripts/lib/`（后者与 `scripts/litellm-bridge.py` 平级）。倾向 `_shared/publish/`（语义更内聚），但若未来想让 MCP/其他工具也复用浏览器原语，顶层 `scripts/lib/` 更合适。落地时可定。
- **纯函数单测覆盖范围**：是否值得给 `mdToPlain`/`truncate` 补「中文、emoji、代码块、超长截断」的边界用例快照（成本低、收益中等）。默认补少量关键用例。

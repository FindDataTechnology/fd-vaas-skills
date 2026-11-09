# Proposal: sync-external-ledgers

## Why

VAAS 工具面 11-05 已重切 26→17（orchestrate_* 退役转技能、新增 render_*/templates_* 五工具），但所有对外台账停在重切之前：finddata 侧 MCP-REGISTRY 最近对账 11-04（§1.4「17/17 注释覆盖」不可复现）、supply-annotations 底稿还是 26 个旧名、**壹座市场目录指引在教客户调用已退役的 `orchestrate_brainstorm`/`orchestrate_voiceover`**（market-annotations.json:14923/14977）；plaza 技能物料仍写「6 视频平台」而真源早已 10+11；`vaas-trial-intro.md` 让试用客户按指南跑 `generate_image` 必撞 503 而全文无一字预警；万星发布套件 v5 引用 vaas-wanxing 零工具声明，下次发版必被 pack 声明闸 400；hosted voice 腿做实后 collateral 的 `--preaudio` 旁路技术前提已满足却仍在产线使用，且 `tencent-tts.js` 直读 `VAAS/.env` 跨仓耦合。核心产品条线的「对外面」必须与真身同步——这是最便宜也最伤客的一层。

## What Changes

- **NEW** `external-ledger-sync` capability：工具面变更触发同波台账对账（registry 台账/供给注释/市场目录与指引/plaza 物料/试用指南五位一体，探针为凭）；试用面诚实（车道健康现状如实披露）；发布套件声明过闸；旁路退役机制。
- **重取现网工具面**：hosted 探针拉 17 工具实况 → 重生成 `supply-annotations/mcp/vaas-wanxing.json` 与 tools 底稿（补 render_*/templates_* 注释、清 26 代孤儿注释）→ `reconcile_mcp_registry.py` 严过 → MCP-REGISTRY 台账补现网镜像 sha 与滚版时间。
- **市场指引清洗**：壹座 market-catalog/market-annotations 删 orchestrate_* 指引、描述补展示面三出口；谦面 facet 目录同源文案更新。
- **试用面修正**：`vaas-trial-intro.md`/TEST-ACCOUNTS 按车道健康实况标注 image/video 腿状态（down 即明说并给等待/替代指引），与 deliver-hosted-surface 的 health 面口径统一。
- **技能与套件重传**：`fd-vaas-publish-videos` SKILL.md 先修自身「六平台」旧口径（真源先于分发），重传技能包（10+11）触发 plaza 再物化；万星发布套件 v6 带 17 名工具声明过 pack 闸。
- **旁路退役**：collateral-solution 出片迁至 VAAS 标准链（.env ciyuan 档直跑 new-task/task-render），`tencent-tts.js`/`build-generic.cjs --preaudio` 退役归档，解除对 VAAS/.env 的直读。
- **公开仓坐标脱敏**（既有 opensource-readiness 条款的违约收口）：`deploy/docker-compose.vaas.example.yml` 的 tailnet IP、`deploy/README.md` 与车道脚本里的网关域名/账号 id/根密钥文件路径 → 占位符化；真值只留运维侧。

## Capabilities

### New Capabilities

- `external-ledger-sync`: VAAS 对外台账（registry 台账、供给注释、市场目录/指引、plaza 物料、试用文档、套件声明）与真身工具面/车道健康的一致性契约。

### Modified Capabilities

（无 spec 修订——公开仓坐标脱敏是 `opensource-readiness` 既有条款「敏感信息/内部 URL MUST NOT 进入公开历史」的执行收口，以任务落地；历史 commit 不外写覆盖，只保证 HEAD 起干净。）

## Impact

- **仓外（finddata/paas 侧）**：MCP-REGISTRY.md、supply-annotations/*、paas/market-catalog.json、paas/market-annotations.json、docs/vaas-trial-intro.md、docs/TEST-ACCOUNTS.md、collateral-solution/video/*——跨仓任务列明文件，按既有 reconcile/发布流程执行。
- **仓内（VAAS）**：fd-vaas-publish-videos SKILL.md 平台计数、deploy compose/README 坐标占位化、scripts/_ciyuan_* 注释脱敏（deliver-hosted-surface 修车道后同步）。
- **依赖序**：registry 注释重生成应在 deliver-hosted-surface 上产后执行（面内容含 health 字段）；trial 文案随 acct 40 修复状态两版（先标 down 后销注）。
- **验证**：reconcile --strict 零缺陷；market 目录 API 回读无 orchestrate_* 字样；trial 指南逐工具可跑通或有明确标注；套件 v6 发版过闸 201；plaza 物料重生成后 10+11 口径。

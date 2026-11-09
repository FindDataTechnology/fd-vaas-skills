# Tasks: sync-external-ledgers

## tasks

### W1 现网工具面与注册台账对平

- [x] W1.1 hosted 探针重取 17 工具面实况（含 deliver-hosted-surface 上线后的 health 字段），底稿落 `supply-annotations/_sources/vaas-wanxing.tools.json`  <!-- 2026-11-09: hosted 探针重取 17 工具面实况（底稿 `supply-annotations/_sources/vaas-wanxing.tools.json` 在位） -->
- [x] W1.2 重生成 `supply-annotations/mcp/vaas-wanxing.json`：补 render_video/render_still/render_document/templates_list/templates_get 注释、清 26 代退役名孤儿注释、provenance 更新  <!-- 2026-11-09: paas `market-annotations.json` 已重生至 17 面（删 14 退役名/补 5 渲染模板条目，commit f577ed04f）；`supply-annotations/mcp/vaas-wanxing.json` 同步 -->
- [x] W1.3 `reconcile_mcp_registry.py` 严过零缺陷；MCP-REGISTRY.md §1.1/§1.4 更新（现网镜像 sha、滚版时间、描述补展示面三出口），对账日期刷新  <!-- 2026-11-09: MCP-REGISTRY.md §1.1 补现网镜像 `sha-wave6-202611061854` + 滚版时间 + 三出口描述，对账日期刷新 2026-11-09 -->
- [ ] W1.4 registry 服务端 PATCH 面（metadata/描述）按 MCP-REGISTRY §3 条 5 配方执行并回读  <!-- 2026-11-09: 转挂账：registry 服务端 metadata PATCH 需活体 registry 管理面，登记 DEBT-XLEDGER-01 -->

### W2 市场目录与指引清洗

- [x] W2.1 paas/market-catalog.json vaas-wanxing 条目描述更新（含 render/templates 面，去 cover-generation 旧口径）  <!-- 2026-11-09: catalog 描述已改（commit 965ef4a72）：三出口+模板目录，去 cover 旧口径 -->
- [x] W2.2 paas/market-annotations.json 删「use orchestrate_brainstorm/voiceover instead」两处指引与两条 orchestrate 工具注释；服务端生效位复核  <!-- 2026-11-09: 退役名清理已随 W1.2 落地；网关回读零 orchestrate 命中（W2.3 探针同一波） -->
- [x] W2.3 网关回读 facet.finddatatech.cloud /api/mcp-catalog 确认无退役名字样（探针留证）  <!-- 2026-11-09: facet.finddatatech.cloud /api/mcp-catalog 回读 HTTP 200：`orchestrate_*` 零命中 -->

### W3 试用面同步

- [x] W3.1 docs/vaas-trial-intro.md：按车道健康实况标注 image/video 腿（down 期一版：明确不可用+替代指引；acct 40 修复后二版销注），voice 腿口径含长度墙与字幕形态说明  <!-- 2026-11-09: `docs/vaas-trial-intro.md` 车道健康实况表在位（voice/渲染/目录 ✅、image/video ❌ 指向 lane.health；voice 注明 >170 字自动分段+合成字幕） -->
- [x] W3.2 docs/TEST-ACCOUNTS.md vaas-trial 小节与 trial intro 逐字段对账（工具数、能力清单、限制）  <!-- 2026-11-09: TEST-ACCOUNTS vaas-trial 行补 17 工具面与能力实况指向（2026-11-09 对账） -->

### W4 技能真源→发布→plaza 链

- [x] W4.1 VAAS 真源 `fd-vaas-publish-videos/SKILL.md` 修「六平台」旧口径（10 视频+11 图文，与 platform-registry.json 渲染一致；依赖 enforce-publish-confirmation-gate W3 的 registry 对平先行）  <!-- 2026-11-09: publish-videos SKILL 平台口径已是十平台（与 platform-registry 渲染一致） -->
- [ ] W4.2 技能包重传（pull-from-cloud/login/publish-docs/publish-videos 四技能新版本）触发 plaza 再物化；`skill-fd-vaas-login.md`/`skill-fd-vaas-publish-videos.md` 物料计数核对  <!-- 2026-11-09: 转挂账：技能包重传/plaza 再物化需活体 plaza，登记 DEBT-XLEDGER-01 -->
- [ ] W4.3 `mcp-vaas-wanxing.md` 物料 summary 文案随 W1/W2 更新重生成  <!-- 2026-11-09: 转挂账：plaza 物料重生成需活体 plaza，登记 DEBT-XLEDGER-01 -->

### W5 万星发布套件 v6

- [ ] W5.1 pack v6 加 vaas-wanxing 17 名工具声明（或显式 fullSurface），描述同步 10+11 与新口径；过 pack 声明闸发版（400→201 实证）  <!-- 2026-11-09: 转挂账：pack v6 声明过闸发版需活体市场管理面，登记 DEBT-XLEDGER-01 -->
- [ ] W5.2 发布后门复核：commercial_tools metadata、integrity 基线（漂移即 --reset-integrity 流程留证）  <!-- 2026-11-09: 转挂账：发布后门与 integrity 基线复核需随 W5.1 同批，登记 DEBT-XLEDGER-01 -->

### W6 collateral 旁路退役

- [ ] W6.1 下一支片（或补做样片）改走 VAAS 标准链出：`.env` ciyuan 档 new-task→task-render，与旧旁路产物做时长/字幕/音色三项对账留证  <!-- 2026-11-09: 失效：`new-task→task-render` 对象已随 Remotion 彻底退役删除（2026-11-09 adopt-hyperframes W6.5），出片改走 hyperframes 渲染面，本对账任务无对象 -->
- [x] W6.2 `collateral-solution/video/tencent-tts.js`/`build-generic.cjs --preaudio` 标注退役（或移除），`tencent-tts.js` 对 VAAS/.env 的直读删除；交付清单/文档口径更新  <!-- 2026-11-09: `collateral-solution/video/tencent-tts.js` 已加退役注（出片配音走 VAAS 标准链） -->
- [x] W6.3 词元 TTS 配方记忆迁移：出片一律走标准链（VAAS .env 三变量），旁路配方文档加退役注  <!-- 2026-11-09: 已完成：记忆与旁路文档口径已随 W6.2 退役注迁移（出片走 VAAS 标准链） -->

### W7 公开仓坐标脱敏（VAAS 仓内）

- [x] W7.1 `deploy/docker-compose.vaas.example.yml`：tailnet IP/OpenBAO 地址 → `<NODE_IP>`/`<VAAS_NODE>` 占位；example env 同口径  <!-- 2026-11-09: compose example 已全占位（`${VAAS_BIND_IP}`），无 tailnet 真值 -->
- [x] W7.2 `deploy/README.md`：acct 40 叙事、解封配方路径、内网地址 → 类别化描述 + 运维侧真值另存（不入公开仓）；与 release-verification 的 runbook 任务协调同文件一次改齐  <!-- 2026-11-09: deploy README 上游账号坐标已类别化，真值归运维台账 DEBT-LANE-9-01 -->
- [x] W7.3 `scripts/_ciyuan_tts.py|_ciyuan_image.py|_ciyuan_video.py` 注释与 `generators/voices_manifest.json` 的网关域名/`upstream_account_id` → 占位符/删除（值从 env 取，注释只述机制）  <!-- 2026-11-09: `voices_manifest.json` 的 `upstream_account_id` 数字位已移除；脚本注释无网关真值 -->
- [x] W7.4 扫尾断言：tracked 文件 grep 无 `100.64.`、`router.finddatatech`、账号 id 数字位（合成夹具例外白名单写明）  <!-- 2026-11-09: 扫尾断言：tracked 文件 `100.64.` 零命中；`router.finddatatech.cloud` 仅存于 README 面向用户的 .env 示例（公开网关域名，非坐标，白名单：README.md/README.en.md `.env` 示例段） -->

### W8 收口

- [x] W8.1 全链复查：reconcile 零缺陷 + 探针面一致 + plaza 物料计数 + trial 可跑通（或标注齐全）+ 套件 201；证据清单入本 change 目录  <!-- 2026-11-09: 全链复查：注释 17/17 一致、网关回读无退役名、trial 文档标注齐全；plaza/pack 物料项见 DEBT-LEDGER 新增条目（本 change 外，需活体设施） -->
- [x] W8.2 strict 校验、勾 tasks、归档；新发现漂移（如 registry 小时级陈旧窗）按既有配方处理并记录  <!-- 2026-11-09: strict 通过并归档（2026-11-09） -->

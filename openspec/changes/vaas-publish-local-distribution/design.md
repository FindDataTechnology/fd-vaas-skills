# Design — 发布面本地分装

## Context

托管生成面已上线（cheap-2，`/vaas-wanxing`，owner 隔离 + 签名下载 URL）；发布面六工具按 ADR-0004 永不上云，依赖平台登录态 + 人工确认。用户实际形态是本地跑 fd-vaas-skills MCP；登录管理页（fd-vaas-login）与两发布技能（publish-docs/videos，ego-browser/patchright 双运行时）全部现成。缺口只在三处胶水：云端产物拉取入口、谦面分装、给用户的安全说明。

## Goals / Non-Goals

**Goals:**
- 租户从零到首次发布：装 pack → 登录管理页扫码 → 云端拉产物 → 确认发布 → 回执回流，全程无需理解内部结构。
- 登录态物理上不进云：技能工具面无上传通道，pack 分发物可审计。

**Non-Goals:**
- 不做任何形式的云端登录态托管/代理/中转（ADR-0004 既定）。
- 不改发布技能的平台适配与确认逻辑（行为契约不变）。
- 不做云端代拉登录态的浏览器服务。

## Decisions

### D-A 拉取走「调用键经网关」为主、「签名 URL 粘贴」为辅
调用键路径让租户无需理解 URL 生命周期（24h 过期）；签名 URL 路径兜底「我在手机上看到了生成结果」的场景。两者都指向同一事实源（owner 隔离的资产库），不新增平台端点——本地技能用标准 MCP 客户端连 `https://mcp.finddatatech.cloud/vaas-wanxing` 即可。备选「本地技能直连 cheap-2」被否：绕过网关鉴权与计量，破坏唯一入口纪律。

### D-B pack 形态 = facet-pack-builder 标准流
四技能（login/publish-docs/publish-videos/_shared/publish）+ 依赖清单（Node 18+、ego-browser、Python 3.8+）+ 云端实例地址配置项打包。pack 里不塞任何密钥；调用键由用户装好后自己配（网关签发，天然按租户隔离）。safeline 拦含 SQL/代码片段 manifest 的坑已知（见 [[safeline-blocks-pack-install]]），发布时按既有判别法走。

### D-C 安全说明 = 一页纸，三问三答
登录态在哪（本机专用 profile，路径明示）、谁碰得到（只有本机进程；平台侧零保管零通道——可审计）、丢了怎么办（本机风险边界与用户日常刷 App 相同；重新扫码即可）。不写免责声明堆砌，写机制。

## Risks / Trade-offs

- **两段式体验**（云生成→本机发布）比全托管多一次跳转 → 换来的是账号安全的物理保证，值得；pack 配置里把云端地址预填好降低摩擦。
- **平台选择器漂移**是发布技能固有维护面（probe 机制已在）→ 不在本 change 范围。
- **发布回执回流依赖本地实例写库** → 本地实例写的就是本地 vaas.db（与发布技能现状一致），云端的 distribution 可见性走既有 record 机制，不强求实时同步。

## Open Questions

无。

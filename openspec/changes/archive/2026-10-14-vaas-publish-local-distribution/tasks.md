# Tasks — vaas-publish-local-distribution

## 1. 内容交接通道

- [x] 1.1 本地新增 `pull-from-cloud` 技能/脚本：输入调用键（或签名 URL）→ 连谦面网关 `/vaas-wanxing` → `assets_list`/`assets_get` 过滤 owner → 下载产物落 `downloads/` 对应目录；验证：用测试调用键端到端拉一张云端生成的图并落盘
- [x] 1.2 拉取结果自动生成发布可用的 task 目录结构（`downloads/fd-docs|videos/<slug>/` + meta 骨架），与发布技能的输入契约对齐；验证：拉取产物后 `publish_simulate`（dry-run）能直接跑通
- [x] 1.3 无凭据时输出引导文案（如何拿调用键/如何重新生成签名 URL），不抛裸错误；验证：清空调用键运行拉取，输出含指引
- [x] 1.4 发布成功后 `--record` 回执确认能写进本地 vaas.db 的 distribution；验证：一次真实（或 dry-run 模拟）发布后 meta.json 与 distribution 可见

## 2. 谦面分装 pack

- [x] 2.1 按 facet-pack-builder 流程打包：fd-vaas-login + fd-vaas-publish-docs + fd-vaas-publish-videos + `_shared/publish` + 依赖清单 + 云端实例地址配置项（预填 `https://mcp.finddatatech.cloud/vaas-wanxing`）；验证：manifest 校验通过、包内无任何密钥/凭据文件
- [x] 2.2 安全说明页随包分发（登录态存哪/谁碰得到/丢了怎么办，三问三答一页纸）；验证：pack 内含说明且渲染正常
- [x] 2.3 发布到谦面市场 v1 并记录 pack id；验证：market 安装接口可达（safeline 拦截时按既有判别法处理）

## 3. 端到端验收与文档

- [x] 3.1 全链演练（真实账号）：fd-vaas-login 扫码 → 云端生成封面 → 拉取落盘 → dry-run 预览 → 真实发布 → 回执可见。
  **2026-10-14 实证**：小红书真实图文发布成功，创作者后台「笔记管理」首位可见该条
  （「云端生成 · 本地发布 全链路演练」，`2026-10-14 04:57`，与发布时刻一致），账号「寻数科技」。
  非仅日志自证：发布后另起浏览器会话读后台列表核到实体记录。发布前先完成 3.4 上游同步。
- [x] 3.4 vendored 上游同步至 `dreammis/social-auto-upload@0012d2c`（2026-09-03）。**2026-10-14 实证**：
  同步前 vendor 停在 2026-08-11，落后 28 个提交；五个在用 uploader 全部有改动
  （douyin +394 / tencent +334 / ks +216 / xhs +119 / baijiahao +534）。
  兼容性核实：`VideoCls.__init__` 仅新增可选参数（`collection_name`），无删改 → 向后兼容；
  sync 脚本保护本地运行态（conf.py 已存在则不覆盖、cookies 不在 rsync 范围），备份后同步。
  能力边界另核：上游 README 能力矩阵标「图文上传 ✅」的仅抖音/快手/小红书三家（我们已全接入）；
  `TencentNote` 虽存在但四个方法有三个是 `NotImplementedError` 空壳，与 README 标 ❌ 一致，不接入。
- [x] 3.2 ADR-0004 补「云端生成、边缘发布」产品形态叙事（决策不变，升格叙事与翻案条件）；验证：ADR 更新提交
- [x] 3.3 `openspec validate vaas-publish-local-distribution --strict` 通过并归档；验证：validate 无 error
  **2026-10-14 实证**：`openspec validate --strict` 输出 `Change 'vaas-publish-local-distribution' is valid`，随后归档。
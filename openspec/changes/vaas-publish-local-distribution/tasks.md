# Tasks — vaas-publish-local-distribution

## 1. 内容交接通道

- [ ] 1.1 本地新增 `pull-from-cloud` 技能/脚本：输入调用键（或签名 URL）→ 连谦面网关 `/vaas-wanxing` → `assets_list`/`assets_get` 过滤 owner → 下载产物落 `downloads/` 对应目录；验证：用测试调用键端到端拉一张云端生成的图并落盘
- [ ] 1.2 拉取结果自动生成发布可用的 task 目录结构（`downloads/fd-docs|videos/<slug>/` + meta 骨架），与发布技能的输入契约对齐；验证：拉取产物后 `publish_simulate`（dry-run）能直接跑通
- [ ] 1.3 无凭据时输出引导文案（如何拿调用键/如何重新生成签名 URL），不抛裸错误；验证：清空调用键运行拉取，输出含指引
- [ ] 1.4 发布成功后 `--record` 回执确认能写进本地 vaas.db 的 distribution；验证：一次真实（或 dry-run 模拟）发布后 meta.json 与 distribution 可见

## 2. 谦面分装 pack

- [ ] 2.1 按 facet-pack-builder 流程打包：fd-vaas-login + fd-vaas-publish-docs + fd-vaas-publish-videos + `_shared/publish` + 依赖清单 + 云端实例地址配置项（预填 `https://mcp.finddatatech.cloud/vaas-wanxing`）；验证：manifest 校验通过、包内无任何密钥/凭据文件
- [ ] 2.2 安全说明页随包分发（登录态存哪/谁碰得到/丢了怎么办，三问三答一页纸）；验证：pack 内含说明且渲染正常
- [ ] 2.3 发布到谦面市场 v1 并记录 pack id；验证：market 安装接口可达（safeline 拦截时按既有判别法处理）

## 3. 端到端验收与文档

- [ ] 3.1 全链演练（真实账号）：装 pack → fd-vaas-login 扫码一平台 → 云端生成图文 → 拉取 → dry-run 预览 → 确认发布 → 回执可见；验证：演练记录归档
- [ ] 3.2 ADR-0004 补「云端生成、边缘发布」产品形态叙事（决策不变，升格叙事与翻案条件）；验证：ADR 更新提交
- [ ] 3.3 `openspec validate vaas-publish-local-distribution --strict` 通过并归档；验证：validate 无 error

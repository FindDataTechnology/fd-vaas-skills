# Tasks: add-presentation-plane

## tasks

### W1 工具面重切（breaking）

- [x] W1.1 `tools/render.py` 新建：`render_video`（storyboard 模式 = 现 compose_video 实现；type 模式 = 包 new-task.mjs/task-render.mjs；入口互斥校验；`validate_paths` 并入输入校验错误信息）
- [x] W1.2 `render_still` 骨架：kind 分发（chart/cover/graphic），cover 内部走 CoverBrand 静帧渲染，产物落 assets 账本 + 下载地址
- [x] W1.3 `render_document` 骨架：md/html 输入、pdf + longimage 两格式、产物落账本
- [x] W1.4 `templates_list` / `templates_get`：内置模板清单（视频场景族/封面版式/文档版式）机读化
- [x] W1.5 退役：orchestrate_brainstorm、orchestrate_voiceover、generate_cover、generate_video（同步）、assets_find_logo/list_common/list_compositions/get_scene_templates/validate_paths、全部 deprecated 别名（main.py + tools/*.py 注册面清干净）
- [x] W1.6 registry.json 扩展：chart（local/echarts）、doc（local/chromium）条目；registry.py driver 接线

### W2 render_still 图表底座

- [x] W2.1 echarts.min.js vendor 进仓（版本钉死），构建期从 theme.ts 生成 `echarts-theme.json` + 漂移测试
- [x] W2.2 chart 渲染：`{echarts_option, size, format}` spec → chromium 截图 PNG；品牌色板注入（option 未显式指定的颜色取主题）
- [x] W2.3 graphic 渲染：调用方 HTML + 品牌 CSS wrapper → 单帧
- [x] W2.4 chart spec 两用验收：同一 spec 出单帧图 + 作为 render_video kenburns 视觉输入，视觉一致

### W3 render_document

- [x] W3.1 md→HTML（python-markdown + 品牌 CSS wrapper）；版式模板目录 `mcp_server/templates/doc/<id>/`（template.json + css），默认版式就位
- [x] W3.2 pdf（printToPdf 分页正确）+ longimage（full-page 截图）双格式产出
- [x] W3.3 未知模板名 → 返回可用模板清单错误

### W4 BGM

- [x] W4.1 assets 树 type=bgm（时长/授权来源字段）+ 种子曲库 3–5 条 CC0/已授权曲目随镜像
- [x] W4.2 render_video storyboard 增加 `bgm: {asset_id|path, volume, fade_out}` 参数；ffmpeg 混流复用 `-t covered_s` 纪律（BGM 在视频时长处收尾）
- [x] W4.3 voiceover_assemble 同参数支持

### W5 知识层 skills

- [x] W5.1 `.agents/skills/fd-vaas-brainstorm/`：SKILL.md（brainstorm.py 的 voiceover/article JSON 模板 + brand_context 用法迁移，LLM 照填）
- [x] W5.2 `.agents/skills/fd-vaas-storyboard/`：SKILL.md（seek 契约撰写指南 + render_video 双模式选型 + kenburns/chart 输入模式 + data-viz 动画组件指引）

### W6 安全与质量

- [x] W6.1 外置场景硬校验：渲染前扫描 http(s)/file 外链 → 拒绝并列出违规资源；chromium 请求拦截兜底（非 data: 全断）；测试含「外链被拒且不产部分产物」
- [x] W6.2 确定性回归：render_video 同 storyboard 双跑一致；render_still/render_document 同输入双跑一致
- [x] W6.3 托管工具面探针更新：工具清单断言 = 17（无 orchestrate/publish；render/templates 在位）
- [x] W6.4 单测补齐：双模式互斥拒绝、未知 chart/doc 方式报错列可用清单、bgm 跨租户引用拒绝

### W7 部署与收口
- [ ] W7.5 生成面凭证池恢复（change 外的 infra 挂账）：用户在词元控制台重出组3(语音)/组9(图像+视频) key → seed `secret/vaas/pool/wanxing/{tts,image,video}`（bao 在 cheap-2 /opt/vaas-bao，root token 在 /opt/vaas-bao/root_token.txt）→ 生成类 E2E 复验

- [x] W7.1 镜像构建（+echarts vendor、种子曲库；pandoc 不进本版）+ 上产 + 探针全绿
      - 完成（11-05）：镜像 sha-d77874a 上产（cheap-2 compose）；工具面探针 5/5 PASS；渲染面生产 E2E 全绿——render_still(chart)+签名下载 PNG、render_document(pdf+longimage)、render_video(storyboard chart桥+dict size 归一) mp4 签名下载、generate_voice 诚实失败（凭证缺失按设计报错）
      - 附带修复两处接缝（随 commit）：render_video 输入路径解析收 downloads 相对路径（render_still→kenburns 桥）；storyboard.size 收 dict 归一
      - 先在事故处置：OpenBAO 已于 11-04 被退役清理，本 change 在 cheap-2 重建极简 bao（file backend+自解封循环 /opt/vaas-bao，KV v2），seed download-hmac；凭证池等用户重出 key（见 W7.5）
- [x] W7.2 pricing.json 补 render_video（second）/render_still（张）/render_document（份），本地算力 0.0 计价口径
- [x] W7.3 README 工具表重写（新命名空间 + hosted/stdio 两面清单）
- [x] W7.4 外账记录（本仓外，另起会话）：finddata `docs/vaas-trial-intro.md` 工具清单、`docs/vaas-presets/` pack 增补两 skill、`MCP-REGISTRY.md` `/vaas-wanxing` 行；部署后壹座重烘焙 registry 快照

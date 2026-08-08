## 1. 字幕定位 Bug 修复

- [ ] 1.1 修改 `remotion-app/src/CostRevolution.tsx` 的 SubtitleBar 组件：外层改用普通 `<div>`（非 AbsoluteFill），设置 `position: absolute; bottom: 60px; left: 0; right: 0; zIndex: 100`
- [ ] 1.2 确保 SubtitleBar 渲染在所有 Sequence 之后（最上层）
- [ ] 1.3 渲染视频并截图验证字幕在底部（用 ffmpeg 截取 00:00:10 的帧）
- [ ] 1.4 验证 captions.json 格式有效（JSON parse 通过）

## 2. MCP 发布服务器实现

- [ ] 2.1 重写 `.claude/mcp/vaas-publish-server.py`，实现 4 个工具：`validate_publish_ready`、`get_publish_config`、`simulate_publish`、`record_distribution`
- [ ] 2.2 `validate_publish_ready`：查找 task 目录，检查视频文件、封面文件、task.json status 字段
- [ ] 2.3 `get_publish_config`：从 task.json 读取 title/description/tags/script，检查 .publish.env 和 .env 覆盖
- [ ] 2.4 `simulate_publish`：返回每个平台的上传状态为 simulated，不执行实际操作
- [ ] 2.5 `record_distribution`：连接 SQLite，查找 video_id，插入 distributions 表，处理 slug 不存在的情况
- [ ] 2.6 用 `fastmcp list` 和 `fastmcp call` 测试每个工具

## 3. MCP 注册与集成

- [ ] 3.1 更新 `.mcp.json`，添加 `vaas-publish` 服务器配置
- [ ] 3.2 重启 Claude Code，验证 MCP 工具可用
- [ ] 3.3 通过对话调用 `validate_publish_ready` 测试 ai-software-cost-revolution

## 4. publish.mjs 过渡层改造

- [ ] 4.1 修改 `.agents/skills/fd-vaas-publish-videos/scripts/publish.mjs`，在 distribution 写入处改为调用 MCP 的 `record_distribution` 工具
- [ ] 4.2 保留 task.json 写入作为 fallback，MCP 调用失败时降级
- [ ] 4.3 测试 dry-run 模式确保不破坏现有流程

## 5. 端到端验证

- [ ] 5.1 用 MCP `validate_publish_ready` 检查 ai-software-cost-revolution 视频就绪状态
- [ ] 5.2 渲染视频确认字幕位置正确
- [ ] 5.3 执行发布（抖音 + 小红书），确认数据库写入成功
- [ ] 5.4 用 `python3 data/query_db.py show ai-software-cost-revolution` 验证 distribution 记录

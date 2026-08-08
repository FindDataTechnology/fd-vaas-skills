# Tasks: unify-material-management

按依赖顺序分四阶段。P0（DB 合一）先行，P1（资产模型+查询）紧接，P2（provider 注册表）铺扩展性，P3（server 归一）收尾。每阶段含验证。

## 1. P0: 统一数据库 (material-store)

- [x] 1.1 在 `mcp-server/mcp_server/db/` 定义统一 schema（assets/variants/distribution 新增，videos/tts_records/renders/tags/history 沿用），更新 `database.py` 初始化
- [x] 1.2 编写 `mcp-server/scripts/migrate_unify_db.py`：导入 `data/vaas.db` videos→assets（关联 video_id）、根 `vaas.db` content→assets（type 映射）、distribution 并入；迁移前自动备份旧库
- [x] 1.3 迁移脚本幂等可重跑，运行并校验：assets 总数 = 两旧库去重后总数；抽查一个已发布 slug 的血缘与 distribution 完整
- [x] 1.4 更新 `data/db_writer.py`（或新增统一 writer）指向新库 schema，skill 链路发布记录改走统一库
- [x] 1.5 `fd-vaas-publish-docs` 的 `--record` 补写 `distribution` 表（与视频发布同构）
- [x] 1.6 验证：跑一次视频发布（dry-run + 记录）与一次图文发布（--record），确认两表一致入统一库

## 2. P1: 资产血缘模型与查询 (material-store)

- [x] 2.1 `assets` 表写入 stage 状态机（draft→rendered→published→failed）并在生成/渲染/发布路径上更新 stage
- [x] 2.2 stage 变化写 `history` 表（时间戳+action+details）
- [x] 2.3 平台适配写入 `variants`（title/body/tags/cover_path，asset_id+platform 唯一），发布成功后回填 distribution.url
- [x] 2.4 实现 `assets.list` / `assets.get`（含 lineage 整树）/ `assets.stats` 工具（FastMCP）
- [x] 2.5 验证：用测试 slug 走 生成→渲染→发布 全链路，确认 lineage 树、variants、distribution 可查

## 3. P2: Provider 注册表 (generation-registry)

- [x] 3.1 定义注册表配置文件格式（按 type 分组：name/provider/model/driver）与统一 driver 接口 `generate(params) -> AssetResult`
- [x] 3.2 实现 `registry.list_generators(type?)` 工具
- [x] 3.3 现有 JS 生成器（tts/seedream/seedance）以 driver 底层形式接入注册表（subprocess 调用，不重写逻辑）
- [x] 3.4 `generate.*` 工具按注册表调度，未知 name 报错并列出可用方式
- [x] 3.5 验证：`registry.list_generators()` 列出全部方式；`generate.video(name=...)` 走通一次并写 assets

## 4. P3: 单一 MCP 服务器 (unified-mcp-interface)

- [x] 4.1 `mcp-server/mcp_server/` 按命名空间重组包（generate/orchestrate/publish/assets/registry）
- [x] 4.2 旧工具名保留为 deprecated 别名（generate_voice 等，行为与命名空间工具一致）
- [x] 4.3 `vaas-video-assets` 的素材发现工具（list_common_assets/find_logo/list_compositions/get_scene_templates）并入 `assets.*`，更新其 DB 读取指向统一库
- [x] 4.4 将 `mcp-publish-pipeline` 变更的编排需求并入 `publish.*`（validate_publish_ready/get_publish_config/simulate_publish/record_distribution），不新建 vaas-publish server
- [x] 4.5 更新 `.mcp.json`：单一 `vaas` 注册，移除 vaas-video-assets 条目；删除 `.claude/mcp/vaas-assets-server.py` 引用
- [x] 4.6 更新 `mcp-server/README.md` 与 `.env.example`（registry 配置说明）
- [x] 4.7 运行 `pytest tests/`，新增命名空间工具与别名的测试用例，全绿

## 5. 收尾

- [x] 5.1 根 `vaas.db` 标记废弃：README 注明只读归档，不再被任何代码写入
- [x] 5.2 全链路冒烟：brainstorm→生成→渲染→发布（dry-run）→assets 查询 走通一次
- [x] 5.3 归档本变更（/opsx:archive）并同步 specs 到 `openspec/specs/`

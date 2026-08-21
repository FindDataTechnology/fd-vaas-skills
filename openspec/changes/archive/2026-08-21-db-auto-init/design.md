# db-auto-init — Design

## Context

`mcp-server/mcp_server/db/database.py` 已提供 `get_connection()` / `init_schema()` / `ensure_db_exists()` 三件套，`init_schema()` 已是「幂等、只增不删」（全部 `CREATE TABLE IF NOT EXISTS`）。但整条启动链路里**没有任何入口调用它们**：

- `mcp_server/main.py::main()` → `mcp.run()`，不建库。
- `mcp_server/tools/*.py` → 直接 `get_connection()` 读写表，假设表已存在（grep 确认 0 处调用 `ensure_db_exists`/`init_schema`）。
- 唯一调用 `init_schema()` 的是迁移脚本 `migrate_task_json_to_db.py`（迁移场景，非启动路径）。
- `pyproject.toml` 无 `[project.scripts]`，`pip install -e .` 不暴露任何命令。

因此「建库」目前是隐性的：要么手动跑 Python 片段，要么碰巧跑过迁移脚本。

## Goals / Non-Goals

**Goals:**
- 新用户 clone 后，首次启动 MCP 服务器即自动得到完整 schema 的 `data/vaas.db`，无需任何记忆步骤。
- 提供一个文档化、可显式调用的 `vaas-init-db` 命令作为手动触发与迁移挂点。
- 对已有库完全无副作用（幂等）。

**Non-Goals:**
- 不做 schema 迁移框架（Alembic 之类）—— 表结构仍在 `init_schema()` 单一来源，`CREATE TABLE IF NOT EXISTS` 的「只增」语义已够用。
- 不改 `migrate_unify_db.py` 的旧库迁移逻辑。
- 不解决 `install.sh` 缺失的问题（那是 opensource-readiness 的另一个缺口，独立处理）。
- 不为 DB 增加连接池/并发层（单进程 MCP，sqlite 直连足够）。

## Decisions

**D1 — 在 `main()` 里惰性建库，而非在 import 时。**
`ensure_db_exists()` 放在 `main()` 函数体内、`mcp.run()` 之前，而不是模块顶层。理由：
- import 副作用（顶层建库）会让「导入包」这个纯动作产生磁盘写入，违背最小惊讶；单测/工具 import `mcp_server.db` 时不该被迫建库。
- `main()` 是唯一真正的「服务器启动」边界，语义清晰。

**D2 — 复用 `ensure_db_exists()`，不新写建库逻辑。**
`ensure_db_exists()` 已负责 `mkdir(data)` + `init_schema()`，正是所需语义。新增代码只有 import + 一行调用，不复制逻辑。

**D3 — CLI 用 `[project.scripts]` 的 console_scripts，命令名 `vaas-init-db`。**
- `pyproject.toml` 当前无 scripts 块；setuptools build-backend 已在，加 `[project.scripts]` 无需新依赖。
- 命名带 `vaas-` 前缀，与项目身份一致，避免与系统 `init-db` 之类冲突。
- 入口点直接指向 `ensure_db_exists`（用 `:` 语法指定模块内函数），一行定义、零新文件。实现为一个薄 `__main__`/函数 wrapper 即可（`ensure_db_exists` 无参数、无返回值，可直接作为入口）。

**D4 — 文档位置在 README「数据库」小节 + mcp-server/README。**
README 数据库小节已描述「单一 SQLite at `data/vaas.db`」+ 迁移命令，正是补「自动建库 + `vaas-init-db`」的自然位置。

**备选方案（已否决）：**
- *顶层 import 建库* → 否决：import 副作用。
- *建库放进每个 `get_connection()`* → 否决：热路径重复 `CREATE TABLE IF NOT EXISTS`，慢且职责错位。
- *单独 `init_db.py` 脚本让用户跑* → 否决：仍是「要记得跑」的隐性步骤，违背本变更初衷；CLI 是它的文档化替代。
- *引入 Alembic* → 否决：Non-Goals，过度设计。

## Risks / Trade-offs

- **[首次启动慢几毫秒]** → 建库只在表缺失时生效；`CREATE TABLE IF NOT EXISTS` 对已有库近乎零开销，可忽略。
- **[多实例并发首启竞争]** → `sqlite3` 对 `CREATE TABLE IF NOT EXISTS` 的并发安全足够；即使两进程同时首启，二者都拿到完整 schema，无损坏。极端可加 `BEGIN IMMEDIATE`，但当前单用户单进程 MCP 不构成风险。
- **[`data/` 目录权限不足导致建库失败]** → `ensure_db_exists()` 会 `mkdir(parents=True)` 并抛异常，服务器启动失败即显式暴露，优于静默「表不存在」的延迟崩溃。
- **[命令名未来与其它工具冲突]** → `vaas-` 前缀已显著降低概率；必要时改 `pyproject.toml` 一行即可。

## Migration Plan

1. 改 `main.py` + `pyproject.toml`，`pip install -e .` 重新安装使 console_script 生效。
2. 验证：删除本地 `data/vaas.db` → 启动服务器 → 断言 `data/vaas.db` 出现且 `.tables` 含全部表。
3. 验证：`vaas-init-db` 在已存在库上重跑幂等、不报错。
4. 已有用户无需迁移（`init_schema` 只增不删）。
5. 回滚：还原 `main.py`/`pyproject.toml` 两文件即可，无数据影响。

## Open Questions

无阻塞项。唯一可选跟进：是否顺带在 `mcp-server/README.md` 加 `pip install -e .` + `vaas-init-db` 的安装小节 —— 属文档收尾，不影响本设计。

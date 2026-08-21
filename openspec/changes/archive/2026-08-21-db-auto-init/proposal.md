# db-auto-init

## Why

新用户 clone 公开仓库后，`data/vaas.db` 不存在（gitignored），且 **没有任何东西自动创建它** —— MCP 服务器 `main()` 只调 `mcp.run()`，`ensure_db_exists()`/`init_schema()` 在整个 `mcp_server/` 里除了迁移脚本外无人调用。结果：任何人首次启动 MCP 服务器跑物料工具都会撞上 `no such table` 崩溃，除非手动执行一条未文档化的 `python -c "from mcp_server.db import ensure_db_exists; ..."`。数据库初始化目前是「靠运气/靠记忆」，不是一个可交付的开源项目应有的状态。

## What Changes

- **MCP 服务器启动时惰性建库**：`mcp_server/main.py::main()` 在 `mcp.run()` 前调用 `ensure_db_exists()`，首次启动即创建 `data/vaas.db` 并铺满 schema，已有库不受影响（`CREATE TABLE IF NOT EXISTS`，幂等、只增不删）。
- **新增显式 CLI 入口**：在 `pyproject.toml` 增加 `[project.scripts]`（当前为空，`pip install -e .` 不暴露任何命令），暴露 `vaas-init-db`（等价 `ensure_db_exists()`），作为文档化的手动触发 + 迁移流程的挂点。
- **文档补齐**：README 的数据库小节写明「数据库在首次启动 MCP 服务器时自动创建；也可 `vaas-init-db` 手动初始化」，消除 `python -c` 的隐性魔法。

## Capabilities

### New Capabilities

无 —— 本次不引入新的能力域，改动落在既有 `material-store` 能力上。

### Modified Capabilities

- `material-store`: 新增「数据库自举」需求 —— 统一数据库 SHALL 在 MCP 服务器启动时自动创建并初始化 schema，且 SHALL 提供显式 CLI 命令手动触发；不再要求用户手工执行未文档化的 Python 片段。

## Impact

- **代码**：`mcp-server/mcp_server/main.py`（+2 行，`main()` 里 import 并调用 `ensure_db_exists()`）；`mcp-server/pyproject.toml`（新增 `[project.scripts]`）。
- **依赖**：无新增（`sqlite3` 标准库已在用；CLI 走 `console_scripts`，setuptools 已在 build-system 声明）。
- **文档**：`README.md` 数据库小节；`mcp-server/README.md`（如提及建库方式）。
- **兼容性**：非破坏性。已有 `data/vaas.db` 不受影响；`init_schema()` 语义不变。迁移脚本 `migrate_unify_db.py` 仍可用（其内部已建 schema）。

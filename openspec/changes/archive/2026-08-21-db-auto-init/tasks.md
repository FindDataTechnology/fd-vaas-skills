# Tasks

## 1. 启动时惰性建库

- [ ] 1.1 `mcp-server/mcp_server/main.py::main()` 在 `mcp.run()` 前 import 并调用 `from mcp_server.db import ensure_db_exists; ensure_db_exists()`（不放到模块顶层，避免 import 副作用）
- [ ] 1.2 验证：删 `data/vaas.db` → 启动服务器 → 断言 `data/vaas.db` 出现且 `sqlite3 data/vaas.db '.tables'` 含全部表；对已有库重跑幂等不报错

## 2. 显式建库 CLI

- [ ] 2.1 `mcp-server/pyproject.toml` 新增 `[project.scripts]`：`vaas-init-db = "mcp_server.db:ensure_db_exists"`（或经薄 wrapper，若 console_scripts 直接指向该函数不可行）
- [ ] 2.2 重新 `pip install -e .` 使 console script 生效；验证 `vaas-init-db` 在空库/已有库上均幂等成功、退出码 0

## 3. 文档补齐

- [ ] 3.1 README「数据库」小节写明：数据库首次启动 MCP 服务器自动创建；可选 `vaas-init-db` 手动初始化；`pip install -e .` 暴露该命令
- [ ] 3.2 若 `mcp-server/README.md` 提及建库/安装方式，同步补齐 `pip install -e .` + `vaas-init-db`

## 4. 收尾

- [ ] 4.1 跑现有测试（`pytest mcp-server/tests`）确认无回归
- [ ] 4.2 commit + push

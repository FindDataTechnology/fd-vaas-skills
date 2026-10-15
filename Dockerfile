# VAAS generation-plane MCP server — root shim.
# Canonical spec: deploy/mcp-server.Dockerfile (kept in sync; this root copy
# exists because the build-pool workflow convention builds ./Dockerfile).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/mcp-server

COPY mcp-server/ /app/mcp-server/
COPY scripts/ /app/scripts/

RUN pip install --no-cache-dir "fastmcp>=3,<4" "pydantic>=2" aiosqlite python-dotenv

EXPOSE 30950
CMD ["python3", "-m", "mcp_server.main"]

# VAAS generation-plane MCP server (hosted mode).
# Publish-plane tools and Remotion are intentionally NOT in this image
# (workspace ADR-0004): the hosted surface is generate/orchestrate/assets/registry.
#
# The server runs from the SOURCE TREE (/app/mcp-server) rather than a wheel:
# utils/db paths resolve VAAS_ROOT by walking up package-relative parents, so
# the /app layout (mcp-server/, scripts/, data/, downloads/) must match the
# repo checkout. PYTHONPATH keeps that true inside the image.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/mcp-server

COPY mcp-server/ /app/mcp-server/
COPY scripts/ /app/scripts/

# Dependencies only — the app itself runs from the copied source tree.
# The relay caliber (萬星·词元) is stdlib HTTP (_openai_compat.py); no SDK needed.
RUN pip install --no-cache-dir "fastmcp>=3,<4" "pydantic>=2" aiosqlite python-dotenv

# Runtime layout (volumes):
#   /app/data/vaas.db        — material store (owner-scoped)
#   /app/downloads/          — generated artifacts (GC-managed)
# Bootstrap env (set at deploy, never baked):
#   VAAS_HOSTED=1, VAAS_LINE, VAAS_PORT, VAAS_BIND, VAAS_BEARER_TOKEN,
#   OPENBAO_ADDR, OPENBAO_TOKEN, VAAS_PRICING_FILE, VAAS_PUBLIC_URL.
EXPOSE 30950
CMD ["python3", "-m", "mcp_server.main"]

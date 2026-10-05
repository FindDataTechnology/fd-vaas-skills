# VAAS generation-plane MCP server (hosted mode).
# Publish-plane tools and Remotion are intentionally NOT in this image
# (workspace ADR-0004): the hosted surface is generate/orchestrate/assets/registry.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY mcp-server/ /app/mcp-server/
COPY scripts/ /app/scripts/

# litellm is optional (volcengine providers go direct); skip it to keep the image slim.
RUN pip install --no-cache-dir /app/mcp-server "fastmcp>=3,<4"

# Runtime layout (volumes):
#   /app/data/vaas.db        — material store (owner-scoped)
#   /app/downloads/          — generated artifacts (GC-managed)
# Bootstrap env (set at deploy, never baked):
#   VAAS_HOSTED=1 VAAS_TRANSPORT implied, VAAS_LINE=<line>, VAAS_PORT,
#   VAAS_BEARER_TOKEN=<egress static bearer>, OPENBAO_ADDR, OPENBAO_TOKEN,
#   VAAS_PRICING_FILE=/run-config/pricing.json (optional), VAAS_PUBLIC_URL.
EXPOSE 30950
CMD ["python3", "-m", "mcp_server.main"]

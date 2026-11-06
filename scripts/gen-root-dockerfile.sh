#!/usr/bin/env bash
# VAAS 镜像 Dockerfile 单源生成器（add-ci-and-provisioning W2）。
# 唯一 canonical：deploy/mcp-server.Dockerfile；根目录 ./Dockerfile 是其逐字节副本
# （build-pool 通道约定从仓根构建 ./Dockerfile，见根 Dockerfile 头注与本脚本产物）。
# 用法：bash scripts/gen-root-dockerfile.sh
# 漂移检查（CI/本地闸同源）：cmp -s Dockerfile deploy/mcp-server.Dockerfile
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cp "$ROOT/deploy/mcp-server.Dockerfile" "$ROOT/Dockerfile"
echo "✅ Dockerfile 已从 deploy/mcp-server.Dockerfile 生成（单源；勿手改根副本）"

#!/usr/bin/env bash
# VAAS 统一测试闸（本地等价入口，语义=.github/workflows/ci.yml 的 test job）。
# 四项检查任一红 = 非零退出，镜像构建不得推进（add-ci-and-provisioning）。
# 用法: bash scripts/ci-local.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

FAIL=0
report() {
  local name="$1"; shift
  echo ""
  echo "── $name ──────────────────────────────"
  if "$@"; then
    echo "✅ $name"
  else
    echo "❌ $name"
    FAIL=1
  fi
}

check_pytest() { (cd mcp-server && python3 -m pytest -q tests); }
check_node() { node --test tests/*.test.mjs .agents/skills/_shared/publish/publish-common.test.mjs; }
check_registry() { python3 .agents/skills/fd-vaas-login/scripts/check-registry-consistency.py; }
check_drift() {
  if ! cmp -s Dockerfile deploy/mcp-server.Dockerfile; then
    echo "根 Dockerfile 与 canonical 漂移；修复: bash scripts/gen-root-dockerfile.sh"
    return 1
  fi
}

report "pytest mcp-server" check_pytest
report "node --test（TTS helpers + publish-common）" check_node
report "registry 一致性（login↔adapter↔publish.mjs）" check_registry
report "Dockerfile 单源漂移" check_drift

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "🟢 测试闸全绿——可合并/可出片"
else
  echo "🔴 测试闸红——按上方失败项修复后重跑；镜像构建必须跳过"
fi
exit "$FAIL"

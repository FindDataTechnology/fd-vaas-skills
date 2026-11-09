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

# 解释器解析：VAAS_PYTHON > 仓内 .venv > 系统 python3。系统 python 被升级
# （homebrew 换 major）后依赖会整片消失，闸会误报红——venv 是稳定口径。
# node 段里 confirm_gate 用例会 spawn `python3` 导入 browser_utils（需 patchright），
# 故解析到的解释器目录同时前置进 PATH。
resolve_python() {
  if [ -n "${VAAS_PYTHON:-}" ]; then echo "$VAAS_PYTHON"
  elif [ -x "$ROOT/.venv/bin/python" ]; then echo "$ROOT/.venv/bin/python"
  elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then echo "$ROOT/.venv/Scripts/python.exe"
  else echo "python3"; fi
}
PY_BIN="$(resolve_python)"
case "$PY_BIN" in
  */*) PATH="$(cd "$(dirname "$PY_BIN")" && pwd):$PATH"; export PATH;;
esac

preflight() {
  local missing=""
  "$PY_BIN" -c "import pytest" 2>/dev/null || missing="$missing pytest"
  "$PY_BIN" -c "import fastmcp" 2>/dev/null || missing="$missing fastmcp"
  "$PY_BIN" -c "import patchright" 2>/dev/null || missing="$missing patchright"
  if [ -n "$missing" ]; then
    echo "解释器 $PY_BIN 缺依赖:$missing"
    echo "修复: python3.12 -m venv .venv && .venv/bin/python -m pip install -e 'mcp-server[dev]' patchright"
    echo "     或 export VAAS_PYTHON=/path/to/python"
    return 1
  fi
}

check_pytest() { (cd mcp-server && "$PY_BIN" -m pytest -q tests); }
check_node() { node --test tests/*.test.mjs .agents/skills/_shared/publish/publish-common.test.mjs; }
check_registry() { "$PY_BIN" .agents/skills/fd-vaas-login/scripts/check-registry-consistency.py; }
check_drift() {
  if ! cmp -s Dockerfile deploy/mcp-server.Dockerfile; then
    echo "根 Dockerfile 与 canonical 漂移；修复: bash scripts/gen-root-dockerfile.sh"
    return 1
  fi
}

report "解释器预检（pytest/fastmcp/patchright）" preflight
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

#!/usr/bin/env bash
# fetch-ppt-master.sh — 按需从上游 sparse-clone ppt-master 重资产技能子树
#
# ppt-master 是一个重资产技能（~12 000 文件 / ~98 MB）。为了让 VAAS 仓库对首次用户保持
# 轻量，仓库只签入了薄壳 SKILL.md（几 KB），完整技能树（脚本 / 模板 / 参考素材 / 多角色
# 工作流）通过本脚本按需从上游拉取到 .agents/skills/ppt-master/upstream/（已 gitignore）。
#
# 用法：bash scripts/fetch-ppt-master.sh
# 重装：rm -rf .agents/skills/ppt-master/upstream && bash scripts/fetch-ppt-master.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
VAAS_ROOT="${SCRIPT_DIR:-$(pwd)}"
[ -d "$VAAS_ROOT/.agents/skills/ppt-master" ] || VAAS_ROOT="$(pwd)"

DEST="$VAAS_ROOT/.agents/skills/ppt-master/upstream"
UPSTREAM="https://github.com/hugohe3/ppt-master.git"
SUBTREE="skills/ppt-master"   # 上游是嵌套布局：真实技能在 skills/ppt-master/

# 0. 幂等：已拉取则跳过
if [ -f "$DEST/SKILL.md" ]; then
    echo "✅ ppt-master 上游已存在: $DEST"
    echo "   如需重装: rm -rf $DEST && bash scripts/fetch-ppt-master.sh"
    exit 0
fi

# 1. 依赖检查
command -v git >/dev/null || { echo "❌ 需要 git（用于 sparse-checkout + partial clone）"; exit 1; }

mkdir -p "$DEST"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 2. partial clone（只拉元数据）+ sparse-checkout（只 populate SUBTREE 子树的 blob）
echo "📥 sparse-clone ppt-master 子树（$SUBTREE）from $UPSTREAM"
echo "   仅下载该子树 blob（~98 MB），不含上游 docs/examples/projects 等"
git clone --depth 1 --filter=blob:none --sparse "$UPSTREAM" "$TMP"
git -C "$TMP" sparse-checkout set "$SUBTREE"

# 3. 校验上游布局未变
if [ ! -f "$TMP/$SUBTREE/SKILL.md" ]; then
    echo "❌ 上游在 $SUBTREE 下未找到 SKILL.md —— 上游布局可能已变，请检查 $UPSTREAM"
    exit 1
fi

# 4. 平移到 DEST（含隐藏文件如 .env.example）
cp -R "$TMP/$SUBTREE/." "$DEST/"

echo ""
echo "✅ 完成: $DEST/SKILL.md （完整、权威的技能契约 —— 驱动前先读它）"
echo "   装生图依赖（如需）: pip install -r $DEST/requirements.txt"
echo "   配置密钥（如需）:   参照 $DEST/.env.example"

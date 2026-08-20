#!/usr/bin/env bash
# fetch-ppt-master.sh — on-demand sparse-clone of the heavy ppt-master skill subtree
#
# ppt-master is a heavy skill (~12k files / ~98 MB). To keep the VAAS repo lightweight
# for first-time users, only a thin-shell SKILL.md is committed; the full skill tree
# (scripts / templates / references / multi-role workflow) is fetched on demand into
# .agents/skills/ppt-master/upstream/ (gitignored).
#
# Usage: bash scripts/fetch-ppt-master.sh
# Reinstall: rm -rf .agents/skills/ppt-master/upstream && bash scripts/fetch-ppt-master.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
VAAS_ROOT="${SCRIPT_DIR:-$(pwd)}"
[ -d "${VAAS_ROOT}/.agents/skills/ppt-master" ] || VAAS_ROOT="$(pwd)"

DEST="${VAAS_ROOT}/.agents/skills/ppt-master/upstream"
UPSTREAM="https://github.com/hugohe3/ppt-master.git"
SUBTREE="skills/ppt-master"   # upstream is nested: real skill lives at skills/ppt-master/

# 0. Idempotent: skip if already fetched
if [ -f "${DEST}/SKILL.md" ]; then
    echo "ppt-master upstream already present: ${DEST}"
    echo "  to reinstall: rm -rf ${DEST} && bash scripts/fetch-ppt-master.sh"
    exit 0
fi

# 1. Dependency check
command -v git >/dev/null || { echo "ERROR: git is required (sparse-checkout + partial clone)"; exit 1; }

mkdir -p "${DEST}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

# 2. partial clone (metadata only) + sparse-checkout (populate only the SUBTREE blobs)
echo "Fetching ppt-master subtree (${SUBTREE}) from ${UPSTREAM}"
echo "  only that subtree's blobs (~98 MB); skips upstream docs/examples/projects"
git clone --depth 1 --filter=blob:none --sparse "${UPSTREAM}" "${TMP}"
git -C "${TMP}" sparse-checkout set "${SUBTREE}"

# 3. Verify upstream layout unchanged
if [ ! -f "${TMP}/${SUBTREE}/SKILL.md" ]; then
    echo "ERROR: upstream has no SKILL.md under ${SUBTREE} — layout may have changed, check ${UPSTREAM}"
    exit 1
fi

# 4. Move into DEST (include hidden files like .env.example)
cp -R "${TMP}/${SUBTREE}/." "${DEST}/"

echo ""
echo "Done: ${DEST}/SKILL.md (the authoritative skill contract — read it before driving)"
echo "  image-gen deps (if needed): pip install -r ${DEST}/requirements.txt"
echo "  keys (if needed):           see ${DEST}/.env.example"

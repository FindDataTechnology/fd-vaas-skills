#!/usr/bin/env bash
# sync-upstream.sh — 快速同步 social-auto-upload 上游到 VAAS vendor 目录
#
# 机制：
#   1. 克隆/拉取 dreammis/social-auto-upload 到临时目录（或用已有 /tmp/sau-upstream）
#   2. rsync uploader/ + utils/ + conf.example.py → scripts/upstream/
#   3. 从 conf.example.py 重新生成 conf.py（保留本地覆盖：headed、proxy 等）
#   4. 记录上游 commit SHA 到 .upstream-version
#
# 用法：
#   ./sync-upstream.sh              # 同步到上游最新 main
#   ./sync-upstream.sh <sha>        # 同步到指定 commit
#   ./sync-upstream.sh --check      # 只看 diff，不写文件
#   ./sync-upstream.sh --remote <url>  # 用 fork（默认 dreammis/social-auto-upload）
#
# 同步后：
#   - upstream 代码是 canonical，不要手改 scripts/upstream/uploader|utils 里的文件
#   - 本地适配全在 sau_adapter.py / conf.py 覆盖块 / migrate-cookies.py
#   - cookies/ 与 logs/ 是运行态，gitignore，不会被 rsync 覆盖
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_DIR="$SCRIPT_DIR/upstream"
VERSION_FILE="$UPSTREAM_DIR/.upstream-version"
REMOTE="${SAU_REMOTE:-https://github.com/dreammis/social-auto-upload.git}"
REF="main"
CHECK_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --remote) REMOTE="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,20p' "$0"; exit 0 ;;
    *) REF="$1"; shift ;;
  esac
done

TMP="$(mktemp -d /tmp/sau-sync.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "▶ 克隆 $REMOTE @ $REF → $TMP"
if ! git clone --quiet --depth 50 "$REMOTE" "$TMP/sau" 2>/dev/null; then
  # depth 50 拿不到老 SHA 时退回全量
  git clone --quiet "$REMOTE" "$TMP/sau"
fi
pushd "$TMP/sau" >/dev/null
git fetch --quiet --depth 50 origin "$REF" 2>/dev/null || git fetch --quiet origin
git checkout --quiet "$REF" 2>/dev/null || git checkout --quiet "origin/$REF"
SHA="$(git rev-parse HEAD)"
SHORT="$(git rev-parse --short HEAD)"
DATE="$(git show -s --format=%ci HEAD)"
popd >/dev/null

OLD_SHA="none"
[[ -f "$VERSION_FILE" ]] && OLD_SHA="$(cat "$VERSION_FILE" | head -1)"

if [[ "$CHECK_ONLY" == "1" ]]; then
  echo "▶ --check 模式：对比上游与本地 vendor"
  diff -rq "$TMP/sau/uploader" "$UPSTREAM_DIR/uploader" 2>/dev/null || true
  diff -rq "$TMP/sau/utils" "$UPSTREAM_DIR/utils" 2>/dev/null || true
  diff -q "$TMP/sau/conf.example.py" "$UPSTREAM_DIR/conf.example.py" 2>/dev/null || true
  echo "本地记录 SHA: $OLD_SHA"
  echo "上游最新 SHA: $SHA ($DATE)"
  [[ "$OLD_SHA" == "$SHA" ]] && echo "✓ 已是最新" || echo "⚠ 有更新"
  exit 0
fi

if [[ "$OLD_SHA" == "$SHA" ]]; then
  echo "✓ 已是最新 ($SHORT)，无需同步"
  exit 0
fi

echo "▶ rsync uploader/ + utils/ + conf.example.py → $UPSTREAM_DIR"
# --delete 让 vendor 与上游完全一致；排除运行态目录
rsync -a --delete \
  --exclude '__pycache__' \
  "$TMP/sau/uploader/" "$UPSTREAM_DIR/uploader/"
rsync -a --delete \
  --exclude '__pycache__' \
  "$TMP/sau/utils/" "$UPSTREAM_DIR/utils/"
cp "$TMP/sau/conf.example.py" "$UPSTREAM_DIR/conf.example.py"

# conf.py 是我们的本地覆盖——sync 不覆盖已有 conf.py（只在首次缺失时 bootstrap）。
# 这样 headed/proxy 等本地偏好不会被 sync 冲掉。douyin cookie_auth 无头会触发反爬，
# 必须 headed；故 bootstrap 默认 False。若上游 conf.example.py 新增 key，手动对照。
if [[ ! -f "$UPSTREAM_DIR/conf.py" ]]; then
  cat > "$UPSTREAM_DIR/conf.py" <<'PY'
# VAAS 本地 conf（sync-upstream.sh 首次 bootstrap 生成；之后 sync 不再覆盖，直接编辑本文件）。
# canonical 上游是 conf.example.py；本文件叠加 VAAS 偏好。
from pathlib import Path
import os

BASE_DIR = Path(__file__).parent.resolve()
XHS_SERVER = "http://127.0.0.1:11901"  # only used by xhs (API-signing) flows; we use web uploader
LOCAL_CHROME_PATH = ""  # 空 = 用 patchright 自带 chromium
LOCAL_CHROME_HEADLESS = False  # headed：douyin cookie_auth 无头会触发反爬；headed 更稳，便于人工介入
DEBUG_MODE = True
YT_PROXY = os.environ.get("VAAS_YT_PROXY") or None  # youtube 需代理时设 VAAS_YT_PROXY=http://127.0.0.1:7892
PY
  echo "  (首次 bootstrap conf.py)"
else
  echo "  (conf.py 已存在，保留本地覆盖；若上游 conf.example.py 新增 key，手动对照)"
fi

echo "$SHA" > "$VERSION_FILE"
echo "$DATE" >> "$VERSION_FILE"
echo "$REMOTE" >> "$VERSION_FILE"
echo "$REF" >> "$VERSION_FILE"

echo "✓ 同步完成: $OLD_SHA → $SHORT ($DATE)"
echo "  vendor 目录: $UPSTREAM_DIR"
echo "  下一步: 跑 python3 $SCRIPT_DIR/platforms/sau_adapter.py --platform xiaohongshu --login 验证登录"

#!/bin/bash
# VAAS 一键安装脚本
# 用法 A（远程）: curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-vaas-skills/main/install.sh | bash
# 用法 B（本地）: 在已克隆的仓库根目录执行 ./install.sh
#
# 设计原则：任何检查失败只警告不中断，最后汇总报告。

set -u

WARNINGS=()
ok()   { echo "✅ $1"; }
warn() { echo "⚠️  $1"; WARNINGS+=("$1"); }
info() { echo "   $1"; }

REPO_URL="https://github.com/FindDataTechnology/fd-vaas-skills.git"

# ---------- 0. 定位仓库根 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-install.sh}")" 2>/dev/null && pwd || echo "")"
if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/.agents/skills" ]; then
    ROOT="$SCRIPT_DIR"
    echo "📂 在已有克隆中运行: $ROOT"
else
    # curl | bash 模式：克隆到 ./fd-vaas-skills
    if [ ! -d "fd-vaas-skills" ]; then
        echo "📥 克隆 VAAS 仓库..."
        git clone "$REPO_URL" || { echo "❌ 克隆失败，请检查网络后重试"; exit 1; }
    else
        echo "📂 fd-vaas-skills 目录已存在，跳过克隆（git pull 更新）"
        git -C fd-vaas-skills pull --ff-only 2>/dev/null || warn "git pull 失败，继续使用现有版本"
    fi
    ROOT="$(cd fd-vaas-skills && pwd)"
fi
cd "$ROOT" || exit 1
echo "🚀 VAAS 安装开始（根目录: ${ROOT}）"
echo ""

# ---------- 1. 依赖检查（缺失只警告） ----------
echo "── 1/5 依赖检查 ──────────────────────────"

OS="$(uname -s 2>/dev/null || echo unknown)"
IS_WINDOWS=0
case "${OSTYPE:-}$OS" in
    msys*|mingw*|cygwin*|*MINGW*|*MSYS*|*CYGWIN*) IS_WINDOWS=1 ;;
esac

# Node 18+
if command -v node &>/dev/null; then
    NODE_MAJOR="$(node -v | sed 's/^v//' | cut -d. -f1)"
    if [ "$NODE_MAJOR" -ge 18 ]; then
        ok "Node.js $(node -v)"
    else
        warn "Node.js $(node -v) 过旧，需要 18+。macOS: brew install node；Linux: https://nodejs.org"
    fi
else
    warn "未安装 Node.js（需要 18+）。macOS: brew install node；Windows/Linux: https://nodejs.org"
fi

# git
if command -v git &>/dev/null; then
    ok "git $(git --version | awk '{print $3}')"
else
    warn "未安装 git。macOS: xcode-select --install；Ubuntu: sudo apt install git"
fi

# ffmpeg / ffprobe
if command -v ffmpeg &>/dev/null && command -v ffprobe &>/dev/null; then
    ok "ffmpeg $(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}')"
else
    warn "缺少 ffmpeg/ffprobe（封面合成、片头嵌入需要）。macOS: brew install ffmpeg；Ubuntu: sudo apt install ffmpeg；Windows: winget install ffmpeg"
fi

# 平台特定工具
if [ "$IS_WINDOWS" -eq 1 ]; then
    info "检测到 Windows：浏览器自动化走 patchright（Python）运行时"
    if command -v uv &>/dev/null; then
        ok "uv $(uv --version | awk '{print $2}')"
    else
        warn "未安装 uv（patchright 依赖管理用）。安装: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""
    fi
    info "patchright 安装: uv pip install patchright && patchright install chromium"
    info "（详见 .agents/skills/fd-vaas-publish-videos/SKILL.md）"
elif [ "$OS" = "Darwin" ]; then
    for tool in ego-browser cap officecli; do
        if command -v "$tool" &>/dev/null || [ -x "$HOME/.local/bin/$tool" ]; then
            ok "$tool 已安装"
        else
            warn "未检测到 ${tool}（浏览器发布/录屏/文档转换需要），安装方式见 README「依赖工具」节"
        fi
    done
else
    info "Linux：ego-browser/cap 无 Linux 构建，发布类技能不可用；视频生成管线可正常使用"
fi
echo ""

# ---------- 2. 项目初始化 ----------
echo "── 2/5 项目初始化 ─────────────────────────"

if [ -d "remotion-app/node_modules" ]; then
    ok "remotion-app 依赖已安装（跳过 npm install）"
else
    echo "📦 安装 remotion-app 依赖（首次约 1-2 分钟）..."
    if npm install --prefix remotion-app; then
        ok "remotion-app 依赖安装完成"
    else
        warn "npm install 失败，请手动执行: cd $ROOT/remotion-app && npm install"
    fi
fi

# VoiceoverVideo 合成注册检查
if grep -q 'id="VoiceoverVideo"' remotion-app/src/Composition.tsx 2>/dev/null; then
    ok "VoiceoverVideo 合成已注册"
else
    warn "VoiceoverVideo 合成未注册，请按 .agents/skills/fd-vaas-video-creator/references/setup.md 完成一次性设置"
fi

# .env 初始化
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "🔑 已创建 .env —— 请编辑填入火山引擎 Ark API Key（VOL_AGENT_API_KEY / ARK_API_KEY）"
    echo "   获取地址: https://console.volcengine.com/ark"
else
    ok ".env 已存在"
fi
echo ""

# ---------- 3. 技能链接（.claude/skills → .agents/skills） ----------
echo "── 3/5 技能链接 ───────────────────────────"

# 需要暴露给 Claude Code 的技能清单（与仓库现有子集一致）
SKILLS_TO_LINK="fd-browser-record fd-coding-wifi-tunnel fd-cover-image fd-vaas-brainstorm fd-vaas-dashboard fd-vaas-dashboard-sharing fd-vaas-publish-docs fd-vaas-publish-videos fd-vaas-video-creator"

mkdir -p .claude/skills

# 探测软链接能力（Windows Git Bash 常无权限）
CAN_SYMLINK=1
if [ "$IS_WINDOWS" -eq 1 ]; then
    CAN_SYMLINK=0
else
    _probe=".claude/skills/.symlink-probe-$$"
    if ln -s "../../.agents/skills" "$_probe" 2>/dev/null; then
        rm -f "$_probe"
    else
        CAN_SYMLINK=0
    fi
fi

LINKED=0; SKIPPED=0; COPIED=0
for name in $SKILLS_TO_LINK; do
    src=".agents/skills/$name"
    dst=".claude/skills/$name"
    rel="../../.agents/skills/$name"
    [ -d "$src" ] || { warn "技能源缺失: $src"; continue; }

    if [ -L "$dst" ]; then
        if [ "$(readlink "$dst")" = "$rel" ]; then
            SKIPPED=$((SKIPPED+1)); continue   # 幂等：已是正确软链
        fi
        rm -f "$dst"                            # 错误软链，重建
    elif [ -e "$dst" ]; then
        SKIPPED=$((SKIPPED+1)); continue        # 真实目录（Windows 副本），跳过
    fi

    if [ "$CAN_SYMLINK" -eq 1 ]; then
        ln -s "$rel" "$dst" && LINKED=$((LINKED+1))
    else
        cp -R "$src" "$dst" && COPIED=$((COPIED+1))
    fi
done
if [ "$CAN_SYMLINK" -eq 1 ]; then
    ok "技能软链接: 新建 ${LINKED}，已存在 $SKIPPED"
else
    ok "技能目录（复制模式，无软链权限）: 新建 ${COPIED}，已存在 $SKIPPED"
fi
echo ""

# ---------- 4. 健康检查 ----------
echo "── 4/5 健康检查 ───────────────────────────"
if [ -f "scripts/doctor.mjs" ] && command -v node &>/dev/null; then
    node scripts/doctor.mjs || true
else
    info "scripts/doctor.mjs 不存在，跳过（旧版本仓库）"
fi
echo ""

# ---------- 5. 汇总 ----------
echo "── 5/5 安装汇总 ───────────────────────────"
if [ "${#WARNINGS[@]}" -eq 0 ]; then
    echo "✅ VAAS 安装完成，无警告！"
else
    echo "⚠️  安装完成，有 ${#WARNINGS[@]} 项需要注意："
    for w in "${WARNINGS[@]}"; do echo "   - $w"; done
fi
echo ""
echo "📖 下一步:"
echo "   1. 编辑 $ROOT/.env，填入火山引擎 Ark API Key"
echo "   2. 看 README「5 分钟第一支视频」快速路径"
echo "   3. cd $ROOT && claude   （在 Claude Code 中使用 /fd-* 技能）"
echo ""
echo "🔗 项目地址: https://github.com/FindDataTechnology/fd-vaas-skills"

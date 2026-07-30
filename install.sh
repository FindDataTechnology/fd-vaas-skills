#!/bin/bash
# VAAS 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-vaas-skills/main/install.sh | bash

set -e

echo "🚀 正在安装 VAAS 视频自动化分发系统..."

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 请先安装 Node.js 18+"
    exit 1
fi

# 检查 git
if ! command -v git &> /dev/null; then
    echo "❌ 请先安装 git"
    exit 1
fi

# 克隆项目
if [ ! -d "VAAS" ]; then
    git clone https://github.com/FindDataTechnology/fd-vaas-skills.git
    cd VAAS
else
    echo "📂 VAAS 目录已存在，跳过克隆"
    cd VAAS
fi

# 安装依赖
echo "📦 安装依赖..."
npm install --prefix remotion-app 2>/dev/null || echo "⚠️ Remotion 依赖安装失败，请手动执行: cd VAAS/remotion-app && npm install"

# 初始化配置
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ 已创建 .env 配置文件，请填写火山引擎密钥"
fi

echo ""
echo "✅ VAAS 安装完成！"
echo ""
echo "📖 下一步操作:"
echo "   1. 编辑 VAAS/.env，填入火山引擎密钥"
echo "   2. cd VAAS && npx @anthropic-ai/claude-code"
echo "   3. 在 Claude Code 中输入: /help 查看可用技能"
echo ""
echo "🔗 项目地址: https://github.com/FindDataTechnology/fd-vaas-skills"

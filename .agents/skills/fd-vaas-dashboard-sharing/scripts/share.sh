#!/bin/bash
PORT=8765

echo ""
echo "🌐 选择看板分享方式"
echo "══════════════════════════════"
echo ""
echo "  1) WiFi 局域网 (同网络设备)"
echo "  2) Bore Tunnel (公网链接)"
echo "  3) Cloudflare Tunnel (公网链接)"
echo ""
echo "  0) 取消"
echo ""

# Check if dashboard is running
if command -v lsof &> /dev/null; then
    RUNNING=$(lsof -i :$PORT -sTCP:LISTEN -t 2>/dev/null)
elif command -v ss &> /dev/null; then
    RUNNING=$(ss -tlnp | grep ":$PORT " 2>/dev/null)
else
    RUNNING=""
fi

if [ -n "$RUNNING" ]; then
    echo "✅ 看板运行中: http://localhost:$PORT"
else
    echo "⚠️  看板未启动，分享前先运行: /dashboard"
fi

echo ""
echo -n "输入选项 (0-3): "
read -r choice

case "$choice" in
    1)
        echo ""
        echo "📡 启动 WiFi 局域网分享..."
        /Users/chengsishi/VAAS/.agents/skills/fd-coding-wifi-tunnel/scripts/wifi-tunnel.sh $PORT
        ;;
    2)
        echo ""
        echo "🕳️  启动 Bore Tunnel..."
        echo "请执行: /bore-tunnel $PORT"
        ;;
    3)
        echo ""
        echo "☁️  启动 Cloudflare Tunnel..."
        echo "请执行: /cloudflare-tunnel $PORT"
        ;;
    0)
        echo "已取消"
        ;;
    *)
        echo "无效选项"
        ;;
esac

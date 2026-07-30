#!/bin/bash
PORT=${1:-8765}

# Get local IP
UNAME=$(uname)
if [ "$UNAME" = "Darwin" ]; then
    # macOS
    IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
    if [ -z "$IP" ]; then
        IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
    fi
else
    # Linux
    IP=$(hostname -I | awk '{print $1}')
fi

if [ -z "$IP" ]; then
    echo "❌ 无法获取局域网 IP，请检查网络连接"
    exit 1
fi

# Check if port is listening
if command -v lsof &> /dev/null; then
    LISTENING=$(lsof -i :$PORT -sTCP:LISTEN -t 2>/dev/null)
elif command -v ss &> /dev/null; then
    LISTENING=$(ss -tlnp | grep ":$PORT " 2>/dev/null)
else
    LISTENING=""
fi

echo ""
echo "📡 WiFi 局域网分享"
echo "══════════════════════════════"
echo "本机 IP:   $IP"
echo "端口:      $PORT"
echo ""
echo "✅ 访问地址:"
echo "   http://$IP:$PORT"
echo ""
echo "📱 手机 / 其他设备 (同 WiFi):"
echo "   浏览器打开上面的地址"
echo ""
echo "💡 提示:"
echo "   - 设备必须连接同一个 WiFi"
echo "   - 防火墙可能需要允许端口 $PORT"
echo "   - 跨网请用 /bore-tunnel 或 /cloudflare-tunnel"
echo ""

if [ -z "$LISTENING" ]; then
    echo "⚠️  警告: 端口 $PORT 上未检测到服务在运行"
    echo "   先启动看板: /dashboard"
fi

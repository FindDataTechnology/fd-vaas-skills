---
name: fd-coding-wifi-tunnel
description: 局域网分享 - 通过 WiFi 共享本地服务给同一网络的其他设备。触发: /wifi-tunnel
---

# WiFi 局域网分享

将本地服务通过局域网 IP 分享给同一 WiFi 下的其他设备。

## 用法

```bash
/wifi-tunnel 8765        # 分享端口 8765 (看板)
/wifi-tunnel 3000        # 分享端口 3000
```

## 对比

| 方式 | 场景 | 延迟 |
|------|------|------|
| WiFi Tunnel | 同一局域网 | 最低 |
| Bore Tunnel | 公网 / 跨网 | 中 |
| Cloudflare Tunnel | 公网 / 跨网 | 中高 |

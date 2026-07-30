---
name: fd-coding-cloudflare-tunnel
description: |
  Start and manage Cloudflare Tunnels (cloudflared) to expose local services to the internet via HTTPS.
  Trigger whenever the user:
  - Wants to access a local service from outside (内网穿透/外网访问)
  - Asks to expose a local port publicly with HTTPS
  - Mentions "cloudflared", "Cloudflare Tunnel", "trycloudflare", "cf tunnel"
  - Needs HTTPS for the public URL (instead of bore's HTTP)
  - Has a dashboard or web service running locally that needs external access
  - The bore.pub domain is not accessible (e.g. blocked by firewall)
---

# fd-coding-cloudflare-tunnel: Expose Local Services via Cloudflare Tunnel

## Prerequisites
- `cloudflared` must be installed: `brew install cloudflared` (one-time)
- The local service must be running before starting the tunnel
- No Cloudflare account needed — `trycloudflare.com` quick tunnels are free

## Quick Start

```bash
# Make sure your local service is running, then:
cloudflared tunnel --url http://localhost:<PORT>
```

The output shows the public URL, e.g.:
```
https://random-words.trycloudflare.com
```

Visit the HTTPS URL in any browser.

## Run in Background (推荐)

```bash
nohup cloudflared tunnel --url http://localhost:<PORT> > /tmp/cloudflared-<PORT>.log 2>&1 &
sleep 5
cat /tmp/cloudflared-<PORT>.log
```

Extract the URL from logs:
```bash
grep -oP 'https?://[a-z-]+\.trycloudflare\.com' /tmp/cloudflared-<PORT>.log | head -1
```

## Lifecycle Management

### Check if tunnel is running
```bash
ps aux | grep "cloudflared tunnel" | grep -v grep
```

### Check logs
```bash
cat /tmp/cloudflared-<PORT>.log | tail -20
```

### Stop tunnel
```bash
pkill -f "cloudflared tunnel --url http://localhost:<PORT>"
```
Or kill all cloudflared processes:
```bash
pkill cloudflared
```

## Common Workflow

1. Start local service: `cd /path/to/project && nohup python app.py <PORT> > /dev/null 2>&1 &`
2. Expose it: `nohup cloudflared tunnel --url http://localhost:<PORT> > /tmp/cloudflared-<PORT>.log 2>&1 &`
3. Wait for tunnel to connect: `sleep 5 && cat /tmp/cloudflared-<PORT>.log`
4. Get URL: `grep -oP 'https?://[a-z-]+\.trycloudflare\.com' /tmp/cloudflared-<PORT>.log | head -1`
5. Share the HTTPS URL with others
6. When done: `pkill -f "cloudflared tunnel --url http://localhost:<PORT>"`

## Notes
- Provides **HTTPS** automatically (unlike bore's HTTP).
- trycloudflare.com may be blocked in some regions (e.g. China). In that case, use `bore` instead.
- First connection may take 10-15 seconds to establish.
- The tunnel URL is randomly generated each time and changes on restart.
- No uptime guarantee for free quick tunnels — for production use, set up a named tunnel with a Cloudflare account.

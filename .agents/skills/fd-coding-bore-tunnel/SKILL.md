---
name: fd-coding-bore-tunnel
description: |
  Start and manage bore tunnels (bore-cli) to expose local services to the internet via bore.pub.
  Trigger whenever the user:
  - Wants to access a local service from outside (内网穿透/外网访问)
  - Asks to expose a local port publicly
  - Mentions "bore", "tunnel", "穿透", "外网", "public URL"
  - Has a dashboard or web service running locally that needs external access
  - Asks for help making a localhost page accessible to others
---

# fd-coding-bore-tunnel: Expose Local Services via bore.pub

## Prerequisites
- `bore-cli` must be installed: `brew install bore-cli` (one-time)
- The local service must be running before starting the tunnel
- `nohup` is used to keep the tunnel alive after terminal closes

## Quick Start

```bash
# 1. Make sure your local service is running on some port, e.g.:
#    nohup python -m http.server 8080 > /dev/null 2>&1 &

# 2. Start bore tunnel
bore local <PORT> --to bore.pub
```

The output shows the public URL, e.g.:
```
listening at bore.pub:32371
```

Visit: `http://bore.pub:{PORT}`

## Run in Background (推荐)

```bash
nohup bore local <PORT> --to bore.pub > /tmp/bore-<PORT>.log 2>&1 &
sleep 2
cat /tmp/bore-<PORT>.log
```

Extract the port from output:
```
grep -oP 'bore\.pub:\K\d+' /tmp/bore-<PORT>.log
```

## Lifecycle Management

### Check if tunnel is running
```bash
ps aux | grep "bore local" | grep -v grep
```

### Check logs
```bash
cat /tmp/bore-<PORT>.log
```

### Stop tunnel
```bash
pkill -f "bore local <PORT>"
```
Or kill all bore processes:
```bash
pkill bore
```

## Common Workflow

1. Start the local service (e.g. dashboard): `cd /path/to/project && nohup python app.py <PORT> > /dev/null 2>&1 &`
2. Expose it: `nohup bore local <PORT> --to bore.pub > /tmp/bore-<PORT>.log 2>&1 &`
3. Get URL: `cat /tmp/bore-<PORT>.log`
4. Share the `http://bore.pub:{port}` URL with others
5. When done: `pkill -f "bore local <PORT>"`

## Notes
- Tunnel is HTTP (not HTTPS). For HTTPS, use cloudflared instead.
- bore.pub is a free public server — no account needed, but no uptime guarantee.
- The tunnel stops when the bore process is killed or the machine sleeps.
- The port on bore.pub is randomly assigned each time.

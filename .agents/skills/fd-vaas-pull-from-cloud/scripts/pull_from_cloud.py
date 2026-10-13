#!/usr/bin/env python3
"""
pull_from_cloud.py — pull tenant-owned assets from a VAAS hosted instance
into local publish-ready directories.

Three input modes (any one suffices):
  --call-key KEY   Facet call key; connects via the gateway and filters by owner
  --url URL        A signed download URL straight from a generation response
  --asset ID       Asset id (requires --call-key or --base+--call-key)

Zero third-party dependencies (stdlib only). Login states are NEVER touched:
this tool moves content files, nothing else.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# 不留默认实例地址：该脚本是随技能分发的，硬编码某个具体实例会把用户静默导到
# 别人的服务上（既是隐私问题也是误用问题）。用户必须显式提供自己的实例地址，
# 方式任选其一：--base 参数、VAAS_BASE 环境变量，或自己的 .env。
#
#   export VAAS_BASE="https://your-vaas-host/vaas-wanxing"
#
# 缺省且未给 --call-key/--url 时，脚本会输出 GUIDE 明确提示如何配置（见 BASE_GUIDE）。
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass  # 零依赖是硬要求：没有 python-dotenv 时靠 shell 环境变量即可

DEFAULT_BASE = os.environ.get("VAAS_BASE", "")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"

GUIDE = """
没有可用的拉取凭据。三选一：

A) 谦面调用键（推荐，可浏览整个内容库）
   1. 在谦面控制台领取你的调用键（sk-...）
   2. export VAAS_CALL_KEY="sk-..."
   3. 重新运行：pull_from_cloud.py --call-key "$VAAS_CALL_KEY" --list

B) 签名下载 URL
   生成工具的响应里带 download_url（24 小时有效）。过期了就在云端实例上
   重新调一次 assets_get 拿新 URL，然后：
   pull_from_cloud.py --url "<download_url>"

C) 自部署/内网实例
   本脚本不含内置实例地址（避免把你静默导到别人的服务上）。显式指定其一：
     export VAAS_BASE="https://your-vaas-host/vaas-wanxing"
   或 python3 pull_from_cloud.py --base https://your-vaas-host/vaas-wanxing ...
   然后：
     pull_from_cloud.py --base "$VAAS_BASE" --call-key ... --asset ...
"""


def _http(url: str, headers: dict | None = None, timeout: int = 60) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _mcp_rpc(base: str, key: str, method: str, params=None, session=None, rid=1):
    """Minimal streamable-HTTP MCP client (initialize + tools/call)."""
    body = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        body["params"] = params
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if session:
        h["Mcp-Session-Id"] = session
    req = urllib.request.Request(base.rstrip("/") + "/mcp",
                                 data=json.dumps(body).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=120) as r:
        sid = r.headers.get("Mcp-Session-Id")
        data = r.read().decode()
    for line in data.splitlines():
        if line.startswith("data:"):
            return sid, json.loads(line[5:])
    return sid, None


def _mcp_session(base: str, key: str) -> str:
    sid, resp = _mcp_rpc(base, key, "initialize",
                         {"protocolVersion": "2024-11-05", "capabilities": {},
                          "clientInfo": {"name": "vaas-pull", "version": "1"}})
    if not resp or "result" not in resp:
        raise RuntimeError(f"initialize failed: {json.dumps(resp)[:200]}")
    _mcp_rpc(base, key, "notifications/initialized", session=sid, rid=0, notify=True)
    return sid


def _mcp_call(base: str, key: str, session: str, tool: str, arguments: dict) -> dict:
    _, resp = _mcp_rpc(base, key, "tools/call",
                       {"name": tool, "arguments": arguments}, session=session, rid=99)
    text = resp["result"]["content"][0]["text"]
    if text.startswith("Error"):
        raise RuntimeError(text[:300])
    return json.loads(text)


def _type_dirs(asset_type: str) -> Path:
    mapping = {"article": "fd-docs", "copy": "fd-docs",
               "video": "fd-videos", "image": "fd-images", "cover": "fd-images",
               "audio": "fd-audio"}
    root = Path(os.environ.get("VAAS_ROOT", Path.cwd()))
    return root / "downloads" / mapping.get(asset_type, "fd-misc")


def _safe_slug(slug: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", slug).strip("-")
    return s or f"asset-{datetime.now():%Y%m%d-%H%M%S}"


def _write_article_task(dest: Path, slug: str, asset: dict) -> None:
    """Shape article/copy assets into the fd-vaas-publish-docs task contract."""
    dest.mkdir(parents=True, exist_ok=True)
    meta = asset.get("metadata") or {}
    title = asset.get("title") or slug
    (dest / "article.md").write_text(
        meta.get("body") or meta.get("text") or f"# {title}\n\n（正文请从云端资产 metadata 补充或本地编辑）\n",
        encoding="utf-8")
    m = {"title": title, "summary": meta.get("summary") or "",
         "tags": meta.get("tags") or [], "cover": meta.get("cover") or "",
         "platforms": meta.get("platforms") or [], "distribution": [],
         "pulled_from_cloud": {"asset_id": asset.get("id"), "slug": asset.get("slug"),
                               "pulled_at": datetime.now(timezone.utc).isoformat()}}
    (dest / "meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def _download_signed(url: str, dest_dir: Path, slug_hint: str) -> Path:
    code, blob = _http(url, timeout=120)
    if code != 200:
        body = blob.decode("utf-8", errors="replace")[:150]
        if code == 403:
            raise SystemExit(f"签名无效或已过期（HTTP 403：{body}）。\n请到云端实例重新生成，或改用 --call-key 拉取。")
        raise SystemExit(f"下载失败 HTTP {code}: {body}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = slug_hint or f"asset-{datetime.now():%Y%m%d-%H%M%S}"
    # extension from URL path if present
    m = re.search(r"\.(\w{2,5})(?:\?|$)", url)
    ext = f".{m.group(1)}" if m else ".bin"
    out = dest_dir / f"{_safe_slug(name)}{ext}"
    out.write_bytes(blob)
    return out


def _fetch_via_gateway(base: str, key: str, asset_id: str, dest_root: Path) -> Path:
    session = _mcp_session(base, key)
    asset = _mcp_call(base, key, session, "assets_get", {"id": asset_id})
    a_type = asset.get("type") or "misc"
    slug = _safe_slug(asset.get("slug") or asset_id[:8])
    dest = _type_dirs(a_type) / slug

    if a_type in ("article", "copy"):
        # signed URL for any binary cover; the markdown itself comes from metadata
        _write_article_task(dest.parent, slug, asset)
        cover = asset.get("metadata", {}).get("cover_path") or ""
        if cover:
            cover_url = _mcp_call(base, key, session, "assets_get", {"id": asset_id}).get("download_url")
            if cover_url:
                _download_signed(cover_url, dest, "cover")
        print(f"落盘：{dest}/（article.md + meta.json）→ 可直接 publish.mjs --slug {slug}")
        return dest

    # binary types: need a fresh signed URL
    fresh = _mcp_call(base, key, session, "assets_get", {"id": asset_id})
    url = fresh.get("download_url")
    if not url:
        raise SystemExit("实例未返回 download_url（可能不是可下载类型）。")
    out = _download_signed(url, dest, slug)
    print(f"落盘：{out}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull tenant-owned VAAS assets for local publishing")
    ap.add_argument("--call-key", default=os.environ.get("VAAS_CALL_KEY", ""))
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--url", help="signed download URL from a generation response")
    ap.add_argument("--asset", help="asset id to pull")
    ap.add_argument("--list", action="store_true", help="list tenant assets (needs --call-key)")
    ap.add_argument("--all", action="store_true", help="pull all listed assets")
    args = ap.parse_args()

    if args.url:
        out = _download_signed(args.url, _type_dirs("misc"), None)
        print(f"落盘：{out}")
        return 0

    if not args.call_key:
        print(GUIDE)
        return 1

    base = args.base
    if not base:
        # 没有实例地址就没法走 MCP 拉取。这里必须明确报错——若带着内置默认值
        # 静默跑下去，用户会在毫不知情的情况下面向别人的实例发起请求。
        print("❌ 未配置 VAAS 实例地址。\n")
        print("本技能不含内置实例地址（避免静默导到他人的服务）。任选其一：\n")
        print('  export VAAS_BASE="https://your-vaas-host/vaas-wanxing"')
        print("  # 或写到 .env：VAAS_BASE=https://your-vaas-host/vaas-wanxing")
        print("  # 或每次显式传：pull_from_cloud.py --base <url> ...\n")
        print("实例地址由你的 VAAS 托管实例提供；不确定时问你的服务提供方。")
        return 1

    if args.list or args.all or args.asset:
        session = _mcp_session(base, args.call_key)
        listing = _mcp_call(base, args.call_key, session, "assets_list", {"limit": 100})
        items = listing.get("items", [])
        print(f"名下资产 {len(items)} 项：")
        for it in items:
            print(f"  {it['id'][:8]}  {it['type']:8s} {it['stage']:9s} {it['slug']}")
        if args.list:
            return 0
        targets = [args.asset] if args.asset else [i["id"] for i in items]
        for aid in targets:
            try:
                _fetch_via_gateway(base, args.call_key, aid, _type_dirs("misc"))
            except SystemExit as e:
                print(e)
        return 0

    print(GUIDE)
    return 1


if __name__ == "__main__":
    sys.exit(main())

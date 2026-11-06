#!/usr/bin/env python3
"""
probe_hosted_surface.py — VAAS hosted tool-surface deployment probe (W6.3).

Walks the MCP streamable-HTTP handshake (initialize → notifications/initialized
→ tools/list) against a live instance, lists the tool names, and asserts the
hosted contract (ADR-0004):
  1. handshake completes and the server issues a session,
  2. the listed surface is exactly the 17 canonical hosted tools,
  3. no publish_* tool is visible in the listing,
  4. a publish_video tools/call is rejected (Unknown tool — nothing executes).

stdlib only on purpose (same caliber as scripts/_openai_compat.py): runnable
from any operator machine with a bare python3, no fastmcp install needed.

Env:
  VAAS_PROBE_BASE    MCP server base URL incl. scheme, e.g. http://10.0.0.2:30950
                     (the endpoint probed is <base>/mcp)
  VAAS_PROBE_TOKEN   static service bearer — behind the gateway this is the
                     egress credential; omit it only for direct node access.
  VAAS_PROBE_USER    tenant identity (X-Forwarded-User) for tools/call checks
                     against a hosted instance; required when the hosted server
                     enforces identity on calls (fail-closed). Never printed.
  VAAS_PROBE_TIMEOUT request timeout in seconds (default 30)

Usage:
  VAAS_PROBE_BASE=http://node:30950 VAAS_PROBE_TOKEN=... VAAS_PROBE_USER=... \\
      python3 scripts/probe_hosted_surface.py

Output: one [ok]/[FAIL] line per check, the visible tool surface, then a final
PASS/FAIL verdict. Exit 0 = PASS, 1 = FAIL, 2 = usage/config error. Never
prints the token value.
"""

import json
import os
import sys
import urllib.error
import urllib.request

# Canonical hosted surface (mirrors mcp_server/main.py CANONICAL_TOOLS minus
# the stdio-only publish plane).
HOSTED_TOOLS = [
    "generate_voice", "generate_image", "generate_video_submit",
    "video_job_status", "models_voices", "voiceover_assemble",
    "reference_clips_check",
    "render_video", "render_still", "render_document",
    "templates_list", "templates_get",
    "assets_list", "assets_get", "assets_stats",
    "registry_list_generators", "registry_describe_generator",
]

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "vaas-surface-probe", "version": "1.0"}


def usage() -> str:
    return (
        "usage: VAAS_PROBE_BASE=<base-url> [VAAS_PROBE_TOKEN=<bearer>] "
        "python3 scripts/probe_hosted_surface.py\n"
        "\n"
        "  VAAS_PROBE_BASE    MCP server base URL incl. scheme "
        "(e.g. http://10.0.0.2:30950); probes <base>/mcp\n"
        "  VAAS_PROBE_TOKEN   static service bearer (gateway egress credential); "
        "optional for direct node access\n"
        "  VAAS_PROBE_USER    tenant identity header for hosted tools/call checks\n"
        "  VAAS_PROBE_TIMEOUT request timeout in seconds (default 30)\n"
        "\n"
        "exit: 0 = PASS, 1 = FAIL, 2 = usage/config error"
    )


def _post(url: str, payload: dict, session: str | None, token: str,
          timeout: int) -> tuple[int, object, bytes]:
    """One JSON-RPC POST; returns (status, response headers, raw body)."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "vaas-surface-probe/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    tenant = os.getenv("VAAS_PROBE_USER", "").strip()
    if tenant:
        headers["X-Forwarded-User"] = tenant
    if session:
        headers["Mcp-Session-Id"] = session
        headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:  # non-2xx still carries a body
        return e.code, e.headers, e.read()
    return resp.status, resp.headers, resp.read()


def _rpc_messages(body: bytes) -> list[dict]:
    """Extract JSON-RPC messages from an application/json or SSE body."""
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    if text.startswith("{"):
        return [json.loads(text)]
    messages = []
    for line in text.splitlines():  # text/event-stream: one JSON per data: line
        if line.startswith("data:"):
            data = line[len("data:"):].strip()
            if data:
                messages.append(json.loads(data))
    return messages


def _rpc_response(body: bytes, request_id: int) -> dict:
    """Pick the response message matching request_id from the body."""
    for msg in _rpc_messages(body):
        if msg.get("id") == request_id and ("result" in msg or "error" in msg):
            return msg
    return {}


def _describe_error(resp: dict) -> str:
    err = resp.get("error")
    if isinstance(err, dict):
        return f"JSON-RPC {err.get('code')}: {err.get('message')}"
    return f"unexpected response: {json.dumps(resp)[:200]}"


def main() -> int:
    base = os.getenv("VAAS_PROBE_BASE", "").strip()
    token = os.getenv("VAAS_PROBE_TOKEN", "").strip()
    if not base:
        print(usage())
        return 2
    try:
        timeout = int(os.getenv("VAAS_PROBE_TIMEOUT", "30") or 30)
    except ValueError:
        print("VAAS_PROBE_TIMEOUT must be an integer number of seconds")
        print(usage())
        return 2
    if not base.startswith(("http://", "https://")):
        print("VAAS_PROBE_BASE must include the scheme, e.g. http://node:30950")
        print(usage())
        return 2
    url = base.rstrip("/") + "/mcp"
    print(f"probing {url} (bearer {'set' if token else 'NOT set — direct access mode'})")

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        print(f"[{'ok' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    session = None
    handshake_ok = False

    # ── check 1: handshake (initialize → initialized) ─────────────────────
    try:
        status, headers, body = _post(url, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": PROTOCOL_VERSION,
                       "capabilities": {}, "clientInfo": CLIENT_INFO},
        }, session=None, token=token, timeout=timeout)
        resp = _rpc_response(body, 1)
        server = (resp.get("result") or {}).get("serverInfo", {})
        session = headers.get("Mcp-Session-Id") if headers else None
        if status == 200 and server:
            handshake_ok = True
            check("handshake: initialize",
                  True,
                  f"server={server.get('name')} v{server.get('version')}, "
                  f"session={'issued' if session else 'not issued (stateless)'}")
            if session:
                nstatus, _, _ = _post(url, {
                    "jsonrpc": "2.0", "method": "notifications/initialized",
                }, session=session, token=token, timeout=timeout)
                check("handshake: notifications/initialized", nstatus == 202,
                      f"status {nstatus} (want 202)")
        else:
            check("handshake: initialize", False,
                  f"HTTP {status}; {_describe_error(resp)}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        check("handshake: initialize", False, f"transport error: {e}")

    # ── check 2-3: tools/list → hosted surface ────────────────────────────
    names: list[str] = []
    listed = False
    if handshake_ok:
        try:
            status, _, body = _post(url, {
                "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            }, session=session, token=token, timeout=timeout)
            resp = _rpc_response(body, 2)
            tools = (resp.get("result") or {}).get("tools")
            if status == 200 and isinstance(tools, list):
                names = sorted(t.get("name", "") for t in tools)
                listed = True
                print(f"\nvisible surface ({len(names)} tools):")
                for n in names:
                    print(f"  {n}")
                print()
            else:
                check("tools/list", False, f"HTTP {status}; {_describe_error(resp)}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            check("tools/list", False, f"transport error: {e}")

    if listed:
        missing = [t for t in HOSTED_TOOLS if t not in names]
        extra = [t for t in names if t not in HOSTED_TOOLS]
        check("hosted surface is exactly the 17 canonical tools",
              not missing and not extra and len(names) == len(HOSTED_TOOLS),
              ("" if not missing and not extra else
               f"missing={missing} unexpected={extra}"))
        leaked = [n for n in names if n.startswith("publish")]
        check("publish plane invisible in listing", not leaked,
              f"leaked: {leaked}" if leaked else "no publish_* tool listed")

        # ── check 4: publish_video call must be rejected (fail closed) ────
        try:
            status, _, body = _post(url, {
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "publish_video",
                           "arguments": {"slug": "surface-probe"}},
            }, session=session, token=token, timeout=timeout)
            resp = _rpc_response(body, 3)
            result = resp.get("result")
            if resp.get("error") or (isinstance(result, dict) and result.get("isError")):
                why = (resp.get("error", {}) or {}).get("message") or result.get("content")
                check("publish_video call rejected", True, f"{str(why)[:120]}")
            else:
                check("publish_video call rejected", False,
                      "tool executed — publish plane leaked into hosted surface")
        except (urllib.error.URLError, OSError, ValueError) as e:
            check("publish_video call rejected", False, f"transport error: {e}")

        # ── check 5: lane health visible in discovery (deliver-hosted-surface
        # W3): registry_list_generators entries carry lane blocks; down lanes
        # must be marked down (never advertised as usable).
        try:
            status, _, body = _post(url, {
                "jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "registry_list_generators", "arguments": {}},
            }, session=session, token=token, timeout=timeout)
            resp = _rpc_response(body, 4)
            content = ((resp.get("result") or {}).get("content") or [])
            text = "".join((c.get("text") or "") for c in content if isinstance(c, dict))
            lanes_found = text.count('"health"') if text else 0
            downs = text.count('"health": "down"') + text.count('"health":"down"')
            check("discovery carries lane health",
                  lanes_found > 0,
                  f"{lanes_found} lane blocks in registry listing"
                  + (f"; down lanes: {downs}" if downs else ""))
        except (urllib.error.URLError, OSError, ValueError) as e:
            check("discovery carries lane health", False, f"transport error: {e}")

    failed = [name for name, ok, _ in checks if not ok]
    print(f"\n{'PASS' if not failed else 'FAIL'}: "
          f"{len(checks) - len(failed)}/{len(checks)} checks passed"
          + (f"; failed: {failed}" if failed else ""))
    return 0 if checks and not failed else 1


if __name__ == "__main__":
    sys.exit(main())

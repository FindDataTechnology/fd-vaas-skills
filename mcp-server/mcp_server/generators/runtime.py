"""
Per-call runtime for generation drivers: guard → owner → credential → env,
then usage recording + download URL on the way out.

Keeps every generator's boilerplate to two calls (prepare/finish) and the
platform invariants in one place:
- tool arguments are scanned for credential material before anything runs
- hosted mode resolves credentials from the vault and injects them into the
  subprocess env only (bridge still reads .env in local mode)
- every successful generation writes a generation_usage row
- every bridge subprocess runs under a finite wall clock
  (fix-hosted-generation-correctness: an upstream hang must never wedge a
  tool call indefinitely)
"""

import os
import subprocess
from typing import Optional

from .. import credentials as _credentials
from ..credentials import (
    CredentialUnavailable,
    credential_source_label,
    resolve,
    reject_secrets_in_params,
    subprocess_env,
)
from ..db import record_usage
from ..hosting import current_owner, download_url, is_hosted
from .errors import classify_upstream_error

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
SCRIPTS_DIR = os.path.abspath(SCRIPTS_DIR)

# Per-call wall clock for bridge subprocesses (seconds). Sync video lanes
# legitimately run minutes (submit+wait), so the default is generous but
# MUST be finite; deploy can tune via env.
BRIDGE_TIMEOUT_S = int(os.getenv("VAAS_BRIDGE_TIMEOUT_S", "900"))


def effective_provider(resolved: dict, env_key: str) -> str:
    """Effective lane provider for a call — the ONE rule both the lane-health
    gate and the truthfulness checks must agree on.

    Hosted: the vault record declares `provider` (it wins — it is what the
    bridge actually injects). Local mode ('env' source): the very lane switch
    the bridge reads — <KIND>_PROVIDER from .env. Fallback: volcengine.

    2026-11-10 修：车道闸此前自己读 `<KIND>_PROVIDER`（未设即 volcengine），
    与 vault 记录脱钩——生产 provider=ciyuan 却报 `image/volcengine
    (unconfigured)`，既误导客户（真因是 ciyuan 上游封禁），又会在
    「env 未设 + volcengine down + ciyuan 健康」时假拦截健康车道。
    """
    p = (resolved.get("provider") or "").lower()
    if p:
        return p
    if resolved.get("source") == "env":
        return (os.getenv(env_key) or "volcengine").lower()
    return "volcengine"


def provider_for(ctx: dict, env_key: str) -> str:
    """Effective lane provider for a prepared call (see effective_provider)."""
    return effective_provider(ctx["resolved"], env_key)


def prepare(kind: str, params: dict) -> dict:
    """Guard params, resolve owner + credential, return the call context.

    kind keys both the vault path (pool/<line>/<kind>) and the bridge env
    mapping; the vendor (volcengine vs openai-compatible relay) comes from
    the resolved vault record, not from code.

    Lane health gate (deliver-hosted-surface W3): a ledgered `down` lane
    refuses the call up front as lane_down — never advertised as usable,
    never burning a doomed subprocess.
    """
    reject_secrets_in_params(params)
    owner = current_owner()
    # Lane health gate — BEFORE credential resolution (C2 discipline): a
    # ledgered `down` lane refuses up front as lane_down, and vault
    # reachability must not mask that verdict.
    # 2026-11-10 修：车道取「有效 provider」——vault 记录优先（容错预读，读不到
    # 就退回本地 <KIND>_PROVIDER / volcengine）。此前闸门自读环境变量，生产
    # provider=ciyuan 却报 `image/volcengine (unconfigured)`：既误导客户（真因是
    # ciyuan 上游封禁），又会在「env 未设 + volcengine down + ciyuan 健康」时
    # 假拦截健康车道。预读不抛错，闸门顺序不变。
    # Local stdio keeps the historical free-lane behavior (the operator runs
    # their own keys); opt in locally with VAAS_LANE_HEALTH_GATE=1.
    from ..lane_health import lane_health  # noqa: E402  (package root module)
    env_key = f"{kind.upper()}_PROVIDER"
    lane_prov = _credentials.provider_peek(kind) or (os.getenv(env_key) or "volcengine").lower()
    gate_on = is_hosted() or os.getenv("VAAS_LANE_HEALTH_GATE", "") == "1"
    if gate_on and lane_health(kind, lane_prov).get("health") == "down":
        h = lane_health(kind, lane_prov)
        raise CredentialUnavailable(
            f"lane_down ({kind}/{lane_prov}): lane is down per lane_health ledger "
            f"({h.get('reason_class')}); check registry.list_generators for "
            f"health and do not retry in a loop"
        )
    resolved = resolve(kind)
    env = subprocess_env(resolved, kind)
    return {"owner": owner, "resolved": resolved, "env": env}


def run_bridge(cmd: list[str], ctx: dict, timeout_s: Optional[int] = None) -> str:
    """Run a litellm-bridge subprocess with the per-call env overlay.

    Finite wall clock by default (BRIDGE_TIMEOUT_S); a timeout is surfaced as
    a classified tenant-safe `timeout:` error, raw detail server-side only.
    """
    env = {**os.environ, **ctx["env"]} if ctx["env"] else None
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True,
                                cwd=SCRIPTS_DIR, env=env,
                                timeout=timeout_s or BRIDGE_TIMEOUT_S)
    except subprocess.TimeoutExpired as e:
        raise classify_upstream_error(
            " ".join(str(x) for x in cmd[2:4]) or "bridge", "timed out",
        ) from e
    return result.stdout


def finish(
    ctx: dict,
    tool: str,
    provider: str,
    model: Optional[str],
    units: float,
    unit_type: str,
    asset_id: str,
) -> dict:
    """Record usage and return response extras (download_url in hosted mode)."""
    source = ctx["resolved"].get("source") or "env"
    record_usage(
        owner=ctx["owner"], tool=tool, provider=provider, model=model,
        units=units, unit_type=unit_type, credential_source=source,
        asset_id=asset_id,
    )
    extras: dict = {"credential_source": source}
    if is_hosted():
        url = download_url(asset_id, ctx["owner"])
        if url:
            extras["download_url"] = url
    return extras

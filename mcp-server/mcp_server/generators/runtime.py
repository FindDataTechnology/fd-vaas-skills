"""
Per-call runtime for generation drivers: guard → owner → credential → env,
then usage recording + download URL on the way out.

Keeps every generator's boilerplate to two calls (prepare/finish) and the
platform invariants in one place:
- tool arguments are scanned for credential material before anything runs
- hosted mode resolves credentials from the vault and injects them into the
  subprocess env only (bridge still reads .env in local mode)
- every successful generation writes a generation_usage row
"""

import os
import subprocess
from typing import Optional

from ..credentials import (
    CredentialUnavailable,
    credential_source_label,
    resolve,
    reject_secrets_in_params,
    subprocess_env,
)
from ..db import record_usage
from ..hosting import current_owner, download_url, is_hosted

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
SCRIPTS_DIR = os.path.abspath(SCRIPTS_DIR)


def prepare(kind: str, params: dict) -> dict:
    """Guard params, resolve owner + credential, return the call context.

    kind keys both the vault path (pool/<line>/<kind>) and the bridge env
    mapping; the vendor (volcengine vs openai-compatible relay) comes from the
    resolved vault record, not from code.
    """
    reject_secrets_in_params(params)
    owner = current_owner()
    resolved = resolve(kind)
    env = subprocess_env(resolved, kind)
    return {"owner": owner, "resolved": resolved, "env": env}


def run_bridge(cmd: list[str], ctx: dict) -> str:
    """Run a litellm-bridge subprocess with the per-call env overlay."""
    env = {**os.environ, **ctx["env"]} if ctx["env"] else None
    result = subprocess.run(cmd, capture_output=True, text=True, check=True,
                            cwd=SCRIPTS_DIR, env=env)
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

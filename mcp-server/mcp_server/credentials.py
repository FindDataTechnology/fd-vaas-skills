"""
Model credential resolution chain (ADR-0005, workspace docs/adr).

Order: request credential-ref (phase 2) → tenant BYOK (phase 2)
       → line pool credential → service default credential.
Phase 1 activates the last two levels only.

Local (non-hosted) mode never touches the vault: the bridge keeps reading
VAAS/.env exactly as before (`source="env"`, nothing injected).

Hosted mode: OpenBAO KV v2 is the only credential home. The process env holds
just the bootstrap pair (OPENBAO_ADDR + OPENBAO_TOKEN); pool credentials rotate
without redeploy thanks to the TTL cache.

Hard rule: credentials never travel through tool arguments — see
`reject_secrets_in_params`, called by the generation dispatch.
"""

import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

CACHE_TTL_SECONDS = int(os.getenv("VAAS_CRED_TTL", "300"))

LINE = os.getenv("VAAS_LINE", "wanxing")

# kind -> (env names for api key / base url / model override)
# Two provider calibers share the vault schema: the record's `provider` field
# picks the bridge path, not hardcoded volcengine assumptions.
#   volcengine  — ARK direct (video today; image/tts until a standard key lands)
#   openai      — any OpenAI-compatible relay (萬星·词元 token.finddatatech.cloud);
#                 bridge routes via litellm with the model prefixed openai/
_KIND_ENV = {
    "tts": {"key": ["vol_agent_api_key", "ARK_API_KEY"], "base": "ARK_TTS_BASE_URL", "model": "TTS_MODEL"},
    "image": {"key": ["vol_agent_api_key", "ARK_API_KEY"], "base": "SEEDREAM_BASE_URL", "model": "IMAGE_MODEL"},
    "video": {"key": ["vol_agent_api_key", "ARK_API_KEY"], "base": "SEEDANCE_BASE_URL", "model": "VIDEO_MODEL"},
}

# OpenAI-compatible relay env names (provider="openai" records).
_OPENAI_ENV = {
    "tts": {"key": "OPENAI_API_KEY", "base": "OPENAI_BASE_URL", "model": "TTS_MODEL", "provider_env": "TTS_PROVIDER"},
    "image": {"key": "OPENAI_API_KEY", "base": "OPENAI_BASE_URL", "model": "IMAGE_MODEL", "provider_env": "IMAGE_PROVIDER"},
    "video": {"key": "OPENAI_API_KEY", "base": "OPENAI_BASE_URL", "model": "VIDEO_MODEL", "provider_env": "VIDEO_PROVIDER"},
}

_SECRET_PATTERNS = [
    re.compile(r"ark-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-[A-Za-z0-9]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
]

_cache: dict[str, tuple[float, Optional[dict]]] = {}
_lock = threading.Lock()


class CredentialUnavailable(RuntimeError):
    pass


# ─── Tool-argument guard ───────────────────────────────────────────────────

def reject_secrets_in_params(params: dict) -> None:
    """Raise when any string parameter looks like provider credential material."""
    for name, value in params.items():
        if not isinstance(value, str):
            continue
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                raise ValueError(
                    f"Parameter '{name}' looks like credential material; "
                    "passing model credentials through tool arguments is not allowed."
                )


# ─── OpenBAO KV v2 client ──────────────────────────────────────────────────

def _vault_get(path: str) -> Optional[dict]:
    """Read secret/vaas/<path> from OpenBAO; None when the path does not exist."""
    addr = os.getenv("OPENBAO_ADDR", "").rstrip("/")
    token = os.getenv("OPENBAO_TOKEN", "")
    if not addr or not token:
        raise CredentialUnavailable(
            "hosted mode needs OPENBAO_ADDR and OPENBAO_TOKEN (bootstrap env)"
        )
    url = f"{addr}/v1/secret/data/vaas/{path}"
    req = urllib.request.Request(url, headers={"X-Vault-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise CredentialUnavailable(f"vault read failed for vaas/{path}: HTTP {e.code}") from e
    import json

    data = json.loads(payload.decode("utf-8"))
    return (data.get("data") or {}).get("data") or {}


def _cached(path: str) -> Optional[dict]:
    now = time.time()
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] > now:
            return hit[1]
    data = _vault_get(path)
    with _lock:
        _cache[path] = (now + CACHE_TTL_SECONDS, data)
    return data


def _resolve_entry(path: str) -> Optional[dict]:
    """Fetch one vault entry and normalize its shape."""
    raw = _cached(path)
    if raw is None:
        return None
    entry = {
        "api_key": raw.get("api_key") or "",
        "base_url": raw.get("base_url") or None,
        "model": raw.get("model") or None,
        "provider": (raw.get("provider") or "volcengine").lower(),
        "path": f"vaas/{path}",
    }
    if not entry["api_key"]:
        return None
    return entry


# ─── Resolution chain ──────────────────────────────────────────────────────

def resolve(kind: str, provider_hint: str = "volcengine") -> dict:
    """
    Resolve the credential for one generation call.

    Vault paths are keyed by asset KIND (pool/<line>/<kind>, e.g. .../tts,
    .../image, .../video), never by the upstream vendor — a line's TTS relay
    and its image relay may be entirely different providers. The record's
    `provider` field picks the bridge caliber at injection time.

    Returns {"source": "env"} in local mode (bridge reads .env itself), or
    {"source": "pool"|"default", "api_key", "base_url", "model", "provider"}
    in hosted mode.
    """
    if os.getenv("VAAS_HOSTED", "").strip() != "1":
        return {"source": "env"}

    for source, path in (
        ("pool", f"pool/{LINE}/{kind}"),
        ("default", f"service/default/{kind}"),
    ):
        entry = _resolve_entry(path)
        if entry:
            entry["source"] = source
            return entry
    raise CredentialUnavailable(
        f"no {kind} credential in vault: pool/{LINE}/{kind} "
        f"and service/default/{kind} are both missing"
    )


def service_secret(name: str) -> str:
    """Read one service-default secret value (e.g. the download HMAC key)."""
    raw = _cached(f"service/default/{name}")
    value = (raw or {}).get("value") or (raw or {}).get("api_key") or ""
    if value:
        return value
    raise CredentialUnavailable(f"missing service secret vaas/service/default/{name}")


def subprocess_env(resolved: dict, kind: str) -> dict:
    """Env overlay that carries the resolved credential into the bridge subprocess."""
    if resolved.get("source") == "env":
        return {}
    if resolved.get("provider") == "openai":
        # OpenAI-compatible relay: bridge takes the litellm path (TTS_PROVIDER/
        # IMAGE_PROVIDER=openai, model prefixed openai/, base/key via the
        # standard OpenAI env names).
        mapping = _OPENAI_ENV[kind]
        env = {
            mapping["key"]: resolved["api_key"],
            mapping["provider_env"]: "openai",
        }
        if resolved.get("base_url"):
            env[mapping["base"]] = resolved["base_url"]
        if resolved.get("model"):
            env[mapping["model"]] = resolved["model"]
        return env
    # Volcengine caliber (default): ARK env names.
    mapping = _KIND_ENV[kind]
    env: dict[str, str] = {}
    for key_name in mapping["key"]:
        env[key_name] = resolved["api_key"]
    if resolved.get("base_url"):
        env[mapping["base"]] = resolved["base_url"]
    if resolved.get("model"):
        env[mapping["model"]] = resolved["model"]
    return env


def credential_source_label(kind: str, provider_hint: str = "volcengine") -> str:
    """Best-effort source label for usage rows; never raises."""
    try:
        return resolve(kind, provider_hint).get("source", "env")
    except Exception:
        return "unresolved"

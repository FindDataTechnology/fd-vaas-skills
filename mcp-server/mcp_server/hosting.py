"""
Hosting mode: identity resolution, service authentication, and download signing.

Local (default) mode  — stdio, single user, everything belongs to SERVICE_OWNER,
                        no bearer required, no vault required.
Hosted mode           — VAAS_HOSTED=1; every MCP call must arrive through the
                        gateway: static service bearer (VAAS_BEARER_TOKEN) plus
                        the gateway-injected X-Forwarded-User (verified claims'
                        sub). Missing identity on a content mutation fails
                        closed.
"""

import hashlib
import hmac
import os
import time
from typing import Optional
from urllib.parse import urlencode

SERVICE_OWNER = "service"

FORWARDED_USER_HEADER = "x-forwarded-user"


class IdentityRequired(Exception):
    """Raised when a hosted-mode call carries no tenant identity."""


def is_hosted() -> bool:
    return os.getenv("VAAS_HOSTED", "").strip() == "1"


def _request():
    """Return the current HTTP request, or None outside a request context."""
    try:
        from fastmcp.server.dependencies import get_http_request

        return get_http_request()
    except Exception:
        return None


def _bearer_ok(request) -> bool:
    expected = os.getenv("VAAS_BEARER_TOKEN", "")
    if not expected:
        return False  # hosted mode without a configured bearer fails closed
    auth = (request.headers.get("authorization") or "").strip()
    return hmac.compare_digest(auth.lower(), f"bearer {expected}".lower())


def current_owner() -> str:
    """
    Resolve the tenant owner for the current call.

    Local mode: SERVICE_OWNER. Hosted mode: the gateway-injected sub, but only
    after the static service bearer proves the request rode the gateway.
    """
    if not is_hosted():
        return SERVICE_OWNER
    request = _request()
    if request is None or not _bearer_ok(request):
        raise IdentityRequired("hosted call without valid service credential")
    sub = (request.headers.get(FORWARDED_USER_HEADER) or "").strip()
    if not sub:
        raise IdentityRequired("hosted call without tenant identity")
    return sub


def service_auth_ok(request) -> bool:
    """Check the static service bearer on a custom HTTP route."""
    if not is_hosted():
        return True
    return _bearer_ok(request)


# ─── Signed download URLs ──────────────────────────────────────────────────

DOWNLOAD_TTL_SECONDS = int(os.getenv("VAAS_DOWNLOAD_TTL", "86400"))


def _download_hmac_key() -> bytes:
    # Circular-import free: credentials resolves the vault path for us.
    from .credentials import service_secret

    return service_secret("download-hmac").encode("utf-8")


def sign_download(asset_id: str, owner: str, ttl: int = DOWNLOAD_TTL_SECONDS) -> dict:
    exp = int(time.time()) + ttl
    payload = f"{asset_id}:{owner}:{exp}"
    sig = hmac.new(_download_hmac_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"asset_id": asset_id, "owner": owner, "exp": exp, "signature": sig}


def verify_download(asset_id: str, owner: str, exp: int, signature: str) -> bool:
    if exp < int(time.time()):
        return False
    payload = f"{asset_id}:{owner}:{exp}"
    expected = hmac.new(_download_hmac_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def download_url(asset_id: str, owner: str, ttl: int = DOWNLOAD_TTL_SECONDS) -> Optional[str]:
    """Build an absolute signed URL; needs a base (request host or VAAS_PUBLIC_URL)."""
    base = os.getenv("VAAS_PUBLIC_URL", "").rstrip("/")
    if not base:
        request = _request()
        if request is not None:
            base = str(request.base_url).rstrip("/")
    if not base:
        return None
    signed = sign_download(asset_id, owner, ttl)
    return f"{base}/download/{asset_id}?{urlencode(signed)}"

"""
Upstream error classification for the hosted generation plane.

Contract (fix-hosted-generation-correctness):
- tenant-visible errors are a short taxonomy code + actionable message;
  raw upstream bodies (gateway internals, account state) stay server-side.
- taxonomy: invalid_input / credential_unavailable / lane_down /
  upstream_transient / upstream_error / timeout
"""

import json
import logging
import re

log = logging.getLogger("vaas.errors")

# lane-level gateway facts that MUST NOT reach tenants verbatim
_LANE_DOWN_MARKERS = (
    "no available compatible accounts",
    "no eligible",
    "site owner blocked",
)
_TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def _http_status(detail: str) -> int | None:
    m = re.search(r"HTTP (\d{3})", detail)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(50[0234]|42[09]|40[1348])\b", detail)
    return int(m.group(1)) if m else None


def _body_digest(detail: str) -> str:
    """Human-safe one-line summary of an upstream body: keys only when JSON."""
    try:
        doc = json.loads(detail)
        if isinstance(doc, dict):
            err = doc.get("error") or doc
            if isinstance(err, dict):
                return str(err.get("type") or err.get("code") or "upstream error")[:80]
            return str(err)[:80]
    except (ValueError, TypeError):
        pass
    first = next((ln for ln in detail.splitlines() if ln.strip()), "")
    return first[:80]


def classify_upstream_error(operation: str, stderr: str, provider: str = "") -> RuntimeError:
    """Build a tenant-safe RuntimeError; the raw detail goes to the server log.

    The bridge/lane scripts raise ``RuntimeError(... HTTP 503: <body>)``;
    we extract just enough to classify, never echo the body to tenants.
    """
    detail = str(stderr or "")
    log.warning("upstream failure op=%s provider=%s: %s",
                operation, provider, detail[:2000])

    low = detail.lower()
    prov = f" ({provider})" if provider else ""

    if any(m in low for m in _LANE_DOWN_MARKERS):
        return RuntimeError(
            f"lane_down{prov}: the {operation} lane is currently unavailable on the "
            f"upstream side. Do not retry in a tight loop; check "
            f"registry.list_generators for lane health."
        )
    status = _http_status(detail)
    if status in (401, 403) and "blocked" not in low:
        return RuntimeError(
            f"credential_unavailable{prov}: the lane credential was rejected upstream."
        )
    if status in _TRANSIENT_STATUSES:
        kind = "upstream_transient"
        hint = "retry later (the job stays pollable; do not resubmit paid work)"
        if status == 503:
            kind = "lane_down"
            hint = "check registry.list_generators for lane health"
        return RuntimeError(f"{kind}{prov}: upstream HTTP {status} for {operation}; {hint}.")
    if isinstance(stderr, TimeoutError) or "timed out" in low or "timeout" in low:
        return RuntimeError(f"timeout{prov}: the {operation} call exceeded its wall clock.")
    return RuntimeError(
        f"upstream_error{prov}: {operation} failed ({_body_digest(detail)})."
    )


def is_transient(exc: BaseException) -> bool:
    """True for poll failures that must NOT terminally mark a paid job failed."""
    msg = str(exc).lower()
    return any(msg.startswith(p) for p in
               ("upstream_transient", "timeout", "lane_down")) or \
        _http_status(msg) in _TRANSIENT_STATUSES or \
        isinstance(exc, TimeoutError) or "timed out" in msg

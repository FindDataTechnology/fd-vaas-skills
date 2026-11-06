"""Lane health ledger: the machine-readable truth for per-lane availability.

Contract (deliver-hosted-surface W3; spec ciyuan-lane-providers「车道缺陷的记录
与规避」+ generation-registry「方式可发现性」):
- discovery surfaces (models_voices / registry_list_generators) annotate each
  lane-dependent entry with the lane's health;
- a `down` lane must never be advertised as usable;
- lane_down classification lives in generators.errors (tenant-safe);
- clearing a debt requires a real E2E probe — never a status flip alone.
"""

import json
from functools import lru_cache
from pathlib import Path

_HEALTH_PATH = Path(__file__).parent / "lane_health.json"


@lru_cache(maxsize=1)
def load_lane_health(path=_HEALTH_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return {"lanes": {}}


def lane_health(kind: str, provider: str) -> dict:
    """Health view for one lane (kind ∈ voice/image/video/render + provider).

    Unknown lane → conservative `degraded` (unknown ≠ advertise as fine).
    """
    lanes = (load_lane_health() or {}).get("lanes") or {}
    entry = lanes.get(f"{kind}.{provider}")
    if entry:
        return {
            "health": entry.get("health", "degraded"),
            "reason_class": entry.get("reason_class"),
            "reason": entry.get("reason"),
            "last_verified": entry.get("last_verified"),
        }
    return {"health": "degraded", "reason_class": None, "reason": "lane not in health ledger",
            "last_verified": None}


def lane_down(kind: str, provider: str) -> bool:
    return lane_health(kind, provider).get("health") == "down"


def annotate(entries: list[dict], kind: str, provider_key: str = "provider") -> list[dict]:
    """Attach a `lane` health sub-dict to each registry entry (in place)."""
    for e in entries:
        prov = (e.get(provider_key) or "").lower()
        if prov:
            e["lane"] = lane_health(kind, prov)
    return entries

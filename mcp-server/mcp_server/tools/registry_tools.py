"""
registry_* namespace: generation method discovery.

Lane health (deliver-hosted-surface W3): every lane-dependent entry carries
its lane's health sub-dict (health/reason_class/last_verified) from the
machine-readable ledger lane_health.json; a down lane must never be
advertised as usable (spec generation-registry「方式可发现性」).
"""

from typing import Optional

from ..registry import list_generators as _list, get_generator
from ..lane_health import annotate as _annotate

# registry type -> health-lane kind (cloud lanes; local compute maps to the
# always-healthy render.local entry)
_KIND_BY_TYPE = {"voice": "voice", "image": "image", "video": "video",
                 "cover": "render", "chart": "render", "doc": "render"}


def registry_list_generators(type: Optional[str] = None) -> dict:
    """
    List available generation methods, optionally filtered by asset type.

    Args:
        type: Optional filter (voice/image/video/cover/chart/doc)

    Returns:
        Dict with items[] (or a single type's items) listing name/provider/
        model — lane-dependent entries additionally carry
        `lane: {health, reason_class, reason, last_verified}`.
    """
    out = _list(type)
    if out.get("type"):
        kind = _KIND_BY_TYPE.get(out["type"])
        if kind and isinstance(out.get("items"), list):
            _annotate(out["items"], kind)
    else:
        for tname, items in out.items():
            kind = _KIND_BY_TYPE.get(tname)
            if kind and isinstance(items, list):
                _annotate(items, kind)
    return out


def registry_describe_generator(type: str, name: str) -> dict:
    """
    Describe a specific generation method.

    Args:
        type: Asset type (voice/image/video/cover/chart/doc)
        name: Method name (e.g. seedance, voiceover, echarts, chromium)

    Raises:
        ValueError: Unknown type or method
    """
    entry = get_generator(type, name)
    if not entry:
        available = [e["name"] for e in _list(type).get("items", [])]
        raise ValueError(f"Unknown generator: {type}/{name}. Available: {available}")
    kind = _KIND_BY_TYPE.get(type)
    if kind:
        _annotate([entry], kind)
    return {"type": type, **entry}

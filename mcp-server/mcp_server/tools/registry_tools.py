"""
registry_* namespace: generation method discovery.
"""

from typing import Optional

from ..registry import list_generators as _list, get_generator


def registry_list_generators(type: Optional[str] = None) -> dict:
    """
    List available generation methods, optionally filtered by asset type.

    Args:
        type: Optional filter (voice/image/video/cover/copy)

    Returns:
        Methods grouped by type (or a single type's items), each with
        name/provider/model.
    """
    return _list(type)


def registry_describe_generator(type: str, name: str) -> dict:
    """
    Describe a specific generation method.

    Args:
        type: Asset type (voice/image/video/cover/copy)
        name: Method name (e.g. seedance, voiceover)

    Raises:
        ValueError: Unknown type or method
    """
    entry = get_generator(type, name)
    if not entry:
        available = [e["name"] for e in _list(type).get("items", [])]
        raise ValueError(f"Unknown generator: {type}/{name}. Available: {available}")
    return {"type": type, **entry}

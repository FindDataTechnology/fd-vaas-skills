"""
Generation registry: pluggable generation methods keyed by asset type.

Each entry: {name, provider, model, driver}. `driver` resolves to a callable
in DRIVERS. New generation/copy methods = one registry entry + one driver
function; no core dispatch changes.
"""

import json
import os
import re
from pathlib import Path
from typing import Callable, Optional

from .generators.tts import synthesize as _driver_voice
from .generators.image import generate as _driver_image
from .generators.video import generate as _driver_video
from .skills.cover import create_cover as _driver_cover
from .skills.voiceover import create_voiceover_video as _driver_voiceover
from .skills.brainstorm import brainstorm as _driver_brainstorm

# driver name -> callable (add a line here + a registry.json entry for a new method)
DRIVERS: dict[str, Callable] = {
    "generate_voice": _driver_voice,
    "generate_image": _driver_image,
    "generate_video": _driver_video,
    "create_cover": _driver_cover,
    "create_voiceover": _driver_voiceover,
    "brainstorm": _driver_brainstorm,
}

REGISTRY_PATH = Path(__file__).parent.parent / "registry.json"

_ENV_REF = re.compile(r"\$\{([A-Z0-9_]+)\}")

_VAAS_ROOT = Path(__file__).parent.parent.parent


def _load_env() -> None:
    """Load VAAS/.env into os.environ if present (does not override existing)."""
    env_path = _VAAS_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()


def _resolve(value: str) -> str:
    """Resolve ${ENV_VAR} references in model strings."""
    _load_env()
    def repl(m: re.Match) -> str:
        return os.getenv(m.group(1), m.group(0))
    return _ENV_REF.sub(repl, value)


def load_registry() -> dict:
    """Load and resolve the generation registry from registry.json."""
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    resolved = {}
    for asset_type, entries in raw.items():
        resolved[asset_type] = [{
            "name": e["name"],
            "provider": e["provider"],
            "model": _resolve(e["model"]),
            "driver": e["driver"],
        } for e in entries]
    return resolved


def list_generators(asset_type: Optional[str] = None) -> dict:
    """
    List available generation methods, optionally filtered by asset type.

    Args:
        asset_type: Optional filter (voice/image/video/cover/copy)

    Returns:
        Dict with items[] (or a single type's items) listing name/provider/model
    """
    reg = load_registry()
    if asset_type:
        return {"type": asset_type, "items": reg.get(asset_type, [])}
    return {t: items for t, items in reg.items()}


def get_generator(asset_type: str, name: str) -> Optional[dict]:
    for e in load_registry().get(asset_type, []):
        if e["name"] == name:
            return e
    return None


def dispatch(asset_type: str, name: str, params: dict):
    """
    Dispatch a generation call to the registered driver.

    Raises:
        ValueError: Unknown generation method (lists available names)
    """
    entry = get_generator(asset_type, name)
    if not entry:
        available = [e["name"] for e in load_registry().get(asset_type, [])]
        raise ValueError(
            f"Unknown {asset_type} generator: {name}. Available: {available}"
        )
    driver = DRIVERS.get(entry["driver"])
    if not driver:
        raise ValueError(f"Driver not implemented: {entry['driver']}")
    return driver(**params)

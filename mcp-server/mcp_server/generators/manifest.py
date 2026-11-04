"""Load the generation capabilities manifest (models/voices truth table)."""
import json
from functools import lru_cache
from pathlib import Path

_MANIFEST_PATH = Path(__file__).with_name("voices_manifest.json")


@lru_cache(maxsize=1)
def load_manifest(path=_MANIFEST_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return {"kind": "tts", "providers": {}}

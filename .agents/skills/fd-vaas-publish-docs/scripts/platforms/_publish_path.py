"""Resolve the shared publish lib path (unify-publish-lib design D1).

The single canonical `browser_utils.py` lives at
`<VAAS>/.agents/skills/_shared/publish/`.  Each platform script calls
`add_publish_path()` instead of hardcoding a relative ``../lib`` path, so there
is only one browser-automation module to maintain across both publish skills.

This file is intentionally duplicated per skill (`scripts/platforms/_publish_path.py`)
because a platform script cannot import from the shared dir until that dir is on
``sys.path`` — it must first be found from a location it already knows.
"""
import os
import sys

_SHARED_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "_shared", "publish")
)


def add_publish_path():
    """Add `<VAAS>/.agents/skills/_shared/publish/` to sys.path and return it."""
    if not os.path.isfile(os.path.join(_SHARED_DIR, "browser_utils.py")):
        raise FileNotFoundError(
            f"shared publish lib not found under {_SHARED_DIR}; "
            "expected <VAAS>/.agents/skills/_shared/publish/browser_utils.py"
        )
    if _SHARED_DIR not in sys.path:
        sys.path.insert(0, _SHARED_DIR)
    return _SHARED_DIR

"""VAAS-generated conf for the vendored social-auto-upload upstream.

This file is OURS — it is NOT overwritten by scripts/sync-upstream.sh
(that script only syncs uploader/, utils/, conf.example.py).
If upstream adds new config keys, re-check conf.example.py after a sync.

BASE_DIR points at this vendored root so upstream's cookies/ and logs/
land next to the vendored code (both gitignored runtime state).
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

# xhs_uploader (API-signing variant) only — we use xiaohongshu_uploader (web),
# so this is unused but must exist for import.
XHS_SERVER = "http://127.0.0.1:11901"

# Empty = use patchright's bundled chromium (channel="chromium"/"chrome").
LOCAL_CHROME_PATH = ""

# Headed by default. douyin cookie_auth MUST be headed (headless triggers
# anti-crawl); headed is also more reliable for the other platforms and lets
# the user see / intervene in the publish flow. Override per-call via the
# adapter's --headless flag (youtube/xiaohongshu tolerate headless).
LOCAL_CHROME_HEADLESS = False

DEBUG_MODE = True

# YouTube is blocked in CN; point at the local proxy when uploading to YT.
# Set VAAS_YT_PROXY=http://127.0.0.1:7892 (or similar) in the environment.
YT_PROXY = os.environ.get("VAAS_YT_PROXY") or None

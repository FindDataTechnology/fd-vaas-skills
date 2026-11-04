"""
W2.1 (add-presentation-plane) echarts vendor + 品牌主题漂移测试.

theme.ts 是品牌单一来源；echarts-theme.json 由 scripts/gen-echarts-theme.mjs
生成。theme.ts 改了没重跑生成器 → --check 漂移测试变红。
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

MCP_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = MCP_ROOT.parent
GEN_SCRIPT = REPO_ROOT / "scripts" / "gen-echarts-theme.mjs"
ECHARTS_DIR = MCP_ROOT / "mcp_server" / "templates" / "echarts"
ECHARTS_JS = ECHARTS_DIR / "echarts.min.js"
THEME_JSON = ECHARTS_DIR / "echarts-theme.json"


def _pinned_version() -> str:
    """钉住的 echarts 版本（生成器常量是唯一 pin 源）。"""
    return json.loads(THEME_JSON.read_text(encoding="utf-8"))["meta"]["echarts"]


def test_theme_json_matches_theme_ts():
    """重跑生成器 --check 对比仓库内 JSON：theme.ts 改了没重生成 → 红。"""
    if not GEN_SCRIPT.is_file():
        pytest.fail(f"generator missing: {GEN_SCRIPT}")
    if shutil.which("node") is None:
        pytest.skip("node unavailable on this host")
    proc = subprocess.run(
        ["node", str(GEN_SCRIPT), "--check"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60)
    assert proc.returncode == 0, (
        "echarts-theme.json drifted from theme.ts — re-run:\n"
        "  node scripts/gen-echarts-theme.mjs\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}")


def test_echarts_vendor_present_and_version_matches_pin():
    assert ECHARTS_JS.is_file(), (
        f"echarts.min.js missing: {ECHARTS_JS} — vendor echarts@{_pinned_version()}")
    text = ECHARTS_JS.read_text(encoding="utf-8")
    assert f'version="{_pinned_version()}"' in text, (
        "vendored echarts version does not match the pin in "
        "gen-echarts-theme.mjs / echarts-theme.json meta.echarts")


def test_theme_json_structure():
    doc = json.loads(THEME_JSON.read_text(encoding="utf-8"))
    assert doc["meta"]["source"] == "remotion-app/src/theme.ts"
    assert doc["meta"]["echarts"].startswith("5.")
    assert doc["palette"] and all(c.startswith("#") for c in doc["palette"])
    brand = doc["brand"]
    for key in ("bg", "surface", "border", "text", "muted", "accent",
                "fontSans", "fontMono"):
        assert brand.get(key), f"brand.{key} missing"
    # 部署镜像 fonts-noto-cjk 的家族名必须折入字体栈（echarts canvas/svg 文本）
    assert "Noto Sans CJK SC" in brand["fontSans"]
    theme = doc["theme"]
    for key in ("color", "backgroundColor", "textStyle", "title", "legend",
                "tooltip", "categoryAxis", "valueAxis"):
        assert key in theme, f"theme.{key} missing"
    assert theme["color"] == doc["palette"]

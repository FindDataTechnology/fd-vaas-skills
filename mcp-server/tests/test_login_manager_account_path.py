"""面板的 cookie 路径解析必须与发布侧同口径（含快手迁移回退）。

事故（2026-11-11）：快手 cookie 从 `cookies/kuaishou_creator.json`（平铺）迁到
`cookies/kuaishou_creator/account.json`（与其它平台同构），**文件没搬**。
发布侧 `sau_adapter._account_path()` 有回退，照常能读；面板直接取
`REGISTRY[p]["account_file"]`，于是 `has_cookie=False`——**假阴性**：
磁盘上 4020B 的 cookie 真在，用户却以为掉登录去白扫一次码。

判据不手抄：直接加载真实 `login-manager.py`（顶层无重依赖，只起 server 时才 bind），
调用真实的 `account_path()`，与 `sau_adapter` 的回退口径对照。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / ".agents/skills/fd-vaas-login/scripts/login-manager.py"
LEGACY_KUAISHOU = (
    ROOT
    / ".agents/skills/fd-vaas-publish-videos/scripts/upstream/cookies/kuaishou_creator.json"
)


def _load_panel():
    spec = importlib.util.spec_from_file_location("login_manager_under_test", PANEL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kuaishou_resolves_to_existing_file():
    """快手必须解析到一个**真实存在**的文件（新路径或缺省时回退到旧平铺路径）。"""
    panel = _load_panel()
    p = panel.account_path("kuaishou")
    assert p is not None
    if LEGACY_KUAISHOU.exists():
        assert p.exists(), f"快手解析出的路径不存在：{p}"
        assert p.name in ("account.json", "kuaishou_creator.json")


def test_kuaishou_fallback_matches_publisher():
    """面板与发布侧对快手必须指向同一个文件（避免一边有、一边无）。"""
    panel = _load_panel()
    panel_path = panel.account_path("kuaishou")

    import sys

    adapter_dir = ROOT / ".agents/skills/fd-vaas-publish-videos/scripts/platforms"
    sys.path.insert(0, str(adapter_dir))
    try:
        import sau_adapter  # noqa: WPS433 - 被测模块，路径需要临时注入

        pub_path = sau_adapter._account_path("kuaishou")
    finally:
        sys.path.pop(0)

    assert Path(panel_path).resolve() == Path(pub_path).resolve(), (
        f"面板={panel_path}  发布侧={pub_path}"
    )


def test_bilibili_has_no_cookie_file():
    """bilibili 走 profile 模式，account_file=None 时必须返回 None 而不是抛错。"""
    panel = _load_panel()
    assert panel.account_path("bilibili") is None


def test_unknown_platform_is_safe():
    panel = _load_panel()
    assert panel.account_path("no_such_platform") is None

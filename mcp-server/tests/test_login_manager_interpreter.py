"""登录管理页的两个「静默失效」回归闸。

背景（2026-11-10 现场）：用户点「扫码登录」没有二维码。根因是
login-manager.py 用 `shutil.which("python3")` 拉起子进程，系统 python 换
major 后缺 playwright → 子进程秒死于 ModuleNotFoundError，浏览器不弹、
二维码永不生成。修复：解释器优先仓内 .venv。

第二个坑同源：子进程 stdout 是 pipe 时 Python 块缓冲，页面在进程结束前
拿不到任何一行输出，表现同样是「点了没反应」。

这两条都属于「不报错、只是不工作」，只能靠测试钉住：
- test_resolves_repo_venv_interpreter：PATH 上的 python3 是错的也必须选 .venv
- test_vaas_python_env_overrides：显式指定优先
- test_every_spawn_is_unbuffered：六处 spawn 都必须带 -u
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

VAAS = Path(__file__).resolve().parents[2]
LOGIN_MANAGER = VAAS / ".agents/skills/fd-vaas-login/scripts/login-manager.py"


def _load(monkeypatch=None, vaas_python=None):
    """按文件路径加载 login-manager.py（它不在任何包的 import 路径上）。"""
    if monkeypatch is not None:
        if vaas_python is None:
            monkeypatch.delenv("VAAS_PYTHON", raising=False)
        else:
            monkeypatch.setenv("VAAS_PYTHON", vaas_python)
    spec = importlib.util.spec_from_file_location("login_manager_under_test", LOGIN_MANAGER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not LOGIN_MANAGER.is_file(), reason="login-manager.py 不存在")
def test_resolves_repo_venv_interpreter(monkeypatch):
    """仓内有 .venv 时必须选它，而不是 PATH 上的 python3。

    这正是「点了没二维码」的根因：PATH 上的 /opt/homebrew/bin/python3 缺
    playwright，子进程秒死。
    """
    venv_py = VAAS / ".venv/bin/python"
    if not venv_py.exists():
        pytest.skip("本机无 .venv（CI 里没有），解释器优先级在本地验")

    mod = _load(monkeypatch, vaas_python=None)
    assert Path(mod.PY) == venv_py, (
        f"未选中仓内 venv：{mod.PY}；PATH 上的解释器可能缺 playwright/patchright，"
        "扫码登录子进程会秒死（见 2026-11-10 现场）"
    )


@pytest.mark.skipif(not LOGIN_MANAGER.is_file(), reason="login-manager.py 不存在")
def test_vaas_python_env_overrides(monkeypatch, tmp_path):
    """VAAS_PYTHON 显式指定时优先（换机/装多套解释器时的逃生口）。"""
    fake = tmp_path / "python"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    mod = _load(monkeypatch, vaas_python=str(fake))
    assert Path(mod.PY) == fake


@pytest.mark.skipif(not LOGIN_MANAGER.is_file(), reason="login-manager.py 不存在")
def test_every_spawn_is_unbuffered():
    """六处 spawn 都必须带 -u。

    子进程 stdout 是 pipe 时 Python 块缓冲；不带 -u 时页面在进程结束前拿不到
    任何输出（youtube_login.py 用 print 而非 loguru，就是这个表现）。
    """
    src = LOGIN_MANAGER.read_text(encoding="utf-8")
    sites = re.findall(r"cmd = \[PY,\s*([^,]+),", src)
    assert len(sites) >= 6, f"spawn 点数量异常（{len(sites)}），可能改了实现方式"
    offenders = [s for s in sites if s.strip() != '"-u"']
    assert not offenders, f"有 spawn 未加 -u（输出会被缓冲，页面看不到进度）: {offenders}"

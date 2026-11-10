"""headless 白名单守卫：判据读 body 文案的平台不得进 HEADLESS_SAFE_CHECK。

为什么要有这条：2026-11-10 实测 xueqiu 在 headless 下判「已登录」、有头判「未登录」
——同一 profile、同一 URL、同一 _detect，只差 headless 开关。原因是它的未登录信号
藏在页内弹层的 innerText 里，headless 渲染不出来。这是**假阳性**：面板绿、发布时才炸。

判据必须来自源码本身，不能手抄一份名单（否则抄错就一起错）：
  1. 解析 docs_login.py，找到 _detect 里所有含 page.evaluate 的分支 → 这些平台=body 判据
  2. 断言它们与 HEADLESS_SAFE_CHECK 交集为空
  3. 断言 headless 取值确实引用了 HEADLESS_SAFE_CHECK（防止有人把它改回写死 False）
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

DOCS_LOGIN = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/fd-vaas-login/scripts/docs_login.py"
)


def _module(tree: ast.Module):
    return tree


def _detect_source() -> str:
    tree = ast.parse(DOCS_LOGIN.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_detect":
            return ast.get_source_segment(DOCS_LOGIN.read_text(encoding="utf-8"), node) or ""
    raise AssertionError("docs_login.py 里找不到 _detect()")


def _headless_safe_check() -> set[str]:
    tree = ast.parse(DOCS_LOGIN.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if getattr(t, "id", None) == "HEADLESS_SAFE_CHECK":
                    return {e.value for e in node.value.elts}
    raise AssertionError("docs_login.py 里找不到 HEADLESS_SAFE_CHECK 集合")


def test_body_text_platforms_are_not_headless():
    src = _detect_source()
    blocks = re.split(r"\n\s*(?:if|elif) platform ==", src)
    body_platforms = set()
    for block in blocks[1:]:
        name = block.strip().split('"')[1] if '"' in block else ""
        if "page.evaluate" in block:
            body_platforms.add(name)
    assert body_platforms, "未能从 _detect 识别出任何 body 文案判据平台 —— 守卫已失效，需修解析"
    clash = body_platforms & _headless_safe_check()
    assert not clash, (
        f"这些平台的判据依赖 body 文案，headless 会假阳性（实测 xueqiu）：{sorted(clash)}；"
        "请从 HEADLESS_SAFE_CHECK 移除"
    )


def test_headless_flag_consults_policy():
    """headless 取值必须同时受 mode 与白名单约束。

    按行取证而不是按括号正则：写成 headless=False 时没有括号，正则抓不到，
    报错会指向「没找到」而不是「绕过了策略」——断言必须对准坏的那个本身。
    """
    src = DOCS_LOGIN.read_text(encoding="utf-8")
    assert "HEADLESS_SAFE_CHECK" in src, "HEADLESS_SAFE_CHECK 被删了"
    lines = [ln.strip() for ln in src.splitlines() if "headless=" in ln]
    assert lines, "launch_persistent_context 的 headless= 取值没找到"
    expr = " ".join(lines)
    assert "HEADLESS_SAFE_CHECK" in expr, f"headless 未受白名单约束（写死 False？）：{expr}"
    assert 'mode == "check"' in expr, f"headless 未按 mode 区分（login 也会开 headless）：{expr}"

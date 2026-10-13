#!/usr/bin/env python3
"""校验 fd-vaas-login 的 PLATFORM_REGISTRY 与 sau_adapter 的 REGISTRY 是否一致。

为什么要有这个检查：login-manager 的 registry key 会被直接拼进
`sau_adapter.py --platform <key>`，起个别名（比如 weibo_video）不会报「未知平台」
那样直白的错，而是在深处 KeyError / 静默走错分支。加平台时极易踩。

用法：
    python3 scripts/check-registry-consistency.py
退出码 0 = 一致；1 = 有不一致。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGIN_MANAGER = HERE / "login-manager.py"
SAU_ADAPTER = (
    HERE.parent.parent
    / "fd-vaas-publish-videos"
    / "scripts"
    / "platforms"
    / "sau_adapter.py"
)
PUBLISH_MJS = HERE.parent.parent / "fd-vaas-publish-videos" / "scripts" / "publish.mjs"

# 不经 sau_adapter 的平台（走自有 profile / 独立脚本）
ADAPTER_EXEMPT = {"bilibili"}


def extract_login_keys(path: Path) -> list[str]:
    """从 login-manager.py 源码里静态取出 PLATFORM_REGISTRY 的顶层 key。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == "PLATFORM_REGISTRY":
                    return [k.value for k in node.value.keys]
    raise RuntimeError(f"未在 {path} 找到 PLATFORM_REGISTRY")


def extract_adapter_keys(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == "REGISTRY":
                    return [k.value for k in node.value.keys]
    raise RuntimeError(f"未在 {path} 找到 REGISTRY")


def extract_mjs_platforms(path: Path) -> set[str]:
    """从 publish.mjs 的 SAU_PLATFORMS Set 里取平台名。"""
    src = path.read_text(encoding="utf-8")
    start = src.find("const SAU_PLATFORMS")
    if start == -1:
        raise RuntimeError(f"未在 {path} 找到 SAU_PLATFORMS")
    end = src.find("])", start)
    block = src[start:end]
    return {s.strip().strip('"') for s in block.split('"') if s.strip() in _KNOWN(block)}


def _KNOWN(block: str) -> set[str]:
    # 逐个候选 token，凡是被引号包裹且形如平台名的都算
    import re

    return set(re.findall(r'"([a-z_]+)"', block))


def main() -> int:
    errors: list[str] = []

    login_keys = extract_login_keys(LOGIN_MANAGER)
    adapter_keys = set(extract_adapter_keys(SAU_ADAPTER))
    mjs_keys = extract_mjs_platforms(PUBLISH_MJS)

    print(f"login-manager 平台数: {len(login_keys)}")
    print(f"sau_adapter  平台数: {len(adapter_keys)}")
    print(f"publish.mjs  平台数: {len(mjs_keys)}")

    # 1) login-manager 的 key 必须能被 adapter 接受（豁免的除外）
    for k in login_keys:
        if k in ADAPTER_EXEMPT:
            continue
        if k not in adapter_keys:
            errors.append(
                f"login-manager 的 '{k}' 不在 sau_adapter REGISTRY 里 —— "
                f"它会被拼成 `--platform {k}` 而报 KeyError。key 必须与 adapter 一致，显示名放 name 字段。"
            )

    # 2) mjs 侧声明走 adapter 的平台，adapter 必须真的支持
    for k in sorted(mjs_keys):
        if k not in adapter_keys:
            errors.append(
                f"publish.mjs 的 SAU_PLATFORMS 含 '{k}'，但 sau_adapter REGISTRY 没有它（会找不到 script）。"
            )

    # 3) adapter 支持但 mjs 未声明（提示级，不算错——可能是只给 login 用）
    only_adapter = sorted(adapter_keys - mjs_keys)
    if only_adapter:
        print(f"ℹ  adapter 有、mjs 未声明（可发布但入口未列）: {only_adapter}")

    if errors:
        print("\n❌ 注册表不一致:")
        for e in errors:
            print(f"   - {e}")
        return 1

    print("\n✅ 注册表一致：login-manager ↔ sau_adapter ↔ publish.mjs")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Builder 自动发现/注册（add-typed-video-html-renderer W1.1）。

扫本包下 builders/*.py（下划线前缀除外），导入后取其 BUILDER 属性
（AbstractBuilder 实例）注册进 typed_scenes.BUILDER_REGISTRY。并行波次新增
builder = 落一个文件、导出 BUILDER，注册零改动。

发现是幂等的（重复调用不重复注册——register 对同实例幂等），由
typed_scenes/__init__ 末尾触发一次。
"""

import importlib
import pkgutil


def discover_builders() -> None:
    from .. import AbstractBuilder, register

    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f".{m.name}", __name__)
        builder = getattr(mod, "BUILDER", None)
        if builder is None:
            continue
        if not isinstance(builder, AbstractBuilder):
            raise TypeError(
                f"builder module '{m.name}' exports BUILDER that is not an "
                f"AbstractBuilder: {type(builder)!r}")
        # register 对同 type_id 幂等；并行波次撞 type_id（不同实例）在此显式暴露
        register(builder)


# 模块导入即发现（兼容直接 import mcp_server.tools.typed_scenes.builders 的用法）
discover_builders()

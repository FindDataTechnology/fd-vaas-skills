"""
Typed-scene 品牌 CSS wrapper（add-typed-video-html-renderer W1.3）。

builder 场景 HTML 的品牌底座单一来源：mcp_server/templates/echarts/
echarts-theme.json（scripts/gen-echarts-theme.mjs 从 brand/theme.ts
生成——palette + brand 变量），经 :root 自定义属性注入（--vaas-*，
kebab-case），builder 的卡片 CSS 直接消费。与 still_graphic 的 wrapper 同源
同形；取数边界仍走 still_chart._load_theme_doc（theme.ts 改动重跑生成器后
无需重启进程）。

场景页零外链：只有内联 CSS/JS 与系统字体栈（theme 的 fontSans），动效由
window.seek(t) 纯函数驱动——compose 逐帧路径 + _assert_scenes_offline 硬
校验的契约面（html_full 场景必须自带 __DURATION__/__SIZE__/data-stage/seek）。
"""

import re

from ..still_chart import _load_theme_doc, _js_json

__all__ = ["load_theme", "brand_root_style", "wrap_scene_html",
           "SEEK_HELPERS_JS", "js_str"]


def load_theme() -> dict:
    """读 echarts-theme.json（每次调用现读，生成器重跑后无需重启进程）。"""
    return _load_theme_doc()


def _kebab(name: str) -> str:
    """brand 键 camelCase → CSS 自定义属性 kebab-case（fontSans → font-sans）。"""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def brand_root_style(theme: dict) -> str:
    """theme doc → :root{--vaas-*} 变量串（brand 全量 + palette 编号槽位）。"""
    decls = [f"--vaas-{_kebab(str(k))}:{v}"
             for k, v in (theme.get("brand") or {}).items()]
    decls += [f"--vaas-palette-{i}:{c}"
              for i, c in enumerate(theme.get("palette") or [])]
    return ":root{" + ";".join(decls) + "}"


def js_str(value) -> str:
    """Python 值 → 内联 <script> 安全的 JS 字面量（</ 转义防 script 提前闭合）。"""
    return _js_json(value)


# 各卡片共用的 seek 工具（阶跃入场：t 落在第几步，纯函数、无过渡动画）
SEEK_HELPERS_JS = (
    "const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));\n"
    "const stepIn=(t,t0,steps,stepS)=>clamp(Math.floor((t-t0)/stepS)+1,0,steps);"
)


def wrap_scene_html(*, size, duration_s: float, body: str, css: str = "",
                    js: str, theme: dict) -> str:
    """builder 卡片 body/css/js → seek 契约整页。

    注入 window.__DURATION__/__SIZE__、品牌 :root 变量、data-stage 基线
    （1080 类画幅下卡片 CSS 用固定 px，两种 orientation 通用）。js 末尾由
    builder 保证 window.seek(0) 首帧落位。
    """
    w, h = int(size[0]), int(size[1])
    dur = float(duration_s)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script>window.__DURATION__={dur};window.__SIZE__=[{w},{h}];</script>
<style>{brand_root_style(theme)}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;background:var(--vaas-bg)}}
[data-stage]{{position:relative;width:{w}px;height:{h}px;overflow:hidden}}
body{{font-family:var(--vaas-font-sans);color:var(--vaas-text)}}
{css}
</style></head>
<body><div data-stage>
{body}
</div>
<script>
{SEEK_HELPERS_JS}
{js}
</script></body></html>
"""

"""storyboard 场景序列 → HyperFrames composition（W4.1）。

storyboard 模式的历史契约是「一场景一整页 + window.seek」。HyperFrames 是
「一个 composition + 多轨 clips」，所以这里做一次降级编译：

  html_intro / html_outro → 标题卡片段（品牌渐变底 + 标题/副标题入场阶跃）
  kenburns                → 图片片段（多图按时间切片切换 + 缓慢推拉）
  html_full               → 调用方 HTML 片段**原样**作为该 clip 内容（静态；
                            需要动画请在片段内用 CSS 动画或改用 type 模式/
                            直接 composition 契约）

所有片段只带 `seek_js`（局部时间纯函数），由 composition.build_composition_html
统一装配成 window.__timelines['main'] 的逐帧驱动；文本静态内联，不做顶层 DOM 写
（HyperFrames 脚本早于元素挂载）。

零外链：图片一律 data: URI；调用方 html_full 会过 composition 的外链硬校验。
"""

from pathlib import Path
from typing import Optional

from ..utils import DOWNLOADS_DIR, VAAS_ROOT  # noqa: F401  (解析器信任面一致)
from ._scene_guard import find_external_refs
from .composition import build_composition_html
from .typed_scenes.theme import load_theme
from .typed_scenes.builders._stage import BASE_BG as _BASE_BG, FURNITURE_HTML

_FONT_STACK = ("'PingFang SC','Noto Sans CJK SC','Source Han Sans SC',"
               "'Microsoft YaHei',sans-serif")

_CARD_CSS = (
    "/* 底(0) < 品牌家具(1) < 内容(2)：家具先于不透明底座进 DOM，必须显式抬层，" "\n"
    "   否则被整块盖住（四族 type 模式已踩过，storyboard 同步） */" "\n"
    ".sb-clip{position:absolute;inset:0;z-index:0;background:" + _BASE_BG + "}"
    ".sb-wrap{position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;" "\n"
    "  justify-content:center;padding:0 9vmin;opacity:0}" "\n"
    ".sb-title{font-size:7.6vmin;line-height:1.28;font-weight:800;" "\n"
    "  color:var(--vaas-text);letter-spacing:0.2vmin}" "\n"
    ".sb-sub{margin-top:3vmin;font-size:3.8vmin;line-height:1.5;color:var(--vaas-muted)}" "\n"
    ".furn-side{position:absolute;z-index:1;left:0;top:0;bottom:0;width:1.4vmin;" "\n"
    "  background:linear-gradient(180deg,var(--vaas-accent) 0%," "\n"
    "  color-mix(in srgb,var(--vaas-accent) 35%,transparent) 60%,transparent 100%)}" "\n"
    ".furn-band{position:absolute;z-index:1;left:0;right:0;bottom:0;height:11vmin;" "\n"
    "  background:linear-gradient(0deg," "\n"
    "  color-mix(in srgb,var(--vaas-accent) 20%,transparent) 0%,transparent 100%)}" "\n"
    ".furn-mark{position:absolute;z-index:1;left:9vmin;bottom:3.4vmin;" "\n"
    "  font-size:2.6vmin;letter-spacing:0.8vmin;color:var(--vaas-muted)}" "\n"
    ".sb-frame{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}" "\n"
    ".sb-cap{position:absolute;z-index:2;left:6vmin;right:6vmin;bottom:8vmin;" "\n"
    "  color:var(--vaas-text);font-size:4.2vmin;line-height:1.4;font-weight:700;" "\n"
    "  opacity:0;text-shadow:0 0.2vmin 1.4vmin rgba(0,0,0,.65)}" "\n"
    ".sb-frag{position:absolute;inset:0;z-index:2}" "\n"
)


_MOTION = {
    "pan_down": ("translate(0,'+(-rel*6)+'%) scale('+(1+rel*0.04)+')'"),
    "zoom_in": ("'scale('+(1+rel*0.08)+')'"),
    "pan_right": ("'translate('+(-rel*5)+'%,0) scale(1.06)'"),
}


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _card_clip(root: str, title: str, sub: str,
               caller_css: str = "") -> tuple[str, str]:
    body = (FURNITURE_HTML +
            f'<div class="sb-clip"><div class="sb-wrap" id="{root}-w">'
            f'<div class="sb-title">{_esc(title)}</div>'
            f'<div class="sb-sub">{_esc(sub)}</div></div></div>')
    if caller_css:
        body = f"<style>{caller_css}</style>" + body
    seek = (
        "function (lt) {\n"
        f"    var w = document.getElementById('{root}-w');\n"
        "    if (!w) { return; }\n"
        "    var p = Math.min(1, Math.max(0, lt / 0.45));\n"
        "    w.style.opacity = String(p);\n"
        "    w.style.transform = 'translateY(' + ((1 - p) * 24) + 'px)';\n"
        "  }"
    )
    return f"<style>{_CARD_CSS}</style>{body}", seek


def _kenburns_clip(root: str, scene: dict) -> tuple[str, str]:
    from .render import _data_uri, _resolve_input_file  # 复用既有解析与内联

    imgs = scene.get("images") or []
    if not imgs:
        raise ValueError("kenburns scene needs non-empty images")
    srcs = []
    for p in imgs:
        path = _resolve_input_file(p)
        if not path.is_file():
            raise ValueError(f"kenburns image not found: {p}")
        srcs.append(_data_uri(path))
    tags = "".join(
        f'<img class="sb-frame" id="{root}-i{i}" src="{s}"'
        + ("" if i == 0 else ' style="display:none"') + ">"
        for i, s in enumerate(srcs))
    cap = scene.get("caption") or ""
    body = (FURNITURE_HTML +
            f'<div class="sb-clip">{tags}'
            f'<div class="sb-cap" id="{root}-cap">{_esc(cap)}</div></div>')
    motion = scene.get("motion", "pan_down")
    transform = _MOTION.get(motion, _MOTION["pan_down"])
    seek = (
        "function (lt) {\n"
        f"    var N = {len(srcs)};\n"
        "    var dur = " + f"{float(scene['duration_s']):.6f}" + ";\n"
        "    var seg = dur / N;\n"
        "    var i = Math.min(N - 1, Math.floor(lt / seg));\n"
        "    var rel = (lt - i * seg) / seg;\n"
        "    for (var j = 0; j < N; j++) {\n"
        f"      var im = document.getElementById('{root}-i' + j);\n"
        "      if (im) { im.style.display = j === i ? 'block' : 'none'; }\n"
        "    }\n"
        f"    var cur = document.getElementById('{root}-i' + i);\n"
        f"    if (cur) {{ cur.style.transform = {transform}; }}\n"
        f"    var cap = document.getElementById('{root}-cap');\n"
        "    if (cap) { cap.style.opacity = String(Math.min(1, rel * 4)); }\n"
        "  }"
    )
    return f"<style>{_CARD_CSS}</style>{body}", seek


def _fragment_clip(scene: dict) -> tuple[str, Optional[str]]:
    html = scene.get("html") or ""
    if not html.strip():
        raise ValueError("html_full scene needs scene.html inline content")
    return (f"<style>{_CARD_CSS}</style>" + FURNITURE_HTML
            + f'<div class="sb-frag">{html}</div>'), None


def storyboard_to_composition(storyboard: dict, fps: int = 30,
                              theme: Optional[dict] = None) -> tuple[str, dict]:
    """storyboard → (composition HTML, 摘要)。返回的 html 已通过零外链硬校验。"""
    scenes = list(storyboard.get("scenes") or [])
    if not scenes:
        raise ValueError("storyboard.scenes must not be empty")
    size = storyboard.get("size") or [1080, 1920]
    if isinstance(size, dict):
        size = [int(size["width"]), int(size["height"])]
    if not (isinstance(size, (list, tuple)) and len(size) == 2):
        raise ValueError('storyboard.size must be [width, height] or {"width","height"}')

    theme = theme or load_theme()
    tracks: list[dict] = []
    visual: list[dict] = []
    violations: list[str] = []
    start = 0.0
    for i, scene in enumerate(scenes):
        kind = scene.get("kind", "html_intro")
        dur = float(scene["duration_s"])
        if dur <= 0:
            raise ValueError(f"scene {i} duration_s must be > 0")
        root = f"sb{i}"
        if kind in ("html_intro", "html_outro"):
            html, seek = _card_clip(root,
                                    str(scene.get("title") or ""),
                                    str(scene.get("sub") or ""),
                                    str(scene.get("css") or ""))
        elif kind == "kenburns":
            html, seek = _kenburns_clip(root, scene)
        elif kind == "html_full":
            html, seek = _fragment_clip(scene)
        else:
            raise ValueError(f"unknown scene kind: {kind}")
        violations.extend(
            f"scene {i} ({kind}): {ref}" for ref in find_external_refs(html))
        clip = {"start": round(start, 6), "duration": round(dur, 6),
                "html": html}
        if seek:
            clip["seek_js"] = seek
        visual.append(clip)
        start = round(start + dur, 6)

    if violations:
        raise ValueError(
            "外置场景含外链资源（渲染面离线，零外链约束）；修法：把资源"
            "内联为 data: URI 或改用相对路径：\n  - "
            + "\n  - ".join(violations))

    tracks.append({"index": 0, "kind": "visual", "clips": visual})
    spec = {"size": list(size), "duration_s": round(start, 6),
            "fps": int(fps), "tracks": tracks}
    html = build_composition_html(spec, theme)
    return html, {"scenes": len(scenes), "duration_s": spec["duration_s"],
                  "fps": int(fps), "size": list(size)}

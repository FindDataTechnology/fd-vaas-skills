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
from .composition import build_composition_html
from .typed_scenes.theme import load_theme

_FONT_STACK = ("'PingFang SC','Noto Sans CJK SC','Source Han Sans SC',"
               "'Microsoft YaHei',sans-serif")

_CARD_CSS = """
.sb-clip{position:absolute;inset:0;background:linear-gradient(160deg,
  var(--vaas-bg) 0%,var(--vaas-bg1) 55%,var(--vaas-surface) 130%)}
.sb-wrap{position:absolute;inset:0;display:flex;flex-direction:column;
  justify-content:center;padding:0 12%;opacity:0}
.sb-title{font-size:76px;line-height:1.28;font-weight:800;color:var(--vaas-text);
  letter-spacing:2px}
.sb-sub{margin-top:34px;font-size:38px;line-height:1.5;color:var(--vaas-muted)}
.sb-frame{position:absolute;top:-4%;left:-4%;width:108%;height:108%;
  object-fit:cover}
.sb-cap{position:absolute;left:6%;bottom:6%;color:var(--vaas-text);
  font-size:42px;line-height:1.4;font-weight:700;opacity:0;
  text-shadow:0 2px 14px rgba(0,0,0,.65)}
.sb-frag{position:absolute;inset:0}
"""

_MOTION = {
    "pan_down": ("translate(0,'+(-rel*6)+'%) scale('+(1+rel*0.04)+')'"),
    "zoom_in": ("'scale('+(1+rel*0.08)+')'"),
    "pan_right": ("'translate('+(-rel*5)+'%,0) scale(1.06)'"),
}


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _card_clip(root: str, title: str, sub: str) -> tuple[str, str]:
    body = (f'<div class="sb-clip"><div class="sb-wrap" id="{root}-w">'
            f'<div class="sb-title">{_esc(title)}</div>'
            f'<div class="sb-sub">{_esc(sub)}</div></div></div>')
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
    body = (f'<div class="sb-clip">{tags}'
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
    return f"<style>{_CARD_CSS}</style><div class=\"sb-frag\">{html}</div>", None


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
                                    str(scene.get("sub") or ""))
        elif kind == "kenburns":
            html, seek = _kenburns_clip(root, scene)
        elif kind == "html_full":
            html, seek = _fragment_clip(scene)
        else:
            raise ValueError(f"unknown scene kind: {kind}")
        clip = {"start": round(start, 6), "duration": round(dur, 6),
                "html": html}
        if seek:
            clip["seek_js"] = seek
        visual.append(clip)
        start = round(start + dur, 6)

    tracks.append({"index": 0, "kind": "visual", "clips": visual})
    spec = {"size": list(size), "duration_s": round(start, 6),
            "fps": int(fps), "tracks": tracks}
    html = build_composition_html(spec, theme)
    return html, {"scenes": len(scenes), "duration_s": spec["duration_s"],
                  "fps": int(fps), "size": list(size)}

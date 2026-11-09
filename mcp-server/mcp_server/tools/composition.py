"""
中性 composition spec 校验与编译（adopt-hyperframes-video-renderer W2.1）。

VAAS 侧只负责「说了什么」：builder 把口播内容编译成视觉/字幕片段，本模块把
**中性 spec** 编译成 HyperFrames composition HTML；渲染由独立渲染面
（render-plane/，HyperFrames 0.9.26）完成。

spec 形态（builder 适配层组装，见 typed_scenes.build_typed_composition）::

    {
      "size": [w, h], "duration_s": float, "fps": int,
      "tracks": [
        {"index": 0, "kind": "visual", "clips": [
            {"start": 0.0, "duration": 3.0, "html": "<div>…</div>",
             "seek_js": "function(lt){…}"}              # seek_js 可选
        ]},
        {"index": 1, "kind": "subtitle", "clips": [
            {"start": 0.0, "duration": 1.2, "text": "句"}
        ]},
        {"index": 2, "kind": "audio", "clips": [
            {"start": 0.0, "duration": 12.0, "src": "assets/voice.mp3",
             "volume": 0.8, "fade_out": True}
        ]},
      ]
    }

编译产物（逐帧确定性，零外链）：

  - 根 div：data-composition-id="main" / data-start / data-duration /
    data-width / data-height / data-fps（HyperFrames composition 契约）
  - visual/subtitle clip → <div class="clip" data-start data-duration
    data-track-index>；字幕走内置品牌字幕条（底部、最多 2 行）
  - audio clip → <audio data-start data-duration data-track-index src volume>；
    fade_out 在汇总 seek 里做线性音量包络（逐帧纯函数，不依赖 CSS 过渡）
  - 所有带 seek_js 的 clip 装配成**一个** window.__hf = {duration, seek(t)}：
    按 clip 的 [start, start+duration) 判窗，命中时以 localT = t - start 调用
    该 clip 的 seek_js（纯函数、无过渡、无随机）
  - 品牌令牌：theme.brand_root_style 注入 :root{--vaas-*}（字体栈
    --vaas-font-sans），舞台 html/body 全幅、background: var(--vaas-bg)

零外链是本模块的硬约束：编译入口自动调用 validate_no_external_refs（渲染面
同样离线校验，这里提前在 API 面报错，违规零产物）。
"""

import html as _html
import json
import re

__all__ = ["build_composition_html", "normalize_composition_spec",
           "validate_no_external_refs", "VISUAL_TRACK_INDEX",
           "SUBTITLE_TRACK_INDEX", "AUDIO_TRACK_INDEX", "BGM_TRACK_INDEX",
           "TRACK_KINDS", "FADE_SECONDS_DEFAULT"]

# 轨位约定（各 type 共用；builder 只填 visual/subtitle，音频轨由适配层组装）
VISUAL_TRACK_INDEX = 0
SUBTITLE_TRACK_INDEX = 1
AUDIO_TRACK_INDEX = 2
BGM_TRACK_INDEX = 3

TRACK_KINDS = ("visual", "subtitle", "audio")

# fade_out 收尾时长（与 render._bgm 的 BGM_FADE_SECONDS 同口径，但本模块不
# import render，避免把账本/DB 依赖拖进纯编译器）
FADE_SECONDS_DEFAULT = 3.0

_EPS = 1e-6


# ─── 零外链静态校验 ────────────────────────────────────────────────────────

# 资源加载属性（srcset 可含多候选）与 CSS 引用面；href 同扫（外链字体/样式
# 表同样不允许）
_REF_ATTR_RE = re.compile(
    r"""\b(src|srcset|poster|href|xlink:href)\s*=\s*"""
    r"""(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
_CSS_URL_RE = re.compile(
    r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)'"\s]+))\s*\)""", re.IGNORECASE)
_CSS_IMPORT_RE = re.compile(
    r"""@import\s+(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)


def _ref_values(html: str):
    """收集 html 里所有可能加载资源的引用值（属性 + CSS url()/@import）。"""
    for m in _REF_ATTR_RE.finditer(html):
        name = m.group(1).lower()
        value = next(g for g in m.groups()[1:] if g is not None)
        if name == "srcset":
            for token in value.split(","):
                token = token.strip()
                if token:  # 去掉 "1x"/"2x" 权重段
                    yield token.split()[0]
        else:
            yield value.strip()
    for m in _CSS_IMPORT_RE.finditer(html):
        yield next(g for g in m.groups() if g is not None).strip()
    for m in _CSS_URL_RE.finditer(html):
        yield next(g for g in m.groups() if g is not None).strip()


def _is_external_ref(value: str) -> bool:
    """http(s):// 与协议相对 //host 视为外链；data:/相对路径/#锚点放行。"""
    value = value.strip()
    if not value:
        return False
    lowered = value.lower()
    return (lowered.startswith("http://") or lowered.startswith("https://")
            or value.startswith("//"))


def validate_no_external_refs(html: str) -> None:
    """零外链静态校验：命中即 ValueError 并逐条列出违规资源。

    扫描面：src/srcset/poster/href/xlink:href 属性值 + CSS url()/@import。
    data: URI、相对路径、根相对路径与 #锚点均放行（渲染面断言的是网络外链）。
    """
    refs: list[str] = []
    for value in _ref_values(html):
        if _is_external_ref(value) and value not in refs:
            refs.append(value)
    if refs:
        raise ValueError(
            "composition 含外链资源（渲染面离线，零外链约束）:\n  - "
            + "\n  - ".join(refs))


# ─── spec 校验与归一化 ─────────────────────────────────────────────────────

def _as_number(value):
    """int/float → float；bool 与其它类型返回 None（True 不是时长）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def normalize_composition_spec(spec: dict) -> dict:
    """校验并归一化 spec（默认值补齐），一次列全全部违规。

    校验面：duration_s > 0、fps 正整数、size 两正整数、track index 非负且
    唯一、kind ∈ {visual, subtitle, audio}、clip start >= 0 且 duration > 0、
    clip 不越界（start + duration <= duration_s + 1e-6）、各 kind 的必填字段。
    """
    if not isinstance(spec, dict):
        raise ValueError(
            f"composition spec 必须是 dict，收到 {type(spec).__name__}")

    errors: list[str] = []

    size = spec.get("size")
    w = h = None
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        errors.append("spec.size 必须是 [width, height]（两个正整数）")
    else:
        w, h = _as_int(size[0]), _as_int(size[1])
        if w is None or h is None or w <= 0 or h <= 0:
            errors.append(f"spec.size 必须是两个正整数，收到 {list(size)!r}")
            w = h = None

    duration_s = _as_number(spec.get("duration_s"))
    if duration_s is None or duration_s <= 0:
        errors.append(
            f"spec.duration_s 必须是 > 0 的数字，收到 {spec.get('duration_s')!r}")
        duration_s = None

    fps = _as_int(spec.get("fps"))
    if fps is None or fps <= 0:
        errors.append(f"spec.fps 必须是正整数，收到 {spec.get('fps')!r}")
        fps = None

    tracks_raw = spec.get("tracks")
    if not isinstance(tracks_raw, list):
        errors.append("spec.tracks 必须是 array（每条轨 {index, kind, clips}）")
        tracks_raw = []

    tracks: list[dict] = []
    seen_indices: set[int] = set()
    for ti, track in enumerate(tracks_raw):
        label = f"tracks[{ti}]"
        if not isinstance(track, dict):
            errors.append(f"{label} 必须是 object，收到 {type(track).__name__}")
            continue

        index = _as_int(track.get("index"))
        if index is None or index < 0:
            errors.append(f"{label}.index 必须是非负整数，收到 {track.get('index')!r}")
            index = None
        elif index in seen_indices:
            errors.append(f"{label}.index 重复：{index}（每条轨的 index 必须唯一）")
        else:
            seen_indices.add(index)

        kind = track.get("kind")
        if kind not in TRACK_KINDS:
            errors.append(
                f"{label}.kind 必须是 {list(TRACK_KINDS)} 之一，收到 {kind!r}")
            kind = None

        clips_raw = track.get("clips", [])
        if not isinstance(clips_raw, list):
            errors.append(f"{label}.clips 必须是 array，收到 {type(clips_raw).__name__}")
            clips_raw = []

        clips: list[dict] = []
        for ci, clip in enumerate(clips_raw):
            clabel = f"{label}.clips[{ci}]"
            if not isinstance(clip, dict):
                errors.append(f"{clabel} 必须是 object，收到 {type(clip).__name__}")
                continue

            start = _as_number(clip.get("start"))
            if start is None or start < 0:
                errors.append(f"{clabel}.start 必须是 >= 0 的数字，收到 {clip.get('start')!r}")
                start = None
            clip_dur = _as_number(clip.get("duration"))
            if clip_dur is None or clip_dur <= 0:
                errors.append(f"{clabel}.duration 必须是 > 0 的数字，收到 {clip.get('duration')!r}")
                clip_dur = None
            if start is not None and clip_dur is not None and duration_s is not None \
                    and start + clip_dur > duration_s + _EPS:
                errors.append(
                    f"{clabel} 越界：start+duration={start + clip_dur:g} > "
                    f"spec.duration_s={duration_s:g}")

            normalized: dict = {"start": start, "duration": clip_dur}
            if kind == "visual":
                body = clip.get("html")
                if not isinstance(body, str) or not body.strip():
                    errors.append(f"{clabel}.html 必须是非空 string（视觉片段 HTML）")
                    body = ""
                seek_js = clip.get("seek_js")
                if seek_js is not None:
                    if not isinstance(seek_js, str) or not seek_js.strip():
                        errors.append(
                            f"{clabel}.seek_js 必须是非空 string（或省略），"
                            f"收到 {seek_js!r}")
                        seek_js = None
                    elif re.search(r"</script", seek_js, re.IGNORECASE):
                        errors.append(
                            f"{clabel}.seek_js 不得包含 </script（会提前闭合内联脚本）")
                        seek_js = None
                normalized.update({"html": body, "seek_js": seek_js})
            elif kind == "subtitle":
                text = clip.get("text")
                if not isinstance(text, str) or not text.strip():
                    errors.append(f"{clabel}.text 必须是非空 string（字幕文本）")
                    text = ""
                normalized["text"] = text
            elif kind == "audio":
                src = clip.get("src")
                if not isinstance(src, str) or not src.strip():
                    errors.append(f"{clabel}.src 必须是非空 string（素材相对路径）")
                    src = ""
                volume = _as_number(clip.get("volume", 1.0))
                if volume is None or not 0.0 < volume <= 1.0:
                    errors.append(
                        f"{clabel}.volume 必须是 (0, 1] 的数字（默认 1.0），"
                        f"收到 {clip.get('volume')!r}")
                    volume = 1.0
                fade_out = clip.get("fade_out", False)
                if not isinstance(fade_out, bool):
                    errors.append(f"{clabel}.fade_out 必须是 boolean，收到 {fade_out!r}")
                    fade_out = False
                normalized.update({"src": src.strip(), "volume": volume,
                                   "fade_out": fade_out})
            clips.append(normalized)

        tracks.append({"index": index, "kind": kind, "clips": clips})

    if errors:
        raise ValueError(
            "composition spec 校验失败（渲染前零产物）:\n  - "
            + "\n  - ".join(errors))

    return {"size": [w, h], "duration_s": duration_s, "fps": fps,
            "tracks": tracks}


# ─── HTML 编译 ─────────────────────────────────────────────────────────────

def _fmt(value: float) -> str:
    """数值 → 紧凑十进制串（3.0 → "3"，1.2 → "1.2"，不产生 3.000000）。"""
    return f"{float(value):.6f}".rstrip("0").rstrip(".") or "0"


def _stage_css(w: int, h: int, subtitle_px: int) -> str:
    return (
        "*{margin:0;padding:0;box-sizing:border-box}"
        f"html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;"
        "background:var(--vaas-bg)}"
        "body{font-family:var(--vaas-font-sans);color:var(--vaas-text)}"
        f".composition{{position:relative;width:{w}px;height:{h}px;"
        "overflow:hidden;background:var(--vaas-bg)}"
        ".clip{position:absolute;inset:0;overflow:hidden}"
        # 内置品牌字幕条：底部居中、半透明底、最多 2 行（line-clamp 兜底）
        ".clip.subtitle{inset:auto 6% 7% 6%;padding:18px 30px;"
        "border-radius:16px;background:rgba(0,0,0,.62);"
        "color:var(--vaas-text);text-align:center;"
        f"font-size:{subtitle_px}px;line-height:1.45;letter-spacing:1px;"
        "text-shadow:0 2px 10px rgba(0,0,0,.55);"
        "display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;"
        "overflow:hidden;word-break:break-word}"
    )


def _seek_runtime(spec: dict) -> str:
    """所有带 seek_js 的 clip + 音频 fade 包络 → 逐帧 seek 运行时。

    两条注册（实测缺一不可）：
      - `window.__timelines["main"]`：HyperFrames 真正逐帧驱动的入口
        （运行时按帧调 timeline.seek(t)；只注册 `__hf` 时动画静止，见 0.9.26 实测）
      - `window.__hf = {duration, seek}`：就绪探针 + 外部可调（headless 校验/调试）

    seek(t) 纯函数：按窗口 [start, start+duration) 命中时以 localT = t - start
    调 clip 的 seek_js；音频 fade_out 在窗口尾部线性收尾（逐帧求值，不依赖
    CSS 过渡）。元素查找一律惰性（脚本执行早于运行时挂载 DOM，顶层取值会 null）。
    """
    duration = spec["duration_s"]
    windows: list[list[float]] = []
    seeks: list[str] = []
    audios: list[dict] = []
    for track in spec["tracks"]:
        ti, kind = track["index"], track["kind"]
        for ci, clip in enumerate(track["clips"]):
            start, clip_dur = clip["start"], clip["duration"]
            if kind == "visual" and clip.get("seek_js"):
                windows.append([round(start, 6), round(start + clip_dur, 6)])
                seeks.append(clip["seek_js"].strip())
            elif kind == "audio" and clip.get("fade_out"):
                fade = min(FADE_SECONDS_DEFAULT, clip_dur)
                audios.append({
                    "id": f"hf-audio-{ti}-{ci}",
                    "start": round(start, 6),
                    "end": round(start + clip_dur, 6),
                    "volume": clip["volume"],
                    "fade": round(fade, 6),
                })

    seeks_js = ("[\n    " + ",\n    ".join(f"({s})" for s in seeks) + "\n  ]"
                if seeks else "[]")
    return (
        "(function () {\n"
        f"  var DURATION = {_fmt(duration)};\n"
        "  var WINDOWS = " + json.dumps(windows) + ";\n"
        "  var SEEKS = " + seeks_js + ";\n"
        "  var AUDIO = " + json.dumps(audios, ensure_ascii=False) + ";\n"
        "  function seek(t) {\n"
        "    if (!(t >= 0)) { t = 0; }\n"
        "    if (t > DURATION) { t = DURATION; }\n"
        "    for (var i = 0; i < SEEKS.length; i++) {\n"
        "      var w = WINDOWS[i];\n"
        "      if (t >= w[0] && t < w[1]) { SEEKS[i](t - w[0]); }\n"
        "    }\n"
        "    for (var j = 0; j < AUDIO.length; j++) {\n"
        "      var a = AUDIO[j];\n"
        "      var local = t - a.start;\n"
        "      if (local < 0 || local >= (a.end - a.start)) { continue; }\n"
        "      var v = a.volume;\n"
        "      if (a.fade > 0) {\n"
        "        var left = (a.end - a.start) - local;\n"
        "        if (left < a.fade) {\n"
        "          v = v * Math.max(0, left / a.fade);\n"
        "        }\n"
        "      }\n"
        "      var el = document.getElementById(a.id);\n"
        "      if (el) { el.volume = Math.max(0, Math.min(1, v)); }\n"
        "    }\n"
        "  }\n"
        "  // ① 就绪探针 + 外部可调（headless 校验/调试）\n"
        "  window.__hf = { duration: DURATION, seek: seek };\n"
        "  // ② 运行时真正逐帧驱动的入口（GSAP 时间轴接口的等价物）\n"
        "  var TL = {\n"
        "    seek: function (t) { seek(t); return TL; },\n"
        "    pause: function () { return TL; },\n"
        "    play: function () { return TL; },\n"
        "    pauseAt: function () { return TL; },\n"
        "    duration: function () { return DURATION; },\n"
        "    totalDuration: function () { return DURATION; },\n"
        "    time: function () { return 0; },\n"
        "    kill: function () {}\n"
        "  };\n"
        "  window.__timelines = window.__timelines || {};\n"
        "  window.__timelines['main'] = TL;\n"
        "  seek(0);\n"
        "})();"
    )


def build_composition_html(spec: dict, theme: dict) -> str:
    """中性 composition spec + 品牌 theme → HyperFrames composition HTML。

    编译后自动跑 validate_no_external_refs（零外链硬约束，违规即 ValueError
    并列出资源）；返回整页 HTML（内联 CSS/JS，无第三方前端库依赖）。
    """
    spec = normalize_composition_spec(spec)
    if not isinstance(theme, dict):
        theme = {}

    # 延迟 import：避免与 typed_scenes 包的初始化顺序耦合（本模块可独立测）
    from .typed_scenes.theme import brand_root_style

    w, h = spec["size"]
    duration = spec["duration_s"]
    subtitle_px = max(24, int(round(min(w, h) * 0.04)))

    blocks: list[str] = []
    for track in spec["tracks"]:
        ti, kind = track["index"], track["kind"]
        for ci, clip in enumerate(track["clips"]):
            attrs = (f'data-start="{_fmt(clip["start"])}" '
                     f'data-duration="{_fmt(clip["duration"])}" '
                     f'data-track-index="{ti}"')
            if kind == "visual":
                blocks.append(f'<div class="clip" {attrs}>{clip["html"]}</div>')
            elif kind == "subtitle":
                blocks.append(
                    f'<div class="clip subtitle" {attrs}>'
                    f'{_html.escape(clip["text"])}</div>')
            elif kind == "audio":
                blocks.append(
                    f'<audio id="hf-audio-{ti}-{ci}" {attrs} '
                    f'src="{_html.escape(clip["src"], quote=True)}" '
                    f'volume="{_fmt(clip["volume"])}"></audio>')

    body_html = "\n".join(blocks)

    out = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width={w}, height={h}">
<style>
{brand_root_style(theme)}
{_stage_css(w, h, subtitle_px)}
</style></head>
<body>
<div data-composition-id="main" data-start="0" data-duration="{_fmt(duration)}" data-width="{w}" data-height="{h}" data-fps="{spec['fps']}" class="composition">
{body_html}
</div>
<script>
{_seek_runtime(spec)}
</script></body></html>
"""
    validate_no_external_refs(out)
    return out

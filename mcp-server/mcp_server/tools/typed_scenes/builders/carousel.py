"""
carousel builder（add-typed-video-html-renderer W2.2）。

图文轮播：每口播段一张图场景。Ken Burns 推拉（motion 按 pan_down/zoom_in/
pan_right 轮换，公式与 render.py kenburns 场景同族）+ 段字幕叠加（theme
字幕带，句级查表与 news-flash 要点卡同款）。全部场景 = html_full 整页
（品牌 CSS wrapper，零外链——图片内联 data: URI，与 kenburns 场景同口径），
动效由 window.seek(t) 纯函数阶跃驱动（无 CSS transition/JS 补间——逐帧重
放确定性）。

交叉淡入口径（v1，场景内实现）：两图交界不需要跨场景状态——场景 i（i>0）
把上一场景的图作为顶层、transform 冻结在上一场景 motion 的 rel=1 末态，
前 FADE_S 秒由 seek(t) 淡出（1 → 0），当前图的 Ken Burns 在底层同窗推进。
t=0 帧与上一场景末帧逐像素同构（同图同 transform 同不透明度），交界即真
交叉淡入。图片只有一张（复用全程同图）时无上一层、无淡入淡出，场景各自
重放 Ken Burns。

图片循环复用：场景 i 用 images[i % M]；M >= 2 时相邻场景必不同图（spec
video-types「图文轮播视频」验收条目）；M == 1 退化为全程同图（相邻不重复
在此无解，按循环复用口径放行）。图片项契约（type.json inputs.images.desc）
与补图 pending 语义（纯字符串 + generate:true → prompt）在公共层
collect_pending_images/resolve_pending_images（typed_scenes/__init__），
render_video 先回填产物路径再进 build——build 读到 {"prompt"} 项即报错
（pending 未确认就到 build 属调用方绕线）。

validate_inputs 一次列全全部违规（渲染前零产物，TTS 花费之前以骨架 Segment
调用即可完成）；carousel 无固定结构数对照（每段一图，任意段数均可）。script
分段口径：`## 段名` 分段（split_script），未标记则整篇单段——v1 不做停顿
自动分段。颜色字体全部取 theme（brand 变量 + palette 槽位）——不硬编码色
值；两种 orientation（1080x1920 / 1920x1080）共用同一套固定 px 版式
（1080 类画幅）。
"""

import base64
import mimetypes

from ..alignment import _resolve_file
from ..theme import js_str, wrap_scene_html
from .. import AbstractBuilder, Segment

# 交叉淡入时长（秒）：场景开窗内上一层淡出；短段时 clamp 截断，确定性不受影响
_FADE_S = 0.6

# motion 轮换（spec：Ken Burns 推拉）；公式与 render.py _scene_kenburns_html 同族
_MOTION_ORDER = ("pan_down", "zoom_in", "pan_right")

# rel ∈ [0,1] 的纯函数 transform 表达式（seek 期驱动当前图）
_MOTION_JS = {
    "pan_down": "'translate(0,'+(-rel*6)+'%) scale('+(1+rel*0.04)+')'",
    "zoom_in": "'scale('+(1+rel*0.08)+')'",
    "pan_right": "'translate('+(-rel*5)+'%,0) scale(1.06)'",
}

# rel=1 冻结末态（交叉淡入上一层：与上一场景末帧同 transform）
_MOTION_END = {
    "pan_down": "translate(0,-6%) scale(1.04)",
    "zoom_in": "scale(1.08)",
    "pan_right": "translate(-5%,0) scale(1.06)",
}

_SCENE_CSS = (
    ".kb{position:absolute;top:-4%;left:-4%;width:108%;height:108%;"
    "object-fit:cover;transition:none}"
    ".subband{position:absolute;left:0;right:0;bottom:0;min-height:220px;"
    "background:var(--vaas-surface);border-top:2px solid var(--vaas-border);"
    "padding:36px 88px;display:flex;align-items:flex-start}"
    ".sub{font-size:38px;line-height:1.55;color:var(--vaas-text)}"
)

_SCENE_JS = """
const D = window.__DURATION__;
const FADE = __FADE_S__;
const cur = document.getElementById('kb-cur');
const prev = document.getElementById('kb-prev');
const SENTS = DATA.sentences;
const sub = document.getElementById('sub');
window.seek = function (t) {
  // Ken Burns：rel ∈ [0,1] 的纯函数 transform（逐帧重放确定性）
  const rel = clamp(t / D, 0, 1);
  cur.style.transform = __MOTION_EXPR__;
  // 交叉淡入（场景内口径）：上一层冻结上一场景末帧，前 FADE 秒淡出
  if (prev) { prev.style.opacity = String(1 - clamp(t / FADE, 0, 1)); }
  // 句级字幕：取 start<=t 的最后一句（段内句子连续，无空窗；查表纯函数）
  let txt = '';
  for (let i = 0; i < SENTS.length; i++) {
    if (t >= SENTS[i].start - 1e-9) { txt = SENTS[i].text; } else { break; }
  }
  sub.textContent = txt;
};
window.seek(0);
"""


def _data_uri(path) -> str:
    """图片文件 → data: URI（场景页零外链口径，与 kenburns 场景同）。"""
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _resolve_image_srcs(inputs: dict) -> list[str]:
    """inputs.images 清单 → 每项一个 data: URI（按清单序）。

    信任级别与 kenburns images / voice_path 相同（_resolve_file：绝对直用，
    相对按序试 CWD → downloads → VAAS_ROOT）。提示词项到 build 仍未回填
    （绕过补图 confirm 协议）显式报错指路。
    """
    images = inputs.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("carousel build: inputs.images (非空 list) is required")
    srcs: list[str] = []
    for i, item in enumerate(images):
        path = None
        if isinstance(item, str) and item.strip():
            path = item.strip()
        elif isinstance(item, dict) and isinstance(item.get("path"), str) \
                and item["path"].strip():
            path = item["path"].strip()
        elif isinstance(item, dict) and isinstance(item.get("prompt"), str) \
                and item["prompt"].strip():
            raise ValueError(
                f"carousel build: images[{i}] 仍是待补图提示词（pending prompt）"
                "——先走 render_video 的补图 confirm 协议（inputs.confirm_images="
                "true）回填产物路径，或直接给文件路径")
        if path is None:
            raise ValueError(
                f'carousel build: images[{i}] 须为非空 string 或 {{"path"/"prompt": string}}')
        p = _resolve_file(path)
        if not p.is_file():
            raise ValueError(f"carousel image not found: {path}")
        srcs.append(_data_uri(p))
    return srcs


class CarouselBuilder(AbstractBuilder):
    type_id = "carousel"

    def validate_inputs(self, inputs: dict, segments: list[Segment]) -> None:
        """图片清单形状校验（一次列全）：非空 array，每项为非空 string /
        {"path": string} / {"prompt": string}。段数无结构数对照（每段一图）；
        提示词 → 产物路径的回填由补图 confirm 协议在 build 之前完成，文件
        存在性由 build 落地时点名（_resolve_image_srcs）。"""
        errors: list[str] = []
        images = inputs.get("images")
        if not isinstance(images, list) or not images:
            errors.append(
                'inputs.images 必须是非空 array（["path" | {"path"} | {"prompt"}],'
                " type.json inputs.images.desc）")
        else:
            for i, item in enumerate(images):
                ok = (isinstance(item, str) and item.strip()) or (
                    isinstance(item, dict)
                    and ((isinstance(item.get("path"), str) and item["path"].strip())
                         or (isinstance(item.get("prompt"), str)
                             and item["prompt"].strip())))
                if not ok:
                    errors.append(
                        f'images[{i}] 须为非空 string、{{"path": string}} 或 '
                        '{"prompt": string}')
        if not segments:
            errors.append("口播稿分段结果为空（carousel 每段一图，至少 1 段）")
        if errors:
            raise ValueError(
                "carousel 输入校验失败（渲染前零产物）:\n  - "
                + "\n  - ".join(errors))

    def build(self, segments: list[Segment], inputs: dict,
              size: list[int], theme: dict) -> list[dict]:
        srcs = _resolve_image_srcs(inputs)
        m = len(srcs)
        scenes = []
        for i, seg in enumerate(segments):
            cur_src = srcs[i % m]
            motion = _MOTION_ORDER[i % len(_MOTION_ORDER)]
            # 交叉淡入上一层：上一场景的图（同图复用时省略——淡入无意义）
            prev_src = srcs[(i - 1) % m] if i > 0 else None
            if prev_src == cur_src:
                prev_src = None
            prev_end = _MOTION_END[_MOTION_ORDER[(i - 1) % len(_MOTION_ORDER)]] \
                if prev_src else None
            scenes.append(self._scene(seg, cur_src, motion, prev_src, prev_end,
                                      size, theme))
        return scenes

    # ── 场景：html_full 整页（图 KB 推拉 + 顶层交叉淡入 + 字幕带，零外链） ──

    def _scene(self, seg: dict, cur_src: str, motion: str,
               prev_src, prev_end, size, theme) -> dict:
        sents = seg["sentences"] or [{"text": seg["text"], "start": 0.0,
                                      "end": float(seg["duration_s"])}]
        prev_img = (f'<img class="kb" id="kb-prev" src="{prev_src}" '
                    f'style="transform:{prev_end}">' if prev_src else "")
        body = (f'<img class="kb" id="kb-cur" src="{cur_src}">'
                + prev_img
                + '<div class="subband"><div class="sub" id="sub"></div></div>')
        js = ("const DATA = " + js_str({"sentences": sents}) + ";\n"
              + _SCENE_JS
              .replace("__FADE_S__", repr(_FADE_S))
              .replace("__MOTION_EXPR__", _MOTION_JS[motion]))
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_SCENE_CSS,
                                        js=js, theme=theme)}


BUILDER = CarouselBuilder()

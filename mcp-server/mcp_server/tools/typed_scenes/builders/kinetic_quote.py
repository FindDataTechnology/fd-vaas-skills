"""
kinetic-quote builder（add-typed-video-html-renderer W2.4）。

金句文字动画：纯文字动态排版。每段一个场景（html_full 整页，品牌 CSS
wrapper，零外链），段内逐句入场——句块随 window.seek(t) 阶跃显现（opacity+
translateY，3 步/句，无 CSS transition/JS 补间——逐帧重放确定性），句切换
与句级字幕严格对齐（同一张句表查表驱动）。排版居中大字，品牌字体栈。

关键词放大变色：`**词**` 显式标记优先；整段无标记时自动取段内最长中文词
（len >= 2，对齐 type.json defaults.minKeywordLen）。强调 = 品牌强调色
（var(--vaas-accent)）+ 放大（em 缩放，不硬编码色值）。

零图片依赖（spec：MUST NOT 依赖任何图片素材）：validate_inputs 拒绝
inputs.images 非空，并把 `**` 标记不成对的段一次列全——渲染前、零产物。
逐字级同步为 stretch 目标，v1 承诺句级对齐（HTML 渲染器口径）。

契约 v2（adopt-hyperframes-video-renderer W3.5）：build_composition 把整页
场景拆成**逐句片段**——每句一个 visual clip（本句文本 + 局部时间 seek_js 的
3 步阶跃入场），字幕轨同句表逐条对齐；clip 的时间窗/轨位由 composition
编译器落地，运行时按窗切换可见性（同一时刻只上当前句，与 v1 句块替换同观
感）。片段只写自身元素样式，品牌变量在 composition 的 :root 单点注入；零
图片、零外链。旧 build() 保留到 W4 切流。
"""

import html as _html
import re
from typing import Optional, Pattern

from ..theme import js_str, wrap_scene_html
from .. import AbstractBuilder, Segment

# 对齐 type.json defaults.minKeywordLen（fallback 关键词最短长度）
MIN_KEYWORD_LEN = 2

# 句块入场：3 步阶跃（0.15s/步，相对句 start）
_STEPS, _STEP_S = 3, 0.15

_CSS = """
.stage-bg{position:absolute;inset:0;
  background:linear-gradient(160deg,var(--vaas-bg) 0%,var(--vaas-bg1) 55%,
  var(--vaas-surface) 130%)}
.kicker{position:absolute;top:110px;left:0;right:0;text-align:center;
  font-size:26px;letter-spacing:14px;color:var(--vaas-muted)}
.quote{position:absolute;inset:0 0 230px 0}
.sblock{position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;padding:0 88px;opacity:0;
  transform:translateY(20px)}
/* 句文本走普通块级流（kw span 内联回绕）——flex 直排会把每个 inline
   片段当独立 flex item 横向摊开，排版碎裂 */
.stext{width:100%;text-align:center;font-size:92px;line-height:1.45;
  font-weight:800;letter-spacing:2px;color:var(--vaas-text);
  text-wrap:balance}
.kw{color:var(--vaas-accent);font-size:1.12em;font-weight:900;
  word-break:keep-all}
.subband{position:absolute;left:0;right:0;bottom:0;min-height:230px;
  border-top:2px solid var(--vaas-border);padding:36px 88px 0;
  display:flex;align-items:flex-start}
.sub{font-size:38px;line-height:1.55;color:var(--vaas-text)}
.progress{position:absolute;left:0;right:0;bottom:0;height:8px;
  background:var(--vaas-surface2)}
.bar{height:100%;width:0;background:var(--vaas-accent)}
"""

_JS = """
const D = window.__DURATION__;
const SENTS = DATA.sentences;
const blocks = Array.from(document.querySelectorAll('.sblock'));
const sub = document.getElementById('sub');
const bar = document.getElementById('bar');
window.seek = function (t) {
  // 当前句：start<=t 的最后一句（段内句子连续，无空窗；查表纯函数）
  let cur = -1;
  for (let i = 0; i < SENTS.length; i++) {
    if (t >= SENTS[i].start - 1e-9) { cur = i; } else { break; }
  }
  blocks.forEach(function (el, i) {
    if (i !== cur) {
      // 前句退场 / 后句未入场：同一时刻舞台只上当前句（金句逐句替换）
      el.style.opacity = '0';
      el.style.transform = 'translateY(20px)';
      return;
    }
    // 句内阶跃入场（3 步 × 0.15s，相对句 start）：opacity/位移全由 t 决定
    const k = stepIn(t, SENTS[i].start, %d, %s);
    el.style.opacity = String(k / %d);
    el.style.transform = 'translateY(' + ((%d - k) * 20) + 'px)';
  });
  // 句级字幕：与句块同一张句表 → 句切换严格对齐；`**` 标记不进字幕
  sub.textContent = cur >= 0 ? SENTS[cur].text.replace(/\\*\\*/g, '') : '';
  bar.style.width = (clamp(t / D, 0, 1) * 100).toFixed(3) + '%%';
};
window.seek(0);
""" % (_STEPS, repr(_STEP_S), _STEPS, _STEPS)

_MARK_KW_RE = re.compile(r"\*\*([^*]+?)\*\*")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")

# 契约 v2 逐句片段 CSS（clip 自带样式；品牌变量在 composition :root 单点注入）。
# 句文本初始 opacity:0 —— 开窗前的 clip 不闪字，首帧由 seek_js 落到 k/3。
_CLIP_CSS = (
    ".kq-bg{position:absolute;inset:0;background:linear-gradient(160deg,"
    "var(--vaas-bg) 0%,var(--vaas-bg1) 55%,var(--vaas-surface) 130%)}"
    ".kq-kicker{position:absolute;top:110px;left:0;right:0;text-align:center;"
    "font-size:26px;letter-spacing:14px;color:var(--vaas-muted)}"
    ".kq-quote{position:absolute;inset:0 0 230px 0;display:flex;"
    "align-items:center;justify-content:center;padding:0 88px}"
    ".kq-text{width:100%;text-align:center;font-size:92px;line-height:1.45;"
    "font-weight:800;letter-spacing:2px;color:var(--vaas-text);"
    "text-wrap:balance;opacity:0;transform:translateY(20px)}"
    ".kw{color:var(--vaas-accent);font-size:1.12em;font-weight:900;"
    "word-break:keep-all}"
    ".kq-progress{position:absolute;left:0;right:0;bottom:0;height:8px;"
    "background:var(--vaas-border)}"
    ".kq-bar{height:100%;width:0;background:var(--vaas-accent)}"
)


def _num(value: float) -> str:
    """数值 → 紧凑 JS 字面量（12.0 → "12"，1.2 → "1.2"，编译期常量直出）。"""
    return f"{float(value):.6f}".rstrip("0").rstrip(".") or "0"



def _extract_keywords(text: str) -> list[str]:
    """段关键词：`**词**` 显式标记优先（出现序去重）；无标记则取段内最长
    中文词（>= MIN_KEYWORD_LEN 字，并列取首个）。"""
    marked = _MARK_KW_RE.findall(text)
    if marked:
        seen, out = set(), []
        for w in marked:
            w = w.strip()
            if w and w not in seen:
                seen.add(w)
                out.append(w)
        return out
    runs = [r for r in _CJK_RUN_RE.findall(text) if len(r) >= MIN_KEYWORD_LEN]
    return [max(runs, key=len)] if runs else []


def _strip_markers(text: str) -> str:
    return text.replace("**", "")


def _esc(s: str) -> str:
    return _html.escape(s, quote=False)


def _keyword_regex(keywords: list[str]) -> Optional[Pattern[str]]:
    """关键词 alternation（长词优先防被子串抢先）；无关键词返回 None。"""
    if not keywords:
        return None
    parts = "|".join(re.escape(k) for k in
                     sorted(keywords, key=len, reverse=True))
    return re.compile("(" + parts + ")")


def _render_sentence_html(sentence_text: str,
                          kw_re: Optional[Pattern[str]]) -> str:
    """句文本 → 强调 HTML：先按关键词切分（原文口径），再逐片 HTML 转义，
    关键词片包 `<span class=\"kw\">`（放大 + 品牌强调色由 CSS 承担）。"""
    text = _strip_markers(sentence_text)
    if kw_re is None:
        return _esc(text)
    out, prev = [], 0
    for m in kw_re.finditer(text):
        if m.start() > prev:
            out.append(_esc(text[prev:m.start()]))
        out.append('<span class="kw">' + _esc(m.group(0)) + "</span>")
        prev = m.end()
    if prev < len(text):
        out.append(_esc(text[prev:]))
    return "".join(out)


def _fallback_sentences(seg: dict) -> list[dict]:
    """句表缺省兜底（骨架/异常句表）：整段记为单句，覆盖全段时长。"""
    return [{"text": seg["text"], "start": 0.0,
             "end": float(seg["duration_s"])}]


class KineticQuoteBuilder(AbstractBuilder):
    type_id = "kinetic-quote"

    def validate_inputs(self, inputs: dict, segments: list[Segment]) -> None:
        """零图片依赖 + 标记成对校验：违规一次列全（渲染前、零产物，
        TTS 花费之前以骨架 Segment 调用即可完成）。"""
        errors: list[str] = []
        if not isinstance(inputs, dict):
            errors.append("inputs 必须是 JSON 对象（type.json inputs 契约）")
            inputs = {}
        images = inputs.get("images")
        if images:
            errors.append(
                "kinetic-quote 为纯文字类型（MUST NOT 依赖任何图片素材）："
                f"inputs.images 须为空或缺省，收到 {len(images)} 项——"
                "请删除图片输入，本类型以文字动效呈现")
        if not segments:
            errors.append("口播稿分段结果为空（须有正文可渲）")
        for i, seg in enumerate(segments):
            name = str((seg or {}).get("name") or f"seg{i}")
            text = str((seg or {}).get("text") or "")
            if not text.strip():
                errors.append(f"段 {name!r} 正文为空（分段后空段须删除）")
            elif text.count("**") % 2:
                errors.append(
                    f"段 {name!r} 的 `**` 关键词标记不成对（奇数个）——"
                    "每处强调须为 `**词**` 成对标记，请修正口播稿")
        if errors:
            raise ValueError(
                "kinetic-quote 输入校验失败（渲染前零产物）:\n  - "
                + "\n  - ".join(errors))

    def build(self, segments: list[Segment], inputs: dict,
              size: list[int], theme: dict) -> list[dict]:
        if not segments:
            raise ValueError("kinetic-quote build: segments is empty")
        return [self._quote_scene(seg, size, theme) for seg in segments]

    # ── 契约 v2：声明式片段（visual 每句一 clip + 字幕逐句一条） ──────────
    #
    # 逐句拆片段：clip 窗口 = 句窗口（段内句子连续、跨段也连续），运行时按窗
    # 切换可见性 → 同一时刻只上当前句（与 v1 句块替换同观感）；clip 内 seek_js
    # 只做本句的 3 步阶跃入场 + 全局进度条（常量在编译期烘死，纯函数）。

    def build_composition(self, segments: list[Segment], inputs: dict,
                          size: list[int], theme: dict) -> dict:
        if not segments:
            raise ValueError("kinetic-quote build_composition: segments is empty")
        total = round(sum(float(s["duration_s"]) for s in segments), 4)
        denom = _num(max(total, 1e-6))  # 进度条分母（0 时长防御，正常不会到这）
        visual: list[dict] = []
        subtitle: list[dict] = []
        start = 0.0
        index = 0
        for seg in segments:
            seg_dur = float(seg["duration_s"])
            sents = seg["sentences"] or _fallback_sentences(seg)
            kw_re = _keyword_regex(_extract_keywords(seg["text"]))
            for s in sents:
                dur = round(float(s["end"]) - float(s["start"]), 4)
                if dur <= 0:  # 零宽句没有可渲窗口（编译器要求 duration > 0）
                    continue
                clip_start = round(start + float(s["start"]), 4)
                visual.append({
                    "start": clip_start,
                    "duration": dur,
                    "html": self._sentence_clip(index, s["text"], kw_re),
                    "seek_js": self._sentence_seek_js(index, clip_start, denom),
                })
                # 句级字幕轨：与句窗口严格同起同止（`**` 标记不进字幕）
                subtitle.append({"start": clip_start, "duration": dur,
                                 "text": _strip_markers(s["text"])})
                index += 1
            start = round(start + seg_dur, 4)
        return {"visual": visual, "subtitle": subtitle}

    def _sentence_clip(self, index: int, text: str, kw_re) -> str:
        """单句 visual clip HTML（品牌底纹 + 题签 + 本句强调文本 + 进度条）。

        元素 id 按 clip 序号唯一（getElementById 在整页内取首个命中，重复 id
        会让 seek_js 写错元素）。
        """
        return (
            "<style>" + _CLIP_CSS + "</style>"
            '<div class="kq-bg"></div>'
            '<div class="kq-kicker">金句</div>'
            '<div class="kq-quote"><div class="kq-text" '
            f'id="hf-kq-s{index}">'
            + _render_sentence_html(text, kw_re)
            + "</div></div>"
            '<div class="kq-progress"><div class="kq-bar" '
            f'id="hf-kq-bar{index}"></div></div>'
        )

    def _sentence_seek_js(self, index: int, clip_start: float,
                          denom: str) -> str:
        """句 clip 的局部时间 seek 函数（lt = 全局 t - clip.start）。

        纯函数：阶跃步数与步长、clip 起点、全片时长均为编译期常量；只读写
        自身 clip 内的两个元素，无日期、无随机、无跨 clip 状态。
        """
        steps = str(_STEPS)
        return (
            "function(lt){"
            "var k=Math.floor(lt/" + repr(_STEP_S) + ")+1;"
            "if(!(k>=0)){k=0}if(k>" + steps + "){k=" + steps + "};"
            f"var el=document.getElementById('hf-kq-s{index}');"
            "el.style.opacity=String(k/" + steps + ");"
            "el.style.transform='translateY('+(" + steps + "-k)*20+'px)';"
            f"var bar=document.getElementById('hf-kq-bar{index}');"
            "if(bar){"
            "var r=(" + _num(clip_start) + "+lt)/" + denom + ";"
            "if(!(r>=0)){r=0}if(r>1){r=1};"
            "bar.style.width=(r*100).toFixed(3)+'%';"
            "}}"
        )

    # ── 场景：html_full 整页（seek 契约 + 品牌 wrapper，零外链零图片） ───

    def _quote_scene(self, seg: dict, size, theme) -> dict:
        sents = seg["sentences"] or _fallback_sentences(seg)
        keywords = _extract_keywords(seg["text"])
        kw_re = _keyword_regex(keywords)
        blocks = "".join(
            '<div class="sblock"><div class="stext">'
            + _render_sentence_html(s["text"], kw_re)
            + "</div></div>" for s in sents)
        body = ('<div class="stage-bg"></div>'
                '<div class="kicker">金句</div>'
                f'<div class="quote">{blocks}</div>'
                '<div class="subband"><div class="sub" id="sub"></div></div>'
                '<div class="progress"><div class="bar" id="bar"></div></div>')
        js = ("const DATA = " + js_str({"sentences": sents}) + ";\n" + _JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_CSS,
                                        js=js, theme=theme)}


BUILDER = KineticQuoteBuilder()

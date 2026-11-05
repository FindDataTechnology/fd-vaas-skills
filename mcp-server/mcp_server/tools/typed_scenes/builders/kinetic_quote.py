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

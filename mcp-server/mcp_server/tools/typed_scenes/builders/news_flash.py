"""
news-flash builder（add-typed-video-html-renderer W2.1 契约验证件）。

热点速报：固定结构卡片视频。标题卡 → 要点卡×N（每段一卡，句级字幕叠加）→
CTA；来源署名位（meta.source）。全部场景 = html_full 整页（品牌 CSS wrapper，
零外链），动效由 window.seek(t) 纯函数阶跃驱动（要点卡入场 3 步阶跃，无
CSS transition/JS 补间——逐帧重放确定性）。

结构数对照（type.json inputs.desc）：口播稿 `## 段名` 分段为
1 hook + N 要点 + 1 cta，段数 - 2 须等于 meta.points 数；validate_inputs
一次列全全部违规。骨架 Segment（duration_s=0）即可校验结构，TTS 花费之前
完成（渲染前零产物）。

颜色字体全部取 theme（brand 变量 + palette 槽位）——不硬编码色值；两种
orientation（1080x1920 / 1920x1080）共用同一套固定 px 版式（1080 类画幅）。
"""

from ..theme import js_str, wrap_scene_html
from .. import AbstractBuilder, Segment

_STAGE_CSS = (
    ".stage-bg{position:absolute;inset:0;"
    "background:linear-gradient(160deg,var(--vaas-bg) 0%,var(--vaas-bg1) 55%,"
    "var(--vaas-surface) 130%)}"
    ".card{position:absolute;inset:0;display:flex;flex-direction:column;"
    "padding:96px 88px;opacity:0}"
)

_TITLE_CSS = _STAGE_CSS + """
.kicker{align-self:flex-start;background:var(--vaas-accent);color:var(--vaas-bg);
  font-size:30px;font-weight:700;letter-spacing:10px;padding:12px 28px;
  border-radius:10px}
.headline{margin:64px 0 0;font-size:82px;line-height:1.28;font-weight:800;
  letter-spacing:2px;color:var(--vaas-text)}
.rule{margin-top:72px;width:0;height:8px;border-radius:4px;
  background:linear-gradient(90deg,var(--vaas-accent),var(--vaas-palette-2))}
.source{margin-top:auto;font-size:26px;color:var(--vaas-muted)}
"""

_POINT_CSS = _STAGE_CSS + """
.head{display:flex;align-items:baseline;gap:24px}
.idx{font-size:96px;font-weight:800;line-height:1}
.label{font-size:28px;letter-spacing:6px;color:var(--vaas-muted)}
.point{margin-top:56px;font-size:64px;line-height:1.42;font-weight:700;
  color:var(--vaas-text)}
.subband{margin-top:auto;min-height:220px;border-top:2px solid var(--vaas-border);
  padding-top:36px;display:flex;align-items:flex-start}
.sub{font-size:38px;line-height:1.55;color:var(--vaas-text)}
.progress{position:absolute;left:0;right:0;bottom:0;height:8px;
  background:var(--vaas-surface2)}
.bar{height:100%;width:0;background:var(--vaas-accent)}
"""

_CTA_CSS = _STAGE_CSS + """
.recap{font-size:30px;letter-spacing:4px;color:var(--vaas-muted)}
.lines{margin-top:72px;display:flex;flex-direction:column;gap:36px}
.line{font-size:60px;line-height:1.4;font-weight:700;color:var(--vaas-text);
  opacity:0}
.source{margin-top:auto;font-size:26px;color:var(--vaas-muted)}
"""

_TITLE_JS = """
const D = window.__DURATION__;
const card = document.getElementById('card');
const rule = document.getElementById('rule');
document.getElementById('headline').textContent = DATA.headline;
const src = document.getElementById('source');
if (DATA.source) { src.textContent = '来源：' + DATA.source; }
else { src.style.display = 'none'; }
window.seek = function (t) {
  // 3 步阶跃入场（0.18s/步）：opacity/位移/分隔线全部由 t 决定，无过渡
  const k = stepIn(t, 0, 3, 0.18);
  card.style.opacity = String(k / 3);
  card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';
  rule.style.width = (k / 3 * 64) + '%';
};
window.seek(0);
"""

_POINT_JS = """
const D = window.__DURATION__;
const card = document.getElementById('card');
const sub = document.getElementById('sub');
const bar = document.getElementById('bar');
const SENTS = DATA.sentences;
document.getElementById('idx').textContent = String(DATA.index).padStart(2, '0');
document.getElementById('num').textContent = String(DATA.index);
document.getElementById('total').textContent = String(DATA.total);
document.getElementById('point').textContent = DATA.point;
window.seek = function (t) {
  const k = stepIn(t, 0, 3, 0.16);
  card.style.opacity = String(k / 3);
  card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';
  // 句级字幕：取 start<=t 的最后一句（段内句子连续，无空窗；查表纯函数）
  let cur = '';
  for (let i = 0; i < SENTS.length; i++) {
    if (t >= SENTS[i].start - 1e-9) { cur = SENTS[i].text; } else { break; }
  }
  sub.textContent = cur;
  bar.style.width = (clamp(t / D, 0, 1) * 100).toFixed(3) + '%';
};
window.seek(0);
"""

_CTA_JS = """
const card = document.getElementById('card');
const lines = Array.from(document.querySelectorAll('.line'));
document.getElementById('recap').textContent = DATA.headline;
const src = document.getElementById('source');
if (DATA.source) { src.textContent = '来源：' + DATA.source; }
else { src.style.display = 'none'; }
window.seek = function (t) {
  const k = stepIn(t, 0, 3, 0.16);
  card.style.opacity = String(k / 3);
  // 逐句阶跃显现：t 越过该句 start 才入场（纯函数查表）
  lines.forEach(function (el, i) {
    const on = t >= DATA.sentences[i].start - 1e-9;
    el.style.opacity = on ? '1' : '0';
    el.style.transform = on ? 'translateY(0)' : 'translateY(12px)';
  });
};
window.seek(0);
"""


def _normalize_points(meta: dict) -> list[str]:
    points = []
    for item in meta.get("points") or []:
        if isinstance(item, str) and item.strip():
            points.append(item.strip())
        elif isinstance(item, dict) and isinstance(item.get("text"), str) \
                and item["text"].strip():
            points.append(item["text"].strip())
    return points


class NewsFlashBuilder(AbstractBuilder):
    type_id = "news-flash"

    def validate_inputs(self, inputs: dict, segments: list[Segment]) -> None:
        """结构数对照：meta 形状 + 口播段数（1 hook + N 要点 + 1 cta）==
        meta.points 数；一次列全全部违规。"""
        errors: list[str] = []
        meta = inputs.get("meta")
        if not isinstance(meta, dict):
            errors.append(
                "inputs.meta 必须是 JSON 对象 {headline, points, source?}"
                "（type.json inputs.meta.desc）")
            meta = {}
        if not isinstance(meta.get("headline"), str) or not meta["headline"].strip():
            errors.append("meta.headline 必须是非空 string")
        points_raw = meta.get("points")
        if not isinstance(points_raw, list) or not points_raw:
            errors.append('meta.points 必须是非空 array（[{text}|"..."], ...）')
        else:
            for i, item in enumerate(points_raw):
                ok = (isinstance(item, str) and item.strip()) or (
                    isinstance(item, dict)
                    and isinstance(item.get("text"), str) and item["text"].strip())
                if not ok:
                    errors.append(
                        f'meta.points[{i}] 须为非空 string 或 {{"text": string}}')
        if meta.get("source") is not None and not isinstance(meta.get("source"), str):
            errors.append("meta.source 须为 string（可选，来源署名位）")

        n_seg = len(segments)
        n_points_seg = max(0, n_seg - 2)
        names = [s["name"] for s in segments]
        if n_seg < 3:
            errors.append(
                "口播稿须用 `## 段名` 分段为 1 hook + N 要点 + 1 cta（>= 3 段），"
                f"当前 {n_seg} 段: {names}")
        elif isinstance(points_raw, list) and points_raw:
            if len(points_raw) != n_points_seg:
                errors.append(
                    f"结构数对照失败：口播要点段数 {n_points_seg} "
                    f"(hook={names[0]!r} + 要点×{n_points_seg}="
                    f"{names[1:-1]} + cta={names[-1]!r}) != meta.points 数 "
                    f"{len(points_raw)}")
        if errors:
            raise ValueError(
                "news-flash 结构数对照失败（渲染前零产物）:\n  - "
                + "\n  - ".join(errors))

    def build(self, segments: list[Segment], inputs: dict,
              size: list[int], theme: dict) -> list[dict]:
        meta = inputs.get("meta")
        if not isinstance(meta, dict):
            raise ValueError("news-flash build: inputs.meta (dict) is required")
        points = _normalize_points(meta)
        headline = str(meta.get("headline") or "").strip()
        source = meta.get("source")
        hook, point_segs, cta = segments[0], segments[1:-1], segments[-1]
        palette = theme.get("palette") or ["var(--vaas-accent)"]

        scenes = [self._title_card(hook, headline, source, size, theme)]
        for i, (seg, point) in enumerate(zip(point_segs, points)):
            scenes.append(self._point_card(
                seg, point, i + 1, len(points),
                palette[i % len(palette)], size, theme))
        scenes.append(self._cta_card(cta, headline, source, size, theme))
        return scenes

    # ── 卡片：html_full 整页（seek 契约 + 品牌 wrapper，零外链） ─────────

    def _title_card(self, seg: dict, headline: str, source, size, theme) -> dict:
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="kicker">热点速报</div>'
                '<h1 class="headline" id="headline"></h1>'
                '<div class="rule" id="rule"></div>'
                '<div class="source" id="source"></div>'
                '</div>')
        js = ("const DATA = " + js_str({"headline": headline, "source": source})
              + ";\n" + _TITLE_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_TITLE_CSS,
                                        js=js, theme=theme)}

    def _point_card(self, seg: dict, point: str, index: int, total: int,
                    palette_color: str, size, theme) -> dict:
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="head">'
                f'<span class="idx" id="idx" style="color:{palette_color}"></span>'
                '<span class="label">要点 <span id="num"></span>/<span id="total"></span></span>'
                '</div>'
                '<div class="point" id="point"></div>'
                '<div class="subband"><div class="sub" id="sub"></div></div>'
                '<div class="progress"><div class="bar" id="bar"></div></div>'
                '</div>')
        js = ("const DATA = " + js_str({
                "index": index, "total": total, "point": point,
                "sentences": seg["sentences"]})
              + ";\n" + _POINT_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_POINT_CSS,
                                        js=js, theme=theme)}

    def _cta_card(self, seg: dict, headline: str, source, size, theme) -> dict:
        sents = seg["sentences"] or [{"text": seg["text"], "start": 0.0,
                                      "end": float(seg["duration_s"])}]
        lines = "".join('<div class="line"></div>' for _ in sents)
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="recap" id="recap"></div>'
                f'<div class="lines">{lines}</div>'
                '<div class="source" id="source"></div>'
                '</div>')
        js = ("const DATA = " + js_str({"headline": headline, "source": source,
                                        "sentences": sents})
              + ";\n" + _CTA_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_CTA_CSS,
                                        js=js, theme=theme)}


BUILDER = NewsFlashBuilder()

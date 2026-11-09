"""
data-viz builder（add-typed-video-html-renderer W2.3）。

数据可视化讲解：每口播段一个图表场景。hook 大字卡 → 图表卡×N（柱状生长/
折线描画/饼图展开，进度动画占段帧 40%——type.json inputs.data.desc 约定，
句级字幕叠加 + stat 数值动画）→ CTA；来源署名位（data.source，hook/CTA
两处）。全部场景 = html_full 整页（品牌 CSS wrapper，零外链）。

结构数对照（type.json inputs.desc）：口播稿 `## 段名` 分段为 1 hook + N
图表段 + 1 cta，段数 - 2 须等于 data.charts 数；validate_inputs 一次列全
全部违规。骨架 Segment（duration_s=0）即可校验结构，TTS 花费之前完成
（渲染前零产物）。

图表动画：seek 驱动器复用 builders/_charts.py（bar/line/pie 三种，
animation:false 纯 setOption 逐帧重放——option 是 t 的纯函数，同 t 同帧，
跨调用历史无关；轴上限 niceMax 首帧固定）。echarts.min.js 内联进场景 body
（vendor 路径与 still_chart 同源）。echarts canvas 吃不了 CSS 变量，色值由
echarts-theme.json 的 palette/brand 注入 DATA 岛——配色全部来自 theme
palette（spec MUST），HTML/CSS 面仍走品牌变量。

颜色字体取 theme（brand 变量 + palette 槽位）——不硬编码色值；两种
orientation（1080x1920 / 1920x1080）共用同一套弹性版式（图表区 flex 撑满
余量，echarts init 按容器实测尺寸落 canvas）。
"""

from html import escape as _esc

from ..theme import js_str, wrap_scene_html
from .. import AbstractBuilder, Segment
from ._charts import (CHART_HELPERS_JS, chart_driver_js, chart_errors,
                      inline_echarts_script, normalize_chart)

# 动画窗 = 段时长 × 40%（type.json inputs.data.desc 约定）；下限防零时长退化
_ANIM_RATIO = 0.4
_ANIM_FLOOR_S = 0.05

_STAGE_CSS = (
    ".stage-bg{position:absolute;inset:0;"
    "background:linear-gradient(160deg,var(--vaas-bg) 0%,var(--vaas-bg1) 55%,"
    "var(--vaas-surface) 130%)}"
    ".card{position:absolute;inset:0;display:flex;flex-direction:column;"
    "padding:96px 88px;opacity:0}"
)

_HOOK_CSS = _STAGE_CSS + """
.kicker{align-self:flex-start;background:var(--vaas-accent);color:var(--vaas-bg);
  font-size:30px;font-weight:700;letter-spacing:10px;padding:12px 28px;
  border-radius:10px}
.headline{margin:64px 0 0;font-size:82px;line-height:1.28;font-weight:800;
  letter-spacing:2px;color:var(--vaas-text)}
.subline{margin-top:40px;font-size:34px;letter-spacing:4px;color:var(--vaas-muted)}
.rule{margin-top:72px;width:0;height:8px;border-radius:4px;
  background:linear-gradient(90deg,var(--vaas-accent),var(--vaas-palette-2))}
.source{margin-top:auto;font-size:26px;color:var(--vaas-muted)}
"""

_CHART_CSS = _STAGE_CSS + """
.head{display:flex;align-items:baseline;gap:24px}
.idx{font-size:88px;font-weight:800;line-height:1}
.label{font-size:28px;letter-spacing:6px;color:var(--vaas-muted)}
.chart-title{margin-top:20px;font-size:54px;line-height:1.3;font-weight:700;
  color:var(--vaas-text)}
.chart-wrap{flex:1;min-height:0;margin-top:32px}
#chart{width:100%;height:100%}
.stat{display:flex;align-items:baseline;gap:20px;margin-top:24px}
.stat-label{font-size:26px;letter-spacing:4px;color:var(--vaas-muted)}
.stat-value{font-size:44px;font-weight:800;color:var(--vaas-accent)}
.subband{margin-top:auto;min-height:200px;border-top:2px solid var(--vaas-border);
  padding-top:32px;display:flex;align-items:flex-start}
.sub{font-size:36px;line-height:1.55;color:var(--vaas-text)}
.progress{position:absolute;left:0;right:0;bottom:0;height:8px;
  background:var(--vaas-surface)}
.bar{height:100%;width:0;background:var(--vaas-accent)}
"""

_CTA_CSS = _STAGE_CSS + """
.recap{font-size:30px;letter-spacing:4px;color:var(--vaas-muted)}
.lines{margin-top:72px;display:flex;flex-direction:column;gap:36px}
.line{font-size:60px;line-height:1.4;font-weight:700;color:var(--vaas-text);
  opacity:0}
.source{margin-top:auto;font-size:26px;color:var(--vaas-muted)}
"""

_HOOK_JS = """
const D = window.__DURATION__;
const card = document.getElementById('card');
const rule = document.getElementById('rule');
document.getElementById('headline').textContent = DATA.title;
document.getElementById('subline').textContent =
  DATA.chartCount + ' 张图表，一图一个重点';
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

# 图表卡 glue：seekChart(t)（_charts 驱动器）+ 句级字幕带 + stat 数值动画
_CHART_CARD_JS = """
const D = window.__DURATION__;
const SENTS = DATA.sentences;
const seeker = DATA.kind === 'bar' ? makeBarSeeker()
  : DATA.kind === 'line' ? makeLineSeeker() : makePieSeeker();
const card = document.getElementById('card');
const sub = document.getElementById('sub');
const bar = document.getElementById('bar');
const statValue = document.getElementById('statValue');
document.getElementById('idx').textContent = String(DATA.index).padStart(2, '0');
document.getElementById('num').textContent = String(DATA.index);
document.getElementById('total').textContent = String(DATA.total);
document.getElementById('chartTitle').textContent = DATA.title;
document.getElementById('statLabel').textContent =
  DATA.kind === 'line' ? '当前值' : '合计';
const STAT_UNIT = DATA.unit || '';
window.seek = function (t) {
  const k = stepIn(t, 0, 3, 0.16);
  card.style.opacity = String(k / 3);
  card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';
  // 数值动画：seeker 返回本帧头条数值（bar=合计 / line=描画头 / pie=已呈现合计）
  statValue.textContent = fmtNum(seeker(t)) + (STAT_UNIT ? ' ' + STAT_UNIT : '');
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
document.getElementById('recap').textContent = DATA.title;
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


def _sentence_fallback(seg: dict) -> list:
    """无句表（骨架/异常）时的单句兜底——字幕带仍查表驱动，形状不变。"""
    return [{"text": seg["text"], "start": 0.0,
             "end": float(seg["duration_s"])}]


class DataVizBuilder(AbstractBuilder):
    type_id = "data-viz"

    def validate_inputs(self, inputs: dict, segments: list[Segment]) -> None:
        """结构数对照：data 形状 + 口播段数（1 hook + N 图表段 + 1 cta）==
        data.charts 数；一次列全全部违规（逐图表违规经 _charts.chart_errors）。"""
        errors: list = []
        data = inputs.get("data")
        if not isinstance(data, dict):
            errors.append("inputs.data 必须是 JSON 对象 "
                          "{title, charts, source?}（type.json inputs.data.desc）")
            data = {}
        if not isinstance(data.get("title"), str) or not data["title"].strip():
            errors.append("data.title 必须是非空 string")
        if data.get("source") is not None and not isinstance(data.get("source"), str):
            errors.append("data.source 须为 string（可选，来源署名位）")
        charts = data.get("charts")
        if not isinstance(charts, list) or not charts:
            errors.append(
                "data.charts 必须是非空 array（[{type:'bar'|'line'|'pie', "
                "title?, labels?, values?, series?, unit?}]）")
            charts = []
        else:
            for i, ch in enumerate(charts):
                errors.extend(chart_errors(i, ch))

        n_seg = len(segments)
        n_chart_seg = max(0, n_seg - 2)
        names = [s["name"] for s in segments]
        if n_seg < 3:
            errors.append(
                "口播稿须用 `## 段名` 分段为 1 hook + N 图表段 + 1 cta（>= 3 段），"
                f"当前 {n_seg} 段: {names}")
        elif isinstance(charts, list) and charts:
            if len(charts) != n_chart_seg:
                errors.append(
                    f"结构数对照失败：口播图表段数 {n_chart_seg} "
                    f"(hook={names[0]!r} + 图表×{n_chart_seg}={names[1:-1]} + "
                    f"cta={names[-1]!r}) != data.charts 数 {len(charts)}")
        if errors:
            raise ValueError(
                "data-viz 结构数对照失败（渲染前零产物）:\n  - "
                + "\n  - ".join(errors))

    def build(self, segments: list[Segment], inputs: dict,
              size: list[int], theme: dict) -> list[dict]:
        data = inputs.get("data")
        if not isinstance(data, dict):
            raise ValueError("data-viz build: inputs.data (dict) is required")
        charts = data.get("charts")
        if not isinstance(charts, list) or not charts:
            raise ValueError("data-viz build: data.charts (non-empty array) is required")
        title = str(data.get("title") or "").strip()
        source = data.get("source")
        palette = theme.get("palette") or []
        hook, chart_segs, cta = segments[0], segments[1:-1], segments[-1]

        scenes = [self._hook_card(hook, title, source, len(charts), size, theme)]
        for i, (seg, ch) in enumerate(zip(chart_segs, charts)):
            scenes.append(self._chart_card(seg, ch, i, len(charts),
                                           palette, size, theme))
        scenes.append(self._cta_card(cta, title, source, size, theme))
        return scenes

    # ── 卡片：html_full 整页（seek 契约 + 品牌 wrapper，零外链） ─────────

    def _hook_card(self, seg: dict, title: str, source, chart_count: int,
                   size, theme) -> dict:
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="kicker">数据可视化</div>'
                '<h1 class="headline" id="headline"></h1>'
                '<div class="subline" id="subline"></div>'
                '<div class="rule" id="rule"></div>'
                '<div class="source" id="source"></div>'
                '</div>')
        js = ("const DATA = " + js_str({"title": title, "source": source,
                                        "chartCount": int(chart_count)})
              + ";\n" + _HOOK_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_HOOK_CSS,
                                        js=js, theme=theme)}

    def _chart_card(self, seg: dict, ch: dict, index: int, total: int,
                    palette: list, size, theme) -> dict:
        anim_s = max(round(_ANIM_RATIO * float(seg["duration_s"]), 4),
                     _ANIM_FLOOR_S)
        island = normalize_chart(index, ch, anim_s)
        island.update({
            "index": index + 1, "total": int(total),
            "sentences": seg["sentences"] or _sentence_fallback(seg),
            "palette": list(palette),
            "brand": theme.get("brand") or {},
        })
        # idx 序号色取 theme palette 槽位（HTML 面直接吃 hex，与 news-flash
        # 同款；palette 缺位时退化到品牌 accent 变量）
        idx_color = palette[index % len(palette)] if palette \
            else "var(--vaas-accent)"
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="head">'
                f'<span class="idx" id="idx" style="color:{idx_color}"></span>'
                '<span class="label">图表 <span id="num"></span>/'
                '<span id="total"></span></span>'
                '</div>'
                '<div class="chart-title" id="chartTitle"></div>'
                '<div class="chart-wrap"><div id="chart"></div></div>'
                '<div class="stat"><span class="stat-label" id="statLabel"></span>'
                '<span class="stat-value" id="statValue"></span></div>'
                '<div class="subband"><div class="sub" id="sub"></div></div>'
                '<div class="progress"><div class="bar" id="bar"></div></div>'
                '</div>'
                + inline_echarts_script())
        js = ("const DATA = " + js_str(island) + ";\n"
              + CHART_HELPERS_JS + "\n"
              + chart_driver_js(island["kind"]) + "\n"
              + _CHART_CARD_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_CHART_CSS,
                                        js=js, theme=theme)}

    def _cta_card(self, seg: dict, title: str, source, size, theme) -> dict:
        sents = seg["sentences"] or _sentence_fallback(seg)
        lines = "".join('<div class="line"></div>' for _ in sents)
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="recap" id="recap"></div>'
                f'<div class="lines">{lines}</div>'
                '<div class="source" id="source"></div>'
                '</div>')
        js = ("const DATA = " + js_str({"title": title, "source": source,
                                        "sentences": sents})
              + ";\n" + _CTA_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_CTA_CSS,
                                        js=js, theme=theme)}


# ══════════════════════════════════════════════════════════════════════════
# 契约 v2（W3.4）：声明式片段 + 惰性 echarts seek
#
# HyperFrames 脚本早于元素挂载执行，因此：
#   - 文本一律静态内联（不做顶层 DOM 写）
#   - echarts 初始化与 seeker 构造放进 seek 内「首次调用」惰性完成
#   - 每个 clip 唯一 id 前缀（多图表卡共存于同一 composition，不能撞 id）
# _charts.py 驱动器原样复用（只依赖 clamp）；helpers 去掉顶层 init 一行。
# ══════════════════════════════════════════════════════════════════════════

_DV_V2_CSS = """
.dv-clip{position:absolute;inset:0}
.dv-card{position:absolute;inset:0;display:flex;flex-direction:column;
  padding:96px 88px;opacity:0}
.dv-bg{position:absolute;inset:0;background:linear-gradient(160deg,
  var(--vaas-bg) 0%,var(--vaas-bg1) 55%,var(--vaas-surface) 130%)}
.dv-kicker{align-self:flex-start;background:var(--vaas-accent);
  color:var(--vaas-bg);font-size:30px;font-weight:700;letter-spacing:10px;
  padding:12px 28px;border-radius:10px}
.dv-headline{margin:56px 0 0;font-size:80px;line-height:1.3;font-weight:800;
  color:var(--vaas-text)}
.dv-subline{margin-top:36px;font-size:34px;letter-spacing:4px;
  color:var(--vaas-muted)}
.dv-rule{margin-top:64px;width:0;height:8px;border-radius:4px;
  background:linear-gradient(90deg,var(--vaas-accent),var(--vaas-palette-2))}
.dv-source{margin-top:auto;font-size:26px;color:var(--vaas-muted)}
.dv-head{display:flex;align-items:baseline;gap:24px}
.dv-idx{font-size:88px;font-weight:800;line-height:1}
.dv-label{font-size:28px;letter-spacing:6px;color:var(--vaas-muted)}
.dv-title{margin-top:20px;font-size:54px;line-height:1.3;font-weight:700;
  color:var(--vaas-text)}
.dv-chartwrap{flex:1;min-height:0;margin-top:28px}
.dv-chart{width:100%;height:100%}
.dv-stat{display:flex;align-items:baseline;gap:20px;margin-top:20px}
.dv-statlabel{font-size:26px;letter-spacing:4px;color:var(--vaas-muted)}
.dv-statval{font-size:44px;font-weight:800;color:var(--vaas-accent)}
.dv-subband{margin-top:auto;min-height:190px;border-top:2px solid var(--vaas-border);
  padding-top:30px;display:flex;align-items:flex-start}
.dv-sub{font-size:36px;line-height:1.55;color:var(--vaas-text)}
.dv-progress{position:absolute;left:0;right:0;bottom:0;height:8px;
  background:var(--vaas-surface)}
.dv-bar{height:100%;width:0;background:var(--vaas-accent)}
.dv-recap{font-size:30px;letter-spacing:4px;color:var(--vaas-muted)}
.dv-lines{margin-top:64px;display:flex;flex-direction:column;gap:34px}
.dv-line{font-size:58px;line-height:1.4;font-weight:700;color:var(--vaas-text);
  opacity:0}
"""


def _helpers_without_init() -> str:
    """CHART_HELPERS_JS 去掉顶层 `const chart = echarts.init(...)`（惰性化）。"""
    kept = [ln for ln in CHART_HELPERS_JS.splitlines()
            if not ln.strip().startswith("const chart = echarts.init")]
    return "\n    ".join(kept)


_CHART_SEEK_TMPL = """function (lt) {
    var D = window.__DATAKEY__;
    if (!D) { return; }
    // 块作用域注意：__HELPERS__ 在下面的 if 块内声明（function 声明块内可见、
    // 块外不可见），因此格式化函数在 seek 顶层自带一份，不跨块引用。
    var fmt = function (x) {
      if (typeof x !== 'number' || !isFinite(x)) { return ''; }
      var r = Math.round(x * 100) / 100;
      return r.toLocaleString('en-US', { maximumFractionDigits: 2 });
    };
    var root = document.getElementById('__ROOT__');
    if (!root) { return; }
    var card = root.querySelector('.dv-card');
    var k = Math.min(3, Math.max(0, Math.floor(lt / 0.16) + 1));
    if (card) {
      card.style.opacity = String(k / 3);
      card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';
    }
    var S = D.sentences || [];
    var cur = '';
    for (var i = 0; i < S.length; i++) {
      if (lt >= S[i].start - 1e-9) { cur = S[i].text; } else { break; }
    }
    var sub = document.getElementById(D.ids.sub);
    if (sub) { sub.textContent = cur; }
    var bar = document.getElementById(D.ids.bar);
    if (bar) {
      bar.style.width = (Math.min(1, Math.max(0, lt / D.dur)) * 100).toFixed(3) + '%';
    }
    if (!D.seekFn) {
      if (typeof echarts === 'undefined') { return; }
      var el = document.getElementById(D.ids.chart);
      if (!el) { return; }
      var DATA = D;
      var clamp = function (v, a, b) { return Math.min(b, Math.max(a, v)); };
      __HELPERS__
      __DRIVER__
      var chart = echarts.init(el);
      D.seekFn = D.kind === 'bar' ? makeBarSeeker()
        : (D.kind === 'line' ? makeLineSeeker() : makePieSeeker());
    }
    var v = D.seekFn(Math.min(lt, D.animS));
    var sv = document.getElementById(D.ids.stat);
    if (sv) { sv.textContent = fmt(v) + (D.unit ? ' ' + D.unit : ''); }
  }"""


def _hook_seek_v2(root: str) -> str:
    return (
        "function (lt) {\n"
        f"    var root = document.getElementById('{root}');\n"
        "    if (!root) { return; }\n"
        "    var card = root.querySelector('.dv-card');\n"
        "    var rule = root.querySelector('.dv-rule');\n"
        "    var k = Math.min(3, Math.max(0, Math.floor(lt / 0.18) + 1));\n"
        "    if (card) {\n"
        "      card.style.opacity = String(k / 3);\n"
        "      card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';\n"
        "    }\n"
        "    if (rule) { rule.style.width = (k / 3 * 64) + '%'; }\n"
        "  }"
    )


def _cta_seek_v2(root: str, starts: list) -> str:
    return (
        "function (lt) {\n"
        f"    var root = document.getElementById('{root}');\n"
        "    if (!root) { return; }\n"
        "    var card = root.querySelector('.dv-card');\n"
        "    var k = Math.min(3, Math.max(0, Math.floor(lt / 0.16) + 1));\n"
        "    if (card) { card.style.opacity = String(k / 3); }\n"
        "    var lines = root.querySelectorAll('.dv-line');\n"
        f"    var starts = {starts};\n"
        "    for (var i = 0; i < lines.length; i++) {\n"
        "      var on = lt >= starts[i] - 1e-9;\n"
        "      lines[i].style.opacity = on ? '1' : '0';\n"
        "      lines[i].style.transform = on ? 'translateY(0)' : 'translateY(12px)';\n"
        "    }\n"
        "  }"
    )


def _dv_clip_html(root: str, body: str, extra: str = "") -> str:
    return (f"<style>{_DV_V2_CSS}</style>"
            f'<div class="dv-clip" id="{root}">'
            '<div class="dv-bg"></div>'
            f'<div class="dv-card">{body}</div></div>'
            + extra)


def _dv_build_composition(self, segments, inputs, size, theme) -> dict:
    """契约 v2：1 hook + N 图表 + 1 CTA 的声明式片段。"""
    data = inputs.get("data")
    if not isinstance(data, dict):
        raise ValueError("data-viz build_composition: inputs.data (dict) is required")
    charts = data.get("charts")
    if not isinstance(charts, list) or not charts:
        raise ValueError(
            "data-viz build_composition: data.charts (non-empty array) is required")
    if len(segments) < 3:
        raise ValueError(
            "data-viz 结构数对照失败：口播稿需 1 hook + N 图表段 + 1 cta（>=3 段），"
            f"当前 {len(segments)} 段")
    # 结构数对照（一次列全，渲染前零产物）
    self.validate_inputs(inputs, segments)
    title = str(data.get("title") or "").strip()
    source = data.get("source")
    palette = list(theme.get("palette") or [])
    hook, chart_segs, cta = segments[0], segments[1:-1], segments[-1]

    built = []
    src_line = f"来源：{source}" if source else ""
    hook_body = ('<div class="dv-kicker">数据可视化</div>'
                 f'<h1 class="dv-headline">{_esc(title)}</h1>'
                 f'<div class="dv-subline">{len(charts)} 张图表，一图一个重点</div>'
                 '<div class="dv-rule"></div>'
                 f'<div class="dv-source">{_esc(src_line)}</div>')
    built.append({"html": _dv_clip_html("dv-hook", hook_body),
                  "seek_js": _hook_seek_v2("dv-hook")})

    for i, (seg, ch) in enumerate(zip(chart_segs, charts)):
        dur = float(seg["duration_s"])
        anim_s = max(round(_ANIM_RATIO * dur, 4), _ANIM_FLOOR_S)
        island = normalize_chart(i, ch, anim_s)
        root = f"dv-c{i}"
        ids = {"chart": f"{root}-chart", "stat": f"{root}-stat",
               "sub": f"{root}-sub", "bar": f"{root}-bar"}
        island.update({
            "index": i + 1, "total": len(charts), "root": root, "ids": ids,
            "dur": round(dur, 4),
            "sentences": seg["sentences"] or _sentence_fallback(seg),
            "palette": palette, "brand": theme.get("brand") or {},
        })
        idx_color = (palette[i % len(palette)] if palette
                     else "var(--vaas-accent)")
        stat_label = "当前值" if island["kind"] == "line" else "合计"
        body = ('<div class="dv-head">'
                f'<span class="dv-idx" style="color:{idx_color}">{i + 1:02d}</span>'
                f'<span class="dv-label">图表 {i + 1}/{len(charts)}</span>'
                '</div>'
                f'<div class="dv-title">{_esc(island["title"])}</div>'
                f'<div class="dv-chartwrap"><div class="dv-chart" id="{ids["chart"]}"></div></div>'
                '<div class="dv-stat">'
                f'<span class="dv-statlabel">{stat_label}</span>'
                f'<span class="dv-statval" id="{ids["stat"]}"></span>'
                '</div>'
                f'<div class="dv-subband"><div class="dv-sub" id="{ids["sub"]}"></div></div>'
                f'<div class="dv-progress"><div class="dv-bar" id="{ids["bar"]}"></div></div>')
        data_key = f"__dvD{i}"
        extra = (inline_echarts_script()
                 + f"<script>window.{data_key} = " + js_str(island) + ";</script>")
        seek = (_CHART_SEEK_TMPL
                .replace("__DATAKEY__", data_key)
                .replace("__ROOT__", root)
                .replace("__HELPERS__", _helpers_without_init())
                .replace("__DRIVER__", chart_driver_js(island["kind"])))
        built.append({"html": _dv_clip_html(root, body, extra), "seek_js": seek})

    sents = cta["sentences"] or _sentence_fallback(cta)
    lines = "".join(f'<div class="dv-line">{_esc(s["text"])}</div>' for s in sents)
    cta_body = (f'<div class="dv-recap">{_esc(title)}</div>'
                f'<div class="dv-lines">{lines}</div>'
                f'<div class="dv-source">{_esc(src_line)}</div>')
    built.append({"html": _dv_clip_html("dv-cta", cta_body),
                  "seek_js": _cta_seek_v2(
                      "dv-cta", [round(float(s["start"]), 4) for s in sents])})

    visual, subtitle = [], []
    start = 0.0
    for seg, clip in zip(segments, built):
        dur = round(float(seg["duration_s"]), 4)
        visual.append({"start": start, "duration": dur,
                       "html": clip["html"], "seek_js": clip["seek_js"]})
        for s in (seg["sentences"] or _sentence_fallback(seg)):
            subtitle.append({"start": round(start + float(s["start"]), 4),
                             "duration": round(float(s["end"]) - float(s["start"]), 4),
                             "text": s["text"]})
        start = round(start + dur, 4)
    return {"visual": visual, "subtitle": subtitle}


# 挂到既有类上（同一类，不重复定义，保留 v1 的 validate_inputs/build）
DataVizBuilder.build_composition = _dv_build_composition


BUILDER = DataVizBuilder()

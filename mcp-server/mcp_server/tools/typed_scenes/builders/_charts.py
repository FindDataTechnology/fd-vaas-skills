"""
Seek 驱动图表组件（add-typed-video-html-renderer W2.3，data-viz 复用底座）。

bar/line/pie 三个 echarts「seek 驱动器」+ 共享 helpers，与具体视频类型解耦
（spec：图表组件 SHALL 可复用，不绑定单一类型）。任何 html renderer builder
按三步接入：

  1. body 里内联 vendor echarts（inline_echarts_script()，路径与 still_chart
     同源，零外链）；
  2. js 里 `const DATA = <卡片数据岛>`（图表字段由 normalize_chart 归一产出，
     再并上卡片级字段 index/total/sentences/source/palette/brand），拼接
     CHART_HELPERS_JS + chart_driver_js(kind) + 卡片 glue；
  3. glue 里按 kind 取 makeBarSeeker/makeLineSeeker/makePieSeeker() 得
     seekChart，window.seek(t) 里调 seekChart(t)——返回值是本帧「stat 头条
     数值」（bar=当前合计 / line=描画头当前值 / pie=已呈现合计），供数值
     动画文本跳动。

确定性口径（data-viz 关键验收：seek 纯函数——同 t 同帧）：
  - echarts 以 animation:false 初始化后不再有内部补间；动画完全由
    setOption(option, true)（notMerge）逐帧重放——渲染只依赖本帧 option；
  - option 是 t 的纯函数：全部插值/ease/扫描角由段内进度算出（easeOutCubic
    等），无随机 id、无时钟、无 JS 侧可变态（驱动器闭包只持常量）；
  - 同 t → 同 option → 同帧；跨调用历史无关（由测试以 node + echarts 桩
    验证 option 级纯性，真渲染双跑 md5 兜底）。
  - 轴上限 niceMax 自首帧固定（生长过程轴不缩放），niceMax 是 max 值的
    纯函数（1/2/2.5/5×10^k 档位）。

颜色边界：echarts canvas 吃不了 CSS 变量，故由 builder 把
echarts-theme.json 的 palette/brand 色值（hex）注入 DATA 岛——配色全部来
自 theme palette（spec MUST），场景 HTML 不出现硬编码业务色值。
"""

import math

from ...still_chart import ECHARTS_JS_PATH

VALID_CHART_TYPES = ("bar", "line", "pie")


# ─── vendor 内联 ───────────────────────────────────────────────────────────

def inline_echarts_script() -> str:
    """vendor echarts.min.js → 场景 body 内联 <script>（零外链）。

    路径与 still_chart 同源（包内 templates/echarts，生成器输出即单一来源）。
    文件不含 `</script`（不会提前闭合外层标签），整页过 _scene_guard 的
    静态外链扫描（src/href/url() 面无 http(s)/file 引用）。
    """
    return "<script>" + ECHARTS_JS_PATH.read_text(encoding="utf-8") + "</script>"


# ─── 校验（validate_inputs 复用；一次列全单图表的全部违规） ─────────────────

def _is_num(v) -> bool:
    """有限 number（bool/NaN/Inf 不算——JSON 数值边界）。"""
    return isinstance(v, (int, float)) and not isinstance(v, bool) \
        and math.isfinite(v)


def chart_errors(index: int, ch) -> list:
    """单个图表 spec 的违规清单（data.charts[index]；合法返回空表）。

    v1 形状（type.json inputs.data.desc）：{type:'bar'|'line'|'pie',
    title?, labels?, values?, series?, unit?}。bar/line 用 values 或
    series（[{name, values}] 多系列）；pie 只用 values 且须非负、不全零。
    """
    label = f"data.charts[{index}]"
    if not isinstance(ch, dict):
        return [label + " 须为对象 {type, title?, labels?, values?, series?, unit?}"]
    errors: list = []
    kind = ch.get("type")
    if kind not in VALID_CHART_TYPES:
        errors.append(f"{label}.type 须为 {'|'.join(VALID_CHART_TYPES)} 之一，"
                      f"got: {kind!r}")
        kind = None
    for key in ("title", "unit"):
        if ch.get(key) is not None and not isinstance(ch[key], str):
            errors.append(f"{label}.{key} 须为 string（可选）")

    labels = ch.get("labels")
    if labels is not None:
        if not isinstance(labels, list) or not labels:
            errors.append(f"{label}.labels 须为非空 array（留空自动用序号/类目名）")
            labels = None
        else:
            for i, lb in enumerate(labels):
                if isinstance(lb, bool) or not isinstance(lb, (str, int, float)):
                    errors.append(f"{label}.labels[{i}] 须为 string 或 number，"
                                  f"got: {lb!r}")

    values = ch.get("values")
    if values is not None:
        if not isinstance(values, list) or not values:
            errors.append(f"{label}.values 须为非空 number array")
            values = None
        else:
            for i, v in enumerate(values):
                if not _is_num(v):
                    errors.append(f"{label}.values[{i}] 须为有限 number，got: {v!r}")

    series = ch.get("series")
    series_n = None
    if series is not None:
        if not isinstance(series, list) or not series:
            errors.append(f"{label}.series 须为非空 array（[{{name, values}}]）")
            series = None
        else:
            lens = set()
            for si, s in enumerate(series):
                ok = isinstance(s, dict) and isinstance(s.get("values"), list) \
                    and bool(s["values"]) and all(_is_num(v) for v in s["values"])
                if not ok:
                    errors.append(f"{label}.series[{si}] 须为 "
                                    "{name?: string, values: 非空 number array}")
                else:
                    lens.add(len(s["values"]))
            if len(lens) > 1:
                errors.append(f"{label}.series 各系列 values 长度须一致，got: {sorted(lens)}")
            elif lens:
                series_n = lens.pop()
    if series is not None and not isinstance(series, list):
        series = None

    # 类型专项
    if kind in ("bar", "line"):
        if values is None and series is None:
            errors.append(f"{label}（{kind}）需要 values 或 series "
                          "（[{name, values}]）二者之一")
    elif kind == "pie":
        if series is not None:
            errors.append(f"{label}（pie）用 values 提供数据（series 仅 bar/line 支持）")
        if values is None:
            errors.append(f"{label}（pie）需要 values（非负 number array）")
        elif isinstance(values, list) and values and all(_is_num(v) for v in values):
            if any(v < 0 for v in values):
                errors.append(f"{label}（pie）values 须非负（扇区无负值语义）")
            if not any(v > 0 for v in values):
                errors.append(f"{label}（pie）values 不能全为 0（扫描展开无物可呈）")

    # labels 与有效数据点数对照（bar/line 取 series 优先，pie 取 values）
    eff_n = series_n if series_n is not None else (
        len(values) if isinstance(values, list) and values
        and all(_is_num(v) for v in values) else None)
    if eff_n is not None and isinstance(labels, list) and len(labels) != eff_n:
        errors.append(f"{label}.labels 数 {len(labels)} != 数据点数 {eff_n}")
    return errors


def normalize_chart(index: int, ch: dict, anim_s: float) -> dict:
    """校验后的图表 spec → DATA 岛图表字段（可复用组件的数据契约）。

    返回 {kind, title, labels, seriesDefs, pieItems, unit, animS}：
      labels    — string 数组（缺省序号「1..n」/ pie 缺省「类目1..n」）
      seriesDefs— bar/line：[{name, values}]（单系列 values 归一成单系列）
      pieItems  — pie：[{name, value}]
      animS     — 段内动画窗秒数（builder 按约定传入：段时长 × 40%，
                  见 type.json inputs.data.desc「进度动画占段帧 40%」）
    未过 validate 的 spec 在此防御性报错（build 直调也安全）。
    """
    errs = chart_errors(index, ch)
    if errs:
        raise ValueError(f"data.charts[{index}] 不合法（先过 validate_inputs）:\n  - "
                         + "\n  - ".join(errs))
    kind = ch["type"]
    title = str(ch.get("title") or "").strip() or f"图表 {index + 1}"
    unit = str(ch.get("unit") or "")
    labels_in = ch.get("labels")

    def _labels(n: int, fallback_prefix: str) -> list:
        if isinstance(labels_in, list) and len(labels_in) == n:
            return [str(lb) for lb in labels_in]
        return [f"{fallback_prefix}{i + 1}" for i in range(n)]

    if kind in ("bar", "line"):
        series_raw = ch.get("series")
        if isinstance(series_raw, list) and series_raw:
            defs = [{"name": str((s or {}).get("name") or f"系列{si + 1}"),
                     "values": list(s["values"])} for si, s in enumerate(series_raw)]
        else:
            defs = [{"name": title, "values": list(ch["values"])}]
        n = len(defs[0]["values"])
        return {"kind": kind, "title": title, "labels": _labels(n, ""),
                "seriesDefs": defs, "pieItems": None, "unit": unit,
                "animS": anim_s}
    # pie
    vals = list(ch["values"])
    names = _labels(len(vals), "类目")
    items = [{"name": names[i], "value": vals[i]} for i in range(len(vals))]
    return {"kind": "pie", "title": title, "labels": names,
            "seriesDefs": None, "pieItems": items, "unit": unit,
            "animS": anim_s}


# ─── JS：共享 helpers + 三个 seek 驱动器 ──────────────────────────────────
# 约定：这些片段运行在 `const DATA = <数据岛>;` 之后（theme.wrap_scene_html
# 的尾 script 里，SEEK_HELPERS_JS 的 clamp/stepIn 已就位；echarts 全局由
# body 内联 script 先行定义）。

CHART_HELPERS_JS = """\
const PAL = DATA.palette || [];
const BRAND = DATA.brand || {};
const chart = echarts.init(document.getElementById('chart'));
const easeOutCubic = function (p) { return 1 - Math.pow(1 - p, 3); };
function fmtNum(v) {
  // 数值动画文本：两位小数截断 + 千分位（显式 locale，跨帧确定性）
  if (typeof v !== 'number' || !isFinite(v)) { return ''; }
  const r = Math.round(v * 100) / 100;
  return r.toLocaleString('en-US', { maximumFractionDigits: 2 });
}
function niceMax(v) {
  // 不小于 v 的 1/2/2.5/5×10^k 档位：轴上限自首帧固定（确定性 + 生长不缩轴）
  if (!(v > 0)) { return 1; }
  const exp = Math.floor(Math.log(v) / Math.LN10);
  const base = Math.pow(10, exp);
  const m = v / base;
  const f = m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10;
  return f * base;
}
function barLineBase(cats, axisMax, showLegend) {
  // bar/line 共用底座：animation 恒 false，轴上限固定，色板/文字取 theme
  return {
    animation: false,
    textStyle: { fontFamily: BRAND.fontSans || 'sans-serif' },
    grid: { left: 24, right: 28, top: 36, bottom: showLegend ? 64 : 28,
            containLabel: true },
    legend: { show: showLegend, bottom: 0, itemWidth: 18, itemHeight: 10,
              textStyle: { color: BRAND.muted } },
    xAxis: { type: 'category', data: cats,
             axisLine: { lineStyle: { color: BRAND.border } },
             axisTick: { alignWithLabel: true },
             axisLabel: { color: BRAND.muted, hideOverlap: true } },
    yAxis: { type: 'value', max: axisMax, name: DATA.unit || '',
             nameTextStyle: { color: BRAND.muted },
             axisLabel: { color: BRAND.muted, formatter: fmtNum },
             splitLine: { lineStyle: { color: BRAND.border } } },
  };
}
"""

BAR_SEEK_JS = """\
function makeBarSeeker() {
  // 柱状生长：逐柱左→右错峰 easeOutCubic 长到目标值，数值标签同步跳动
  // （label 取本帧插值）。返回本帧各系列当前值合计（stat 头条数值）。
  const cats = DATA.labels;
  const defs = DATA.seriesDefs;
  const animS = DATA.animS;
  const growDur = animS * 0.6;
  const stag = cats.length > 1 ? (animS * 0.4) / (cats.length - 1) : 0;
  let allMax = 0;
  defs.forEach(function (s) {
    s.values.forEach(function (v) { if (v > allMax) { allMax = v; } });
  });
  const base = barLineBase(cats, niceMax(allMax), defs.length > 1);
  return function (t) {
    let sum = 0;
    const series = defs.map(function (s, si) {
      const data = s.values.map(function (v, i) {
        const cur = v * easeOutCubic(clamp((t - i * stag) / growDur, 0, 1));
        sum += cur;
        return { value: cur };
      });
      return { name: s.name, type: 'bar', data: data, barMaxWidth: 64,
               itemStyle: { color: PAL[si % PAL.length],
                            borderRadius: [6, 6, 0, 0] },
               label: { show: true, position: 'top', color: BRAND.text,
                        formatter: function (p) {
                          return p.value ? fmtNum(p.value) : '';
                        } } };
    });
    chart.setOption(Object.assign({}, base, { series: series }), true);
    return sum;
  };
}
"""

LINE_SEEK_JS = """\
function makeLineSeeker() {
  // 折线描画：未揭示点为 null（线断在描画前沿），点 i 在其揭示窗内从
  // 前一点值 easeOutCubic 生长到目标值——线从左到右逐点显影 + 描画，
  // 描画头数值同步跳动。返回描画头（最后揭示点）当前值。
  const cats = DATA.labels;
  const defs = DATA.seriesDefs;
  const animS = DATA.animS;
  const n = cats.length;
  const revealDur = animS * 0.4;
  const stag = n > 1 ? (animS - revealDur) / (n - 1) : 0;
  let allMax = 0;
  defs.forEach(function (s) {
    s.values.forEach(function (v) { if (v > allMax) { allMax = v; } });
  });
  const base = barLineBase(cats, niceMax(allMax), defs.length > 1);
  return function (t) {
    let head = null;
    const series = defs.map(function (s, si) {
      const data = s.values.map(function (v, i) {
        const t0 = i * stag;
        if (t < t0 - 1e-9) { return { value: null }; }
        if (i === 0) { head = v; return { value: v }; }
        const prev = s.values[i - 1];
        const cur = prev + (v - prev)
          * easeOutCubic(clamp((t - t0) / revealDur, 0, 1));
        head = cur;
        return { value: cur };
      });
      return { name: s.name, type: 'line', data: data,
               symbol: 'circle', symbolSize: 9,
               lineStyle: { width: 4, color: PAL[si % PAL.length] },
               itemStyle: { color: PAL[si % PAL.length] },
               label: { show: true, position: 'top', color: BRAND.text,
                        formatter: function (p) {
                          return p.value != null ? fmtNum(p.value) : '';
                        } } };
    });
    chart.setOption(Object.assign({}, base, { series: series }), true);
    return head;
  };
}
"""

PIE_SEEK_JS = """\
function makePieSeeker() {
  // 饼图扫描展开：扫掠角 S(t)=easeOutCubic(段内进度)×360°，扇区按数据序
  // （自 startAngle 顺时针）在扫掠线越过其角窗时整块显影；未扫过的剩余角
  // 由一块透明「缓冲」扇区吸收——已显影扇区的角度/位置与终态完全一致
  // （几何稳定），扇区标签随显影出现，stat 头条数值 = 已呈现合计。
  const items = DATA.pieItems;
  const animS = DATA.animS;
  const total = items.reduce(function (a, d) { return a + d.value; }, 0);
  const starts = [];
  let acc = 0;
  items.forEach(function (d) {
    starts.push(total > 0 ? (acc / total) * 360 : 0);
    acc += d.value;
  });
  return function (t) {
    const S = easeOutCubic(clamp(t / animS, 0, 1)) * 360;
    let vis = 0;
    const data = items.map(function (d, k) {
      const swept = S >= starts[k] - 1e-9;
      if (swept) { vis += d.value; }
      return { name: d.name, value: swept ? d.value : 0,
               itemStyle: { color: PAL[k % PAL.length] },
               label: { show: swept }, labelLine: { show: swept } };
    });
    data.push({ name: '', value: Math.max(total - vis, 0), silent: true,
                itemStyle: { color: 'transparent' },
                label: { show: false }, labelLine: { show: false },
                emphasis: { disabled: true } });
    chart.setOption({
      animation: false,
      textStyle: { fontFamily: BRAND.fontSans || 'sans-serif' },
      series: [{ type: 'pie', radius: '66%', center: ['50%', '52%'],
                 startAngle: 90, data: data, avoidLabelOverlap: true,
                 itemStyle: { borderColor: BRAND.bg, borderWidth: 2 },
                 label: { color: BRAND.text,
                          formatter: function (p) {
                            return p.value > 0
                              ? p.name + ' ' + fmtNum(p.value)
                                + (DATA.unit ? ' ' + DATA.unit : '')
                              : '';
                          } },
                 labelLine: { lineStyle: { color: BRAND.muted } } }],
    }, true);
    return vis;
  };
}
"""

_DRIVERS = {"bar": BAR_SEEK_JS, "line": LINE_SEEK_JS, "pie": PIE_SEEK_JS}


def chart_driver_js(kind: str) -> str:
    """kind → 该图表的 seek 驱动器 JS（与 CHART_HELPERS_JS 拼接使用）。"""
    if kind not in _DRIVERS:
        raise ValueError(f"unknown chart kind: {kind!r} (one of {sorted(_DRIVERS)})")
    return _DRIVERS[kind]

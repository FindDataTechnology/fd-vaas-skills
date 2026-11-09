"""
listicle builder（add-typed-video-html-renderer W2.1 card 族第二件）。

榜单合集：倒数排名卡片视频。hook 卡（榜单 kicker + TOP N 大字 + 钩子句）→
条目卡×N（每条一卡：rank 大数字弹出随 seek 阶跃、title/desc、可选配图以
data: URI 内联、句级字幕带）→ CTA。全部场景 = html_full 整页（品牌 CSS
wrapper，零外链），动效由 window.seek(t) 纯函数阶跃驱动（卡片入场/rank 弹入
均为 3 步阶跃，无 CSS transition/JS 补间——逐帧重放确定性）。

结构数对照（type.json inputs.desc / spec「榜单合集视频（listicle）」）：口播
稿 `## 段名` 分段为 1 hook + N 条目 + 1 cta，段数 - 2 须等于 inputs.items 数
（items = [{rank,title,desc,image?}]）；validate_inputs 一次列全全部违规。
骨架 Segment（duration_s=0）即可校验结构，TTS 花费之前完成（渲染前零产物）。

颜色字体全部取 theme（brand 变量 + palette 槽位）——不硬编码色值；两种
orientation（1080x1920 / 1920x1080）共用同一套固定 px 版式（1080 类画幅）。
配图解析用 alignment._resolve_file（绝对直用，相对按 downloads/VAAS_ROOT
次序），读字节按魔数定 MIME 后 base64 内联——场景页不落任何文件路径引用。

契约 v2（adopt-hyperframes-video-renderer W3.2）：build_composition 产出
**卡片片段**（hook → item×N → cta），每片段自带 <style> 与唯一根 id，
seek_js 是局部时间纯函数（lt = 全局 t - clip.start）：卡片入场阶跃、rank
弹入、句级字幕切换与进度条全部由它驱动；句级字幕以 span/div 的
data-start/data-end（段内局部时间）承载，seek_js 直接读属性判窗（无 JS
数据表、无 window.seek 整页契约）。句级字幕内嵌卡内，故 subtitle 轨置空：
单一屏上文本源，避免与编译器内置字幕条同句双显。配图仍以 data: URI 内联，
品牌变量由 composition 的 :root 注入。
"""

import base64
import re
from html import escape as _esc

from .. import AbstractBuilder, Segment
from ..alignment import _resolve_file
from ..theme import js_str, wrap_scene_html

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
.top{margin-top:56px;font-size:150px;line-height:1;font-weight:800;
  letter-spacing:4px;
  background:linear-gradient(90deg,var(--vaas-accent),var(--vaas-palette-2));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.headline{margin:48px 0 0;font-size:64px;line-height:1.35;font-weight:700;
  color:var(--vaas-text)}
.rule{margin-top:56px;width:0;height:8px;border-radius:4px;
  background:linear-gradient(90deg,var(--vaas-accent),var(--vaas-palette-2))}
.subband{margin-top:auto;min-height:200px;border-top:2px solid var(--vaas-border);
  padding-top:36px;display:flex;align-items:flex-start}
.sub{font-size:38px;line-height:1.55;color:var(--vaas-text)}
"""

_ITEM_CSS = _STAGE_CSS + """
.head{display:flex;align-items:baseline;gap:28px}
.rank{font-size:170px;font-weight:800;line-height:1;opacity:0;
  font-variant-numeric:tabular-nums}
.label{font-size:28px;letter-spacing:6px;color:var(--vaas-muted)}
.row{display:flex;gap:56px;margin-top:40px;align-items:flex-start}
.col{flex:1;min-width:0}
.title{font-size:58px;line-height:1.3;font-weight:800;color:var(--vaas-text)}
.desc{margin-top:32px;font-size:40px;line-height:1.55;color:var(--vaas-text)}
.fig{margin:0;flex:0 0 360px;width:360px;height:360px;border-radius:24px;
  overflow:hidden;border:2px solid var(--vaas-border)}
.img{width:100%;height:100%;object-fit:cover;display:block}
.subband{margin-top:auto;min-height:220px;border-top:2px solid var(--vaas-border);
  padding-top:36px;display:flex;align-items:flex-start}
.sub{font-size:38px;line-height:1.55;color:var(--vaas-text)}
.progress{position:absolute;left:0;right:0;bottom:0;height:8px;
  background:var(--vaas-surface2)}
.bar{height:100%;width:0;background:var(--vaas-accent)}
"""

_CTA_CSS = _STAGE_CSS + """
.recap{font-size:130px;line-height:1;font-weight:800;letter-spacing:4px;
  background:linear-gradient(90deg,var(--vaas-accent),var(--vaas-palette-2));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.lines{margin-top:72px;display:flex;flex-direction:column;gap:36px}
.line{font-size:52px;line-height:1.4;font-weight:700;color:var(--vaas-text);
  opacity:0}
"""

_HOOK_JS = """
const card = document.getElementById('card');
const rule = document.getElementById('rule');
const sub = document.getElementById('sub');
const band = document.getElementById('band');
// 钩子首句做大字标题（静态），其余句子走句级字幕带（REST 查表）
const REST = DATA.sentences.slice(1);
document.getElementById('top').textContent = 'TOP ' + DATA.top;
document.getElementById('headline').textContent = DATA.headline;
if (!REST.length) { band.style.display = 'none'; }
window.seek = function (t) {
  // 3 步阶跃入场（0.18s/步）：opacity/位移/分隔线全部由 t 决定，无过渡
  const k = stepIn(t, 0, 3, 0.18);
  card.style.opacity = String(k / 3);
  card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';
  rule.style.width = (k / 3 * 64) + '%';
  // 句级字幕：REST 取 start<=t 的最后一句（查表纯函数，无补间）
  let cur = '';
  for (let i = 0; i < REST.length; i++) {
    if (t >= REST[i].start - 1e-9) { cur = REST[i].text; } else { break; }
  }
  sub.textContent = cur;
};
window.seek(0);
"""

_ITEM_JS = """
const D = window.__DURATION__;
const card = document.getElementById('card');
const rank = document.getElementById('rank');
const sub = document.getElementById('sub');
const bar = document.getElementById('bar');
const SENTS = DATA.sentences;
document.getElementById('title').textContent = DATA.title;
document.getElementById('desc').textContent = DATA.desc;
document.getElementById('pos').textContent = String(DATA.pos);
document.getElementById('total').textContent = String(DATA.total);
if (DATA.image) { document.getElementById('img').src = DATA.image; }
window.seek = function (t) {
  // 卡片入场 3 步阶跃（0.16s/步）
  const k = stepIn(t, 0, 3, 0.16);
  card.style.opacity = String(k / 3);
  card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';
  // rank 弹入：卡片落位后（t0=0.16 延迟起步）3 步阶跃，scale 2.08→1 纯函数
  const r = stepIn(t, 0.16, 3, 0.14);
  rank.style.opacity = (r > 0) ? '1' : '0';
  rank.style.transform = 'scale(' + (1 + (3 - r) * 0.36).toFixed(3) + ')';
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
document.getElementById('recap').textContent = 'TOP ' + DATA.top;
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

# 配图魔数 → MIME（读字节判定，扩展名兜底）；内联后零外链（scene guard 兜底）
_IMAGE_MAGIC = (
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
    (b"BM", "image/bmp"),
)
_EXT_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}

_INT_RE = re.compile(r"[+-]?\d+")


def _norm_rank(value) -> int | None:
    """rank → int（bool 拒绝；整数字符串可）；不合法返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and _INT_RE.fullmatch(value.strip()):
        return int(value.strip())
    return None


# ─── 契约 v2：卡片片段 + 局部时间 seek_js ───────────────────────────────────

# 片段根定位（同页多卡共存，seek_js 按唯一 id 找本卡，互不串台）
_CLIP_V2_CSS = (
    ".lc-clip{position:absolute;inset:0}"
    # 句级字幕：同段多句绝对叠放（只切 opacity，无回流抖动；
    # .subband 提为定位上下文，top 36px 对齐原 padding-top）
    ".subband{position:relative}"
    ".s{position:absolute;left:0;right:0;top:36px;opacity:0;font-size:38px;"
    "line-height:1.55;color:var(--vaas-text)}"
)

# 入场阶跃模板（__ROOT__ 换成片段根 id，__DUR__ 换成片段时长）——
# 全部为局部时间纯函数：无 Date.now / Math.random / 过渡 / 定时器
_HOOK_SEEK_V2 = """
function(lt){
  var root = document.getElementById('__ROOT__');
  if (!root) { return; }
  var card = root.querySelector('.card');
  var rule = root.querySelector('.rule');
  // 3 步阶跃入场（0.18s/步）：opacity/位移/分隔线全部由局部时间决定，无过渡
  var k = Math.min(3, Math.max(0, Math.floor(lt / 0.18) + 1));
  card.style.opacity = String(k / 3);
  card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';
  rule.style.width = (k / 3 * 64) + '%';
  // 钩子首句做大字标题（静态），其余句走字幕带（data-start 判窗，末句保持到卡尾）
  var ss = root.querySelectorAll('.s');
  for (var i = 0; i < ss.length; i++) {
    var s0 = parseFloat(ss[i].getAttribute('data-start'));
    var s1 = parseFloat(ss[i].getAttribute('data-end'));
    var on = lt >= s0 - 1e-9 && (i === ss.length - 1 || lt < s1);
    ss[i].style.opacity = on ? '1' : '0';
  }
}
"""

_ITEM_SEEK_V2 = """
function(lt){
  var root = document.getElementById('__ROOT__');
  if (!root) { return; }
  var card = root.querySelector('.card');
  var rank = root.querySelector('.rank');
  var bar = root.querySelector('.bar');
  // 卡片入场 3 步阶跃（0.16s/步）
  var k = Math.min(3, Math.max(0, Math.floor(lt / 0.16) + 1));
  card.style.opacity = String(k / 3);
  card.style.transform = 'translateY(' + ((3 - k) * 16) + 'px)';
  // rank 弹入：卡片落位后（t0=0.16 延迟起步）3 步阶跃，scale 2.08→1 纯函数
  var r = Math.min(3, Math.max(0, Math.floor((lt - 0.16) / 0.14) + 1));
  rank.style.opacity = (r > 0) ? '1' : '0';
  rank.style.transform = 'scale(' + (1 + (3 - r) * 0.36).toFixed(3) + ')';
  // 句级字幕：按句 span 的 data-start/data-end 判窗（局部时间读属性，末句
  // 保持到本卡结束）
  var ss = root.querySelectorAll('.s');
  for (var i = 0; i < ss.length; i++) {
    var s0 = parseFloat(ss[i].getAttribute('data-start'));
    var s1 = parseFloat(ss[i].getAttribute('data-end'));
    var on = lt >= s0 - 1e-9 && (i === ss.length - 1 || lt < s1);
    ss[i].style.opacity = on ? '1' : '0';
  }
  bar.style.width = (Math.min(1, Math.max(0, lt / __DUR__))).toFixed(3) + '%';
}
"""

_CTA_SEEK_V2 = """
function(lt){
  var root = document.getElementById('__ROOT__');
  if (!root) { return; }
  var card = root.querySelector('.card');
  var k = Math.min(3, Math.max(0, Math.floor(lt / 0.16) + 1));
  card.style.opacity = String(k / 3);
  // 逐句阶跃显现：lt 越过该行 data-start 才入场（局部时间查属性，纯函数）
  var lines = root.querySelectorAll('.line');
  for (var i = 0; i < lines.length; i++) {
    var s0 = parseFloat(lines[i].getAttribute('data-start'));
    var on = lt >= s0 - 1e-9;
    lines[i].style.opacity = on ? '1' : '0';
    lines[i].style.transform = on ? 'translateY(0)' : 'translateY(12px)';
  }
}
"""


def _seek(template: str, root_id: str, duration: float) -> str:
    """seek_js 模板 → 缝合后的局部时间函数串（str.replace，避开 % 格式化）。"""
    return (template.replace("__ROOT__", root_id)
            .replace("__DUR__", f"{float(duration):.6f}").strip())


def _sentences(seg: Segment) -> list[dict]:
    """段句表（空句表兜底整段一句：字幕带始终有内容，与原 build 同口径）。"""
    sents = [s for s in (seg["sentences"] or [])
             if str(s.get("text") or "").strip()]
    if sents:
        return sents
    return [{"text": seg["text"], "start": 0.0,
             "end": float(seg["duration_s"])}]


def _clip_fragment(root_id: str, css: str, body: str) -> str:
    """视觉 clip 片段：内联 <style>（品牌 :root 变量由 composition 顶层注入）
    + 自带唯一 id 的片段根——去掉整页 wrapper，片段可单独成卡。"""
    return (f"<style>{css}</style>"
            f'<div class="lc-clip" id="{root_id}">{body}</div>')


def _sentence_spans(sents: list[dict]) -> str:
    """句级字幕 → 叠放 span（data-start/data-end = 段内局部时间，秒）。"""
    return "".join(
        f'<span class="s" data-start="{float(s["start"]):.4f}" '
        f'data-end="{float(s["end"]):.4f}">{_esc(str(s["text"]))}</span>'
        for s in sents)


def _image_data_uri(path) -> str:
    """图片文件 → data: URI（魔数定 MIME，扩展名兜底；零外链内联口径）。"""
    raw = path.read_bytes()
    mime = next((m for sig, m in _IMAGE_MAGIC if raw.startswith(sig)), None)
    if mime is None and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        mime = "image/webp"
    if mime is None:
        mime = _EXT_MIME.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _normalize_items(raw) -> list[dict]:
    """items 原始值 → [{rank:int, title, desc, image?:data:URI}]（build 用）；
    形状不合法 raise ValueError（validate_inputs 已在渲染前列全，这里防御）。"""
    if not isinstance(raw, list) or not raw:
        raise ValueError(
            "listicle build: inputs.items (非空数组 [{rank,title,desc,image?}]) "
            "is required")
    items = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"listicle build: items[{i}] must be an object")
        rank = _norm_rank(item.get("rank"))
        if rank is None:
            raise ValueError(
                f"listicle build: items[{i}].rank must be an integer")
        title = str(item.get("title") or "").strip()
        desc = str(item.get("desc") or "").strip()
        if not title or not desc:
            raise ValueError(
                f"listicle build: items[{i}].title/.desc must be non-empty")
        entry = {"rank": rank, "title": title, "desc": desc}
        image = item.get("image")
        if isinstance(image, str) and image.strip():
            p = _resolve_file(image.strip())
            if not p.is_file():
                raise ValueError(
                    f"listicle build: items[{i}].image file missing: {image}")
            entry["image"] = _image_data_uri(p)
        items.append(entry)
    return items


class ListicleBuilder(AbstractBuilder):
    type_id = "listicle"

    def validate_inputs(self, inputs: dict, segments: list[Segment]) -> None:
        """结构数对照：items 形状 + 口播段数（1 hook + N 条目 + 1 cta）==
        items 数；一次列全全部违规（渲染前、零产物）。"""
        errors: list[str] = []
        items_raw = inputs.get("items")
        if not isinstance(items_raw, list) or not items_raw:
            errors.append(
                "inputs.items 必须是非空 JSON 数组 [{rank,title,desc,image?}]"
                "（type.json inputs.items.desc）")
            items_raw = []
        for i, item in enumerate(items_raw):
            if not isinstance(item, dict):
                errors.append(f'items[{i}] 须为对象 {{rank,title,desc,image?}}')
                continue
            if _norm_rank(item.get("rank")) is None:
                errors.append(
                    f'items[{i}].rank 须为整数（或整数字符串，如 "3"）')
            title = item.get("title")
            if not isinstance(title, str) or not title.strip():
                errors.append(f"items[{i}].title 必须是非空 string")
            desc = item.get("desc")
            if not isinstance(desc, str) or not desc.strip():
                errors.append(f"items[{i}].desc 必须是非空 string（条目口播文案）")
            image = item.get("image")
            if image is not None:
                if not isinstance(image, str) or not image.strip():
                    errors.append(
                        f"items[{i}].image 须为非空 string 路径（可选）")
                elif not _resolve_file(image.strip()).is_file():
                    errors.append(
                        f"items[{i}].image 文件不存在: {image}（须为已就绪图片，"
                        "绝对路径或相对 downloads/VAAS_ROOT）")

        n_seg = len(segments)
        n_items_seg = max(0, n_seg - 2)
        names = [s["name"] for s in segments]
        if n_seg < 3:
            errors.append(
                "口播稿须用 `## 段名` 分段为 1 hook + N 条目 + 1 cta（>= 3 段），"
                f"当前 {n_seg} 段: {names}")
        elif isinstance(items_raw, list) and items_raw:
            if len(items_raw) != n_items_seg:
                errors.append(
                    f"结构数对照失败：口播条目段数 {n_items_seg} "
                    f"(hook={names[0]!r} + 条目×{n_items_seg}="
                    f"{names[1:-1]} + cta={names[-1]!r}) != items 数 "
                    f"{len(items_raw)}")
        if errors:
            raise ValueError(
                "listicle 结构数对照失败（渲染前零产物）:\n  - "
                + "\n  - ".join(errors))

    def build(self, segments: list[Segment], inputs: dict,
              size: list[int], theme: dict) -> list[dict]:
        items = _normalize_items(inputs.get("items"))
        if len(items) != max(0, len(segments) - 2):
            raise ValueError(
                "listicle build: items 数与条目段数不一致 "
                f"(items={len(items)}, item segments={len(segments) - 2})")
        hook, item_segs, cta = segments[0], segments[1:-1], segments[-1]
        palette = theme.get("palette") or ["var(--vaas-accent)"]

        scenes = [self._hook_card(hook, len(items), size, theme)]
        for i, (seg, item) in enumerate(zip(item_segs, items)):
            scenes.append(self._item_card(
                seg, item, i + 1, len(items),
                palette[i % len(palette)], size, theme))
        scenes.append(self._cta_card(cta, len(items), size, theme))
        return scenes

    # ── 卡片：html_full 整页（seek 契约 + 品牌 wrapper，零外链） ─────────

    def _hook_card(self, seg: dict, top_n: int, size, theme) -> dict:
        sentences = seg["sentences"] or []
        headline = sentences[0]["text"] if sentences else seg["text"]
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="kicker">榜单合集</div>'
                '<div class="top" id="top"></div>'
                '<h1 class="headline" id="headline"></h1>'
                '<div class="rule" id="rule"></div>'
                '<div class="subband" id="band"><div class="sub" id="sub"></div></div>'
                '</div>')
        js = ("const DATA = " + js_str({"top": top_n, "headline": headline,
                                        "sentences": sentences})
              + ";\n" + _HOOK_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_HOOK_CSS,
                                        js=js, theme=theme)}

    def _item_card(self, seg: dict, item: dict, pos: int, total: int,
                   palette_color: str, size, theme) -> dict:
        fig = ('<figure class="fig"><img class="img" id="img" alt="">'
               '</figure>') if item.get("image") else ""
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="head">'
                f'<span class="rank" id="rank" style="color:{palette_color}"></span>'
                '<span class="label">第 <span id="pos"></span> / '
                '<span id="total"></span> 项</span>'
                '</div>'
                '<div class="row"><div class="col">'
                '<div class="title" id="title"></div>'
                '<div class="desc" id="desc"></div>'
                '</div>' + fig + '</div>'
                '<div class="subband"><div class="sub" id="sub"></div></div>'
                '<div class="progress"><div class="bar" id="bar"></div></div>'
                '</div>')
        js = ("const DATA = " + js_str({"rank": item["rank"], "pos": pos,
                                        "total": total, "title": item["title"],
                                        "desc": item["desc"],
                                        "image": item.get("image", ""),
                                        "sentences": seg["sentences"]})
              + ";\n" + _ITEM_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_ITEM_CSS,
                                        js=js, theme=theme)}

    def _cta_card(self, seg: dict, top_n: int, size, theme) -> dict:
        sents = seg["sentences"] or [{"text": seg["text"], "start": 0.0,
                                      "end": float(seg["duration_s"])}]
        lines = "".join('<div class="line"></div>' for _ in sents)
        body = ('<div class="stage-bg"></div>'
                '<div class="card" id="card">'
                '<div class="recap" id="recap"></div>'
                f'<div class="lines">{lines}</div>'
                '</div>')
        js = ("const DATA = " + js_str({"top": top_n, "sentences": sents})
              + ";\n" + _CTA_JS)
        return {"kind": "html_full", "name": seg["name"],
                "duration_s": float(seg["duration_s"]),
                "html": wrap_scene_html(size=size,
                                        duration_s=seg["duration_s"],
                                        body=body, css=_CTA_CSS,
                                        js=js, theme=theme)}

    # ── 契约 v2：卡片片段（声明的视觉轨，seek_js 局部时间） ────────────────

    def build_composition(self, segments: list[Segment], inputs: dict,
                          size: list[int], theme: dict) -> dict:
        """契约 v2：hook 卡 → 条目卡×N（rank 弹入）→ CTA，每段一 clip。

        返回 {"visual": [clip…], "subtitle": []}：句级字幕内嵌卡内（.s/.line
        由 seek_js 按局部时间切换），不重复投递全局字幕轨（避免同句双显）。
        片段首尾相接覆盖 [0, Σ段时长]；composition 时长由适配层按
        max(画面末点, 旁白时长) + tailPad 决定。
        """
        items = _normalize_items(inputs.get("items"))
        if len(items) != max(0, len(segments) - 2):
            raise ValueError(
                "listicle build_composition: items 数与条目段数不一致 "
                f"(items={len(items)}, item segments={len(segments) - 2})")
        hook, item_segs, cta = segments[0], segments[1:-1], segments[-1]
        palette = theme.get("palette") or ["var(--vaas-accent)"]

        clips = [self._hook_clip(hook, len(items), theme)]
        for i, (seg, item) in enumerate(zip(item_segs, items)):
            clips.append(self._item_clip(
                seg, item, i + 1, len(items),
                palette[i % len(palette)], theme))
        clips.append(self._cta_clip(cta, len(items), theme))
        return self._assemble(clips)

    @staticmethod
    def _assemble(clips: list[dict]) -> dict:
        """卡片片段 → 视觉轨（start 首尾相接，duration = 段时长，4 位小数）。"""
        visual: list[dict] = []
        start = 0.0
        for clip in clips:
            dur = round(float(clip["duration"]), 4)
            visual.append({"start": start, "duration": dur,
                           "html": clip["html"], "seek_js": clip["seek_js"]})
            start = round(start + dur, 4)
        return {"visual": visual, "subtitle": []}

    def _hook_clip(self, seg: Segment, top_n: int, theme) -> dict:
        dur = float(seg["duration_s"])
        root_id = "lc-hook"
        sents = _sentences(seg)
        headline = sents[0]["text"]
        rest = sents[1:]
        band = (f'<div class="subband">{_sentence_spans(rest)}</div>'
                if rest else "")
        body = ('<div class="stage-bg"></div>'
                '<div class="card">'
                '<div class="kicker">榜单合集</div>'
                f'<div class="top">TOP {top_n}</div>'
                f'<h1 class="headline">{_esc(str(headline))}</h1>'
                '<div class="rule"></div>'
                f'{band}'
                '</div>')
        return {"duration": dur,
                "html": _clip_fragment(root_id, _HOOK_CSS + _CLIP_V2_CSS, body),
                "seek_js": _seek(_HOOK_SEEK_V2, root_id, dur)}

    def _item_clip(self, seg: Segment, item: dict, pos: int, total: int,
                   palette_color: str, theme) -> dict:
        dur = float(seg["duration_s"])
        root_id = f"lc-item-{pos}"
        fig = ('<figure class="fig"><img class="img" alt="" '
               f'src="{item["image"]}"></figure>') if item.get("image") else ""
        body = ('<div class="stage-bg"></div>'
                '<div class="card">'
                '<div class="head">'
                f'<span class="rank" style="color:{palette_color}">'
                f'{item["rank"]}</span>'
                f'<span class="label">第 {pos} / {total} 项</span>'
                '</div>'
                '<div class="row"><div class="col">'
                f'<div class="title">{_esc(item["title"])}</div>'
                f'<div class="desc">{_esc(item["desc"])}</div>'
                '</div>' + fig + '</div>'
                f'<div class="subband">{_sentence_spans(_sentences(seg))}</div>'
                '<div class="progress"><div class="bar"></div></div>'
                '</div>')
        return {"duration": dur,
                "html": _clip_fragment(root_id, _ITEM_CSS + _CLIP_V2_CSS, body),
                "seek_js": _seek(_ITEM_SEEK_V2, root_id, dur)}

    def _cta_clip(self, seg: Segment, top_n: int, theme) -> dict:
        dur = float(seg["duration_s"])
        root_id = "lc-cta"
        lines = "".join(
            f'<div class="line" data-start="{float(s["start"]):.4f}">'
            f'{_esc(str(s["text"]))}</div>'
            for s in _sentences(seg))
        body = ('<div class="stage-bg"></div>'
                '<div class="card">'
                f'<div class="recap">TOP {top_n}</div>'
                f'<div class="lines">{lines}</div>'
                '</div>')
        return {"duration": dur,
                "html": _clip_fragment(root_id, _CTA_CSS + _CLIP_V2_CSS, body),
                "seek_js": _seek(_CTA_SEEK_V2, root_id, dur)}


BUILDER = ListicleBuilder()

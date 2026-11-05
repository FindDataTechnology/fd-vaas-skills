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
"""

import base64
import re

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


BUILDER = ListicleBuilder()

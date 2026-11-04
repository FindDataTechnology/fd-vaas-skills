"""
Document renderer (render_document 的 chromium print 内核).

W3 (add-presentation-plane)：md/html → 品牌 wrapper HTML → playwright chromium
（pdf: page.pdf 分页打印；longimage: full_page 截图）→ 统一 assets 账本。

契约（registry.json doc/chromium 的 driver 指向本模块）:
  - source: markdown 或 html 文本，或指向本地文件的路径（存在文件即读入；
    行首出现块级 HTML 标签按 html 直通，否则按 markdown 转 HTML）
  - W6.1 安全边界：html source 含 http(s)/file 外链（src/href/url()）→ 渲染
    失败并逐条点名违规资源、零部分产物；markdown 来源不硬拦——外链图片经
    result.warnings 注释报告（渲染离线不取数，chromium 请求拦截兜底断网）
  - format: "pdf" | "longimage"，或两者列表（["pdf","longimage"]）——每份
    产物独立落账并返回 id/slug/file_path
  - template: 版式 id（默认 "default"，清单与 templates_list(domain="doc")
    同源；版式目录 mcp_server/templates/doc/<id>/ = template.json + style.css）。
    未知模板名报错并列出可用模板清单。
  - template.json 可声明: page.size（pdf 纸张，默认 A4）、page.margin（pdf
    页边距，默认 24mm，str 或逐边 dict）、content_width（longimage 像素宽，
    默认 1080）、fonts（字体栈，覆盖 wrapper 基线的兜底栈）

品牌 CSS wrapper：md 转出的 HTML 片段与调用方 html 片段走同一 wrapper（包进
<article data-doc>，注入兜底基线 + 模板 style.css）；整页 html（含 <html>）只
在 </head> 前注入 <style>，不改调用方结构。兜底字体栈（部署镜像
fonts-noto-cjk 家族名）写死在基线 css，模板样式在其后注入可覆盖。

产物落 downloads/doc/<slug>/，insert_content 落统一 assets 账本（type=doc），
usage 记 tool="render_document"，hosted 模式附 download_url。slug 缺省按
(template, source) 规范化哈希派生；请求多格式时每份产物 slug 加 -<format>
后缀（assets.slug 全局唯一）。同 slug 幂等重放既有资产（格式须匹配，否则
删除重建）。

playwright 交互集中在 _print_pdf / _shot_longimage / _chromium（与 still_chart
共享）缝上，测试 mock 这两个 capture 函数即可全链不碰真浏览器；真实渲染由
本机冒烟探针（环境不可用则 skip）与部署探针兜底。
"""

import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Optional

from ..db import (generate_id, insert_content, record_usage, scoped_asset_slug,
                  get_asset_by_slug, delete_asset)
from ..utils import (DOWNLOADS_DIR, ensure_directory_rel, get_relative_path,
                     validate_slug)
from ..hosting import current_owner, download_url, is_hosted
from ._scene_guard import assert_no_external_refs, find_external_refs
from .templates import DOC_TEMPLATES_DIR, _load_doc_templates
from .still_chart import _chromium, SETTLE_MS

VALID_FORMATS = ("pdf", "longimage")
CONTENT_WIDTH_DEFAULT = 1080
PDF_PAPER_DEFAULT = "A4"
PDF_MARGIN_DEFAULT = "24mm"
MD_EXTENSIONS = ("tables", "fenced_code", "toc")
PDF_PROBE_VIEWPORT = (794, 1123)  # A4 @96dpi 名义视口（pdf 布局以纸张选项为准）

# 兜底字体栈写死在 wrapper 基线 css（部署镜像 fonts-noto-cjk 家族名，
# 与 render.py FONT_STACK / default 版式 style.css 同一族名序列）
FONT_STACK = ("'PingFang SC','Hiragino Sans GB','Noto Sans CJK SC','Noto Sans SC',"
              "'Microsoft YaHei',sans-serif")

# 行首块级 HTML 标签 → 按 html 直通（markdown 文本几乎不会这样起行）
_HTML_BLOCK_RE = re.compile(
    r"^\s*<(?:!doctype|html|head|body|article|section|div|p|h[1-6]|table|"
    r"thead|tbody|ul|ol|li|blockquote|pre|figure|hr|img|br|center)\b",
    re.IGNORECASE | re.MULTILINE)

# Chromium PDF 顶层页对象计数（\b 排除 /Pages 页树节点）
_PDF_PAGE_RE = re.compile(rb"/Type\s*/Page\b")

# W6.2 确定性：chromium(Skia) 在 PDF Info dict 写 /CreationDate /ModDate
# （渲染时刻，秒精度），是同输入双跑字节漂移的唯一来源（正文流全部一致，
# W6.2 双跑探针实测）。渲染侧归一化为固定时间戳：等长替换（年份恒 4 位、
# 空白与时区原样保留），xref 偏移与对象布局不变，PDF 结构不受影响。
_PDF_DATE_RE = re.compile(rb"/(CreationDate|ModDate)(\s*)\(D:\d{14}([^)]*)\)")
_PDF_DATE_PINNED = rb"/\1\2(D:20000101000000\3)"


def _pin_pdf_dates(out_path: Path) -> None:
    """渲染完即抹平 Info dict 时间戳（pdf 产物字节级确定性的根因修复）。"""
    data = out_path.read_bytes()
    pinned = _PDF_DATE_RE.sub(_PDF_DATE_PINNED, data)
    if pinned != data:
        out_path.write_bytes(pinned)


# ─── 版式模板（与 templates_list(domain="doc") 同源）────────────────────────

def _load_template(template_id: str) -> dict:
    """读 templates/doc/<id>/（template.json + style.css）。

    未知 id → 报错并列出可用模板清单（清单与 templates_list(domain="doc")
    同一 _load_doc_templates 来源）。
    """
    known = _load_doc_templates()
    if not any(t["id"] == template_id for t in known):
        raise ValueError(
            f"unknown doc template: {template_id}. Available: {[t['id'] for t in known]}")
    d = DOC_TEMPLATES_DIR / template_id
    meta = json.loads((d / "template.json").read_text(encoding="utf-8"))
    css_path = d / "style.css"
    return {**meta, "id": template_id,
            "css": css_path.read_text(encoding="utf-8") if css_path.is_file() else ""}


def _pdf_page_options(template: dict) -> dict:
    """template.json page 块 → playwright page.pdf 选项（纸张/页边距）。"""
    page = template.get("page") or {}
    m = page.get("margin")
    margin = m if isinstance(m, str) else PDF_MARGIN_DEFAULT
    opts = {"format": page.get("size") or PDF_PAPER_DEFAULT,
            "margin": {k: margin for k in ("top", "bottom", "left", "right")}}
    if isinstance(m, dict):  # 模板可逐边覆盖
        opts["margin"].update({k: m[k] for k in ("top", "bottom", "left", "right")
                               if k in m})
    return opts


# ─── W3.1: md → HTML + 品牌 wrapper ─────────────────────────────────────────

def md_to_html(source: str) -> str:
    """markdown → HTML（python-markdown；tables/fenced_code/toc）。"""
    import markdown  # 延迟导入：registry.py 启动即 import 本模块
    return markdown.markdown(source, extensions=list(MD_EXTENSIONS))


def _read_source(source: str) -> tuple:
    """source → (html_body, source_kind)。本地文件路径读入；html 直通，md 转 HTML。"""
    text = source
    try:
        p = Path(source).expanduser()
        if p.is_file():
            text = p.read_text(encoding="utf-8")
    except OSError:
        pass  # 长内联文本当路径 stat 会 ENAMETOOLONG 等 → 按文本处理
    if _HTML_BLOCK_RE.search(text):
        return text, "html"
    return md_to_html(text), "markdown"


def _base_css(content_width: Optional[int] = None) -> str:
    """wrapper 兜底基线（字体栈写死；模板 style.css 在其后注入可覆盖）。"""
    css = (f":root{{--doc-font:{FONT_STACK}}}"
           "*{box-sizing:border-box}"
           "html,body{margin:0;padding:0}"
           "body{font-family:var(--doc-font);line-height:1.7;"
           "-webkit-print-color-adjust:exact;print-color-adjust:exact}"
           "img,table,pre{max-width:100%}")
    if content_width:  # longimage：钉住像素宽（full_page 截图宽度对齐）；
        # pdf 的横向留白由页边距提供，长图无页边距 → 内边距只在长图基线给
        css += (f"body{{width:{content_width}px;overflow-x:hidden}}"
                f"[data-doc]{{width:{content_width}px;margin:0 auto;"
                "padding:12px 24px}}")
    return css


def _wrap_document_html(body_html: str, template: dict,
                        content_width: Optional[int] = None) -> str:
    """品牌 CSS wrapper（md 片段与 html 片段同一入口，见模块 docstring）。"""
    styles = [f'<style id="doc-base">{_base_css(content_width)}</style>']
    tpl_head = (f":root{{--doc-font:{template['fonts']}}}"
                if template.get("fonts") else "")
    styles.append(f'<style id="doc-template">{tpl_head}{template.get("css") or ""}</style>')
    style = "".join(styles)
    if re.search(r"<html[\s>]", body_html, re.IGNORECASE):
        low = body_html.lower()
        if "</head>" in low:
            idx = low.index("</head>")
            return body_html[:idx] + style + body_html[idx:]
        return style + body_html
    return ('<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
            + style + '</head>\n<body><article data-doc>\n' + body_html
            + "\n</article></body></html>\n")


# ─── W3.2: chromium 双格式产出 ──────────────────────────────────────────────

def _print_pdf(html: str, template: dict, out_path: Path) -> None:
    """chromium page.pdf 分页打印（模板纸张/页边距，print_background 保底色）。"""
    with _chromium(PDF_PROBE_VIEWPORT) as page:
        page.goto("about:blank")
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(SETTLE_MS)
        page.pdf(path=str(out_path), print_background=True,
                 **_pdf_page_options(template))
    _pin_pdf_dates(out_path)  # W6.2：抹平 Skia 渲染时刻时间戳（确定性）


def _shot_longimage(html: str, width: int, out_path: Path) -> tuple:
    """chromium full_page 截图 → PNG 长图；返回实际 (width, height)。"""
    with _chromium((width, 800)) as page:
        page.goto("about:blank")
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(SETTLE_MS)
        page.screenshot(path=str(out_path), full_page=True)
    return _png_size(out_path)


def _png_size(path: Path) -> tuple:
    """PNG IHDR 头解析实际像素尺寸（比 scroll 尺寸可靠）。"""
    with path.open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"longimage output is not a PNG: {path}")
    return struct.unpack(">II", head[16:24])


def _pdf_pages(data: bytes) -> Optional[int]:
    """Chromium PDF 计页（/Type /Page 对象计数；对象流压缩等计数为 0 时 None）。"""
    n = len(_PDF_PAGE_RE.findall(data))
    return n or None


# ─── 落账（参照 render.py / still_chart.py 的既有方式）──────────────────────

def _replay_or_none(scoped: str, owner: str, fmt: str) -> Optional[dict]:
    """同 slug 已有成功记录且文件在且格式匹配 → 幂等重放；否则删除重建。"""
    replay = get_asset_by_slug(scoped, owner=owner)
    if replay is None:
        return None
    rel = replay.get("file_path") or ""
    meta = replay.get("metadata") or {}
    if (replay.get("stage") != "failed" and meta.get("format") == fmt
            and rel and (DOWNLOADS_DIR / rel).exists()):
        result = {
            "id": replay["id"], "slug": replay["slug"], "file_path": rel,
            "format": fmt, "type": replay.get("type"),
            "pages": meta.get("pages"), "width": meta.get("width"),
            "height": meta.get("height"), "idempotent_replay": True,
        }
        if is_hosted():
            url = download_url(replay["id"], owner)
            if url:
                result["download_url"] = url
        return result
    delete_asset(replay["id"])
    return None


# ─── 入口 ───────────────────────────────────────────────────────────────────

def _normalize_formats(format) -> tuple:
    """format 形参 → 去重保序 tuple；接受 str 或非空 list/tuple。"""
    if isinstance(format, str):
        fmts = (format,)
    elif isinstance(format, (list, tuple)) and format:
        fmts = tuple(format)
    else:
        raise ValueError(
            f"format must be {list(VALID_FORMATS)} (string or list), got: {format!r}")
    unknown = next((f for f in fmts if f not in VALID_FORMATS), None)
    if unknown:
        raise ValueError(f"unknown document format: {unknown}. "
                         f"Available: {list(VALID_FORMATS)}")
    return tuple(dict.fromkeys(fmts))


def render_document(source: str, format, template: Optional[str] = None,
                    slug: Optional[str] = None) -> dict:
    """Render md/html source into pdf / longimage document(s) (chromium print).

    source: markdown/html 文本或本地文件路径；format: "pdf" | "longimage" |
    两者列表（每份产物独立落账）。template 未指定用 "default"。
    返回 {type, template, source_kind, formats, products: [{id, slug,
    file_path, format, ...}]}；单格式时首份产物字段同时上提到顶层。
    """
    if not source or not isinstance(source, str):
        raise ValueError("source is required (markdown/html text or path)")
    formats = _normalize_formats(format)
    template_id = template or "default"
    if slug is not None and not validate_slug(slug):
        raise ValueError(f"invalid slug: {slug!r} (lowercase letters/numbers/"
                         "hyphens, min length 2)")

    tpl = _load_template(template_id)  # 未知模板 → 报错列可用清单（W3.3）
    body, source_kind = _read_source(source)
    # W6.1c：html source 与 graphic caller HTML 同一硬校验（外链拒绝、逐条
    # 点名）；markdown 来源是纯文本面不做硬拦——外链图片只注释报告（渲染
    # 离线不取数，chromium 侧兜底断网，图片空渲染），普通超链不算
    if source_kind == "html":
        assert_no_external_refs(body, label="document html source")
        warnings: list[str] = []
    else:
        external = find_external_refs(body, include_links=False)
        warnings = []
        if external:
            warnings.append(
                "markdown source references external resource(s) — rendering "
                "is offline so they will not load; inline as data: URI if "
                "needed:\n  " + "\n  ".join(f"- {ref}" for ref in external))

    if not slug:
        canonical = json.dumps({"template": template_id, "source": source},
                               ensure_ascii=False, sort_keys=True)
        slug = f"doc-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"

    owner = current_owner()
    multi = len(formats) > 1
    products = []
    for fmt in formats:
        pslug = f"{slug}-{fmt}" if multi else slug
        scoped = scoped_asset_slug(pslug, owner)
        replayed = _replay_or_none(scoped, owner, fmt)
        if replayed is not None:
            products.append(replayed)
            continue

        out_dir = ensure_directory_rel("doc", pslug)
        out_path = out_dir / f"{pslug}.{'pdf' if fmt == 'pdf' else 'png'}"
        rel_path = get_relative_path("doc", pslug, out_path.name)

        meta = {"kind": "doc_render", "format": fmt, "template": template_id,
                "source_kind": source_kind, "generator": "playwright+chromium"}
        if fmt == "pdf":
            html = _wrap_document_html(body, tpl)
            _print_pdf(html, tpl, out_path)
            if not out_path.is_file() or out_path.stat().st_size == 0:
                raise RuntimeError(f"pdf print produced no output: {out_path}")
            meta["paper"] = _pdf_page_options(tpl)["format"]
            meta["pages"] = _pdf_pages(out_path.read_bytes())
            product = {"format": "pdf", "pages": meta["pages"]}
        else:
            width = int(tpl.get("content_width") or CONTENT_WIDTH_DEFAULT)
            html = _wrap_document_html(body, tpl, content_width=width)
            w, h = _shot_longimage(html, width, out_path)
            if not out_path.is_file() or out_path.stat().st_size == 0:
                raise RuntimeError(
                    f"longimage capture produced no output: {out_path}")
            meta.update({"width": w, "height": h, "content_width": width})
            product = {"format": "longimage", "width": w, "height": h}

        content_id = generate_id()
        insert_content(
            id=content_id, type="doc", slug=scoped, file_path=rel_path,
            metadata=meta, status="rendered", owner=owner,
        )
        record_usage(
            owner=owner, tool="render_document", provider="local",
            model="chromium+print" if fmt == "pdf" else "chromium+screenshot",
            units=1, unit_type="render", credential_source="local",
            asset_id=content_id,
        )
        product = {"id": content_id, "slug": scoped, "file_path": rel_path,
                   "type": "doc", **product}
        if is_hosted():
            url = download_url(content_id, owner)
            if url:
                product["download_url"] = url
        products.append(product)

    result = {"type": "doc", "template": template_id, "source_kind": source_kind,
              "formats": list(formats), "products": products}
    if warnings:
        result["warnings"] = warnings
    if len(products) == 1:
        result.update(products[0])
    return result

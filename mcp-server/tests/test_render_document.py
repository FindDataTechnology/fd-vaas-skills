"""
W3 (add-presentation-plane) render_document 内核单测 + 本机真渲染冒烟.

覆盖 tools/doc_render.py（tools/render.py 的 pdf/longimage 内核）：
  - md 解析（tables/fenced_code/toc）与 html 直通判定、文件路径读入
  - 品牌 wrapper 结构（兜底基线写死 fonts-noto-cjk 字体栈 + 模板 style.css
    注入 + data-doc 盒 + 整页 html 只注入不改结构）
  - format 分发（str/list/去重/白名单）与多格式独立落账（slug -<format> 后缀）
  - W3.3 模板错误：未知模板名 → 报错并列可用清单（与 templates_list(domain="doc")
    同源）
  - 落账与幂等重放（type=doc，usage tool=render_document）
  - render.py 分发面契约不变（W1 校验 + template 默认值透传）
  - 真实渲染冒烟（chromium 可用时：PDF 页数>0 / 长图宽=content_width；
    环境不可用则 skip 标注原因）

playwright 交互全部 mock（除标注 probe 的用例）；DB/downloads 全部重定向
tmp_path。
"""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
from mcp_server.db import init_schema, get_asset_by_slug, usage_summary
from mcp_server.tools import render as render_mod
from mcp_server.tools import doc_render as doc_mod
from mcp_server.tools.templates import templates_list

MD_DOC = """# 季度报告

正文一段，含**加粗**与`行内代码`。

> 引用：数据截至上季度末。

| 指标 | 数值 |
| --- | --- |
| 营收 | 120 |

```python
print("hello")
```
"""

FAKE_PDF = b"%PDF-1.4\n%fake-doc-pdf-bytes\n"


def _fake_png(width=1080, height=2400):
    """合法 PNG 头（签名 + IHDR 宽高）+ 填充字节，供 _png_size 解析。"""
    return (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
            + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
            + b"fake-idat")


FAKE_PNG = _fake_png()


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


def _ensure_rel_factory(downloads):
    def _ensure_rel(*parts):
        path = downloads.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return _ensure_rel


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
    """Redirect downloads/ writes for the doc module."""
    downloads = tmp_path / "downloads"
    monkeypatch.setattr(doc_mod, "DOWNLOADS_DIR", downloads)
    monkeypatch.setattr(doc_mod, "ensure_directory_rel", _ensure_rel_factory(downloads))
    return {"downloads": downloads}


def _fake_captures(monkeypatch, png_wh=(1080, 2400)):
    """Mock 截图缝（_print_pdf/_shot_longimage）：写假产物并记录调用。"""
    pdf_calls, shot_calls = [], []

    def _print_pdf(html, template, out_path):
        Path(out_path).write_bytes(FAKE_PDF)
        pdf_calls.append({"html": html, "template": dict(template),
                          "out_path": Path(out_path)})

    def _shot_longimage(html, width, out_path):
        Path(out_path).write_bytes(_fake_png(*png_wh))
        shot_calls.append({"html": html, "width": width,
                           "out_path": Path(out_path)})
        return png_wh

    monkeypatch.setattr(doc_mod, "_print_pdf", _print_pdf)
    monkeypatch.setattr(doc_mod, "_shot_longimage", _shot_longimage)
    return pdf_calls, shot_calls


class TestFormatNormalization:
    def test_string_and_list(self):
        assert doc_mod._normalize_formats("pdf") == ("pdf",)
        assert doc_mod._normalize_formats(["pdf", "longimage"]) == ("pdf", "longimage")
        assert doc_mod._normalize_formats(("longimage",)) == ("longimage",)

    def test_dedup_preserves_order(self):
        assert doc_mod._normalize_formats(["longimage", "pdf", "longimage"]) == \
            ("longimage", "pdf")

    def test_unknown_format_rejected(self):
        with pytest.raises(ValueError, match="unknown document format: docx"):
            doc_mod._normalize_formats("docx")
        with pytest.raises(ValueError, match="unknown document format: gif"):
            doc_mod._normalize_formats(["pdf", "gif"])

    def test_empty_or_wrong_type_rejected(self):
        with pytest.raises(ValueError, match="format must be"):
            doc_mod._normalize_formats([])
        with pytest.raises(ValueError, match="format must be"):
            doc_mod._normalize_formats(None)
        with pytest.raises(ValueError, match="format must be"):
            doc_mod._normalize_formats(7)


class TestMdAndSource:
    def test_md_tables_fenced_code_toc(self):
        html = doc_mod.md_to_html(MD_DOC)
        assert "<table>" in html and "<th>指标</th>" in html
        assert "<pre><code" in html and "print" in html
        assert "<blockquote>" in html
        assert "<h1" in html and "id=" in html  # toc 扩展给标题锚点
        assert "<strong>加粗</strong>" in html

    def test_html_block_direct_pass(self):
        body, kind = doc_mod._read_source("<p>你好 VAAS</p>\n<p>第二段</p>")
        assert kind == "html" and body == "<p>你好 VAAS</p>\n<p>第二段</p>"

    def test_markdown_text_converted(self):
        body, kind = doc_mod._read_source("# 标题\n\n正文")
        assert kind == "markdown" and body.startswith("<h1")

    def test_source_path_read_from_file(self, tmp_path):
        md = tmp_path / "report.md"
        md.write_text("# 文件标题\n\n| a | b |\n| - | - |\n", encoding="utf-8")
        body, kind = doc_mod._read_source(str(md))
        assert kind == "markdown" and "文件标题" in body

    def test_long_inline_text_not_treated_as_path(self):
        """单行长 md 文本按文本处理（Path.is_file 对长名会 ENAMETOOLONG）。"""
        text = "# 长文本标题\n\n" + "正文内容。" * 200
        body, kind = doc_mod._read_source(text)
        assert kind == "markdown" and "长文本标题" in body

    def test_source_required(self, hermetic_fs):
        with pytest.raises(ValueError, match="source is required"):
            doc_mod.render_document("", format="pdf")
        with pytest.raises(ValueError, match="source is required"):
            doc_mod.render_document(None, format="pdf")


class TestBrandWrapper:
    def test_fragment_wrapped_with_template_css_and_fallback_fonts(self):
        tpl = doc_mod._load_template("default")
        html = doc_mod._wrap_document_html("<p>正文</p>", tpl)
        assert "<article data-doc>" in html and "正文" in html
        assert html.count("<html") == 1 and html.startswith("<!DOCTYPE html>")
        base = html[html.index('<style id="doc-base">'):html.index("</style>") + 8]
        # 兜底字体栈写死在基线 css（fonts-noto-cjk 家族名）
        assert "Noto Sans CJK SC" in base and "--doc-font" in base
        tpl_style = html[html.index('<style id="doc-template">'):]
        # 模板 style.css 在基线之后注入（同特异性下模板可覆盖）
        assert "--accent" in tpl_style and "--code-bg" in tpl_style

    def test_content_width_pinned_for_longimage(self):
        tpl = doc_mod._load_template("default")
        html = doc_mod._wrap_document_html("<p>x</p>", tpl, content_width=1080)
        assert ("[data-doc]{width:1080px;margin:0 auto;padding:12px 24px}" in html)
        assert "body{width:1080px;overflow-x:hidden}" in html
        # pdf 模式不定宽（分页纸张决定宽度，横向留白由页边距提供）
        assert "width:1080px" not in doc_mod._wrap_document_html("<p>x</p>", tpl)

    def test_full_page_html_injected_not_restructured(self):
        tpl = doc_mod._load_template("default")
        page = ('<!DOCTYPE html><html><head><title>x</title>'
                "<style>p{color:red}</style></head><body><p>整页</p></body></html>")
        html = doc_mod._wrap_document_html(page, tpl)
        assert html.count("<html") == 1 and html.count("<body") == 1
        assert "<article" not in html  # 结构未改
        low = html.lower()
        assert low.index('<style id="doc-base">') < low.index("</head>")
        # 注入点在调用方样式之后 → 同特异性下调用方样式优先
        assert low.index("<style>p{color:red}") < low.index('<style id="doc-base">')

    def test_template_fonts_override_fallback_stack(self):
        html = doc_mod._wrap_document_html(
            "<p>x</p>", {"css": "", "fonts": "'Custom',serif"})
        assert "--doc-font:'Custom',serif" in html


class TestTemplateErrors:
    def test_unknown_template_lists_available(self, hermetic_fs):
        with pytest.raises(ValueError) as ei:
            doc_mod.render_document("# x", format="pdf", template="gongwen")
        msg = str(ei.value)
        assert "unknown doc template: gongwen" in msg
        listed = [t["id"] for t in templates_list(domain="doc")["templates"]["doc"]]
        assert listed == ["default"] and listed[0] in msg  # 清单与 templates_list 同源

    def test_default_template_loads_css_and_meta(self):
        tpl = doc_mod._load_template("default")
        assert tpl["id"] == "default" and "css" in tpl
        assert tpl["page"]["size"] == "A4"
        assert tpl["content_width"] == 1080


class TestRenderFlow:
    def test_pdf_happy_path_ledger_and_usage(self, hermetic_fs, monkeypatch):
        pdf_calls, _ = _fake_captures(monkeypatch)
        out = doc_mod.render_document(MD_DOC, format="pdf", slug="doc-a")
        assert out["type"] == "doc" and out["format"] == "pdf"
        assert out["file_path"] == f"doc/doc-a/doc-a.pdf"
        f = hermetic_fs["downloads"] / out["file_path"]
        assert f.is_file() and f.read_bytes() == FAKE_PDF

        row = get_asset_by_slug(out["slug"])
        assert row["type"] == "doc" and row["stage"] == "rendered"
        meta = row["metadata"]
        assert meta["kind"] == "doc_render" and meta["template"] == "default"
        assert meta["format"] == "pdf" and meta["paper"] == "A4"
        assert meta["source_kind"] == "markdown"
        assert any(r["tool"] == "render_document" for r in usage_summary())

        assert len(pdf_calls) == 1
        assert pdf_calls[0]["out_path"] == f
        # wrapper 契约进入真 HTML：md 表格转出 + 模板样式注入
        assert "<table>" in pdf_calls[0]["html"]
        assert '<style id="doc-template">' in pdf_calls[0]["html"]

    def test_longimage_happy_path_width_from_template(self, hermetic_fs, monkeypatch):
        _, shot_calls = _fake_captures(monkeypatch, png_wh=(1080, 3600))
        out = doc_mod.render_document(MD_DOC, format="longimage", slug="doc-b")
        assert out["format"] == "longimage" and out["width"] == 1080
        assert out["height"] == 3600
        assert out["file_path"] == "doc/doc-b/doc-b.png"
        assert (hermetic_fs["downloads"] / out["file_path"]).read_bytes() \
            == _fake_png(1080, 3600)
        row = get_asset_by_slug(out["slug"])
        assert row["metadata"]["width"] == 1080 and row["metadata"]["height"] == 3600
        assert row["metadata"]["content_width"] == 1080
        # 截图宽度 = 模板 content_width（默认 1080）
        assert shot_calls[0]["width"] == 1080

    def test_dual_format_each_product_ledgered(self, hermetic_fs, monkeypatch):
        pdf_calls, shot_calls = _fake_captures(monkeypatch)
        out = doc_mod.render_document(MD_DOC, format=["pdf", "longimage"],
                                      slug="doc-both")
        assert [p["format"] for p in out["products"]] == ["pdf", "longimage"]
        assert len(out["products"]) == 2 and len(pdf_calls) == 1 and len(shot_calls) == 1
        # assets.slug 全局唯一 → 多格式产物 slug 加 -<format> 后缀，独立落账
        p_pdf, p_img = out["products"]
        assert p_pdf["slug"] == "doc-both-pdf" and p_img["slug"] == "doc-both-longimage"
        assert p_pdf["id"] != p_img["id"]
        assert (hermetic_fs["downloads"] / p_pdf["file_path"]).is_file()
        assert (hermetic_fs["downloads"] / p_img["file_path"]).is_file()
        for p in (p_pdf, p_img):
            row = get_asset_by_slug(p["slug"])
            assert row["type"] == "doc" and row["metadata"]["format"] == p["format"]
        # 多格式不镜像顶层 id（避免二义）；单格式才上提
        assert "id" not in out

    def test_idempotent_replay_same_input(self, hermetic_fs, monkeypatch):
        pdf_calls, _ = _fake_captures(monkeypatch)
        first = doc_mod.render_document(MD_DOC, format="pdf")
        second = doc_mod.render_document(MD_DOC, format="pdf")
        assert second["id"] == first["id"] and second["idempotent_replay"] is True
        assert len(pdf_calls) == 1  # 第二次未再渲染

    def test_replay_format_mismatch_rebuilds(self, hermetic_fs, monkeypatch):
        _fake_captures(monkeypatch)
        pdf = doc_mod.render_document(MD_DOC, format="pdf", slug="doc-mix")
        img = doc_mod.render_document(MD_DOC, format="longimage", slug="doc-mix")
        # 同 slug 不同格式 → 旧记录删除重建（不能把 pdf 产物当 longimage 重放）
        assert img["id"] != pdf["id"] and img["format"] == "longimage"
        assert "idempotent_replay" not in img
        assert get_asset_by_slug("doc-mix")["metadata"]["format"] == "longimage"

    def test_hosted_mode_returns_download_url(self, hermetic_fs, monkeypatch):
        _fake_captures(monkeypatch)
        monkeypatch.setattr(doc_mod, "is_hosted", lambda: True)
        monkeypatch.setattr(doc_mod, "download_url",
                            lambda asset_id, owner: f"https://cdn.test/{asset_id}")
        out = doc_mod.render_document(MD_DOC, format="pdf", slug="doc-hosted")
        assert out["download_url"] == f"https://cdn.test/{out['id']}"

    def test_caller_slug_validated(self, hermetic_fs):
        with pytest.raises(ValueError, match="invalid slug"):
            doc_mod.render_document("# x", format="pdf", slug="../escape")

    def test_template_overrides_paper(self):
        """模板 paper/margin 覆盖默认（A4/24mm）；margin 支持逐边 dict。"""
        opts = doc_mod._pdf_page_options(
            {"page": {"size": "A3", "margin": "10mm"}})
        assert opts["format"] == "A3"
        assert opts["margin"] == {"top": "10mm", "bottom": "10mm",
                                  "left": "10mm", "right": "10mm"}
        opts2 = doc_mod._pdf_page_options(
            {"page": {"size": "A4", "margin": {"top": "5mm", "left": "8mm"}}})
        assert opts2["margin"] == {"top": "5mm", "bottom": "24mm",
                                   "left": "8mm", "right": "24mm"}
        # 缺省：默认纸张与页边距
        opts3 = doc_mod._pdf_page_options({})
        assert opts3["format"] == "A4" and opts3["margin"]["top"] == "24mm"


class TestPdfPageCount:
    def test_counts_page_objects_not_page_tree(self, tmp_path):
        data = (b"1 0 obj<</Type /Page/Parent 2 0 R>>endobj\n" * 3
                + b"<</Type /Pages/Kids[1 0 R]>>")
        assert doc_mod._pdf_pages(data) == 3
        assert doc_mod._pdf_pages(b"garbage") is None

    def test_png_size_parses_ihdr(self, tmp_path):
        p = tmp_path / "a.png"
        p.write_bytes(_fake_png(720, 1280))
        assert doc_mod._png_size(p) == (720, 1280)
        p.write_bytes(b"not a png")
        with pytest.raises(RuntimeError, match="not a PNG"):
            doc_mod._png_size(p)


class TestDispatcherSurface:
    """render.py 分发面契约不变（W1 校验 + 内核接线）。"""

    def test_dispatch_reaches_kernel_with_default_template(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(doc_mod, "render_document",
                            lambda **kw: captured.update(kw) or {"type": "doc"})
        out = render_mod.render_document("# hi", format="longimage")
        assert out == {"type": "doc"}
        assert captured == {"source": "# hi", "format": "longimage",
                            "template": "default", "slug": None}

    def test_dispatch_format_whitelist_unchanged(self):
        with pytest.raises(ValueError, match="unknown document format: docx"):
            render_mod.render_document("# hi", format="docx")

    def test_kernel_supports_list_format(self, hermetic_fs, monkeypatch):
        _fake_captures(monkeypatch)
        out = doc_mod.render_document("# hi", format=["pdf", "longimage"])
        assert out["formats"] == ["pdf", "longimage"]


# ─── 本机真渲染冒烟：playwright + chromium 可用时做真实产物验证 ────────────────

def _chromium_available() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    import os
    pinned = os.getenv("VAAS_CHROMIUM_EXECUTABLE")
    if pinned and Path(pinned).is_file():
        return True
    if Path("/usr/bin/chromium").is_file():
        return True
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


@pytest.mark.skipif(not _chromium_available(), reason="chromium unavailable "
                    "(local smoke probe: needs playwright + chromium)")
class TestRealRenderSmoke:
    def test_real_pdf_pages_and_wrapper(self, hermetic_fs):
        out = doc_mod.render_document(MD_DOC, format="pdf", slug="doc-probe-pdf")
        f = hermetic_fs["downloads"] / out["file_path"]
        data = f.read_bytes()
        assert data[:5] == b"%PDF-" and len(data) > 1000
        assert out["pages"] and out["pages"] >= 1  # PDF 页数 > 0
        assert get_asset_by_slug("doc-probe-pdf")["metadata"]["pages"] == out["pages"]

    def test_real_longimage_width_matches_content_width(self, hermetic_fs):
        out = doc_mod.render_document(MD_DOC, format="longimage",
                                      slug="doc-probe-img")
        f = hermetic_fs["downloads"] / out["file_path"]
        assert f.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert out["width"] == 1080 and out["height"] > 0  # 长图尺寸正确

    def test_real_document_ledgered(self, hermetic_fs):
        out = doc_mod.render_document(MD_DOC, format=["pdf", "longimage"],
                                      slug="doc-probe-both")
        assert len(out["products"]) == 2
        rows = [get_asset_by_slug(p["slug"]) for p in out["products"]]
        assert all(r["type"] == "doc" and r["stage"] == "rendered" for r in rows)
        assert any(r["tool"] == "render_document" for r in usage_summary())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

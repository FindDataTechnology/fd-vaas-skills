"""
W6.2 (add-presentation-plane) 确定性回归：三个渲染面同输入双跑（不同 slug）
重渲染产物必须一致（只测「重渲染确定性」；计划级重放语义由各自落账测试覆盖，
本文件不测重放）。

实测口径（本机 playwright chromium + ffmpeg 实跑标定，add-presentation-plane
W6.2；真跑结论见各用例 docstring）：
  - render_video storyboard 模式：mp4 容器字节 md5 一致——最强口径（本机
    ffmpeg mov muxer 默认不写创建时间戳，容器可比；与原 compose_video「同
    storyboard 双跑 md5 一致」验收先例同口径）。另附解码帧级 framemd5 交叉
    验证：若未来 ffmpeg/muxer 版本开始往容器写时间戳，帧级口径仍成立。
  - render_still chart：png 与 svg 双跑字节一致（echarts svg renderer 未引入
    随机 id / 时间戳）。
  - render_still graphic：png 双跑字节一致。
  - render_document：pdf 与 longimage 双跑字节一致。真跑曾暴露 pdf 仅差
    Info dict 的 /CreationDate /ModDate（chromium/Skia 渲染时刻，秒精度；
    解压正文流全部一致）——已根因修复：doc_render._pin_pdf_dates 渲染后把
    两个日期归一化为固定时间戳（等长替换不动 xref），归一后整文件字节直比。

CI / 无 chromium 环境自动 skip（检测 playwright chromium 可用性，skip 原因
注明；视频组另检 ffmpeg）。DB/downloads 全部重定向 tmp_path，不触碰
data/vaas.db。
"""

import hashlib
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest
def _render_plane_available() -> bool:
    """渲染面可达性（W4 起真实出片必须经渲染面）。"""
    import os, socket
    from urllib.parse import urlparse
    url = os.getenv("VAAS_RENDER_URL", "http://127.0.0.1:8099")
    u = urlparse(url)
    try:
        with socket.create_connection((u.hostname or "127.0.0.1", u.port or 80), 1):
            return True
    except OSError:
        return False


sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
import mcp_server.utils.file_manager as file_manager
from mcp_server.db import init_schema
from mcp_server.tools import doc_render as doc_mod
from mcp_server.tools import render as render_mod
from mcp_server.tools import still_chart as chart_mod
from mcp_server.tools import still_graphic as graphic_mod

# ─── 环境探针（与 test_render_still/test_render_document 的既有口径一致）──────

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


# ─── 隔离：临时 DB + 临时 downloads（勿污染 data/vaas.db）────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database; force local hosting."""
    db = tmp_path / "determinism.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.delenv("VAAS_HOSTED", raising=False)  # 本地模式（identity 免网）
    init_schema(db)
    return db


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
    """Redirect downloads/ writes for every render plane.

    file_manager.DOWNLOADS_DIR 在调用时解析 → 覆盖它即覆盖 ensure_directory /
    ensure_directory_rel 全部调用方；chart/graphic/doc 的重放检查读各自模块
    的 DOWNLOADS_DIR 绑定，逐个覆盖；render.py 重放检查读 render_mod.VAAS_ROOT。
    """
    root = tmp_path / "hermetic"
    downloads = root / "downloads"
    monkeypatch.setattr(file_manager, "DOWNLOADS_DIR", downloads)
    for mod in (chart_mod, graphic_mod, doc_mod):
        if hasattr(mod, "DOWNLOADS_DIR"):
            monkeypatch.setattr(mod, "DOWNLOADS_DIR", downloads)
    monkeypatch.setattr(render_mod, "VAAS_ROOT", root)
    return {"downloads": downloads, "resolve": lambda rel: downloads / rel}


# ─── 比对口径工具 ────────────────────────────────────────────────────────────

def _md5(path: Path) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def _framemd5_hashes(path: Path) -> list:
    """ffmpeg 解码帧级 md5（容器时间戳无关的帧内容口径）。"""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "framemd5", "-"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"framemd5 failed: {proc.stderr[-300:]}")
    return [line.split(",")[-1].strip().lower()
            for line in proc.stdout.splitlines()
            if line and not line.startswith("#")]


def _gradient_png(width: int, height: int) -> bytes:
    """确定性渐变 PNG（纯 zlib/struct，无 PIL）——kenburns 视觉输入。"""
    rows = b"".join(
        b"\x00" + bytes(v for x in range(width) for v in (
            (x * 255) // width,
            ((x + y) * 200) // (width + height),
            (y * 255) // height))
        for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        piece = struct.pack(">I", len(data)) + tag + data
        return piece + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


# ─── 真渲染双跑（chromium 可用才跑；无则整类 skip 并注明原因）─────────────────

CHART_SPEC = {"echarts_option": {
    "xAxis": {"type": "category", "data": ["一月", "二月", "三月"]},
    "yAxis": {"type": "value"},
    "series": [{"type": "bar", "data": [120, 200, 150]}],
}}

DOC_SOURCE = ("# 季度报告\n\n正文一段,含**加粗**与`行内代码`。\n\n"
              "| 指标 | 数值 |\n| --- | --- |\n| 营收 | 120 |\n")


def _double_run(fn, slug_a, slug_b):
    """同输入不同 slug 各跑一次，返回两次结果 dict。"""
    return fn(slug=slug_a), fn(slug=slug_b)


@pytest.mark.skipif(not _chromium_available(), reason="chromium unavailable "
                    "(W6.2 determinism regression needs real playwright+chromium)")
@pytest.mark.real_render
@pytest.mark.skipif(not _render_plane_available(), reason="渲染面不可达（VAAS_RENDER_URL），确定性双跑跳过")
class TestDeterministicDoubleRun:
    """同输入、不同 slug 双跑 → 产物字节一致（重渲染确定性）。"""

    def test_render_video_storyboard_double_run(self, hermetic_fs, tmp_path):
        """storyboard 双跑 mp4 字节 md5 一致（容器口径；帧级 framemd5 交叉验证）。

        实测：480x854 / fps 8 / 1.5s html_intro + 1.5s kenburns（共 24 帧，
        总长 3s），两次渲染（相隔数秒）md5 逐字节一致——ffmpeg mov muxer 默认
        不写创建时间戳，容器可比；帧级解码哈希同步一致。
        """
        if shutil.which("ffmpeg") is None:
            pytest.skip("ffmpeg unavailable (video determinism needs ffmpeg)")
        kb_image = tmp_path / "kb.png"
        kb_image.write_bytes(_gradient_png(480, 540))
        storyboard = {
            "size": [480, 854],
            "scenes": [
                {"kind": "html_intro", "duration_s": 1.5,
                 "title": "确定性回归", "sub": "W6.2"},
                {"kind": "kenburns", "duration_s": 1.5,
                 "images": [str(kb_image)], "caption": "逐帧重放",
                 "motion": "pan_down"},
            ],
        }
        (va, vb) = _double_run(
            lambda slug: render_mod.render_video(
                storyboard=storyboard, slug=slug, fps=8),
            "det-vid-a", "det-vid-b")

        assert va["slug"] != vb["slug"] and va["id"] != vb["id"]
        assert va["frames"] == vb["frames"] == 24  # 12 + 12 @ fps 8
        assert va["duration_ms"] and 2000 <= va["duration_ms"] <= 4000

        fa, fb = hermetic_fs["resolve"](va["file_path"]), \
            hermetic_fs["resolve"](vb["file_path"])
        ma, mb = _md5(fa), _md5(fb)
        # 帧级口径（解码内容，与容器时间戳无关）——确定性契约本体
        assert _framemd5_hashes(fa) == _framemd5_hashes(fb), \
            "decoded frames differ between double runs"
        # 容器字节口径（最强；本机 ffmpeg mov muxer 无时间戳，实测可比）
        assert ma == mb, f"mp4 container bytes differ: {ma} vs {mb}"

    def test_render_still_chart_double_run(self, hermetic_fs):
        """chart 双跑（png 与 svg 各一对）字节一致；echarts svg 无随机 id。"""
        for fmt in ("png", "svg"):
            spec = {**CHART_SPEC, "size": [320, 240], "format": fmt}
            (ca, cb) = _double_run(
                lambda slug: chart_mod.render_chart(spec, slug=slug),
                f"det-chart-a-{fmt}", f"det-chart-b-{fmt}")
            assert ca["slug"] != cb["slug"] and ca["id"] != cb["id"]
            da = hermetic_fs["resolve"](ca["file_path"]).read_bytes()
            db = hermetic_fs["resolve"](cb["file_path"]).read_bytes()
            assert len(da) > 0 and da == db, \
                f"chart {fmt} bytes differ between double runs"

    def test_render_still_graphic_double_run(self, hermetic_fs):
        """graphic 双跑 png 字节一致（品牌 wrapper + chromium 单帧截图）。"""
        spec = {"html": "<h2>品牌图形</h2><p>确定性回归 W6.2</p>",
                "size": [320, 240]}
        (ga, gb) = _double_run(
            lambda slug: graphic_mod.render_graphic(spec, slug=slug),
            "det-graphic-a", "det-graphic-b")
        assert ga["slug"] != gb["slug"] and ga["id"] != gb["id"]
        da = hermetic_fs["resolve"](ga["file_path"]).read_bytes()
        db = hermetic_fs["resolve"](gb["file_path"]).read_bytes()
        assert da[:8] == b"\x89PNG\r\n\x1a\n" and da == db, \
            "graphic png bytes differ between double runs"

    def test_render_document_double_run(self, hermetic_fs):
        """document 双跑 pdf 与 longimage 均字节一致。

        口径历史：真跑曾暴露 pdf 仅差 Info dict /CreationDate /ModDate
        （Skia 渲染时刻秒精度），解压正文流全部一致——已在渲染侧根因修复
        （_pin_pdf_dates 等长归一化），归一后整文件字节直比（不再退到
        「抽正文流比对」的弱口径）。
        """
        (pa, pb) = _double_run(
            lambda slug: doc_mod.render_document(DOC_SOURCE, format="pdf",
                                                 slug=slug),
            "det-doc-a", "det-doc-b")
        assert pa["slug"] != pb["slug"] and pa["id"] != pb["id"]
        da = hermetic_fs["resolve"](pa["file_path"]).read_bytes()
        db = hermetic_fs["resolve"](pb["file_path"]).read_bytes()
        assert da[:5] == b"%PDF-" and da == db, \
            "pdf bytes differ between double runs"
        assert b"D:20000101000000" in da  # 时间戳已钉住（根因修复生效）
        assert pa["pages"] and pa["pages"] >= 1

        (la, lb) = _double_run(
            lambda slug: doc_mod.render_document(DOC_SOURCE, format="longimage",
                                                 slug=slug),
            "det-doc-img-a", "det-doc-img-b")
        assert la["slug"] != lb["slug"] and la["id"] != lb["id"]
        da = hermetic_fs["resolve"](la["file_path"]).read_bytes()
        db = hermetic_fs["resolve"](lb["file_path"]).read_bytes()
        assert da[:8] == b"\x89PNG\r\n\x1a\n" and da == db, \
            "longimage png bytes differ between double runs"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

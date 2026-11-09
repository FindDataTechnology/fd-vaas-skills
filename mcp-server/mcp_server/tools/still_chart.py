"""
Chart still renderer (render_still(kind="chart") 的 echarts→chromium 内核).

W2 (add-presentation-plane)：本地 HTML（内联 vendor 的 echarts.min.js +
registerTheme 品牌主题）→ playwright chromium 截图 → 统一 assets 账本。

契约:
  spec: {
    echarts_option: {...},              # 必填，原生 echarts option
    size:  {width, height} | [w, h],    # 可选，默认 1280x720
    format: "png"(默认) | "svg",
  }
  品牌注入：echarts-theme.json（由 scripts/gen-echarts-theme.mjs 从
  brand/theme.ts 生成）经 echarts.registerTheme + init(theme) 接入——
  option 未显式指定颜色的槽位取主题色板，调用方 option 显式色优先（echarts
  的 option-over-theme 合并语义）。caller 未写 animation 时强制 False，
  静帧确定性（显式传 animation 的调用方意图保留）。

产物落 downloads/chart/<slug>/，insert_content 落统一 assets 账本
（type=chart）并附 download_url（hosted 模式），usage 记 tool="render_still"。
slug 缺省按 spec 规范化哈希派生，同一 spec 幂等重放既有资产。

playwright 交互集中在 _capture_chart / _chromium 两个缝上，测试 mock 这两个
函数即可全链不碰真浏览器；真实像素级渲染由部署探针兜底（镜像内置 chromium）。
"""

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from ..db import (generate_id, insert_content, record_usage, scoped_asset_slug,
                  get_asset_by_slug, delete_asset)
from ..utils import (DOWNLOADS_DIR, ensure_directory_rel, get_relative_path,
                     validate_slug)
from ..hosting import current_owner, download_url, is_hosted
from ._scene_guard import install_route_guard
from .render import _launch_kwargs

# vendor 资产在包内 templates/echarts/（不随 VAAS_ROOT 重定向， Wheel 打包见
# pyproject package-data）；路径从模块位置解析，生成器输出即单一来源。
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "echarts"
ECHARTS_JS_PATH = TEMPLATES_DIR / "echarts.min.js"
ECHARTS_THEME_PATH = TEMPLATES_DIR / "echarts-theme.json"

THEME_NAME = "vaas"
DEFAULT_SIZE = (1280, 720)
MAX_EDGE = 8192
VALID_FORMATS = ("png", "svg")
CHART_READY_TIMEOUT_MS = 15000
SETTLE_MS = 150  # 首帧/字体 settle（与 render.py 逐帧路径同款）


# ─── 共享底座（still_graphic 复用）───────────────────────────────────────────

def _js_json(obj) -> str:
    """JSON → 内联 <script> 安全的 JS 字面量（</ 转义防 script 提前闭合）。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/")


@contextmanager
def _chromium(size):
    """One chromium page at the given viewport; launch args shared with render.py."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(**_launch_kwargs())
        page = browser.new_page(viewport={"width": size[0], "height": size[1]},
                                device_scale_factor=1)
        install_route_guard(page)  # W6.1b：chart/graphic/doc 三路共用的断网兜底
        try:
            yield page
        finally:
            browser.close()


def _load_theme_doc() -> dict:
    """读 echarts-theme.json（每次调用现读，生成器重跑后无需重启进程）。"""
    if not ECHARTS_THEME_PATH.is_file():
        raise FileNotFoundError(
            f"echarts theme missing: {ECHARTS_THEME_PATH} — re-run "
            f"`node scripts/gen-echarts-theme.mjs` (repo root)")
    return json.loads(ECHARTS_THEME_PATH.read_text(encoding="utf-8"))


# ─── spec 解析 ──────────────────────────────────────────────────────────────

def _parse_size(size) -> tuple:
    """spec.size → (width, height)；支持 {width, height} 与 [w, h]。"""
    if size is None:
        return DEFAULT_SIZE
    if isinstance(size, dict):
        raw = (size.get("width"), size.get("height"))
    elif isinstance(size, (list, tuple)) and len(size) == 2:
        raw = tuple(size)
    else:
        raise ValueError(
            f"spec.size must be {{width, height}} or [w, h], got: {size!r}")
    out = []
    for v in raw:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v):
            raise ValueError(f"spec.size must be integers, got: {size!r}")
        v = int(v)
        if not 1 <= v <= MAX_EDGE:
            raise ValueError(
                f"spec.size out of range 1..{MAX_EDGE}: {size!r}")
        out.append(v)
    return out[0], out[1]


# ─── 本地渲染 HTML ──────────────────────────────────────────────────────────

def _chart_html(option: dict, size: tuple, theme_doc: dict, fmt: str) -> str:
    """内联 echarts + 主题注入 + setOption 的单页 HTML。

    色板注入机制：registerTheme(THEME_NAME, theme) + init(el, THEME_NAME) 后，
    未显式指定颜色的槽位按 theme.color 色板取色；caller option 里的显式色
    （顶层 color 数组、series.itemStyle.color…）按 echarts option-over-theme
    语义优先。
    """
    w, h = size
    brand = theme_doc.get("brand") or {}
    bg = brand.get("bg", "#0a0e14")
    echarts_js = ECHARTS_JS_PATH.read_text(encoding="utf-8")
    merged = {"animation": False, **option}  # caller 显式 animation 优先
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;padding:0;background:{bg}}}
  #chart{{width:{w}px;height:{h}px;background:{bg}}}
</style></head>
<body><div id="chart"></div>
<script>{echarts_js}</script>
<script>
  var THEME = {_js_json(theme_doc.get("theme") or {})};
  var OPTION = {_js_json(merged)};
  echarts.registerTheme('{THEME_NAME}', THEME);
  var chart = echarts.init(document.getElementById('chart'), '{THEME_NAME}',
                           {{renderer: '{'svg' if fmt == 'svg' else 'canvas'}'}});
  chart.setOption(OPTION, true);
  window.__CHART_READY__ = true;
</script></body></html>
"""


def _capture_chart(html: str, size: tuple, fmt: str, out_path: Path) -> None:
    """Load the chart page in chromium and write the still to out_path.

    png — #chart 元素截图（与 spec.size 逐像素对齐）；
    svg — svg renderer 下取容器 innerHTML（echarts 根节点自带 xmlns）。
    """
    with _chromium(size) as page:
        pageErrors: list[str] = []
        page.on("pageerror", lambda e: pageErrors.append(str(e)))
        page.goto("about:blank")
        page.set_content(html, wait_until="load")
        try:
            page.wait_for_function("window.__CHART_READY__ === true",
                                   timeout=CHART_READY_TIMEOUT_MS)
        except Exception:
            raise RuntimeError(
                "echarts failed to initialize in chromium "
                f"(pageerror: {pageErrors[:3] or 'none'})") from None
        page.wait_for_timeout(SETTLE_MS)
        if fmt == "svg":
            svg = page.evaluate("document.getElementById('chart').innerHTML")
            if "<svg" not in svg:
                raise RuntimeError("svg renderer produced no <svg> root")
            start = svg.index("<svg")
            out_path.write_text(svg[start:], encoding="utf-8")
        else:
            page.locator("#chart").screenshot(path=str(out_path))


# ─── 落账（参照 render.py::compose_storyboard 的既有方式）──────────────────

def _replay_or_none(scoped: str, owner: str) -> Optional[dict]:
    """同 slug 已有成功记录且文件在 → 幂等重放；failed/缺失 → 删除重建。"""
    replay = get_asset_by_slug(scoped, owner=owner)
    if replay is None:
        return None
    rel = replay.get("file_path") or ""
    if replay.get("stage") != "failed" and rel and (DOWNLOADS_DIR / rel).exists():
        meta = replay.get("metadata") or {}
        result = {
            "id": replay["id"], "slug": replay["slug"], "file_path": rel,
            "format": meta.get("format"), "width": meta.get("width"),
            "height": meta.get("height"), "type": replay.get("type"),
            "idempotent_replay": True,
        }
        if is_hosted():
            url = download_url(replay["id"], owner)
            if url:
                result["download_url"] = url
        return result
    delete_asset(replay["id"])
    return None


# ─── 入口 ───────────────────────────────────────────────────────────────────

def render_chart(spec: dict, slug: Optional[str] = None, format: str = "png") -> dict:
    """Render one chart still from an echarts option spec (local chromium driver).

    spec: {echarts_option: {...} 必填, size?: {width, height} | [w, h],
           format?: "png"(默认)|"svg"}。spec.format 优先于 format 形参。
    返回 {id, slug, file_path, format, width, height[, download_url]}，
    file_path 相对 downloads/，绝对路径 = <VAAS_ROOT>/downloads/<file_path>。
    """
    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")
    option = spec.get("echarts_option")
    if not isinstance(option, dict) or not option:
        raise ValueError(
            "spec.echarts_option (non-empty dict, native echarts option) is required")
    fmt = spec.get("format") or format
    if fmt not in VALID_FORMATS:
        raise ValueError(f"format must be one of {VALID_FORMATS}, got: {fmt!r}")
    size = _parse_size(spec.get("size"))
    w, h = size
    if slug is not None and not validate_slug(slug):
        raise ValueError(f"invalid slug: {slug!r} (lowercase letters/numbers/"
                         "hyphens, min length 2)")

    theme_doc = _load_theme_doc()

    # 计划级幂等：slug 缺省按 spec 规范化哈希派生（同 spec → 同 slug → 重放）
    if not slug:
        canonical = json.dumps(
            {"echarts_option": option, "size": list(size), "format": fmt},
            ensure_ascii=False, sort_keys=True)
        slug = f"chart-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"

    owner = current_owner()
    scoped = scoped_asset_slug(slug, owner)
    replayed = _replay_or_none(scoped, owner)
    if replayed is not None:
        return replayed

    out_dir = ensure_directory_rel("chart", slug)
    out_path = out_dir / f"{slug}.{fmt}"
    rel_path = get_relative_path("chart", slug, out_path.name)

    html = _chart_html(option, size, theme_doc, fmt)
    _capture_chart(html, size, fmt, out_path)
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise RuntimeError(f"chart capture produced no output: {out_path}")

    echarts_version = (theme_doc.get("meta") or {}).get("echarts", "unknown")
    content_id = generate_id()
    insert_content(
        id=content_id, type="chart", slug=scoped, file_path=rel_path,
        metadata={"kind": "chart_still", "format": fmt, "width": w, "height": h,
                  "echarts": echarts_version, "theme": THEME_NAME,
                  "renderer": "svg" if fmt == "svg" else "canvas",
                  "generator": "playwright+echarts"},
        status="rendered", owner=owner,
    )
    record_usage(
        owner=owner, tool="render_still", provider="local",
        model=f"chromium+echarts@{echarts_version}", units=1,
        unit_type="render", credential_source="local", asset_id=content_id,
    )

    result = {
        "id": content_id, "slug": scoped, "file_path": rel_path,
        "format": fmt, "width": w, "height": h, "type": "chart",
    }
    if is_hosted():
        url = download_url(content_id, owner)
        if url:
            result["download_url"] = url
    return result

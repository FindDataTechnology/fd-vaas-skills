"""
Scene safety guard (add-presentation-plane W6.1): 外置场景安全边界.

Spec 契约：外置 HTML 场景 MUST 无外链渲染——网络访问被禁用、外部资源以
data: URI 内联、违反时渲染失败并指明违规资源、不产部分产物；外置场景不得
访问宿主文件系统。两条防线共用本模块：

  1. 渲染前硬校验（W6.1a）— find_external_refs / assert_no_external_refs：
     扫描 src/srcset/poster/href 属性值与 CSS url()/@import 中的 http(s)://
     与 file:// 引用，命中即抛 ValueError 并逐条列出违规资源 URL。渲染底座
     在任何磁盘写入（帧目录/产物/账本行）之前调用，违规时零部分产物。
     data: URI、相对路径、#锚点放行。
  2. chromium 请求拦截兜底（W6.1b）— install_route_guard(page)：
     page.route 拦截一切非 data: 且非 about: 的请求一律 abort——静态扫描
     不可见的 JS 动态外链（fetch/XHR/new Image）在渲染期被断网，file://
     请求同被断（外置场景不得读宿主文件）。拦截走 CDP Fetch 域，playwright
     托管 chromium 与镜像 /usr/bin/chromium 双启动路径（render._launch_kwargs）
     同享，不改 launch 行为。

出 HTML 的渲染路径全部接线本模块：
  tools/render.py::_render_html_frames  — storyboard 场景页（逐帧）
  tools/still_chart.py::_chromium       — chart / graphic / doc 三处共享 page 缝
"""

import re
from urllib.parse import urlsplit

# 违规 scheme：http(s) 外链与 file:// 宿主文件引用（离线渲染 + 不读宿主文件）
_EXTERNAL_SCHEME_RE = re.compile(r"^(?:https?|file)://", re.IGNORECASE)

# 资源加载属性与链接属性分开扫：markdown 来源的「只报告资源引用、不拦普通
# 超链」模式（W6.1c）用 include_links=False 关掉 href 面。
# srcset 值可含多候选（"a.png 1x, b.png 2x"），逐段取 URL 部分。
_RESOURCE_ATTR_RE = re.compile(
    r"""\b(src|srcset|poster)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
    re.IGNORECASE)
_LINK_ATTR_RE = re.compile(
    r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
_CSS_URL_RE = re.compile(
    r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)'"]+?))\s*\)""", re.IGNORECASE)
_CSS_IMPORT_RE = re.compile(
    r"""@import\s+(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)

# 请求拦截放行的 scheme：data:（内联子资源，kenburns 图等）与 about:（about:blank 载体页）
_ROUTE_ALLOWED_SCHEMES = ("data", "about")


def _first_group(groups) -> str:
    """三选一的捕获组（双引号/单引号/裸值）里取实际命中的那个。"""
    return next(g for g in groups if g is not None)


def find_external_refs(html: str, *, include_links: bool = True) -> list[str]:
    """收集 html 引用的外部资源 URL（保序去重，不抛错）。

    扫描面：src/srcset/poster（及 href，include_links=True 时）属性值 +
    CSS url()/@import。值以 http(s):// 或 file:// 起头即违规；data: URI、
    相对路径、#锚点放行。markdown 转出的 HTML 传 include_links=False 只看
    资源加载面（普通超链不是渲染期取数，只报告图片类外链）。
    """
    values: list[str] = []
    for m in _RESOURCE_ATTR_RE.finditer(html):
        name = m.group(1).lower()
        value = _first_group(m.groups()[1:])
        if name == "srcset":
            for token in value.split(","):
                token = token.strip()
                if token:  # 去掉 "1x"/"2x" 权重段
                    values.append(token.split()[0])
        else:
            values.append(value.strip())
    if include_links:
        for m in _LINK_ATTR_RE.finditer(html):
            values.append(_first_group(m.groups()).strip())
    for m in _CSS_IMPORT_RE.finditer(html):  # @import 在合法 CSS 里先于规则出现
        values.append(_first_group(m.groups()).strip())
    for m in _CSS_URL_RE.finditer(html):
        values.append(_first_group(m.groups()).strip())

    refs: list[str] = []
    for v in values:
        if _EXTERNAL_SCHEME_RE.match(v) and v not in refs:
            refs.append(v)
    return refs


def assert_no_external_refs(html: str, label: str = "scene html",
                            *, include_links: bool = True) -> None:
    """W6.1a 硬校验：html 含外链即抛 ValueError，逐条列出违规资源 URL。"""
    refs = find_external_refs(html, include_links=include_links)
    if refs:
        raise ValueError(
            f"{label} contains external resource reference(s) — external "
            "assets must be inlined as data: URIs (rendering is offline):\n  "
            + "\n  ".join(f"- {ref}" for ref in refs))


def install_route_guard(page, on_abort=None) -> None:
    """chromium 侧兜底（W6.1b）：本页一切非 data:/about: 请求一律 abort。

    静态校验只见静态引用；JS 动态外链（fetch/XHR/new Image）由这里断网。
    file:// 同被 abort（外置场景不得访问宿主文件系统）。data: 子资源
    （kenburns 内联图等）与 about:blank 导航放行。

    on_abort(url) — 可选审计回调，每次 abort 携带请求 URL（单测/部署探针
    观测面；回调异常不干扰拦截）。
    """

    def _gate(route) -> None:
        scheme = urlsplit(route.request.url).scheme.lower()
        if scheme in _ROUTE_ALLOWED_SCHEMES:
            route.continue_()
            return
        if on_abort is not None:
            try:
                on_abort(route.request.url)
            except Exception:
                pass
        route.abort()

    page.route("**/*", _gate)

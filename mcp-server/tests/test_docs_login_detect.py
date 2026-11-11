"""登录态判据回归：`docs_login._detect` 必须把「登录页 URL」判成未登录，
且微博必须按**页面用户态**判（它的 URL 不可靠）。

两条真实事故（都在 2026-11-11 实证）：

1. **假绿**：微博登录页 URL 是 `https://weibo.com/newlogin?url=…`，旧判据
   `r"/(login|signin|passport)"` 锚定了前置斜杠 —— `newlogin` 里没有独立的 `/login`，
   于是登录页被判成已登录。面板绿牌、`.docs_state.json` 里 `logged_in: true`，
   真正的代价是发布时才炸。

2. **修过头也会错**：把 newlogin 一律判未登录后，实测发现**已登录时微博照样把 URL
   停在 `/newlogin?…&url=https://weibo.com/`**，页面渲染的却是已登录 feed
   （avatar=24、body 含「热搜/关注」、SUB 在场）。同 profile 同 URL，
   headless 与有头结果逐项一致 ⇒ 变量是 URL，不是 headless。
   故判据改为优先看页面用户态，拿不到 DOM 才退回 URL。

判据不手抄：直接 import 真实模块、喂一个只有 `.url` + `.evaluate` 的假 page 对象，
跑真实分支。`docs_login.py` 顶层只 import stdlib（patchright 在 `run()` 内部才 import），
所以可安全加载。

同一判据在 `fd-vaas-publish-docs/scripts/platforms/weibo.py::logged_in` 里也有一份，
两条路径必须同结论；发布侧本测试按源码内正则重建判据做比对（该模块顶层会 import
浏览器工具，不宜直接加载）。
"""
from __future__ import annotations

import importlib.util
import re
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS_LOGIN = ROOT / ".agents/skills/fd-vaas-login/scripts/docs_login.py"
WEIBO_PUBLISH = ROOT / ".agents/skills/fd-vaas-publish-docs/scripts/platforms/weibo.py"


def _load_docs_login():
    spec = importlib.util.spec_from_file_location("docs_login_under_test", DOCS_LOGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Page:
    """`_detect` 只读 `page.url`；微博分支另读 `page.evaluate(...)` 数用户态节点。"""

    def __init__(self, url: str, user_nodes: int = 0, eval_raises: bool = False):
        self.url = url
        self._user_nodes = user_nodes
        self._eval_raises = eval_raises

    def evaluate(self, _script: str):
        if self._eval_raises:
            raise RuntimeError("evaluate unavailable")
        return self._user_nodes


def _p(url: str, **kw) -> _Page:
    return _Page(url, **kw)


# (platform, page_kwargs, expected_logged_in) —— 每条都是线上真实观测过的形状
CASES = [
    # ── 微博：最要紧的一组 ──
    # 已登录但 URL 停在 newlogin（真实形态）：靠 DOM 判据认出「已登录」
    ("weibo", dict(url="https://weibo.com/newlogin?url=https%3A%2F%2Fweibo.com%2F", user_nodes=24), True),
    # 真正未登录：URL 是登录页、页面也没有用户态节点
    ("weibo", dict(url="https://weibo.com/newlogin?url=https%3A%2F%2Fweibo.com%2F", user_nodes=0), False),
    # 拿不到 DOM（evaluate 抛错）时退回 URL 判据：newlogin 必须判未登录
    ("weibo", dict(url="https://weibo.com/newlogin?url=x", user_nodes=0, eval_raises=True), False),
    ("weibo", dict(url="https://weibo.com/", user_nodes=0), True),
    ("weibo", dict(url="https://weibo.com/u/1234567890", user_nodes=0), True),
    ("weibo", dict(url="https://weibo.com/login.php", user_nodes=0), False),
    # passport 域即使数到节点也不算（SSO 页会带站点外壳）
    ("weibo", dict(url="https://passport.weibo.com/sso/signin", user_nodes=5), False),
    # ── 微信公众号：登录后必落 /cgi-bin/ ──
    ("weixin_mp", dict(url="https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN"), True),
    ("weixin_mp", dict(url="https://mp.weixin.qq.com/"), False),
    # ── 同花顺：未登录或无资质都会停在 upass / adviserEnterGuide ──
    ("tonghuashun", dict(url="http://upass.10jqka.com.cn/media/index/?department=sns"), False),
    ("tonghuashun", dict(url="https://media.10jqka.com.cn/adviserEnterGuide"), False),
    ("tonghuashun", dict(url="https://media.10jqka.com.cn/"), True),
    # ── 百家号：登录页带 /login ──
    ("baijiahao", dict(url="https://baijiahao.baidu.com/builder/theme/bjh/login"), False),
    ("baijiahao", dict(url="https://baijiahao.baidu.com/builder/rc/edit"), True),
    # ── 知乎 / 东方财富 / 今日头条 ──
    ("zhihu", dict(url="https://www.zhihu.com/signin?next=%2F"), False),
    ("zhihu", dict(url="https://zhuanlan.zhihu.com/write"), True),
    ("eastmoney", dict(url="https://passport.eastmoney.com/login"), False),
    ("eastmoney", dict(url="https://mp.eastmoney.com/dashboard"), True),
    ("toutiao", dict(url="https://mp.toutiao.com/auth/page/login"), False),
    ("toutiao", dict(url="https://mp.toutiao.com/profile_v4/index"), True),
]


def test_detect_matches_expected_verdicts():
    docs_login = _load_docs_login()
    wrong = []
    for platform, kw, expected in CASES:
        got, _ = docs_login._detect(platform, _Page(**kw))
        if got != expected:
            wrong.append(f"{platform}: {kw} → {got}（期望 {expected}）")
    assert not wrong, "登录态判据与预期不符：\n  " + "\n  ".join(wrong)


def test_weibo_newlogin_without_session_is_not_logged_in():
    """钉住 11-11 的假绿：登录页 URL + 无用户态节点 ⇒ 未登录。"""
    docs_login = _load_docs_login()
    for url in (
        "https://weibo.com/newlogin?url=https%3A%2F%2Fweibo.com%2F",
        "https://weibo.com/newlogin?tabtype=weibo&gid=102803&openLoginLayer=0",
    ):
        assert docs_login._detect("weibo", _Page(url, user_nodes=0))[0] is False, url


def test_weibo_newlogin_with_session_is_logged_in():
    """钉住 11-11 的「修过头」：会话在时 URL 仍带 newlogin，但必须判已登录。

    这条是本案的关键——只按 URL 判的平台在这里必错。
    """
    docs_login = _load_docs_login()
    url = "https://weibo.com/newlogin?tabtype=weibo&gid=102803&openLoginLayer=0&url=https://weibo.com/"
    assert docs_login._detect("weibo", _Page(url, user_nodes=24))[0] is True, url


def test_weibo_publish_uses_same_url_reject_list():
    """发布侧退化路径必须与 docs_login 同一条 URL 拒绝正则，且同样带 passport 守卫。"""
    src = WEIBO_PUBLISH.read_text(encoding="utf-8")
    m = re.search(r"def logged_in\(b\):\n(.*?)\n\n", src, re.S)
    assert m, "weibo.py 里找不到 logged_in(b)"
    body = m.group(1)

    assert "evaluate" in body, "发布侧微博判据应优先读页面用户态（与 docs_login 同口径）"
    assert '"passport.weibo.com" not in url' in body, "发布侧缺 passport 域守卫"

    regex_src = re.search(r're\.search\((r"[^"]*login[^"]*"),\s*url', body)
    assert regex_src, "weibo.py::logged_in 里找不到 URL 拒绝正则"
    pattern = eval(regex_src.group(1))  # noqa: S307 - 被测源码里的正则字面量

    docs_login = _load_docs_login()
    for url in (
        "https://weibo.com/newlogin?url=x",
        "https://passport.weibo.com/sso/signin",
        "https://weibo.com/login.php",
        "https://weibo.com/",
    ):
        # 发布侧退化路径（无 DOM）与 docs_login（无 DOM）必须同结论
        publish_ok = not re.search(pattern, url, re.I)
        docs_ok = docs_login._detect("weibo", _Page(url, user_nodes=0))[0]
        assert publish_ok == docs_ok, (
            f"两处判据分歧：{url}\n  publish-docs={publish_ok}  docs_login={docs_ok}"
        )

"""登录态判据回归：`docs_login._detect` 必须把「登录页 URL」判成未登录。

为什么要有这条（2026-11-11 实证）：微博登录页的 URL 是
`https://weibo.com/newlogin?url=…`，而旧判据 `r"/(login|signin|passport)"`
锚定了前置斜杠 —— `newlogin` 里没有独立的 `/login`，于是**登录页被判成已登录**。
面板显示 ✅ 绿牌、`.docs_state.json` 里 `logged_in: true`，但 `url` 明明是新登录页；
真正的代价是发布时才炸，而且会被误当成「发帖选择器坏了」。

判据不手抄：直接 import 真实模块、喂一个只有 `.url` 的假 page 对象，跑真实分支。
`docs_login.py` 顶层只 import stdlib（patchright 在 `run()` 内部才 import），所以可安全加载。

同一判据在 `fd-vaas-publish-docs/scripts/platforms/weibo.py::logged_in` 里也有一份
（docs_login 的注释明说「语义与 publish-docs 各平台 logged_in() 一致」），因此两边
都必须回归到同一结论 —— 本测试同时断言两处对同一批 URL 给出一致结果。
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


def _page(url: str):
    """`_detect` 只读 `page.url`（以及个别平台的 evaluate），这里给最小替身。"""
    return types.SimpleNamespace(url=url)


# (platform, url, expected_logged_in) —— 每条都是线上真实观测过的 URL 形状
CASES = [
    # 微博：本轮修的就是第一条
    ("weibo", "https://weibo.com/newlogin?url=https%3A%2F%2Fweibo.com%2F", False),
    ("weibo", "https://passport.weibo.com/sso/signin", False),
    ("weibo", "https://weibo.com/login.php", False),
    ("weibo", "https://weibo.com/", True),
    ("weibo", "https://weibo.com/u/1234567890", True),
    # 微信公众号：登录后必落 /cgi-bin/
    ("weixin_mp", "https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN", True),
    ("weixin_mp", "https://mp.weixin.qq.com/", False),
    # 同花顺：未登录或无资质都会停在 upass / adviserEnterGuide
    ("tonghuashun", "http://upass.10jqka.com.cn/media/index/?department=sns", False),
    ("tonghuashun", "https://media.10jqka.com.cn/adviserEnterGuide", False),
    ("tonghuashun", "https://media.10jqka.com.cn/", True),
    # 百家号：登录页带 /login
    ("baijiahao", "https://baijiahao.baidu.com/builder/theme/bjh/login", False),
    ("baijiahao", "https://baijiahao.baidu.com/builder/rc/edit", True),
    # 知乎 / 东方财富 / 今日头条
    ("zhihu", "https://www.zhihu.com/signin?next=%2F", False),
    ("zhihu", "https://zhuanlan.zhihu.com/write", True),
    ("eastmoney", "https://passport.eastmoney.com/login", False),
    ("eastmoney", "https://mp.eastmoney.com/dashboard", True),
    ("toutiao", "https://mp.toutiao.com/auth/page/login", False),
    ("toutiao", "https://mp.toutiao.com/profile_v4/index", True),
]


def test_detect_matches_expected_verdicts():
    docs_login = _load_docs_login()
    wrong = []
    for platform, url, expected in CASES:
        got, _ = docs_login._detect(platform, _page(url))
        if got != expected:
            wrong.append(f"{platform}: {url} → {got}（期望 {expected}）")
    assert not wrong, "登录态判据与预期不符：\n  " + "\n  ".join(wrong)


def test_weibo_newlogin_is_never_logged_in():
    """单独把本轮的真 bug 钉住：登录页 URL 必须是 False。"""
    docs_login = _load_docs_login()
    for url in (
        "https://weibo.com/newlogin?url=https%3A%2F%2Fweibo.com%2F",
        "https://weibo.com/newlogin?tabtype=weibo&gid=102803&openLoginLayer=0",
    ):
        assert docs_login._detect("weibo", _page(url))[0] is False, url


def test_weibo_publish_matches_docs_login():
    """两处判据必须同结论（docs_login 的注释声明「语义与 publish-docs 一致」）。"""
    docs_login = _load_docs_login()
    src = WEIBO_PUBLISH.read_text(encoding="utf-8")
    m = re.search(r"def logged_in\(b\):\n(.*?)\n\n", src, re.S)
    assert m, "weibo.py 里找不到 logged_in(b)"

    # 用真实函数体里的那条正则重建判据，避免手抄
    regex_src = re.search(r"re\.search\((r\".*?\"),\s*b\.page\.url", m.group(1), re.S)
    assert regex_src, "weibo.py::logged_in 未按预期用 re.search(..., b.page.url)"
    pattern = eval(regex_src.group(1))  # noqa: S307 - 被测源码里的正则字面量

    urls = [u for p, u, _ in CASES if p == "weibo"]
    for url in urls:
        publish_ok = not re.search(pattern, url, re.I)
        docs_ok = docs_login._detect("weibo", _page(url))[0]
        assert publish_ok == docs_ok, (
            f"两处判据分歧：{url}\n  publish-docs={publish_ok}  docs_login={docs_ok}"
        )

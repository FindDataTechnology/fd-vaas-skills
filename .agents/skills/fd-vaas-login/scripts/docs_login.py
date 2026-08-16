#!/usr/bin/env python3
"""
图文平台登录助手 — 通过 patchright（自带 Chromium，跨平台）驱动。

自有逻辑图文平台（知乎/公众号/雪球/东财/同花顺/头条/百家号/微博）走持久化
profile（$VAAS/.profiles/<name>），登录态与发布共用（登一次即可发）。
本脚本给 fd-vaas-login 面板提供「检查登录态 / 打开窗口登录」两种动作：

  python3 docs_login.py <platform> --check   # 打开页面检测登录态，打印 VAAS_DOCS_RESULT，关窗
  python3 docs_login.py <platform> --login   # 打开登录页，轮询直到登录成功（最多 10 分钟），关窗

镜像同目录 bilibili_login.py 的 patchright persistent-context 模式（channel=None 用
patchright 自带 stealth chromium，macOS / Windows 通用）。检测标记与
fd-vaas-publish-docs/references/<platform>.md 的「登录态校验」保持一致。
小红书/抖音/快手图文走上游 Note，cookie 与视频发布共享，不在本脚本范围。

对 login-manager.py 的契约（零改动即可继续工作）：
  - argv：<platform> --check|--login
  - stdout：打印一行 VAAS_DOCS_RESULT {platform, logged_in, url}
  - 退出码：0 = 已登录，1 = 未登录/超时
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# ─── 平台注册表 ─────────────────────────────────────────────────
# detect 逻辑移进 _detect()，这里只留打开 URL + 等待秒数。
REGISTRY = {
    "zhihu": {
        "name": "知乎",
        "url": "https://zhuanlan.zhihu.com/write",
        "wait": 3,  # 未登录时编辑器跳 www.zhihu.com/signin
    },
    "weixin_mp": {
        "name": "微信公众号",
        "url": "https://mp.weixin.qq.com/",
        "wait": 4,  # 登录后跳 /cgi-bin/home；未登录停在登录页
    },
    "xueqiu": {
        "name": "雪球",
        "url": "https://xueqiu.com/",
        "wait": 4,  # 未登录：页内弹层（URL 不变），body 含「发送验证码」+「登录」
    },
    "eastmoney": {
        "name": "东方财富号",
        "url": "https://mp.eastmoney.com/collect/pc_article/index.html#/",
        "wait": 6,  # SPA 渲染；未登录跳 passport/login
    },
    "tonghuashun": {
        "name": "同花顺财经号",
        "url": "https://media.10jqka.com.cn/",
        "wait": 5,  # 302 跳转；未登录/无资质被 302 到 adviserEnterGuide
    },
    "toutiao": {
        "name": "今日头条",
        "url": "https://mp.toutiao.com/profile_v4/graphic/publish",
        "wait": 5,
    },
    "baijiahao": {
        "name": "百家号",
        "url": "https://baijiahao.baidu.com/builder/rc/edit",
        "wait": 6,
    },
    "weibo": {
        "name": "微博",
        "url": "https://weibo.com/",
        "wait": 5,
    },
}


def _profile_dir(platform: str) -> Path:
    """$VAAS/.profiles/<name>；公众号在发布 skill 里目录名是 weixin。"""
    vaas = os.environ.get("VAAS_ROOT") or os.path.expanduser("~/VAAS")
    name = "weixin" if platform == "weixin_mp" else platform
    return Path(vaas) / ".profiles" / name


def _detect(platform: str, page) -> tuple[bool, str]:
    """按平台标记判断登录态。返回 (logged_in, url)。语义与 publish-docs 各平台 logged_in() 一致。"""
    try:
        url = page.url
    except Exception:
        return False, ""

    if platform == "zhihu":
        ok = not re.search(r"/(signin|login)\b", url, re.I)
    elif platform == "weixin_mp":
        ok = "/cgi-bin/" in url
    elif platform == "xueqiu":
        # 登录是页内弹层（URL 不变）；body 同时含「发送验证码」+「登录」=未登录
        ok_url = not re.search(r"login|signin", url, re.I)
        try:
            txt = page.evaluate("document.body ? document.body.innerText.slice(0,3000) : ''")
        except Exception:
            txt = ""
        ok = ok_url and not (isinstance(txt, str) and "发送验证码" in txt and "登录" in txt)
    elif platform == "eastmoney":
        ok = not re.search(r"/(login|passport|sso)\b", url, re.I)
    elif platform == "tonghuashun":
        ok = (not re.search(r"login|upass|passport", url, re.I)) and ("adviserEnterGuide" not in url)
    elif platform == "toutiao":
        ok = ("mp.toutiao.com" in url) and (not re.search(r"login|passport", url, re.I))
    elif platform == "baijiahao":
        ok = (not re.search(r"login", url, re.I)) and ("passport" not in url)
    elif platform == "weibo":
        ok = not re.search(r"/(login|signin|passport)", url, re.I)
    else:
        ok = False
    return bool(ok), url


def run(platform: str, mode: str) -> int:
    cfg = REGISTRY[platform]
    try:
        from patchright.sync_api import sync_playwright
    except ImportError as e:
        print(f"❌ patchright 未安装: {e}")
        print("   pip install patchright && patchright install chromium")
        print(f"VAAS_DOCS_RESULT {json.dumps({'platform': platform, 'logged_in': False, 'url': ''}, ensure_ascii=False)}", flush=True)
        return 1

    profile = _profile_dir(platform)
    profile.mkdir(parents=True, exist_ok=True)
    print(f"▶ {cfg['name']}: {'打开登录窗口' if mode == 'login' else '检测登录态'}（{cfg['url']}）", flush=True)
    print(f"   profile: {profile}", flush=True)

    logged = False
    last_url = ""
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=False,
                channel=None,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 820},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(cfg["url"], wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(f"⚠️ goto 未正常完成: {type(e).__name__}: {e}", flush=True)
            time.sleep(cfg["wait"])

            if mode == "check":
                logged, last_url = _detect(platform, page)
                print(f"▶ 落地 URL: {last_url}", flush=True)
            else:
                print(f"▶ 窗口已打开：请在弹出的浏览器中完成「{cfg['name']}」登录（扫码/密码/短信），检测到后自动关窗，最多等 10 分钟", flush=True)
                start = time.time()
                while time.time() - start < 600:
                    try:
                        logged, last_url = _detect(platform, page)
                    except Exception:
                        logged = False
                    if logged:
                        time.sleep(2)  # 让登录态落定
                        break
                    # 用户手动关了浏览器 → 结束
                    try:
                        if not ctx.pages:
                            print("⚠️ 浏览器被关闭，结束", flush=True)
                            break
                    except Exception:
                        break
                    time.sleep(5)

            try:
                ctx.close()
            except Exception:
                pass
    except Exception as e:
        print(f"❌ 启动失败: {e}", flush=True)

    print(f"VAAS_DOCS_RESULT {json.dumps({'platform': platform, 'logged_in': logged, 'url': last_url}, ensure_ascii=False)}", flush=True)
    print("✅ 已登录" if logged else ("⚠️ 登录超时或未完成" if mode == "login" else "❌ 未登录"), flush=True)
    return 0 if logged else 1


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args or args[0] not in REGISTRY:
        print(f"用法: python3 {os.path.basename(__file__)} <platform> --check|--login")
        print(f"平台: {', '.join(REGISTRY.keys())}")
        return 2
    mode = "login" if "--login" in flags else "check"
    return run(args[0], mode)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
同花顺财经号发文 (patchright 版) ⚠️ 全部选择器待 probe;需财经号资质
- 入口 https://media.10jqka.com.cn/ ⚠️ 2026-08-11 probe 实测:302 跳
  t.10jqka.com.cn/newcircle/creation/adviserEnterGuide/(投顾入驻引导页)
- 未登录/无财经号资质落投顾引导页 -> logged_in 判 adviserEnterGuide;发文编辑器入口待登录后重 probe
- 非交互:login_or_wait 轮询登录;--confirm-file 发布前确认
"""

import os
import re
import sys
import argparse

from _publish_path import add_publish_path  # noqa: E402
add_publish_path()
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait,
    default_profile_dir, paste_text, fill_title, upload_images,
    click_by_text, login_or_wait, publish_and_verify,
)

# ⚠️ 2026-08-11 probe 实测:302 -> t.10jqka.com.cn/newcircle/creation/adviserEnterGuide/(投顾入驻引导)
HOME = "https://media.10jqka.com.cn/"
URL_OK = re.compile(r"(article|content|发布成功|manage)", re.I)


def logged_in(b):
    url = b.page.url
    if re.search(r"/(login|upass|passport)", url, re.I):
        return False
    # 2026-08 probe:未登录/无财经号资质会被引到投顾入驻引导页
    if "adviserEnterGuide" in url:
        return False
    return True


ap = argparse.ArgumentParser(description="同花顺财经号发文 (patchright)")
ap.add_argument("--title", required=True)
ap.add_argument("--body-file", required=True)
ap.add_argument("--tags", default="")
ap.add_argument("--cover", default="")
ap.add_argument("--summary", default="")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--auto-publish", action="store_true")
ap.add_argument("--headless", action="store_true")
ap.add_argument("--markdown", action="store_true")
ap.add_argument("--confirm-file", default="")
ap.add_argument("--preview", default="")
args = ap.parse_args()

title = args.title[:30]
with open(args.body_file, "r", encoding="utf-8") as f:
    body = f.read()
tags = [t.strip() for t in args.tags.split(",") if t.strip()][:10]
covers = [c.strip() for c in args.cover.split(",") if c.strip()]

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("tonghuashun", VAAS)

cli_log(f"""
📝 同花顺财经号发文(需财经号资质)
{'━' * 41}
标题: {title}  正文: {len(body)} 字
{'━' * 41}
""")

with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开同花顺媒体开放平台...")
    if not login_or_wait(b, HOME, lambda: logged_in(b), timeout=300, hint="登录同花顺财经号(需财经号资质)"):
        cli_log("❌ 登录超时/可能未开通财经号,退出")
        sys.exit(1)
    cli_log("✅ 已登录")

    # 进发文编辑器
    click_by_text(b, "发文章", "发文入口") or click_by_text(b, "写文章", "发文入口") or click_by_text(b, "发布内容", "发文入口")
    wait(4)

    if args.dry_run:
        b.screenshot()
        sys.exit(0)

    fill_title(b, 'input[placeholder*="标题"], #title, .article-title', title, label="标题")
    wait(0.5)

    editor_sel = '[contenteditable="true"], .ql-editor, .editor-content'
    try:
        b.page.locator(editor_sel).first.click(timeout=10000)
    except Exception as e:
        cli_log(f"⚠️ 正文编辑器未找到: {e}")
    paste_text(b, body, editor_selector=editor_sel, label="正文")
    wait(1)

    if covers:
        try:
            click_by_text(b, "上传封面", "封面入口") or click_by_text(b, "封面图", "封面入口")
            wait(1)
            upload_images(b, 'input[type="file"][accept*="image"]', covers[:1], label="封面上传")
            wait(3)
        except Exception as e:
            cli_log(f"⚠️ 封面跳过: {e}")

    for t in tags:
        try:
            if click_by_text(b, "添加标签", "加标签") or click_by_text(b, "标签", "加标签"):
                wait(1)
                b.page.keyboard.type(t, delay=30)
                wait(2)
                b.page.keyboard.press("Enter")
                wait(1)
        except Exception:
            pass

    ok, url = publish_and_verify(
        b, click_texts=["发布", "提交"], url_pattern=URL_OK,
        label="发布", timeout=20, auto_publish=args.auto_publish,
        confirm_file=args.confirm_file or None, screenshot_path=args.preview or None,
    )
    b.screenshot()
    cli_log(f"{'✅' if ok else '⚠️'} 同花顺发布 {'成功' if ok else '未确认'}: {url}")
    sys.exit(0 if ok else 1)

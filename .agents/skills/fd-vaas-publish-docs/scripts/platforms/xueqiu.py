#!/usr/bin/env python3
"""
雪球长文 (patchright 版) ⚠️ 选择器待 probe
- 富文本不吃 markdown,正文走剪贴板粘贴纯文本
- 可关联 $股票/话题;标题 ~50 字
- 非交互:login_or_wait 轮询登录;--confirm-file 发布前确认
"""

import os
import re
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait,
    default_profile_dir, paste_text, fill_title, upload_images,
    click_by_text, login_or_wait, publish_and_verify,
)

EDITOR = "https://xueqiu.com/zhuanlan/publish"
URL_OK = re.compile(r"xueqiu.com/\d+/\d+|/zhuanlan")


def logged_in(b):
    return not re.search(r"/(login|signin)", b.page.url, re.I)


ap = argparse.ArgumentParser(description="雪球长文 (patchright)")
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

title = args.title[:50]
with open(args.body_file, "r", encoding="utf-8") as f:
    body = f.read()
tags = [t.strip() for t in args.tags.split(",") if t.strip()][:10]
covers = [c.strip() for c in args.cover.split(",") if c.strip()]

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("xueqiu", VAAS)

cli_log(f"""
📝 雪球长文
{'━' * 41}
标题: {title}  正文: {len(body)} 字
{'━' * 41}
""")

with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开雪球长文编辑器...")
    if not login_or_wait(b, EDITOR, lambda: logged_in(b), timeout=300, hint="登录雪球(扫码或账密)"):
        cli_log("❌ 登录超时,退出")
        sys.exit(1)
    cli_log("✅ 已登录")

    if args.dry_run:
        b.screenshot()
        sys.exit(0)

    fill_title(b, 'input[placeholder*="标题"], #title', title, label="标题")
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
            click_by_text(b, "上传封面", "封面入口") or click_by_text(b, "封面", "封面入口")
            wait(1)
            upload_images(b, 'input[type="file"][accept*="image"]', covers[:1], label="封面上传")
            wait(3)
        except Exception as e:
            cli_log(f"⚠️ 封面跳过: {e}")

    for t in tags:
        try:
            if click_by_text(b, "添加标签", "加标签") or click_by_text(b, "话题", "加话题"):
                wait(1)
                b.page.keyboard.type(t, delay=30)
                wait(2)
                b.page.keyboard.press("Enter")
                wait(1)
        except Exception:
            pass

    ok, url = publish_and_verify(
        b, click_texts=["发布"], url_pattern=URL_OK,
        label="发布", timeout=20, auto_publish=args.auto_publish,
        confirm_file=args.confirm_file or None, screenshot_path=args.preview or None,
    )
    b.screenshot()
    cli_log(f"{'✅' if ok else '⚠️'} 雪球发布 {'成功' if ok else '未确认'}: {url}")
    sys.exit(0 if ok else 1)

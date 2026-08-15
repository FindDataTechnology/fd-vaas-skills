#!/usr/bin/env python3
"""
微博 (patchright 版) ✅ 选择器 2026-07-30 实机验证
- 入口 weibo.com 顶部 textarea[placeholder="有什么新鲜事想分享给大家？"]
- 标签 #话题# 拼正文末尾;配图可选
- 非交互:login_or_wait 轮询登录;--confirm-file 发送前确认
"""

import os
import re
import sys
import argparse

from _publish_path import add_publish_path  # noqa: E402
add_publish_path()
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait,
    default_profile_dir, paste_text, upload_images, click_by_text,
    login_or_wait, confirm_gate,
)

HOME = "https://weibo.com/"


def logged_in(b):
    return not re.search(r"/(login|signin|passport)", b.page.url, re.I)


ap = argparse.ArgumentParser(description="微博 (patchright)")
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

with open(args.body_file, "r", encoding="utf-8") as f:
    body = f.read()
tags = [t.strip() for t in args.tags.split(",") if t.strip()]
covers = [c.strip() for c in args.cover.split(",") if c.strip()]

content = body[:1000]
if tags:
    content = content.rstrip() + "\n\n" + " ".join(f"#{t}#" for t in tags)

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("weibo", VAAS)

cli_log(f"""
📝 微博(短博文)
{'━' * 41}
正文: {len(content)} 字(含话题)  配图: {len(covers)} 张
{'━' * 41}
""")

with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开微博首页...")
    if not login_or_wait(b, HOME, lambda: logged_in(b), timeout=300, hint="登录微博(扫码或账密)"):
        cli_log("❌ 登录超时,退出")
        sys.exit(1)
    cli_log("✅ 已登录")

    if args.dry_run:
        b.screenshot()
        sys.exit(0)

    try:
        b.page.locator('textarea[placeholder="有什么新鲜事想分享给大家？"]').first.click(timeout=10000)
        wait(0.5)
    except Exception as e:
        cli_log(f"⚠️ 微博输入框未找到: {e}")
    paste_text(b, content, editor_selector='textarea[placeholder="有什么新鲜事想分享给大家？"]', label="正文")
    wait(1)

    if covers:
        try:
            click_by_text(b, "图片", "点图片按钮")
            wait(1)
            upload_images(b, 'input[type="file"][accept*="image"]', covers, label="配图上传")
            wait(3)
        except Exception as e:
            cli_log(f"⚠️ 配图跳过: {e}")

    if not confirm_gate(b, args.confirm_file, screenshot_path=args.preview, hint="发送微博"):
        cli_log("⚠️ 未确认,退出")
        sys.exit(1)
    if not (click_by_text(b, "发送", "发送") or click_by_text(b, "发微博", "发送")):
        cli_log("⚠️ 未找到发送按钮,请手动点")
    wait(5)
    b.screenshot()
    cli_log("✅ 微博发布流程完成,请在微博确认")
    sys.exit(0)

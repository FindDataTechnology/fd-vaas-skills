#!/usr/bin/env python3
"""
今日头条(头条号)发文 (patchright 版) ✅ 选择器 2026-07-30 实机验证
- 标题 textarea[placeholder*="请输入文章标题"];正文 .ProseMirror;「预览并发布」
- 预览页最终发布由用户手动确认
- 非交互:login_or_wait 轮询登录;--confirm-file 预览后放行
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait,
    default_profile_dir, paste_text, upload_images, click_by_text,
    login_or_wait, confirm_gate,
)

EDITOR = "https://mp.toutiao.com/profile_v4/graphic/publish"


def logged_in(b):
    return "login" not in b.page.url and "passport" not in b.page.url


ap = argparse.ArgumentParser(description="今日头条发文 (patchright)")
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
covers = [c.strip() for c in args.cover.split(",") if c.strip()]

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("toutiao", VAAS)

cli_log(f"""
📝 今日头条发文
{'━' * 41}
标题: {title}  正文: {len(body)} 字
{'━' * 41}
""")

with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开头条号图文编辑器...")
    if not login_or_wait(b, EDITOR, lambda: logged_in(b), timeout=300, hint="登录今日头条(扫码或账密)"):
        cli_log("❌ 登录超时,退出")
        sys.exit(1)
    cli_log("✅ 已登录")

    if args.dry_run:
        b.screenshot()
        sys.exit(0)

    # 标题(等编辑器加载完,30s)
    try:
        b.page.wait_for_selector('textarea[placeholder*="请输入文章标题"]', timeout=30000)
        b.page.locator('textarea[placeholder*="请输入文章标题"]').first.click(timeout=10000)
        wait(0.3)
    except Exception as e:
        cli_log(f"⚠️ 标题框未找到: {e}")
    paste_text(b, title, editor_selector='textarea[placeholder*="请输入文章标题"]', label="标题")
    wait(0.5)

    # 正文
    try:
        b.page.locator(".ProseMirror").first.click(timeout=10000)
        wait(0.3)
    except Exception as e:
        cli_log(f"⚠️ 正文编辑器未找到: {e}")
    paste_text(b, body, editor_selector=".ProseMirror", label="正文")
    wait(2)

    if covers:
        try:
            click_by_text(b, "上传封面", "封面入口") or click_by_text(b, "封面", "封面入口")
            wait(1)
            upload_images(b, 'input[type="file"][accept*="image"]', covers[:1], label="封面上传")
            wait(3)
        except Exception as e:
            cli_log(f"⚠️ 封面跳过: {e}")

    # 预览并发布(放行后点;预览页最终发布手动)
    if not confirm_gate(b, args.confirm_file, screenshot_path=args.preview, hint="预览并发布头条"):
        cli_log("⚠️ 未确认,退出")
        sys.exit(1)
    if not click_by_text(b, "预览并发布", "预览并发布"):
        click_by_text(b, "发布", "发布")
    wait(3)
    b.screenshot()
    if args.auto_publish:
        click_by_text(b, "发布", "最终发布")
        wait(5)
    cli_log("✅ 头条已到预览页,请在头条号后台确认/手动发布")
    sys.exit(0)

#!/usr/bin/env python3
"""
百家号发文 (patchright 版) ✅ 选择器 2026-07-30 实机验证
- 标题 = 第 1 个 contenteditable;正文 = 第 2 个 contenteditable
- 封面必填;默认存草稿
- 非交互:login_or_wait 轮询登录;--confirm-file 存草稿前确认
"""

import os
import sys
import argparse

from _publish_path import add_publish_path  # noqa: E402
add_publish_path()
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait,
    default_profile_dir, paste_text, upload_images, click_by_text,
    login_or_wait, confirm_gate,
)

EDITOR = "https://baijiahao.baidu.com/builder/rc/edit"


def logged_in(b):
    return "login" not in b.page.url and "passport" not in b.page.url


ap = argparse.ArgumentParser(description="百家号发文 (patchright)")
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

title = args.title[:40]
with open(args.body_file, "r", encoding="utf-8") as f:
    body = f.read()
covers = [c.strip() for c in args.cover.split(",") if c.strip()]

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("baijiahao", VAAS)

cli_log(f"""
📝 百家号发文(默认存草稿)
{'━' * 41}
标题: {title}  正文: {len(body)} 字
{'━' * 41}
""")

with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开百家号编辑器...")
    if not login_or_wait(b, EDITOR, lambda: logged_in(b), timeout=300, hint="登录百家号(扫码或账密)"):
        cli_log("❌ 登录超时,退出")
        sys.exit(1)
    cli_log("✅ 已登录")

    if args.dry_run:
        b.screenshot()
        sys.exit(0)

    # 标题 = 第 1 个 contenteditable
    try:
        b.eval('document.querySelectorAll(\'[contenteditable="true"]\')[0]?.focus()')
        wait(0.3)
    except Exception as e:
        cli_log(f"⚠️ 标题 contenteditable 未找到: {e}")
    paste_text(b, title, editor_selector=None, label="标题")
    wait(0.5)

    # 正文 = 第 2 个 contenteditable
    try:
        b.eval("""
        () => { const es = document.querySelectorAll('[contenteditable="true"]'); if (es.length > 1) es[1].focus(); }
        """)
        wait(0.3)
    except Exception as e:
        cli_log(f"⚠️ 正文 contenteditable 未找到: {e}")
    paste_text(b, body, editor_selector=None, label="正文")
    wait(2)

    if covers:
        try:
            click_by_text(b, "上传封面", "封面入口") or click_by_text(b, "封面", "封面入口")
            wait(1)
            upload_images(b, 'input[type="file"][accept*="image"]', covers[:1], label="封面上传")
            wait(3)
        except Exception as e:
            cli_log(f"⚠️ 封面上传跳过(百家号封面必填,请手动补): {e}")

    if not confirm_gate(b, args.confirm_file, screenshot_path=args.preview, hint="存草稿百家号"):
        cli_log("⚠️ 未确认,退出")
        sys.exit(1)
    if not click_by_text(b, "存草稿", "存草稿"):
        cli_log("⚠️ 未找到存草稿按钮,请手动点")
    wait(3)
    b.screenshot()
    cli_log("✅ 百家号已存草稿,请在后台确认分类后手动发布")
    sys.exit(0)

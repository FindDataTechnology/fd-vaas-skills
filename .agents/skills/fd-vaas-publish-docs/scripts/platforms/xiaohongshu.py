#!/usr/bin/env python3
"""
小红书图文笔记 (patchright 版) ✅ 选择器 2026-07-29 实机确认
- 必须至少 1 张图(封面即首图);标题 ≤20 字;话题 #话题# 放正文末尾
- 图片 .upload-input;标题 input[placeholder*="填写标题"];正文 .tiptap.ProseMirror
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
    click_by_text, login_or_wait, confirm_gate,
)

EDITOR = "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image"
URL_OK = re.compile(r"/publish/success\?")

ap = argparse.ArgumentParser(description="小红书图文笔记 (patchright)")
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

title = args.title[:20]
with open(args.body_file, "r", encoding="utf-8") as f:
    body = f.read()
tags = [t.strip() for t in args.tags.split(",") if t.strip()][:10]
covers = [c.strip() for c in args.cover.split(",") if c.strip()]

if tags:
    body = body.rstrip() + "\n\n" + " ".join(f"#{t}#" for t in tags)

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("xiaohongshu", VAAS)

cli_log(f"""
📝 小红书图文笔记
{'━' * 41}
标题: {title}  正文: {len(body)} 字  图片: {len(covers)} 张
{'━' * 41}
""")

with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开小红书图文发布页...")
    if not login_or_wait(b, EDITOR, lambda: "/login" not in b.page.url, timeout=300, hint="用小红书 APP 扫码登录"):
        cli_log("❌ 登录超时,退出")
        sys.exit(1)
    cli_log("✅ 已登录")

    if args.dry_run:
        b.screenshot()
        sys.exit(0)

    # 先上传图片(至少 1 张),上传后标题框才出现
    if covers:
        upload_images(b, '.upload-input, input[type="file"][accept*="image"]', covers, label="图片上传")
        wait(4)
    else:
        cli_log("❌ 小红书必须至少 1 张图,退出")
        sys.exit(1)

    fill_title(b, 'input[placeholder*="填写标题"]', title, label="标题")
    wait(0.5)

    try:
        b.page.locator(".tiptap.ProseMirror").first.click(timeout=10000)
        wait(0.3)
    except Exception as e:
        cli_log(f"⚠️ 正文编辑器未找到: {e}")
    paste_text(b, body, editor_selector=".tiptap.ProseMirror", label="正文")
    wait(1)

    if not confirm_gate(b, args.confirm_file, screenshot_path=args.preview, hint="发布小红书"):
        cli_log("⚠️ 未确认,退出")
        sys.exit(1)
    ok = click_by_text(b, "发布", "发布")
    url = ""
    for _ in range(30):
        wait(1)
        url = b.page.url
        if URL_OK.search(url):
            cli_log(f"✅ 小红书发布成功: {url}")
            break
    else:
        cli_log(f"⚠️ 小红书发布未确认: {b.page.url}")
    b.screenshot()
    sys.exit(0 if URL_OK.search(url or "") else 1)

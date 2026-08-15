#!/usr/bin/env python3
"""
知乎专栏发文 (patchright 版)

选择器 ✅ 2026-07-29 实机验证:
  标题  textarea[placeholder*="请输入标题"]
  正文  .public-DraftEditor-content (Draft.js)
  发布  button 文本含「发布」
  封面  input[type="file"][accept*="image"](先点「上传封面」)

正文按真实段落逐段输入,每段后双回车,阻断知乎自动编号识别。
CLI 一致: --title --body-file --tags --cover --summary --dry-run --auto-publish --headless --confirm-file --preview
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
    click_by_text, confirm_gate,
)

EDITOR = "https://zhuanlan.zhihu.com/write"


def logged_in(b):
    # 知乎登录后设 z_c0 cookie;URL 不可靠(扫码后停在 /signin 不自动跳转)
    try:
        cookies = b.context.cookies("https://www.zhihu.com")
        if any(c["name"] == "z_c0" and c.get("value") for c in cookies):
            return True
    except Exception:
        pass
    return not re.search(r"/(signin|login)\b", b.page.url, re.I) and "/write" in b.page.url


ap = argparse.ArgumentParser(description="知乎专栏发文 (patchright)")
ap.add_argument("--title", required=True)
ap.add_argument("--body-file", required=True)
ap.add_argument("--tags", default="")
ap.add_argument("--cover", default="")
ap.add_argument("--summary", default="")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--auto-publish", action="store_true")
ap.add_argument("--headless", action="store_true")
ap.add_argument("--confirm-file", default="")
ap.add_argument("--preview", default="")
args = ap.parse_args()

title = args.title
with open(args.body_file, "r", encoding="utf-8") as f:
    body = f.read()
tags = [t.strip() for t in args.tags.split(",") if t.strip()][:5]
covers = [c.strip() for c in args.cover.split(",") if c.strip()]

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("zhihu", VAAS)

cli_log(f"""
📝 知乎专栏发布
{'━' * 41}
标题: {title}
正文: {len(body)} 字
标签: {','.join(tags) or '(无)'}
封面: {covers[0] if covers else '(无)'}
{'━' * 41}
""")

with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开知乎专栏编辑器...")
    if not logged_in(b):
        b.goto("https://www.zhihu.com/signin", then_wait=3)
        if not confirm_gate(b, args.confirm_file or "/tmp/vaas-doc-zhihu-login.go",
                           hint="扫码登录知乎后回车继续"):
            cli_log("❌ 登录超时,退出")
            sys.exit(1)
    b.goto(EDITOR, then_wait=4)
    cli_log("✅ 已登录")

    if args.dry_run:
        b.screenshot(args.preview if args.preview else None)
        cli_log("🔍 dry-run:页面已打开")
        sys.exit(0)

    # 标题
    fill_title(b, 'textarea[placeholder*="请输入标题"]', title, label="标题")
    wait(0.5)

    # 正文(按真实段落逐段输入,每段后双回车,阻断知乎自动编号识别)
    try:
        b.page.locator(".public-DraftEditor-content").first.click(timeout=10000)
        wait(0.3)
        b.page.keyboard.press("Meta+a")
        b.page.keyboard.press("Delete")
        wait(0.3)
        # 按换行符分割成真实段落,每段输入后按两次回车(段间空行),知乎就不会连续编号
        paragraphs = [p.strip() for p in body.split('\n') if p.strip()]
        for i, para in enumerate(paragraphs):
            b.page.keyboard.type(para, delay=1)
            b.page.keyboard.press("Enter")
            b.page.keyboard.press("Enter")
            wait(0.1)
        wait(1)
        cli_log(f"✅  正文: 已分段输入({len(body)} 字, {len(paragraphs)} 段)")
    except Exception as e:
        cli_log(f"⚠️  正文输入失败: {e}")

    cli_log(f"⚠️  请手动操作:")
    cli_log(f"     1. 上传封面: {covers[0] if covers else '(无)'}")
    cli_log(f"     2. 添加话题: {', '.join(tags)}")
    cli_log(f"     3. 点击发布按钮")

    # 发布确认门
    if not confirm_gate(b, args.confirm_file or "/tmp/vaas-doc-zhihu.go",
                        screenshot_path=args.preview, hint="发布知乎"):
        cli_log("⚠️  未确认发布,退出")
        sys.exit(1)

    # 点发布
    ok = click_by_text(b, "发布", "点击发布")
    if not ok:
        cli_log("⚠️  未找到发布按钮,请手动点击")
    wait(5)
    url = b.page.url
    success = "/p/" in url and "edit" not in url.lower()
    cli_log(f"{'✅' if success else '⚠️'} 知乎发布 {'成功' if success else '未确认'}: {url}")
    b.screenshot()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
东方财富号发长文 (patchright 版) ✅ 选择器 2026-07-29 实机验证(需开通财经号)
- SPA(hash 路由),goto 后 wait 8s 等渲染
- 标题 input[placeholder*="标题(1-64字)"];正文 .ProseMirror.cfh_editor_area
- 需财经号资质,没开通进不了编辑器
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
    click_by_text, readback, login_or_wait, publish_and_verify,
)

EDITOR = "https://mp.eastmoney.com/collect/pc_article/index.html#/"
URL_OK = re.compile(r"(article|collect|发布成功|manage)", re.I)


def logged_in(b):
    if re.search(r"/(login|passport|sso)", b.page.url, re.I):
        return False
    return True


ap = argparse.ArgumentParser(description="东方财富号发长文 (patchright)")
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
profile = default_profile_dir("eastmoney", VAAS)

cli_log(f"""
📝 东方财富号长文(需财经号资质)
{'━' * 41}
标题: {title}  正文: {len(body)} 字
{'━' * 41}
""")

# eastmoney 是 SPA,login_or_wait 默认 then_wait=4 不够;手动控制
with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开东方财富号编辑器(SPA,等渲染)...")
    b.goto(EDITOR, then_wait=8)
    if not logged_in(b):
        cli_log("⚠️ 未登录东方财富号(需财经号资质),请在浏览器扫码登录")
        from browser_utils import wait_until
        ok = wait_until(lambda: logged_in(b), timeout=300, poll=3, hint="登录东方财富号(需财经号)")
        if ok:
            b.goto(EDITOR, then_wait=8)
        if not logged_in(b):
            cli_log("❌ 仍未登录/可能未开通财经号,退出")
            sys.exit(1)
    cli_log("✅ 已登录")

    if args.dry_run:
        b.screenshot()
        sys.exit(0)

    title_sel = 'input[placeholder*="标题"], #title, .article-title input'
    if not fill_title(b, title_sel, title, label="标题"):
        cli_log("❌ 标题框未出现,可能未开通财经号或改版,请 probe")
    wait(0.5)

    editor_sel = ".ProseMirror.cfh_editor_area, [contenteditable='true'], .ql-editor"
    try:
        b.page.locator(editor_sel).first.click(timeout=10000)
    except Exception as e:
        cli_log(f"⚠️ 正文编辑器未找到: {e}")
    paste_text(b, body, editor_selector=editor_sel, label="正文")
    wait(1)
    readback(b, editor_sel, label="正文读回")

    if covers:
        try:
            b.eval("window.scrollTo(0, document.body.scrollHeight)")
            wait(0.5)
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
    cli_log(f"{'✅' if ok else '⚠️'} 东方财富号发布 {'成功' if ok else '未确认'}: {url}")
    sys.exit(0 if ok else 1)

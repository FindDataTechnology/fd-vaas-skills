#!/usr/bin/env python3
"""
微信公众号图文 (patchright 版) ⚠️ 选择器待 probe
- 编辑器不吃 markdown,正文走剪贴板粘贴纯文本(body-file 已 strip)
- 封面必填 900×500、摘要必填;默认存草稿不群发
- 正文可能在 iframe(ueditor),有 iframe fallback
- 非交互:login_or_wait 轮询登录;--confirm-file 发布前确认
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait,
    default_profile_dir, paste_text, fill_title, upload_images,
    click_by_text, fill_input, login_or_wait, confirm_gate, wait_for_file,
)

HOME = "https://mp.weixin.qq.com/"


def logged_in(b):
    # URL 含 /cgi-bin/ 或页面出现「新的创作」(登录后首页才有)都算已登录
    if "/cgi-bin/" in b.page.url:
        return True
    try:
        return "新的创作" in b.page.locator("body").inner_text(timeout=2000)
    except Exception:
        return False

ap = argparse.ArgumentParser(description="微信公众号图文 (patchright)")
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

title = args.title[:64]
with open(args.body_file, "r", encoding="utf-8") as f:
    body = f.read()
summary = args.summary or body[:120]
covers = [c.strip() for c in args.cover.split(",") if c.strip()]

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("weixin", VAAS)

cli_log(f"""
📝 微信公众号图文(默认存草稿)
{'━' * 41}
标题: {title}  摘要: {summary[:40]}
正文: {len(body)} 字  封面: {covers[0] if covers else '(无)'}
{'━' * 41}
""")

with Browser(profile, headless=args.headless) as b:
    cli_log("🌐 打开公众号后台...")
    if not login_or_wait(b, HOME, lambda: logged_in(b), timeout=120, hint="用微信扫码登录公众号后台"):
        cli_log("❌ 登录超时,退出")
        sys.exit(1)
    cli_log("✅ 已登录后台")

    click_by_text(b, "新的创作", "新建图文入口")
    wait(1.5)
    click_by_text(b, "文章", "新建图文")
    wait(5)

    if args.dry_run:
        b.screenshot()
        cli_log("🔍 dry-run 完成")
        sys.exit(0)

    # 标题
    fill_title(b, "#title", title, label="标题")
    wait(0.5)

    # 正文:主文档 contenteditable,失败切 iframe
    editor_sel = 'body[contenteditable="true"], .edui-body-container, [contenteditable="true"]'
    try:
        b.page.locator(editor_sel).first.click(timeout=8000)
    except Exception:
        cli_log("⚠️ 主文档无编辑器,尝试 iframe...")
        try:
            b.eval("""
            () => {
              const f = document.querySelector('iframe');
              const d = f && f.contentDocument;
              const e = d && (d.querySelector('[contenteditable="true"],.edui-body-container,body'));
              if (e) e.focus();
              return e ? 'iframe-focused' : 'no-iframe-editor';
            }
            """)
        except Exception as e:
            cli_log(f"⚠️ iframe 聚焦失败: {e}")
    paste_text(b, body, editor_selector=editor_sel, label="正文")
    wait(1)

    # 封面(必填)
    if covers:
        try:
            b.eval("window.scrollTo(0, document.body.scrollHeight)")
            wait(0.5)
            click_by_text(b, "从正文选择", "封面入口") or click_by_text(b, "上传", "封面入口")
            wait(1)
            upload_images(b, 'input[type="file"][accept*="image"]', covers[:1], label="封面上传")
            wait(3)
            click_by_text(b, "完成", "封面完成")
            wait(1)
        except Exception as e:
            cli_log(f"⚠️ 封面设置跳过: {e}")

    # 摘要(必填)
    fill_input(b, 'textarea[placeholder*="摘要"], #digest', summary, label="摘要")

    # 存草稿(默认不群发)
    if not confirm_gate(b, args.confirm_file, screenshot_path=args.preview, hint="存草稿"):
        cli_log("⚠️ 未确认,退出")
        sys.exit(1)
    if not (click_by_text(b, "保存为草稿", "存草稿") or click_by_text(b, "保存", "存草稿")):
        cli_log("⚠️ 未找到保存按钮,请手动点「保存为草稿」")
        if args.confirm_file:
            cli_log(f"⏸️ 手动点完后 touch {args.confirm_file}")
            wait_for_file(args.confirm_file, timeout=300, hint="等待手动存草稿")
    wait(3)
    b.screenshot()
    cli_log("✅ 已存草稿,群发需在后台手动操作")
    sys.exit(0)

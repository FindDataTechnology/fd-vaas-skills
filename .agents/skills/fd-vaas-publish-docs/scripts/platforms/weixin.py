#!/usr/bin/env python3
"""
微信公众号图文 (patchright 版) ✅ 选择器已实测(2026-07-30)
- 编辑器入口:appmsg URL 直拼(token 从 home URL 取),不走「新的创作」下拉(点不动)
- 标题 #title 是 hidden textarea -> js 赋值;正文 .ProseMirror -> HTML 粘贴保换行
- 摘要 #js_description;封面必填 900×500;默认存草稿不群发
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
    default_profile_dir, paste_html, upload_images,
    click_by_text, fill_hidden, login_or_wait, confirm_gate, wait_for_file,
)

HOME = "https://mp.weixin.qq.com/"
# type=77 = 图文消息;token 从登录后 home 页 URL 取
APPMSG = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&lang=zh_CN&token={token}"


def logged_in(b):
    # URL 含 /cgi-bin/ 或页面出现「新的创作」(登录后首页才有)都算已登录
    if "/cgi-bin/" in b.page.url:
        return True
    try:
        return "新的创作" in b.page.locator("body").inner_text(timeout=2000)
    except Exception:
        return False


def open_editor(b):
    """从 home 页 URL 取 token,直拼 appmsg 编辑器 URL 打开新图文。"""
    m = re.search(r"token=(\d+)", b.page.url)
    if not m:
        # 兜底:回 home 再取一次
        b.goto(HOME, then_wait=4)
        m = re.search(r"token=(\d+)", b.page.url)
    if not m:
        cli_log("❌ 取不到 token(未登录?),无法拼编辑器 URL")
        return False
    url = APPMSG.format(token=m.group(1))
    cli_log(f"📄 打开图文编辑器: {url[:80]}...")
    b.goto(url, then_wait=6)
    return True


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

    if not open_editor(b):
        sys.exit(1)

    if args.dry_run:
        b.screenshot()
        cli_log("🔍 dry-run 完成")
        sys.exit(0)

    # 标题:#title 是 hidden textarea,locator.fill 会超时,用 js 赋值 + input 事件
    fill_hidden(b, "#title", title, label="标题")
    wait(0.5)

    # 正文:.ProseMirror(页面上有 2 个 contenteditable,第 1 个是正文)
    # 纯文本粘贴丢换行 -> 按行转 <p> 走 text/html 剪贴板
    paste_html(b, body, ".ProseMirror", label="正文")
    wait(1)

    # 封面(必填):先点「选择封面」区域让 hidden file input 可用
    if covers:
        try:
            b.eval("window.scrollTo(0, document.body.scrollHeight)")
            wait(0.5)
            click_by_text(b, ["选择封面", "从正文选择", "上传"], "封面入口")
            wait(1)
            upload_images(b, 'input[type="file"][accept*="image"]', covers[:1], label="封面上传")
            wait(3)
            click_by_text(b, "完成", "封面完成")
            wait(1)
        except Exception as e:
            cli_log(f"⚠️ 封面设置跳过: {e}")

    # 摘要(必填):#js_description(不是 #digest)
    if not fill_hidden(b, "#js_description", summary, label="摘要"):
        fill_hidden(b, 'textarea[placeholder*="摘要"]', summary, label="摘要(兜底)")

    # 存草稿(默认不群发)
    if not confirm_gate(b, args.confirm_file, screenshot_path=args.preview, hint="存草稿"):
        cli_log("⚠️ 未确认,退出")
        sys.exit(1)
    if not click_by_text(b, "保存为草稿", "存草稿"):
        cli_log("⚠️ 未找到保存按钮,请手动点「保存为草稿」")
        if args.confirm_file:
            cli_log(f"⏸️ 手动点完后 touch {args.confirm_file}")
            wait_for_file(args.confirm_file, timeout=300, hint="等待手动存草稿")
    wait(3)
    b.screenshot()
    cli_log("✅ 已存草稿,群发需在后台手动操作")
    sys.exit(0)

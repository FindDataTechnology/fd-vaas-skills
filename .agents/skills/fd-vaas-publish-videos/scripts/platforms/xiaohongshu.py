#!/usr/bin/env python3
"""
小红书视频上传 CLI (patchright 版)

从 xiaohongshu.mjs port。CLI 参数与 .mjs 一致。
注意：标题 ≤ 20 字，话题 ≤ 10 个。本脚本自动点「发布」并按 URL 验证（同 .mjs）。
"""

import os
import sys
import re
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait, upload_file, fill_input, click_selector,
    wait_for_selector, press_key, type_text, page_url, screenshot_confirm,
    default_profile_dir,
)

ap = argparse.ArgumentParser(description="小红书视频上传 (patchright)")
ap.add_argument("--file", required=True)
ap.add_argument("--title", required=True)
ap.add_argument("--desc", default="")
ap.add_argument("--tags", default="")
ap.add_argument("--cover", default="")
ap.add_argument("--dry-run", action="store_true")
args, _unknown = ap.parse_known_args()

file = args.file
title = args.title
desc = args.desc
tags = [t.strip() for t in args.tags.split(",") if t.strip()]
cover = args.cover
dry_run = args.dry_run

if not os.path.exists(file):
    print(f"❌ 视频文件不存在: {file}")
    sys.exit(1)

abs_file = os.path.abspath(file)
title_sliced = title[:20]

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("xiaohongshu", VAAS)

URL = "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video"
VIDEO_INPUT = "div[class^='upload-content'] input.upload-input"
TITLE_INPUT = 'input[placeholder*="填写标题"]'

cli_log(f"""
📱 小红书发布
{'━' * 41}
视频:   {abs_file}
标题:   {title_sliced}
描述:   {desc or '(无)'}
标签:   {', '.join(tags) or '(无)'}
{'━' * 41}
""")

# 等待上传完成的页内判定（从 .mjs 原样搬）
JS_UPLOAD_DONE = """
(() => {
  const p = document.querySelector('input.upload-input');
  if (p) {
    const n = p.parentElement && p.parentElement.querySelector('.preview-new');
    if (n && /上传成功|分辨率|重新上传|编辑封面|已上传|已选择|100%/.test(n.innerText)) return true;
  }
  return !!document.querySelector('input[placeholder*="填写标题"]');
})()
"""

with Browser(profile, headless=False) as b:
    cli_log("🌐 打开小红书发布页...")
    b.goto(URL, then_wait=3)

    # 检查登录（URL 含 /login 即未登录）
    if "/login" in page_url(b):
        cli_log("⚠️ 需要登录小红书，请在浏览器窗口扫码登录")
        for _ in range(60):
            wait(3)
            if "/login" not in page_url(b):
                cli_log("✅ 登录成功！")
                break
        else:
            cli_log("⚠️ 登录超时，后续可能需要手动操作")

    if dry_run:
        cli_log("🔍 dry-run 模式")
        b.screenshot()
        from browser_utils import handoff
        handoff("dry-run: 页面已打开")
        sys.exit(0)

    # 上传视频
    cli_log("📤 上传视频...")
    upload_file(b, VIDEO_INPUT, abs_file, label="上传视频")
    cli_log("等待上传完成...")
    for _ in range(90):
        try:
            if b.eval(JS_UPLOAD_DONE):
                break
        except Exception:
            pass
        wait(2)
    cli_log("✅ 视频上传完成")

    # 填标题（≤ 20 字）
    cli_log("📝 填写标题...")
    wait_for_selector(b, TITLE_INPUT, timeout=60)
    fill_input(b, TITLE_INPUT, title_sliced, "填标题")
    wait(1)

    # 填正文
    if desc:
        cli_log("📝 填写正文...")
        try:
            click_selector(b, 'p[data-placeholder*="输入正文描述"]', "定位正文框")
            press_key(b, "Backspace")
            press_key(b, "Control+a")
            press_key(b, "Delete")
            type_text(b, desc)
            press_key(b, "Enter")
            wait(1)
        except Exception as e:
            cli_log(f"⚠️ 正文填写失败，请手动: {e}")

    # 添加话题（≤ 10 个）
    if tags:
        cli_log("🏷️ 添加话题...")
        for t in tags[:10]:
            type_text(b, "#" + t)
            try:
                wait_for_selector(b, "#creator-editor-topic-container", timeout=6)
                wait_for_selector(b, "#creator-editor-topic-container .item", timeout=4)
                click_selector(b, "#creator-editor-topic-container .item", f"选话题 #{t}")
            except Exception:
                # 没出现候选，回退删掉这次输入
                for _ in range(len("#" + t)):
                    press_key(b, "Backspace")
            wait(0.5)

    # 发布
    cli_log("🚀 点击发布...")
    click_selector(b, 'xpath=//button[normalize-space(text())="发布"]', "点发布")
    wait(3)

    # 验证发布
    for _ in range(30):
        if "/publish/success?" in page_url(b):
            cli_log("✅ 发布成功！")
            break
        wait(1)
    else:
        cli_log("⚠️ 未检测到发布成功页，请手动确认")

    b.screenshot()

#!/usr/bin/env python3
"""
B站视频上传 CLI (patchright 版)

从 bilibili.mjs port。CLI 参数与 .mjs 一致（含 --tid 分区）。
⚠️ 技术要点：
- B站用 micro-app 微前端，页面内容在 micro-app[name=video-up].shadowRoot 内
- Playwright/patchright 的 locator 默认穿透 **open** shadow DOM，所以 set_input_files
  多数情况能直接命中 shadow 内的 file input（比 .mjs 的 uploadFile 更可靠，CDP 回退一般用不上）
- 标题/简介/标签/封面/发布都通过 evaluate 进 shadowRoot 操作（JS 从 .mjs 原样搬）
本脚本自动点「发布」并按 URL 验证（同 .mjs）。
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait, upload_file, page_url, default_profile_dir,
)

ap = argparse.ArgumentParser(description="B站视频上传 (patchright)")
ap.add_argument("--file", required=True)
ap.add_argument("--title", required=True)
ap.add_argument("--desc", default="")
ap.add_argument("--tags", default="")
ap.add_argument("--cover", default="")
ap.add_argument("--tid", default="124")
ap.add_argument("--dry-run", action="store_true")
args, _unknown = ap.parse_known_args()

file = args.file
title = args.title
desc = args.desc
tags = [t.strip() for t in args.tags.split(",") if t.strip()]
cover = args.cover
tid = args.tid
dry_run = args.dry_run

if not os.path.exists(file):
    print(f"❌ 视频文件不存在: {file}")
    sys.exit(1)

abs_file = os.path.abspath(file)
abs_cover = os.path.abspath(cover) if (cover and os.path.exists(cover)) else ""

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("bilibili", VAAS)

MICRO_APP = "micro-app[name=video-up]"

cli_log(f"""
📺 B站发布
{'━' * 41}
视频:   {abs_file}
标题:   {title}
简介:   {desc or '(无)'}
标签:   {', '.join(tags) or '(无)'}
分区:   {tid}
封面:   {abs_cover or '(默认)'}
{'━' * 41}
""")

JS_MICRO_READY = f"!!document.querySelector('{MICRO_APP}')?.shadowRoot"

JS_LOGIN_CHECK = "document.body.innerText.slice(0, 500).includes('扫码登录') || document.body.innerText.slice(0, 500).includes('登录')"

JS_SET_TITLE = """
([sel, val]) => {
  // ✅ B站表单元素在主文档里直接可访问，不需要 shadowRoot
  const input = document.querySelector('input[placeholder*="标题"]')
    || document.querySelector('input[placeholder*="标题"]')
    || document.querySelector('input.bili-upload-input')
    || document.querySelector('input[type="text"]');
  if (input) {
    input.focus();
    input.value = val;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return 'title set';
  }
  return 'no title input';
}
"""

JS_SET_DESC = """
([sel, val]) => {
  // ✅ 直接从主文档找 textarea
  const textarea = document.querySelector('textarea');
  if (textarea) {
    textarea.focus();
    textarea.value = val;
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    return 'desc set';
  }
  return 'no textarea';
}
"""

JS_ADD_TAG = """
([sel, tag]) => {
  // ✅ 直接从主文档找标签输入框
  const tagInput = document.querySelector('input[placeholder*="标签"]');
  if (tagInput) {
    tagInput.focus();
    tagInput.value = tag;
    tagInput.dispatchEvent(new Event('input', { bubbles: true }));
    tagInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    return 'tag: ' + tag;
  }
  return 'no tag input';
}
"""

JS_CLICK_COVER_AREA = """
(sel) => {
  // ✅ 直接从主文档找封面上传区
  const coverArea = document.querySelector('[class*="cover"] [class*="upload"], [class*="cover-upload"], [class*="cover"]');
  if (coverArea) { coverArea.click(); return 'clicked'; }
  return 'no cover area';
}
"""

JS_CLICK_SUBMIT = """
(sel) => {
  // ✅ 直接从主文档找发布按钮
  const btn = document.querySelector('button.submit, [class*="submit"], button.btn-publish');
  if (btn) { btn.click(); return 'clicked submit'; }
  // 退而求其次：按文本找
  const btns = document.querySelectorAll('button');
  for (const b of btns) {
    const t = (b.textContent || '').trim();
    if (t === '发布' || t === '立即发布') { b.click(); return 'clicked: ' + t; }
  }
  return 'no submit btn';
}
"""

with Browser(profile, headless=False) as b:
    cli_log("🌐 打开 B站创作中心上传页...")
    b.goto("https://member.bilibili.com/v2#/upload/video/frame", then_wait=5)

    # 等待 micro-app 加载
    cli_log("⏳ 等待 micro-app 微前端加载...")
    for _ in range(15):
        try:
            if b.eval(JS_MICRO_READY):
                cli_log("✅ micro-app 已加载")
                break
        except Exception:
            pass
        wait(2)

    # 检查登录
    try:
        if b.eval(JS_LOGIN_CHECK):
            cli_log("⚠️ 需要登录 B站，请在浏览器窗口扫码登录")
            for _ in range(60):
                wait(3)
                try:
                    if b.eval(JS_MICRO_READY):
                        cli_log("✅ 登录成功！")
                        break
                except Exception:
                    pass
            else:
                cli_log("⚠️ 登录超时")
    except Exception:
        pass

    if dry_run:
        cli_log("🔍 dry-run 模式")
        b.screenshot()
        from browser_utils import handoff
        handoff("dry-run: 页面已打开")
        sys.exit(0)

    # 上传视频（patchright locator 穿透 open shadow DOM）
    cli_log("📤 上传视频...")
    # ✅ 精确匹配：只选 accept 里有视频格式的 input，避免匹配到 txt 上传框
    video_input = 'input[type="file"][accept*="mp4"], input[type="file"][accept*="mp4"]'
    if not upload_file(b, video_input, abs_file, label="上传视频"):
        cli_log("⚠️ 自动上传失败，请在浏览器中手动上传视频文件")
    cli_log("等待上传完成...")
    # ✅ 等待标题输入框出现（最多 3 分钟），表单出现才说明上传转码完成
    cli_log("⏳ 等待表单出现（上传+转码中）...")
    form_ready = False
    for i in range(36):
        wait(5)
        try:
            r = b.eval('!!document.querySelector("input[placeholder*=\\"标题\\"], input[placeholder*=\\"标题\\"]")')
            if r:
                cli_log(f"✅ 表单已出现！(约 {i*5} 秒)")
                form_ready = True
                break
        except Exception:
            pass
        if i % 6 == 0:
            cli_log(f"⏳ 仍在等待上传完成... ({i*5}秒)")
    if not form_ready:
        cli_log("⚠️ 表单未出现，继续尝试填写...")

    # 填标题
    cli_log("📝 填写标题...")
    try:
        cli_log(b.eval(JS_SET_TITLE, [MICRO_APP, title]))
    except Exception as e:
        cli_log(f"⚠️ 标题填写失败: {e}")
    wait(1)

    # 填简介
    if desc:
        cli_log("📝 填写简介...")
        try:
            cli_log(b.eval(JS_SET_DESC, [MICRO_APP, desc]))
        except Exception as e:
            cli_log(f"⚠️ 简介填写失败: {e}")
        wait(1)

    # 添加标签
    if tags:
        cli_log("🏷️ 添加标签...")
        for tag in tags:
            try:
                cli_log(b.eval(JS_ADD_TAG, [MICRO_APP, tag]))
            except Exception as e:
                cli_log(f"⚠️ 标签 {tag} 失败: {e}")
            wait(1)

    # 上传封面
    if abs_cover:
        cli_log("🖼️ 上传封面...")
        try:
            cli_log(b.eval(JS_CLICK_COVER_AREA, MICRO_APP))
            wait(2)
            if upload_file(b, 'input[type="file"][accept*="image"]', abs_cover, label="上传封面"):
                wait(5)
                cli_log("✅ 封面已上传")
        except Exception as e:
            cli_log(f"⚠️ 封面上传失败: {e}")

    # 点击发布
    cli_log("🚀 点击发布...")
    try:
        cli_log(b.eval(JS_CLICK_SUBMIT, MICRO_APP))
    except Exception as e:
        cli_log(f"⚠️ 点击发布失败: {e}")
    wait(5)

    # 验证
    url = page_url(b)
    success = "success" in url or "manager" in url
    cli_log("✅ 发布成功！" if success else "⚠️ 请检查发布状态")

    b.screenshot()

#!/usr/bin/env python3
"""
快手视频上传 CLI (patchright 版)

从 kuaishou.mjs port。CLI 参数与 .mjs 一致。
⚠️ 技术要点：
- React Joyride 遮罩需移除（否则拦截所有点击）
- 封面：点默认封面打开 Ant Design Modal 选帧确认（.mjs 的 --cover 实际未用于上传文件，保持一致）
- 发布按钮在视口外，需 scrollIntoView
- 话题标签 ≤ 4 个
本脚本自动点「发布」并按 URL 验证（同 .mjs）。
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait, upload_file, page_url, default_profile_dir,
)

ap = argparse.ArgumentParser(description="快手视频上传 (patchright)")
ap.add_argument("--file", required=True)
ap.add_argument("--title", default="")
ap.add_argument("--desc", default="")
ap.add_argument("--tags", default="")
ap.add_argument("--cover", default="")  # .mjs 接受但未用于上传，保持一致
ap.add_argument("--dry-run", action="store_true")
args, _unknown = ap.parse_known_args()

file = args.file
title = args.title
desc = args.desc
tags = [t.strip() for t in args.tags.split(",") if t.strip()][:4]  # ≤ 4
dry_run = args.dry_run

if not os.path.exists(file):
    print(f"❌ 视频文件不存在: {file}")
    sys.exit(1)

abs_file = os.path.abspath(file)
# 快手标题和描述合一
full_desc = " ".join([s for s in [title, desc, " ".join(f"#{t}" for t in tags)] if s])

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("kuaishou", VAAS)

cli_log(f"""
📱 快手发布
{'━' * 41}
视频:   {abs_file}
描述:   {full_desc}
标签:   {', '.join(tags) or '(无)'}
{'━' * 41}
""")

# ─── 页内 JS（从 .mjs 原样搬）──
JS_LOGIN_CHECK = "document.body.innerText.slice(0, 500).includes('扫码登录') || document.body.innerText.slice(0, 500).includes('密码登录')"
JS_LOGIN_GONE = "document.body.innerText.includes('扫码登录')"

JS_REMOVE_JOYRIDE = """
(() => {
  const overlays = document.querySelectorAll('[class*="react-joyride"], [class*="joyride"]');
  overlays.forEach(el => el.remove());
  return 'removed ' + overlays.length + ' joyride elements';
})()
"""

JS_FILL_DESC = """
(text) => {
  const editor = document.querySelector('[contenteditable="true"]');
  if (!editor) return 'no editor';
  editor.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, text);
  return 'filled: ' + editor.textContent.trim().slice(0, 40);
}
"""

JS_COVER_MODAL = """
(() => {
  const modal = document.querySelector('.ant-modal-body');
  if (!modal) return 'no modal';
  const confirmBtn = modal.querySelector('.ant-btn-primary');
  if (confirmBtn) { confirmBtn.click(); return 'cover confirmed'; }
  return 'no confirm btn';
})()
"""

JS_SCROLL_PUBLISH = """
(() => {
  let btn = document.querySelector('._button-primary_3a3lq_60');
  if (!btn) {
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const bg = getComputedStyle(b).backgroundColor;
      if (bg.includes('254, 54, 102') && b.textContent?.trim()) { btn = b; break; }
    }
  }
  if (btn) { btn.scrollIntoView({ block: 'center' }); return 'scrolled to: ' + btn.textContent?.trim(); }
  return 'no publish btn';
})()
"""

JS_CLICK_PUBLISH = """
(() => {
  let btn = document.querySelector('._button-primary_3a3lq_60');
  if (!btn) {
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const bg = getComputedStyle(b).backgroundColor;
      if (bg.includes('254, 54, 102') && b.textContent?.includes('发布')) { btn = b; break; }
    }
  }
  if (btn) { btn.click(); return 'clicked: ' + btn.textContent?.trim(); }
  return 'no publish btn';
})()
"""

with Browser(profile, headless=False) as b:
    cli_log("🌐 打开快手创作者平台...")
    b.goto("https://cp.kuaishou.com/article/publish/video", then_wait=5)

    # 检查登录
    try:
        if b.eval(JS_LOGIN_CHECK):
            cli_log("⚠️ 需要登录快手，请在浏览器窗口扫码登录")
            for _ in range(60):
                wait(3)
                if not b.eval(JS_LOGIN_GONE):
                    cli_log("✅ 登录成功！")
                    break
            else:
                cli_log("⚠️ 登录超时")
    except Exception:
        pass

    # 移除 React Joyride 遮罩
    cli_log("🧹 移除 React Joyride 遮罩...")
    try:
        cli_log(b.eval(JS_REMOVE_JOYRIDE))
    except Exception:
        pass
    wait(1)

    if dry_run:
        cli_log("🔍 dry-run 模式")
        b.screenshot()
        from browser_utils import handoff
        handoff("dry-run: 页面已打开")
        sys.exit(0)

    # 上传视频
    cli_log("📤 上传视频...")
    upload_file(b, 'input[type="file"]', abs_file, label="上传视频")
    cli_log("等待上传完成...")
    wait(30)

    # 填描述
    cli_log("📝 填写描述...")
    try:
        cli_log(b.eval(JS_FILL_DESC, full_desc))
    except Exception as e:
        cli_log(f"⚠️ 描述填写失败: {e}")
    wait(2)

    # 设置封面（默认封面选帧）
    cli_log("🖼️ 设置封面...")
    try:
        b.eval("document.querySelector('._default-cover')?.click()")
    except Exception:
        pass
    wait(2)
    try:
        cli_log("封面: " + str(b.eval(JS_COVER_MODAL)))
    except Exception:
        pass
    wait(2)

    # 滚动到发布按钮
    cli_log("📜 滚动到发布按钮...")
    try:
        cli_log(b.eval(JS_SCROLL_PUBLISH))
    except Exception:
        pass
    wait(1)

    # 点击发布
    cli_log("🚀 点击发布...")
    try:
        cli_log("发布: " + str(b.eval(JS_CLICK_PUBLISH)))
    except Exception as e:
        cli_log(f"⚠️ 点击发布失败: {e}")
    wait(5)

    # 验证
    url = page_url(b)
    success = "status=2" in url or ("manage" in url and "video" in url)
    cli_log("✅ 发布成功！" if success else "⚠️ 请检查发布状态")

    b.screenshot()

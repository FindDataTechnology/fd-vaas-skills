#!/usr/bin/env python3
"""
YouTube 视频上传 CLI (patchright 版)

从 youtube.mjs port。CLI 参数与 .mjs 一致（含 --thumbnail / --visibility）。
⚠️ 技术要点：
- Polymer Web Components：tp-yt-paper-dialog 需强制 opened=true + display:block
- 4 步对话框：Details -> Video elements -> Checks -> Visibility
- "Not made for kids" 必答，否则 Next 禁用
- 标题用 execCommand（contenteditable #textbox）
本脚本自动点「Publish」并按 URL 验证（同 .mjs）。
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait, upload_file, page_url, default_profile_dir,
)

ap = argparse.ArgumentParser(description="YouTube 视频上传 (patchright)")
ap.add_argument("--file", required=True)
ap.add_argument("--title", required=True)
ap.add_argument("--desc", default="")
ap.add_argument("--tags", default="")
ap.add_argument("--thumbnail", default="")
ap.add_argument("--visibility", default="public")
ap.add_argument("--dry-run", action="store_true")
args, _unknown = ap.parse_known_args()

file = args.file
title = args.title
desc = args.desc
thumbnail = args.thumbnail
visibility = args.visibility
dry_run = args.dry_run

if not os.path.exists(file):
    print(f"❌ 视频文件不存在: {file}")
    sys.exit(1)

abs_file = os.path.abspath(file)
abs_thumb = os.path.abspath(thumbnail) if (thumbnail and os.path.exists(thumbnail)) else ""

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("youtube", VAAS)

cli_log(f"""
▶️ YouTube 发布
{'━' * 41}
视频:     {abs_file}
标题:     {title}
描述:     {desc or '(无)'}
缩略图:   {abs_thumb or '(无)'}
可见性:   {visibility}
{'━' * 41}
""")

JS_LOGIN_CHECK = "document.body.innerText.slice(0, 500).includes('Sign in') || document.body.innerText.slice(0, 500).includes('登录')"
JS_LOGIN_GONE = "document.body.innerText.includes('Sign in')"

JS_FORCE_DIALOG = """
(() => {
  const dialog = document.querySelector('ytcp-uploads-dialog');
  if (!dialog) return 'no dialog';
  const paper = dialog.querySelector('tp-yt-paper-dialog');
  if (paper) {
    paper.opened = true;
    paper.style.display = 'block';
    paper.setAttribute('opened', '');
  }
  return 'forced open';
})()
"""

JS_SET_TITLE = """
(text) => {
  const textbox = document.querySelector('#textbox');
  if (!textbox) return 'no textbox';
  textbox.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, text);
  return 'title set';
}
"""

JS_SET_DESC = """
(text) => {
  const textboxes = document.querySelectorAll('#textbox[contenteditable]');
  if (textboxes.length >= 2) {
    textboxes[1].focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
    document.execCommand('insertText', false, text);
    return 'desc set';
  }
  return 'no desc textbox';
}
"""

JS_NOT_FOR_KIDS = """
(() => {
  const radios = document.querySelectorAll('tp-yt-paper-radio-button');
  for (const r of radios) {
    if (r.textContent?.includes('No') && r.textContent?.includes('kids')) {
      r.click();
      return 'clicked not for kids';
    }
  }
  return 'not found';
})()
"""

JS_CLICK_NEXT = """
(() => {
  const btns = document.querySelectorAll('ytcp-button, #next-button');
  for (const b of btns) {
    if (b.textContent?.trim() === 'Next' && !b.hasAttribute('disabled') && !b.disabled) {
      b.click();
      return 'next';
    }
  }
  return 'no next (may be processing)';
})()
"""

JS_SELECT_VISIBILITY = """
(vis) => {
  const radios = document.querySelectorAll('tp-yt-paper-radio-button');
  for (const r of radios) {
    if (r.textContent?.includes(vis)) {
      r.click();
      return vis + ' selected';
    }
  }
  return 'not found';
}
"""

JS_CLICK_PUBLISH = """
(() => {
  const btn = document.querySelector('#done-button');
  if (btn && !btn.hasAttribute('disabled')) {
    btn.click();
    return 'published via #done-button';
  }
  const btns = document.querySelectorAll('ytcp-button');
  for (const b of btns) {
    if (b.textContent?.trim() === 'Publish') {
      b.click();
      return 'published via ytcp-button';
    }
  }
  return 'no publish btn';
})()
"""

# YouTube 需要代理访问
_YT_PROXY = os.environ.get("VAAS_PROXY", "http://127.0.0.1:7892")
with Browser(profile, headless=False, proxy=_YT_PROXY) as b:
    cli_log("🌐 打开 YouTube Studio 主页...")
    b.goto("https://studio.youtube.com", then_wait=8)
    wait(3)

    # 检查登录
    try:
        if b.eval(JS_LOGIN_CHECK):
            cli_log("⚠️ 需要登录 Google 账号，请在浏览器窗口完成登录（可能需要 2FA）")
            for _ in range(100):
                wait(3)
                if not b.eval(JS_LOGIN_GONE):
                    cli_log("✅ 登录成功！")
                    break
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

    # ✅ 新流程：点 Create -> 点 Upload video，等文件 input 出现
    cli_log("📤 点击 Create 按钮打开上传菜单...")
    b.eval("""() => {
        const btns = document.querySelectorAll('button, [role="button"]');
        for (const b of btns) {
            if ((b.textContent || '').trim() === 'Create') { b.click(); return 'clicked Create'; }
        }
        return 'no Create btn';
    }""")
    wait(2)
    cli_log("📤 点击 Upload video...")
    b.eval("""() => {
        const items = document.querySelectorAll('a, button, [role="menuitem"], [role="link"]');
        for (const el of items) {
            const t = (el.textContent || '').trim();
            if (t.includes('Upload video') || t.includes('上传视频') || t === 'Upload') {
                el.click(); return 'clicked: ' + t;
            }
        }
        return 'no Upload item';
    }""")
    wait(5)

    # 等文件 input 出现（最多 30 秒）
    cli_log("⏳ 等待上传 input 出现...")
    for i in range(15):
        cnt = b.eval('document.querySelectorAll("input[type=file]").length')
        if cnt and cnt > 0:
            cli_log(f"✅ 上传 input 已出现 ({cnt} 个)")
            break
        wait(2)

    # 上传视频
    cli_log("📤 上传视频...")
    upload_file(b, 'input[type="file"]', abs_file, label="上传视频")
    cli_log("等待上传完成...")
    wait(30)

    # 等待上传对话框
    cli_log("⏳ 等待上传对话框...")
    for _ in range(15):
        try:
            if b.eval("!!document.querySelector('ytcp-uploads-dialog')"):
                break
        except Exception:
            pass
        wait(3)

    # 强制打开 Polymer 对话框
    cli_log("🔓 强制打开 Polymer 对话框...")
    try:
        cli_log(b.eval(JS_FORCE_DIALOG))
    except Exception as e:
        cli_log(f"⚠️ 强制打开失败: {e}")
    wait(2)

    # 填标题
    cli_log("📝 填写标题...")
    try:
        cli_log(b.eval(JS_SET_TITLE, title))
    except Exception as e:
        cli_log(f"⚠️ 标题填写失败: {e}")
    wait(1)

    # 填描述
    if desc:
        cli_log("📝 填写描述...")
        try:
            cli_log(b.eval(JS_SET_DESC, desc))
        except Exception as e:
            cli_log(f"⚠️ 描述填写失败: {e}")
        wait(1)

    # Not made for kids
    cli_log('👶 选择 "Not made for kids"...')
    try:
        cli_log(b.eval(JS_NOT_FOR_KIDS))
    except Exception as e:
        cli_log(f"⚠️ kids 选项失败: {e}")
    wait(1)

    # 缩略图
    if abs_thumb:
        cli_log("🖼️ 上传缩略图...")
        try:
            b.eval("document.querySelector('#thumbnail [class*=\"upload\"]')?.click()")
            wait(1)
            if upload_file(b, 'input[type="file"][accept*="image"]', abs_thumb, label="上传缩略图"):
                wait(5)
                cli_log("✅ 缩略图已上传")
        except Exception as e:
            cli_log(f"⚠️ 缩略图上传失败: {e}")

    # Next 3 次
    cli_log("➡️ 导航到 Visibility 步骤...")
    for i in range(3):
        try:
            cli_log(b.eval(JS_CLICK_NEXT))
        except Exception as e:
            cli_log(f"⚠️ Next {i+1} 失败: {e}")
        wait(5)  # Checks 步骤需等待处理

    # 可见性
    cli_log(f"👁️ 选择可见性: {visibility}...")
    try:
        cli_log(b.eval(JS_SELECT_VISIBILITY, visibility))
    except Exception as e:
        cli_log(f"⚠️ 可见性选择失败: {e}")
    wait(1)

    # Publish
    cli_log("🚀 点击 Publish...")
    try:
        cli_log(b.eval(JS_CLICK_PUBLISH))
    except Exception as e:
        cli_log(f"⚠️ 点击 Publish 失败: {e}")
    wait(5)

    # 验证
    url = page_url(b)
    success = "dashboard" in url or "videos" in url
    cli_log("✅ 发布成功！" if success else "⚠️ 请检查发布状态")

    b.screenshot()

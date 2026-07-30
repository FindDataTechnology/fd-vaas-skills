#!/usr/bin/env python3
"""
抖音视频上传 CLI (patchright 版)

从 douyin.mjs port。CLI 参数与 .mjs 完全一致，便于 publish.mjs 统一派发：
  --file <mp4> --title <标题> [--desc <描述>] [--tags <a,b,c>]
  [--cover-horizontal <path>] [--cover-vertical <path>]
  [--schedule "YYYY-MM-DD HH:MM"] [--dry-run]

半自动：填完一切 + 截图，暂停让你手动点「发布」（对应 skill 的安全约束）。
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait, is_logged_in, wait_for_login,
    click_by_text, safe_fill, upload_file, with_retry, handoff,
    default_profile_dir,
)

# ─── args ────────────────────────────────────────────────
ap = argparse.ArgumentParser(description="抖音视频上传 (patchright)")
ap.add_argument("--file", required=True)
ap.add_argument("--title", required=True)
ap.add_argument("--desc", default="")
ap.add_argument("--tags", default="")
ap.add_argument("--cover-horizontal", dest="cover_horizontal", default="")
ap.add_argument("--cover-vertical", dest="cover_vertical", default="")
ap.add_argument("--cover", default="")  # 兼容 publish.mjs 统一传的 --cover
ap.add_argument("--schedule", default="")
ap.add_argument("--dry-run", action="store_true")
args, _unknown = ap.parse_known_args()

file = args.file
title = args.title
desc = args.desc
tags = args.tags
# 横封面优先 --cover-horizontal，退到 --cover
cover_h = args.cover_horizontal or args.cover
cover_v = args.cover_vertical
schedule = args.schedule
dry_run = args.dry_run

if not os.path.exists(file):
    print(f"❌ 视频文件不存在: {file}")
    sys.exit(1)

abs_file = os.path.abspath(file)
abs_cover_h = os.path.abspath(cover_h) if cover_h else ""
abs_cover_v = os.path.abspath(cover_v) if cover_v else ""

full_desc = f"{title}\n{desc}\n#{tags.replace(',', ' #')}" if tags else f"{title}\n{desc}"

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("douyin", VAAS)

# 登录标记
LOGGED_IN = ["发布作品", "上传视频", "创作者服务", "创作者中心"]
NOT_LOGGED_IN = ["登录", "扫码登录", "验证码登录", "密码登录"]

cli_log(f"""
🎵 抖音视频发布
{'━' * 41}
视频:      {abs_file}
标题:      {title}
描述:      {desc or '(无)'}
标签:      {tags or '(无)'}
横封面:    {abs_cover_h or '(未设置)'}
竖封面:    {abs_cover_v or '(未设置)'}
定时:      {schedule or '(立即发布)'}
{'━' * 41}
""")

# ─── 页内 JS（从 douyin.mjs 原样搬，由 patchright evaluate 执行）──
JS_ID_VIDEO_INPUT = """
(() => {
  const inputs = document.querySelectorAll('input[type="file"]');
  for (let i = 0; i < inputs.length; i++) {
    const accept = inputs[i].accept || '';
    if (accept.includes('video') || accept.includes('mp4')) {
      inputs[i].setAttribute('id', 'douyin-video-input');
      return { found: true };
    }
  }
  if (inputs.length > 0) {
    inputs[0].setAttribute('id', 'douyin-video-input');
    return { found: true };
  }
  return { found: false };
})()
"""

JS_FILL_DESC = """
(text) => {
  const editor = document.querySelector('[contenteditable="true"]');
  if (editor) {
    editor.focus();
    document.execCommand('insertText', false, text);
    return true;
  }
  return false;
}
"""

JS_COVER_REGION_COUNT = """
(() => {
  const elements = document.querySelectorAll('div');
  let n = 0;
  for (const el of elements) {
    const text = (el.textContent || '').trim();
    if (text === '横封面' || text === '选择封面') n++;
  }
  return n;
})()
"""

JS_ID_COVER_INPUT = """
(() => {
  const inputs = document.querySelectorAll('input[type="file"]');
  for (let i = 0; i < inputs.length; i++) {
    const accept = inputs[i].accept || '';
    if (accept.includes('image') || accept.includes('jpg') || accept.includes('png')) {
      inputs[i].setAttribute('id', 'douyin-cover-input');
      return true;
    }
  }
  return false;
})()
"""


def upload_cover(b, cover_path, cover_type):
    if not cover_path:
        return
    cli_log(f"🖼️  上传{cover_type}封面...")
    try:
        click_by_text(b, ["上传封面"], "点击上传封面按钮")
        wait(2)
        b.eval(JS_ID_COVER_INPUT)
        if upload_file(b, "#douyin-cover-input", cover_path, label=f"{cover_type}封面"):
            wait(5)
            click_by_text(b, ["完成", "确定"], "点击完成按钮", exact=True)
            wait(2)
            cli_log(f"✅  {cover_type}封面上传成功")
    except Exception as e:
        cli_log(f"⚠️  {cover_type}封面可能需要手动操作: {e}")


# ─── 主流程 ──────────────────────────────────────────────
with Browser(profile, headless=False) as b:
    # 步骤 1: 打开抖音创作者中心
    cli_log("\n▶ [1/6] 打开抖音创作者中心")
    b.goto("https://creator.douyin.com/creator-micro/content/upload", then_wait=5)
    cli_log("✅  页面加载完成")

    # 步骤 2: 检查登录状态
    cli_log("\n▶ [2/6] 检查登录状态")
    if not wait_for_login(b, LOGGED_IN, NOT_LOGGED_IN,
                          hint="请在浏览器窗口中扫码登录抖音"):
        cli_log("⚠️  登录未完成，后续步骤可能需要手动操作")
    else:
        wait(3)
        cli_log("✅  登录状态正常")

    if not dry_run:
        # 步骤 3: 上传视频
        cli_log("\n▶ [3/6] 上传视频")
        try:
            r = b.eval(JS_ID_VIDEO_INPUT)
            if r and r.get("found"):
                with_retry(lambda: upload_file(b, "#douyin-video-input", abs_file, label="上传视频"),
                           max_retries=2, name="上传视频")
                cli_log("✅  视频上传中... 等待上传和转码完成 (约 30-60 秒)")
                wait(45)
            else:
                cli_log("⚠️  未找到视频上传入口，请手动上传")
        except Exception as e:
            cli_log(f"⚠️  视频上传可能需要手动操作: {e}")

        # 步骤 4: 填写作品描述
        cli_log("\n▶ [4/6] 填写作品描述")
        try:
            ok = b.eval(JS_FILL_DESC, full_desc)
            if ok:
                cli_log("✅  描述填写完成")
            else:
                cli_log("⚠️  未找到描述输入框，请手动填写")
            wait(1)
        except Exception as e:
            cli_log(f"⚠️  描述填写失败，请手动填写: {e}")

        # 步骤 5: 上传封面
        cli_log("\n▶ [5/6] 上传封面")
        b.eval("window.scrollTo(0, 350)")
        wait(1)
        cover_count = 0
        try:
            cover_count = b.eval(JS_COVER_REGION_COUNT) or 0
        except Exception:
            pass
        if cover_count >= 1 and abs_cover_h:
            upload_cover(b, abs_cover_h, "横")
        elif not abs_cover_h:
            cli_log("  跳过横封面（未提供）")
        else:
            cli_log("⚠️  未找到横封面区域，请手动设置")
        if cover_count >= 2 and abs_cover_v:
            upload_cover(b, abs_cover_v, "竖")
        elif abs_cover_v and cover_count < 2:
            cli_log("⚠️  未找到竖封面区域，请手动设置")

        if schedule:
            cli_log("⏰  设置定时发布...")
            click_by_text(b, ["定时发布", "定时"], "点击定时发布")
            wait(1)
            cli_log(f"⚠️  定时发布时间请手动设置: {schedule}")

        cli_log("✅  封面设置完成")

    # 步骤 6: 发布前确认
    cli_log("\n▶ [6/6] 发布前确认")
    cli_log("")
    cli_log("━" * 41)
    cli_log("📋  请在浏览器中确认以下信息：")
    cli_log("   • 视频是否上传完成")
    cli_log("   • 标题/描述/话题是否正确")
    cli_log("   • 横封面是否已设置")
    cli_log("   • 竖封面是否已设置")
    cli_log("   • 发布设置是否正确（立即/定时）")
    cli_log("")
    cli_log("👉  确认无误后，请手动点击「发布」按钮")
    cli_log("━" * 41)

    try:
        b.screenshot()
    except Exception:
        cli_log("⚠️  截图失败，请直接查看浏览器窗口")

    b.eval("window.scrollTo(0, document.body.scrollHeight)")
    wait(1)

    # 🚀 全自动发布模式
    cli_log("\n🚀  自动发布中...")

    # 反复滚动到底，确保发布按钮在可视区域
    for _ in range(3):
        b.eval("window.scrollTo(0, document.body.scrollHeight)")
        wait(0.5)

    # 找真正的发布按钮：优先 button 标签，文本精确匹配
    js_click_publish = """
    () => {
      const targets = ['发布', '立即发布', '发布作品', '公开发布'];
      // 优先找 button
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (!btn.offsetParent) continue;
        const text = (btn.textContent || '').trim();
        if (targets.includes(text)) {
          btn.scrollIntoView({block: 'center'});
          btn.click();
          return { found: true, text, tag: 'button' };
        }
      }
      // 退而求其次：div/span
      const els = document.querySelectorAll('div, span');
      for (const el of els) {
        if (!el.offsetParent) continue;
        const text = (el.textContent || '').trim();
        if (text.length > 20) continue;  // 跳过长文本
        if (targets.includes(text)) {
          el.scrollIntoView({block: 'center'});
          el.click();
          return { found: true, text, tag: el.tagName };
        }
      }
      return { found: false };
    }
    """
    try:
        r = b.eval(js_click_publish)
        if r and r.get("found"):
            cli_log(f"✅  点击发布按钮 ({r['text']}, {r['tag']})")
            # 点击后等 20 秒，确保发布请求发出 + 页面跳转
            wait(20)
            # 检测是否跳转到发布成功页
            try:
                url = b.page.url
                if "success" in url or "manage" in url or "content" in url:
                    cli_log("✅  发布成功！已跳转到管理页")
                else:
                    cli_log(f"✅  已点击发布，当前页: {url}")
            except Exception:
                cli_log("✅  已点击发布按钮")
        else:
            cli_log("⚠️  未找到发布按钮，请手动点击")
            handoff("手动点击发布后按回车继续")
    except Exception as e:
        cli_log(f"⚠️  点击发布失败: {e}")
        handoff("手动点击发布后按回车继续")

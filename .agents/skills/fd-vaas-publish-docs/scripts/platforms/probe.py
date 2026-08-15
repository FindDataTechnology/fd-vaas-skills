#!/usr/bin/env python3
"""
probe.py - 选择器核对工具 (patchright 版)

移植 references/probe.md:打开某平台图文编辑器,dump 可交互元素 + file input,
照着输出找标题/正文/封面/发布按钮的真实选择器,再改对应 <platform>.py。

用法:
  python3 probe.py zhihu                 # 用内置 editor URL
  python3 probe.py --url https://...     # 自定义 URL
  python3 probe.py zhihu --headless      # 无头(不推荐,登录态看不到)
"""

import os
import sys
import json
import argparse
from datetime import date

from _publish_path import add_publish_path  # noqa: E402
_shared_dir = add_publish_path()
from browser_utils import Browser, cli_log, wait, handoff, default_profile_dir  # noqa: E402

REGISTRY = os.path.join(_shared_dir, "platform-registry.json")


def writeback(status):
    """回写 platform-registry.json 的 selectorStatus / lastVerified(单一可机读源)。"""
    if not args.platform or args.platform == "probe":
        return
    try:
        with open(REGISTRY, "r", encoding="utf-8") as f:
            reg = json.load(f)
    except FileNotFoundError:
        cli_log(f"⚠️ 未找到 {REGISTRY},跳过回写")
        return
    entry = reg.get("platforms", {}).get(args.platform)
    if entry is None:
        cli_log(f"⚠️ {args.platform} 不在 registry,跳过回写")
        return
    entry["selectorStatus"] = status
    entry["lastVerified"] = date.today().isoformat()
    with open(REGISTRY, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    cli_log(f"📝 已回写 registry: {args.platform} -> {status} ({entry['lastVerified']})")

EDITORS = {
    "zhihu": "https://zhuanlan.zhihu.com/write",
    "weixin": "https://mp.weixin.qq.com/",
    "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image",
    "xueqiu": "https://xueqiu.com/zhuanlan/publish",
    "eastmoney": "https://mp.eastmoney.com/collect/pc_article/index.html#/",
    "tonghuashun": "https://media.10jqka.com.cn/",
    "toutiao": "https://mp.toutiao.com/profile_v4/graphic/publish",
    "baijiahao": "https://baijiahao.baidu.com/builder/rc/edit",
    "weibo": "https://weibo.com/",
}

ap = argparse.ArgumentParser(description="选择器核对 (patchright)")
ap.add_argument("platform", nargs="?", help="平台名(zhihu/weixin/...)")
ap.add_argument("--url", help="自定义编辑器 URL(覆盖 platform)")
ap.add_argument("--headless", action="store_true")
ap.add_argument("--mark-broken", action="store_true", help="回写 selectorStatus=broken(入口 404/302 等)")
args = ap.parse_args()

url = args.url or EDITORS.get(args.platform or "")
if not url:
    cli_log(f"❌ 需要平台名({'/'.join(EDITORS)})或 --url")
    sys.exit(1)
platform = args.platform or "probe"

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir(platform, VAAS)

DUMP_JS = """
() => {
  const out = [];
  const sel = 'input,textarea,[contenteditable="true"],button,[role="textbox"],[role="button"],[contenteditable]';
  document.querySelectorAll(sel).forEach((el, i) => {
    if (i > 150) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    out.push({
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || '',
      role: el.getAttribute('role') || '',
      placeholder: el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || '',
      text: (el.innerText || el.value || '').slice(0, 50).replace(/\\n/g, ' '),
      id: el.id || '',
      cls: (el.className || '').toString().slice(0, 90),
      editable: el.getAttribute('contenteditable') || '',
    });
  });
  return JSON.stringify(out, null, 1);
}
"""

FILE_INPUTS_JS = """
() => {
  const out = [];
  document.querySelectorAll('input[type="file"]').forEach((el) => {
    out.push({ accept: el.getAttribute('accept') || '', id: el.id || '', cls: (el.className || '').toString().slice(0, 70) });
  });
  return JSON.stringify(out);
}
"""

IFRAME_JS = """
() => {
  const ifs = [];
  document.querySelectorAll('iframe').forEach((f, i) => {
    try {
      const d = f.contentDocument;
      const es = d ? d.querySelectorAll('[contenteditable="true"],textarea,input') : [];
      ifs.push({ src: (f.src||'').slice(0,80), editableCount: es.length });
    } catch (e) { ifs.push({ src: (f.src||'').slice(0,80), error: 'cross-origin' }); }
  });
  return JSON.stringify(ifs);
}
"""

with Browser(profile, headless=args.headless) as b:
    cli_log(f"🌐 打开 {url}")
    b.goto(url, then_wait=6)
    cli_log(f"URL: {b.page.url}")
    cli_log(f"TITLE: {b.page.title()}")
    import re
    logged_in = not re.search(r"/(login|signin|upass|passport|sso)\b", b.page.url, re.I)
    cli_log(f"LOGGED_IN: {logged_in}")
    if not logged_in:
        cli_log("⚠️ 未登录,请在浏览器登录后回车继续 dump(或 Ctrl+C 退出)")
        handoff("登录后回车继续 dump")

    cli_log("\n===== ELEMENTS =====")
    try:
        cli_log(b.eval(DUMP_JS))
    except Exception as e:
        cli_log(f"⚠️ dump 失败: {e}")

    cli_log("\n===== FILE_INPUTS =====")
    try:
        cli_log(b.eval(FILE_INPUTS_JS))
    except Exception as e:
        cli_log(f"⚠️ file input dump 失败: {e}")

    cli_log("\n===== IFRAMES =====")
    try:
        cli_log(b.eval(IFRAME_JS))
    except Exception as e:
        cli_log(f"⚠️ iframe dump 失败: {e}")

    b.screenshot()
    cli_log("\n✅ dump 完成。照输出找标题/正文/封面/发布按钮选择器,改回 <platform>.py。")
    writeback("broken" if args.mark_broken else "verified")
    handoff("回车关闭浏览器")

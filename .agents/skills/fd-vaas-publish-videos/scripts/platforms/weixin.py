#!/usr/bin/env python3
"""
微信视频号上传 CLI (patchright 版)

从 weixin.mjs port。CLI 参数与 .mjs 一致。
⚠️ 核心技术挑战：视频号用 Wujie 微前端（shadow DOM），React 事件不跨越 shadow 边界，
   patchright 的 set_input_files / CDP setFileInputFiles 都不会触发上传。
   方案：Python 起本地 HTTP 服务器提供视频 -> 页内 fetch -> Blob -> File ->
        DataTransfer.items.add -> input.files = dt.files -> dispatch change。
   （.mjs 的 --cover 实际未用于上传，保持一致，用默认截帧）
本脚本自动点「发表」并按 URL 验证（同 .mjs）。
"""

import os
import sys
import http.server
import threading
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from browser_utils import (  # noqa: E402
    Browser, cli_log, wait, page_url, default_profile_dir,
)

ap = argparse.ArgumentParser(description="微信视频号上传 (patchright)")
ap.add_argument("--file", required=True)
ap.add_argument("--desc", default="")
ap.add_argument("--cover", default="")  # .mjs 接受但未用于上传，保持一致
ap.add_argument("--dry-run", action="store_true")
args, _unknown = ap.parse_known_args()

file = args.file
desc = args.desc
dry_run = args.dry_run

if not os.path.exists(file):
    print(f"❌ 视频文件不存在: {file}")
    sys.exit(1)

abs_file = os.path.abspath(file)

VAAS = os.environ.get("VAAS_ROOT") or os.getcwd()
profile = default_profile_dir("weixin", VAAS)


# ─── 本地 HTTP 服务器：给页内 fetch 提供 mp4（带 CORS）──
class _VideoHandler(http.server.BaseHTTPRequestHandler):
    file_path = None

    def do_GET(self):
        if self.path == "/video.mp4" and self.file_path:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(os.path.getsize(self.file_path)))
            self.end_headers()
            with open(self.file_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


def serve_video(path):
    _VideoHandler.file_path = path
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _VideoHandler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


cli_log(f"""
📱 微信视频号发布
{'━' * 41}
视频:   {abs_file}
描述:   {desc or '(无)'}
{'━' * 41}
""")

# ─── 页内 JS（从 .mjs 原样搬）──
JS_WUJIE_READY = "!!document.querySelector('wujie-app')?.shadowRoot?.querySelector('input[type=\"file\"]')"

JS_NEEDS_LOGIN = """
(() => {
  const sr = document.querySelector('wujie-app')?.shadowRoot;
  if (!sr) return true;
  const text = sr.textContent || '';
  return text.includes('扫码登录') || text.includes('二维码') || !sr.querySelector('input[type="file"]');
})()
"""

# port 作参数传入，避免字符串拼接
JS_DATATRANSFER_UPLOAD = """
(port) => {
  return fetch('http://localhost:' + port + '/video.mp4')
    .then(r => r.blob())
    .then(blob => {
      const wujie = document.querySelector('wujie-app');
      const sr = wujie?.shadowRoot;
      if (!sr) return 'no shadow';
      const input = sr.querySelector('input[type="file"]');
      if (!input) return 'no input';
      const file = new File([blob], 'video.mp4', { type: 'video/mp4' });
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
      return 'file set: count=' + input.files.length + ', size=' + input.files[0].size;
    })
    .catch(e => 'error: ' + e.message);
}
"""

JS_UPLOAD_STATUS = """
(() => {
  const sr = document.querySelector('wujie-app')?.shadowRoot;
  const form = sr?.querySelector('.form');
  const text = (form?.textContent || '').trim();
  return { uploading: text.includes('文件上传中'), text: text.slice(0, 40) };
})()
"""

JS_FILL_DESC = """
(text) => {
  const sr = document.querySelector('wujie-app')?.shadowRoot;
  const editor = sr?.querySelector('.input-editor');
  if (!editor) return 'no editor';
  editor.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, text);
  return 'desc filled: ' + editor.textContent.trim().slice(0, 40);
}
"""

JS_CLICK_PUBLISH = """
(() => {
  const sr = document.querySelector('wujie-app')?.shadowRoot;
  const btns = sr?.querySelectorAll('.weui-desktop-btn_primary');
  for (const btn of btns) {
    if (btn.textContent?.trim() === '发表' && !btn.disabled) {
      btn.click();
      return 'clicked 发表';
    }
  }
  return 'no publish btn';
})()
"""

with Browser(profile, headless=False) as b:
    cli_log("🌐 打开视频号助手发布页...")
    b.goto("https://channels.weixin.qq.com/platform/post/create", then_wait=5)

    # 等待 wujie-app shadow DOM 加载
    cli_log("⏳ 等待 Wujie 微前端加载...")
    for _ in range(15):
        try:
            if b.eval(JS_WUJIE_READY):
                cli_log("✅ Wujie 已加载")
                break
        except Exception:
            pass
        wait(2)

    # 检查登录
    try:
        if b.eval(JS_NEEDS_LOGIN):
            cli_log("⚠️ 需要登录视频号，请在浏览器窗口用微信扫码登录")
            for _ in range(60):
                wait(3)
                try:
                    if b.eval(JS_WUJIE_READY):
                        cli_log("✅ 登录成功！")
                        break
                except Exception:
                    pass
            else:
                cli_log("⚠️ 登录超时")
    except Exception:
        pass

    if dry_run:
        cli_log("🔍 dry-run 模式，仅打开页面")
        b.screenshot()
        from browser_utils import handoff
        handoff("dry-run: 页面已打开")
        sys.exit(0)

    # 核心：HTTP 服务器 + DataTransfer 上传
    cli_log("📤 启动本地 HTTP 服务器...")
    httpd, port = serve_video(abs_file)
    wait(1)
    try:
        cli_log("📤 通过 fetch + DataTransfer 上传视频...")
        try:
            cli_log("上传结果: " + str(b.eval(JS_DATATRANSFER_UPLOAD, port)))
        except Exception as e:
            cli_log(f"⚠️ DataTransfer 上传失败: {e}")
    finally:
        httpd.shutdown()
        cli_log("📡 HTTP 服务器已关闭")

    # 等待上传完成
    cli_log("⏳ 等待视频上传完成...")
    for i in range(30):
        wait(10)
        try:
            status = b.eval(JS_UPLOAD_STATUS)
            if not status.get("uploading"):
                cli_log("✅ 视频上传完成！")
                break
            if i % 3 == 0:
                cli_log(f"   仍在上传... {(i + 1) * 10}s")
        except Exception:
            pass

    # 填描述
    if desc:
        cli_log("📝 填写描述...")
        try:
            cli_log(b.eval(JS_FILL_DESC, desc))
        except Exception as e:
            cli_log(f"⚠️ 描述填写失败: {e}")
        wait(2)

    # 点击发表
    cli_log("🚀 点击发表按钮...")
    try:
        cli_log("发表: " + str(b.eval(JS_CLICK_PUBLISH)))
    except Exception as e:
        cli_log(f"⚠️ 点击发表失败: {e}")
    wait(5)

    # 验证
    url = page_url(b)
    success = "/platform/post/list" in url
    cli_log("✅ 发布成功！视频将在处理完后自动发布" if success else "⚠️ 请检查发布状态")

    b.screenshot()

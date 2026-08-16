#!/usr/bin/env python3
"""
VAAS 扫码登录管理页 — 单文件，零依赖。

镜像 fd-vaas-dashboard 模式：Python stdlib http.server + ThreadingHTTPServer
+ inline HTML，不引入 Flask/Vite。触发：/login，跑在 localhost:8766。

功能:
  - GET / → 登录态总览页（视频 + 图文两个分区）
  - GET /api/status → 各平台状态（视频 cookie / 图文检测结果）
  - POST /api/login?platform=<p> → 后台 spawn sau_adapter.py --login（有头浏览器弹出）
  - POST /api/check?platform=<p> → 验证 cookie 有效性
  - GET /api/qr?platform=<p> → 最新 QR PNG（轮询用）
  - POST /api/docs/login?platform=<p> → 图文平台：patchright Chromium 窗口打开登录页，用户登录后自动关窗
  - POST /api/docs/check?platform=<p> → 图文平台：patchright Chromium 窗口检测登录态后自动关窗

支持的 Playwright 平台：douyin/kuaishou/xiaohongshu/weixin/youtube
bilibili 使用 patchright profile 持久化（bilibili_login.py 打开浏览器手动登录，不扫码）。
图文自有逻辑平台（zhihu/weixin_mp/xueqiu/eastmoney/tonghuashun/toutiao/baijiahao/weibo）
走 docs_login.py + patchright（自带 Chromium，跨平台，持久化 profile，无 cookie 文件）；
小红书/抖音/快手图文与视频共享 cookie，不单独管理。
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse


# ─── 配置 ────────────────────────────────────────────────────────
PORT = 8766
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent.parent.parent  # scripts/ -> fd-vaas-login/ -> skills/ -> .agents/ -> VAAS/
_SAU_ADAPTER = _HERE.parent.parent / "fd-vaas-publish-videos" / "scripts" / "platforms" / "sau_adapter.py"
_BILIBILI_LOGIN = _HERE / "bilibili_login.py"
_YOUTUBE_LOGIN = _HERE / "youtube_login.py"
_DOCS_LOGIN = _HERE / "docs_login.py"
_DOCS_STATE_FILE = _HERE / ".docs_state.json"  # 图文平台检测结果落盘（gitignored）


# ─── 平台注册表（对齐 sau_adapter.py REGISTRY）────────────────────────────────
PLATFORM_REGISTRY = {
    "xiaohongshu": {
        "account_file": _ROOT / ".agents" / "skills" / "fd-vaas-publish-videos" / "scripts" / "upstream" / "cookies" / "xiaohongshu_uploader" / "account.json",
        "name": "小红书",
        "type": "video",
    },
    "douyin": {
        "account_file": _ROOT / ".agents" / "skills" / "fd-vaas-publish-videos" / "scripts" / "upstream" / "cookies" / "douyin_uploader" / "account.json",
        "name": "抖音",
        "type": "video",
    },
    "kuaishou": {
        "account_file": _ROOT / ".agents" / "skills" / "fd-vaas-publish-videos" / "scripts" / "upstream" / "cookies" / "kuaishou_creator.json",
        "name": "快手",
        "type": "video",
    },
    "weixin": {
        "account_file": _ROOT / ".agents" / "skills" / "fd-vaas-publish-videos" / "scripts" / "upstream" / "cookies" / "tencent_uploader" / "account.json",
        "name": "视频号",
        "type": "video",
    },
    "youtube": {
        "account_file": _ROOT / ".agents" / "skills" / "fd-vaas-publish-videos" / "scripts" / "upstream" / "cookies" / "youtube_uploader" / "account.json",
        "name": "YouTube",
        "type": "video",
    },
    "bilibili": {
        "account_file": None,  # bilibili 用 .profiles/bilibili profile 模式
        "name": "Bilibili",
        "type": "video",
        "profile_dir": _ROOT / ".profiles" / "bilibili",
    },
}


# ─── 图文平台注册表（fd-vaas-publish-docs 自有逻辑平台）────────────────────
# 登录态在 patchright 持久 profile（$VAAS/.profiles/<name>）里，无 cookie 文件；
# 检测/登录由 docs_login.py 驱动，结果落盘 _DOCS_STATE_FILE。
DOCS_REGISTRY = {
    "zhihu": {"name": "知乎"},
    "weixin_mp": {"name": "微信公众号"},
    "xueqiu": {"name": "雪球"},
    "eastmoney": {"name": "东方财富号"},
    "tonghuashun": {"name": "同花顺财经号"},
    "toutiao": {"name": "今日头条"},
    "baijiahao": {"name": "百家号"},
    "weibo": {"name": "微博"},
}
# 图文与视频共享 cookie 的平台（发布走 note_adapter.py），页面复用视频区状态
DOCS_SHARED = ["xiaohongshu", "douyin", "kuaishou"]


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """多进程线程池 HTTP Server（非阻塞）。"""
    allow_reuse_address = True
    daemon_threads = True


# ─── 全局子进程状态存储 ────────────────────────────────────────────────
_login_processes = {}  # platform（图文用 "docs:<p>"）→ {"process": Popen, "started_at": float, "last_output": str, "state": str}
_lock = threading.Lock()

# 图文平台检测结果（落盘，重启不丢）：platform → {"logged_in": bool, "url": str, "checked_at": str}
_docs_state: dict = {}


def _load_docs_state():
    global _docs_state
    try:
        if _DOCS_STATE_FILE.exists():
            _docs_state = json.loads(_DOCS_STATE_FILE.read_text("utf-8"))
    except Exception:
        _docs_state = {}


def _save_docs_state():
    try:
        _DOCS_STATE_FILE.write_text(
            json.dumps(_docs_state, ensure_ascii=False, indent=1), "utf-8"
        )
    except Exception as e:
        print(f"⚠️ docs state 保存失败: {e}")


def _find_latest_qr(platform: str) -> Path | None:
    """查找平台最新的 *_login_qrcode_*.png 文件。"""
    cfg = PLATFORM_REGISTRY[platform]
    if not cfg["account_file"]:
        return None
    cookies_dir = cfg["account_file"].parent
    if not cookies_dir.exists():
        return None
    try:
        files = [f for f in cookies_dir.iterdir() if "_login_qrcode_" in f.name and f.suffix.lower() == ".png"]
        if not files:
            return None
        return max(files, key=lambda p: p.stat().st_mtime)
    except Exception:
        return None


def _run_login(platform: str) -> int:
    """后台运行 sau_adapter.py --login。返回 exit code。"""
    cfg = PLATFORM_REGISTRY[platform]
    cmd = ["python3", str(_SAU_ADAPTER), "--platform", platform, "--login"]

    # YouTube 需要代理环境变量
    if platform == "youtube":
        proxy = os.environ.get("VAAS_YT_PROXY")
        if proxy:
            env = os.environ.copy()
            env["http_proxy"] = proxy
            cmd_env = cmd
        else:
            env = None
            cmd_env = cmd
    else:
        env = None
        cmd_env = cmd

    print(f"▶ 启动 {platform} 登录流程...")
    with _lock:
        process = subprocess.Popen(
            cmd_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=str(_ROOT),
        )
        _login_processes[platform] = {
            "process": process,
            "started_at": time.time(),
            "last_output": "",
            "state": "running",
        }

    # 后台监控子进程输出
    def monitor_output():
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_lines.append(line.rstrip())
                print(f"  {platform}: {line.strip()}")

        final_output = "\n".join(output_lines)
        exit_code = process.returncode

        with _lock:
            if platform in _login_processes:
                _login_processes[platform]["last_output"] = final_output
                _login_processes[platform]["state"] = "success" if exit_code == 0 else "failed"
                _login_processes[platform]["exit_code"] = exit_code
                if exit_code == 0:
                    print(f"✅ {platform} 登录完成")
                else:
                    print(f"❌ {platform} 登录失败（exit={exit_code}）")

    t = threading.Thread(target=monitor_output, daemon=True)
    t.start()
    return 0


def _run_bilibili_login() -> int:
    """后台运行 bilibili_login.py 打开浏览器供用户手动登录（profile 持久化模式）。"""
    cfg = PLATFORM_REGISTRY["bilibili"]
    profile_dir = cfg["profile_dir"]
    cmd = ["python3", str(_BILIBILI_LOGIN), str(profile_dir)]

    print("▶ 启动 bilibili 登录流程...")
    with _lock:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(_ROOT),
        )
        _login_processes["bilibili"] = {
            "process": process,
            "started_at": time.time(),
            "last_output": "",
            "state": "running",
        }

    def monitor_output():
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_lines.append(line.rstrip())
                print(f"  bilibili: {line.strip()}")

        final_output = "\n".join(output_lines)
        exit_code = process.returncode

        with _lock:
            if "bilibili" in _login_processes:
                _login_processes["bilibili"]["last_output"] = final_output
                _login_processes["bilibili"]["state"] = "success" if exit_code == 0 else "failed"
                _login_processes["bilibili"]["exit_code"] = exit_code
                if exit_code == 0:
                    print("✅ bilibili 登录完成")
                else:
                    print(f"❌ bilibili 登录未完成（exit={exit_code}）")

    t = threading.Thread(target=monitor_output, daemon=True)
    t.start()
    return 0


def _run_youtube_login() -> int:
    """后台运行 youtube_login.py：复用本机 Chrome profile 的登录态导出 storage_state。

    与 sau_adapter --login（隔离 new_context，看不到 Chrome 登录态）不同，这里用
    launch_persistent_context 指向用户真实 Chrome user-data-dir + channel="chrome"，
    直接继承 Chrome 里已有的 Google/YouTube 登录。前提：先 Cmd+Q 退出 Chrome。
    """
    cfg = PLATFORM_REGISTRY["youtube"]
    account_file = cfg["account_file"]
    cmd = ["python3", str(_YOUTUBE_LOGIN), str(account_file)]

    # youtube.com 需要代理（patchright 启的 chromium 不吃系统代理）。
    # 用 channel="chrome" 走真 Chrome 时，Chrome 自身读系统代理；这里设 env 保险。
    env = os.environ.copy()
    yt_proxy = os.environ.get("VAAS_YT_PROXY") or "http://127.0.0.1:7892"
    env["http_proxy"] = yt_proxy
    env["https_proxy"] = yt_proxy

    print("▶ 启动 youtube 登录流程（复用 Chrome profile）...")
    with _lock:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=str(_ROOT),
        )
        _login_processes["youtube"] = {
            "process": process,
            "started_at": time.time(),
            "last_output": "",
            "state": "running",
        }

    def monitor_output():
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_lines.append(line.rstrip())
                print(f"  youtube: {line.strip()}")

        final_output = "\n".join(output_lines)
        exit_code = process.returncode

        with _lock:
            if "youtube" in _login_processes:
                _login_processes["youtube"]["last_output"] = final_output
                _login_processes["youtube"]["state"] = "success" if exit_code == 0 else "failed"
                _login_processes["youtube"]["exit_code"] = exit_code
                if exit_code == 0:
                    print("✅ youtube 登录完成")
                else:
                    print(f"❌ youtube 登录未完成（exit={exit_code}）")

    t = threading.Thread(target=monitor_output, daemon=True)
    t.start()
    return 0


def _run_login_check(platform: str) -> tuple[bool, str]:
    """运行 sau_adapter.py --login-check，返回 (is_valid, message)。"""
    cfg = PLATFORM_REGISTRY[platform]
    account_file = cfg["account_file"]

    if not account_file or not account_file.exists():
        return False, "cookie 不存在"

    cmd = ["python3", str(_SAU_ADAPTER), "--platform", platform, "--login-check"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(_ROOT))
    output = result.stdout + result.stderr

    if result.returncode == 0:
        return True, "cookie 有效"
    else:
        return False, output.split("\n")[-1] if output else "cookie 检查失败"


def _run_docs_action(platform: str, mode: str) -> int:
    """后台跑 docs_login.py --check/--login，结束后把检测结果落盘。"""
    key = f"docs:{platform}"
    cmd = ["python3", str(_DOCS_LOGIN), platform, f"--{mode}"]

    print(f"▶ 图文[{platform}] {mode} ...")
    with _lock:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(_ROOT),
        )
        _login_processes[key] = {
            "process": process,
            "started_at": time.time(),
            "last_output": "",
            "state": "running",
            "mode": mode,
        }

    def monitor_output():
        output_lines = []
        last_result = None
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_lines.append(line.rstrip())
                idx = line.find("VAAS_DOCS_RESULT ")
                if idx >= 0:
                    try:
                        last_result = json.loads(line[idx + len("VAAS_DOCS_RESULT "):])
                    except Exception:
                        pass
                print(f"  docs:{platform}: {line.strip()}")

        exit_code = process.returncode
        with _lock:
            if key in _login_processes:
                _login_processes[key]["last_output"] = "\n".join(output_lines[-50:])
                _login_processes[key]["state"] = "success" if exit_code == 0 else "failed"
                _login_processes[key]["exit_code"] = exit_code
            if last_result is not None:
                _docs_state[platform] = {
                    "logged_in": bool(last_result.get("logged_in")),
                    "url": last_result.get("url", ""),
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                _save_docs_state()
        mark = "✅" if exit_code == 0 else "❌"
        print(f"{mark} 图文[{platform}] {mode} 结束 exit={exit_code}")

    t = threading.Thread(target=monitor_output, daemon=True)
    t.start()
    return 0


def _get_docs_status(platform: str) -> dict:
    """图文平台状态：检测结果（落盘）+ 进行中的子进程 + patchright profile 提示。"""
    cfg = DOCS_REGISTRY[platform]
    persisted = _docs_state.get(platform, {})

    login_state = "idle"
    mode = None
    with _lock:
        proc_info = _login_processes.get(f"docs:{platform}")
        if proc_info and proc_info["state"] == "running":
            login_state = "running"
            mode = proc_info.get("mode")
        elif proc_info and proc_info["state"] in ("success", "failed"):
            login_state = proc_info["state"]

    # patchright runtime 的独立 profile（仅提示；公众号在 docs skill 里目录名是 weixin）
    profile_name = "weixin" if platform == "weixin_mp" else platform
    profile_dir = _ROOT / ".profiles" / profile_name
    has_profile = profile_dir.exists() and (profile_dir / "Default").exists()

    return {
        "platform": platform,
        "display_name": cfg["name"],
        "logged_in": persisted.get("logged_in"),  # None = 从未检测
        "checked_at": persisted.get("checked_at"),
        "login_state": login_state,
        "mode": mode,
        "has_patchright_profile": has_profile,
    }


def _get_platform_status(platform: str) -> dict:
    """获取单个平台的完整状态。"""
    cfg = PLATFORM_REGISTRY[platform]
    account_file = cfg["account_file"]

    has_cookie = False
    cookie_mtime = None
    last_login = None
    login_state = "idle"
    qr_available = False
    last_line = ""

    # cookie / profile 就绪检测
    if account_file and account_file.exists():
        stat = account_file.stat()
        has_cookie = True
        cookie_mtime = stat.st_mtime
        last_login = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    elif platform == "bilibili":
        profile_dir = cfg.get("profile_dir")
        # patchright 初始化过的 profile 会有 Default 子目录
        if profile_dir and profile_dir.exists() and (profile_dir / "Default").exists():
            stat = profile_dir.stat()
            has_cookie = True
            cookie_mtime = stat.st_mtime
            last_login = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

    # 子进程登录状态（所有平台共用，含 bilibili）
    with _lock:
        proc_info = _login_processes.get(platform)
        if proc_info and proc_info["state"] == "running":
            login_state = "running"
            last_line = proc_info.get("last_output", "")
        elif proc_info and proc_info["state"] in ("success", "failed"):
            login_state = proc_info["state"]
            last_line = proc_info.get("last_output", "")

    # 找 QR 图片
    qr_path = _find_latest_qr(platform)
    if qr_path and qr_path.exists():
        qr_available = True

    return {
        "platform": platform,
        "display_name": cfg["name"],
        "has_cookie": has_cookie,
        "cookie_path": str(account_file) if account_file else None,
        "cookie_mtime": cookie_mtime,
        "last_login": last_login,
        "login_state": login_state,
        "qr_available": qr_available,
        "qr_path": str(qr_path) if qr_path else None,
        "bilibili_profile": str(cfg["profile_dir"]) if cfg.get("profile_dir") else None,
        "last_line": last_line,
    }


# ─── HTTP Request Handler ─────────────────────────────────────
class LoginHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass  # 静默日志

    def send_json(self, data: dict, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        # 防止浏览器缓存旧版页面（JS 改动后普通刷新会加载坏页面 → 卡片不渲染）
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def send_image(self, path: Path):
        if not path.exists():
            self.send_error(404, "QR not found")
            return
        content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(data))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "":
            self.handle_home()
        elif path == "/api/status":
            self.handle_api_status()
        elif path == "/api/qr":
            platform = query.get("platform", [None])[0]
            if not platform or platform not in PLATFORM_REGISTRY:
                self.send_json({"error": "Invalid platform"}, 400)
            else:
                qr_path = _find_latest_qr(platform)
                if qr_path and qr_path.exists():
                    self.send_image(qr_path)
                else:
                    self.send_json({"qr_available": False}, 204)
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        if path == "/api/login":
            platform = query.get("platform", [None])[0] or (body.decode("utf-8") if body else None)
            if not platform or platform not in PLATFORM_REGISTRY:
                self.send_json({"error": "Invalid platform"}, 400)
            elif platform == "bilibili":
                # 后台启动 bilibili 浏览器登录（profile 持久化模式）
                with _lock:
                    running = _login_processes.get("bilibili", {}).get("state") == "running"
                if running:
                    self.send_json({
                        "started": False,
                        "message": "bilibili 登录已在进行中，请在弹出的浏览器完成登录",
                    })
                else:
                    threading.Thread(target=_run_bilibili_login, daemon=True).start()
                    self.send_json({
                        "started": True,
                        "platform": "bilibili",
                        "message": "正在打开 bilibili 登录浏览器，请在弹出的窗口登录",
                    })
            elif platform == "youtube":
                # 后台启动 youtube 登录（复用本机 Chrome profile 的登录态，不重新输密码）
                with _lock:
                    running = _login_processes.get("youtube", {}).get("state") == "running"
                if running:
                    self.send_json({
                        "started": False,
                        "message": "YouTube 登录已在进行中，请在弹出的浏览器完成登录",
                    })
                else:
                    threading.Thread(target=_run_youtube_login, daemon=True).start()
                    self.send_json({
                        "started": True,
                        "platform": "youtube",
                        "message": "正在克隆本机 Chrome profile 打开 YouTube（Chrome 无需退出）。若已登录 Google 会自动导出登录态；否则会弹出登录页。",
                    })
            else:
                # 后台启动登录流程（扫码平台：douyin/kuaishou/xiaohongshu/weixin）
                threading.Thread(target=_run_login, args=(platform,), daemon=True).start()
                self.send_json({"started": True, "platform": platform})
        elif path == "/api/check":
            platform = query.get("platform", [None])[0] or (body.decode("utf-8") if body else None)
            if not platform or platform not in PLATFORM_REGISTRY:
                self.send_json({"error": "Invalid platform"}, 400)
            elif platform == "bilibili":
                # bilibili: 跑 bilibili_login.py --check 检查 profile 是否就绪
                cfg = PLATFORM_REGISTRY[platform]
                profile_dir = cfg.get("profile_dir")
                cmd = ["python3", str(_BILIBILI_LOGIN), str(profile_dir), "--check"]
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=15, cwd=str(_ROOT)
                    )
                    out = (result.stdout + result.stderr).strip()
                    valid = result.returncode == 0
                    self.send_json({
                        "valid": valid,
                        "message": out.split("\n")[-1] if out else ("profile 已就绪" if valid else "未找到 profile"),
                    })
                except Exception as e:
                    self.send_json({"valid": False, "message": f"检查失败: {e}"})
            else:
                valid, msg = _run_login_check(platform)
                self.send_json({"valid": valid, "message": msg})
        elif path in ("/api/docs/login", "/api/docs/check"):
            platform = query.get("platform", [None])[0] or (body.decode("utf-8") if body else None)
            if not platform or platform not in DOCS_REGISTRY:
                self.send_json({"error": "Invalid docs platform"}, 400)
            else:
                mode = "login" if path.endswith("/login") else "check"
                key = f"docs:{platform}"
                with _lock:
                    running = _login_processes.get(key, {}).get("state") == "running"
                if running:
                    self.send_json({
                        "started": False,
                        "message": f"{DOCS_REGISTRY[platform]['name']} 已有任务进行中，请先等它完成",
                    })
                else:
                    threading.Thread(target=_run_docs_action, args=(platform, mode), daemon=True).start()
                    msg = (
                        "正在打开登录窗口，请在弹出的窗口中完成登录（检测到后自动关窗）"
                        if mode == "login"
                        else "正在打开窗口检测登录态（检测后自动关窗）"
                    )
                    self.send_json({"started": True, "platform": platform, "mode": mode, "message": msg})
        else:
            self.send_error(404, "Not found")

    # ─── Page Handlers ───────────────────────────────────────────
    def handle_api_status(self):
        """返回所有平台的登录状态 JSON（视频 + 图文）。"""
        statuses = [_get_platform_status(p) for p in PLATFORM_REGISTRY.keys()]
        docs = [_get_docs_status(p) for p in DOCS_REGISTRY.keys()]
        self.send_json({"platforms": statuses, "docs": docs, "docs_shared": DOCS_SHARED})

    def handle_home(self):
        """渲染主页面。"""
        # 收集各平台状态（首次渲染直接注入 HTML，避免 fetch 被代理拦截导致空白）
        statuses = [_get_platform_status(p) for p in PLATFORM_REGISTRY.keys()]
        docs = [_get_docs_status(p) for p in DOCS_REGISTRY.keys()]
        initial_json = json.dumps(
            {"platforms": statuses, "docs": docs, "docs_shared": DOCS_SHARED},
            ensure_ascii=False,
        )

        # 生成 HTML（内嵌 CSS/JS）
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VAAS 登录管理</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0a0a0a;
    color: #e5e7eb;
    padding: 32px;
    max-width: 900px;
    margin: 0 auto;
    line-height: 1.6;
}}
.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 32px;
    flex-wrap: wrap;
    gap: 16px;
}}
h1 {{ font-size: 28px; font-weight: 700; }}
.subtitle {{ color: #6b7280; font-size: 14px; }}
.refresh-btn {{
    background: #2563eb;
    color: white;
    border: none;
    padding: 10px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
}}
.refresh-btn:hover {{ background: #1d4ed8; }}
.platform-card {{
    background: #111;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 16px;
    transition: transform 0.2s, border-color 0.2s;
}}
.platform-card:hover {{ transform: translateY(-2px); border-color: #333; }}
.platform-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}}
.platform-name {{ font-size: 18px; font-weight: 600; }}
.platform-status {{
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 16px;
    font-weight: 500;
}}
.status-logged-in {{ background: #10b98120; color: #34d399; }}
.status-not-logged-in {{ background: #ef444420; color: #f87171; }}
.status-running {{ background: #3b82f620; color: #60a5fa; animation: pulse 1.5s infinite; }}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}
.qr-container {{
    background: #1a1a1a;
    border-radius: 12px;
    padding: 16px;
    margin-top: 12px;
    display: none;
}}
.qr-image {{
    width: 240px;
    height: 240px;
    border: 1px solid #333;
    border-radius: 8px;
    image-rendering: pixelated;
}}
.qr-status {{
    font-size: 12px;
    color: #6b7280;
    margin-top: 8px;
}}
.actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.btn {{
    background: #1f1f1f;
    color: #e5e7eb;
    border: 1px solid #333;
    padding: 8px 16px;
    border-radius: 7px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s;
}}
.btn:hover {{ background: #2a2a2a; border-color: #444; }}
.btn-primary {{ background: #2563eb; border-color: #2563eb; color: white; }}
.btn-primary:hover {{ background: #1d4ed8; }}
.btn-success {{ background: #10b981; border-color: #10b981; color: white; }}
.btn-success:hover {{ background: #059669; }}
.cookie-info {{
    font-size: 11px;
    color: #6b7280;
    margin-top: 8px;
    padding: 8px 12px;
    background: #0a0a0a;
    border-radius: 6px;
    font-family: monospace;
}}
.hint {{
    font-size: 12px;
    color: #9ca3af;
    padding: 12px;
    background: #1a1a1a;
    border-radius: 8px;
    border-left: 3px solid #3b82f6;
    margin-top: 8px;
}}
.section-title {{ font-size: 20px; font-weight: 700; margin: 32px 0 8px; }}
.section-note {{ color: #6b7280; font-size: 13px; margin-bottom: 16px; }}
.tag {{
    font-size: 11px;
    background: #1f1f1f;
    border: 1px solid #333;
    border-radius: 4px;
    padding: 1px 6px;
    color: #9ca3af;
    vertical-align: middle;
    margin-left: 6px;
}}
.nav {{ display: flex; gap: 4px; border-bottom: 1px solid #1f1f1f; margin-bottom: 24px; }}
.nav-tab {{
    background: transparent;
    color: #9ca3af;
    border: none;
    padding: 12px 20px;
    cursor: pointer;
    font-size: 15px;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
}}
.nav-tab:hover {{ color: #e5e7eb; }}
.nav-tab.active {{ color: #60a5fa; border-bottom-color: #3b82f6; }}
.page {{ display: none; }}
.page.active {{ display: block; }}
</style>
</head>
<body>
<div class="header">
    <div>
        <h1>✨ VAAS 登录管理</h1>
        <div class="subtitle">视频 / 图文平台登录状态总览</div>
    </div>
    <button class="refresh-btn" onclick="refreshStatus()">🔄 刷新状态</button>
</div>

<nav class="nav">
    <button class="nav-tab active" onclick="switchPage('video', this)">🎬 视频平台</button>
    <button class="nav-tab" onclick="switchPage('docs', this)">📄 图文平台</button>
</nav>

<div id="page-video" class="page active">
    <div id="platforms"></div>
</div>

<div id="page-docs" class="page">
    <div class="section-note">
        小红书 / 抖音 / 快手图文与视频共享登录态；其余 8 个平台走 patchright（自带 Chromium，跨平台）持久化登录态--
        点「打开窗口登录」弹出浏览器完成登录（检测到后自动关窗），登录态由 patchright profile 持久保存。
    </div>
    <div id="docs-shared"></div>
    <div id="docs-platforms"></div>
</div>

<script>
const platforms = {json.dumps([{"id": k, "name": v["name"]} for k, v in PLATFORM_REGISTRY.items()], ensure_ascii=False)};

function switchPage(name, btn) {{
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('page-' + name).classList.add('active');
    history.replaceState(null, '', '#' + name);
}}

async function fetchStatus() {{
    try {{
        const res = await fetch('/api/status');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return await res.json();
    }} catch (e) {{
        console.error('Fetch status failed:', e);
        return null;
    }}
}}

async function refreshStatus() {{
    const json = await fetchStatus();
    if (!json) {{
        const msg = '<div class="hint" style="border-left-color:#ef4444;">⚠️ 无法连接 /api/status（' + (new Date()).toLocaleTimeString() + '）。可能是系统代理 127.0.0.1:7892 拦截了 localhost — 请在「系统设置 → 网络 → 以太网 → 代理」的 bypass 列表确认含 localhost，或临时关代理后刷新。</div>';
        document.getElementById('platforms').innerHTML = msg;
        document.getElementById('docs-shared').innerHTML = '';
        document.getElementById('docs-platforms').innerHTML = msg;
        return;
    }}
    render(json.platforms || []);
    renderDocs(json);
}}

async function startLogin(platform) {{
    try {{
        const res = await fetch('/api/login?platform=' + platform, {{ method: 'POST' }});
        const result = await res.json();
        console.log('Login started:', result);
    }} catch (e) {{
        alert('启动登录失败：' + e.message);
    }}
}}

async function checkCookie(platform) {{
    try {{
        const res = await fetch('/api/check?platform=' + platform, {{ method: 'POST' }});
        const result = await res.json();
        alert((result.valid ? '✅' : '❌') + ' ' + result.message);
        refreshStatus();
    }} catch (e) {{
        alert('检查失败：' + e.message);
    }}
}}

async function docsAction(platform, mode) {{
    try {{
        const res = await fetch('/api/docs/' + mode + '?platform=' + platform, {{ method: 'POST' }});
        const result = await res.json();
        if (!result.started) {{
            alert(result.message || '操作失败');
        }} else if (mode === 'login') {{
            alert('✅ 登录窗口已弹出：请在弹出的浏览器窗口中完成登录，检测到后自动关窗。');
        }}
        refreshStatus();
    }} catch (e) {{
        alert('操作失败：' + e.message);
    }}
}}

function renderDocs(json) {{
    const sharedIds = json.docs_shared || [];
    const videoStatuses = json.platforms || [];

    // 共享视频 cookie 的 3 个平台：直接镜像视频区状态
    const sharedContainer = document.getElementById('docs-shared');
    sharedContainer.innerHTML = sharedIds.map(id => {{
        const s = videoStatuses.find(v => v.platform === id) || {{ display_name: id }};
        const isLoggedIn = s.has_cookie && s.login_state !== 'running';
        const statusClass = s.login_state === 'running' ? 'status-running'
                          : (isLoggedIn ? 'status-logged-in' : 'status-not-logged-in');
        const statusText = s.login_state === 'running' ? '登录中...'
                         : (isLoggedIn ? '已登录' : '未登录');
        return `
            <div class="platform-card">
                <div class="platform-header">
                    <span class="platform-name">${{s.display_name}}<span class="tag">共享视频登录态</span></span>
                    <span class="platform-status ${{statusClass}}">${{statusText}}</span>
                </div>
                <div class="hint">🔗 图文与视频发布共用同一份 cookie — 在上方「视频平台」区扫码登录即可，无需单独操作。</div>
            </div>`;
    }}).join('');

    // 8 个自有逻辑平台：patchright 检测 / 登录
    const container = document.getElementById('docs-platforms');
    container.innerHTML = (json.docs || []).map(s => {{
        const running = s.login_state === 'running';
        const statusClass = running ? 'status-running'
                          : (s.logged_in === true ? 'status-logged-in' : 'status-not-logged-in');
        const statusText = running ? (s.mode === 'check' ? '检测中…' : '登录中…')
                         : (s.logged_in === true ? '已登录' : (s.logged_in === false ? '未登录' : '未检测'));

        const loginBtn = s.logged_in === true
            ? `<button class="btn" onclick="docsAction('${{s.platform}}', 'login')">重新登录</button>`
            : `<button class="btn btn-primary" onclick="docsAction('${{s.platform}}', 'login')">打开窗口登录</button>`;
        const actions = running
            ? `<button class="btn" disabled>等待完成…</button>`
            : `<button class="btn" onclick="docsAction('${{s.platform}}', 'check')">检查登录态</button>` + loginBtn;

        let info = '';
        const parts = [];
        if (s.checked_at) parts.push('上次检测：' + s.checked_at);
        if (s.has_patchright_profile) parts.push('patchright profile 已就绪');
        if (parts.length) info = `<div class="cookie-info">${{parts.join(' · ')}}</div>`;

        let hint = '';
        if (running && s.mode === 'login') {{
            hint = '<div class="hint">⏳ 请在弹出的浏览器窗口中完成登录（扫码 / 密码 / 短信），检测到后会自动关窗，最多等 10 分钟。</div>';
        }} else if (running) {{
            hint = '<div class="hint">⏳ 正在打开窗口检测登录态，检测后自动关窗。</div>';
        }} else if (s.logged_in === false) {{
            hint = '<div class="hint">💡 点「打开窗口登录」会弹出 patchright Chromium 窗口，登录一次后登录态由 .profiles 持久保存（macOS / Windows 通用）。</div>';
        }}

        return `
            <div class="platform-card">
                <div class="platform-header">
                    <span class="platform-name">${{s.display_name}}</span>
                    <span class="platform-status ${{statusClass}}">${{statusText}}</span>
                </div>
                <div class="actions">${{actions}}</div>
                ${{info}}
                ${{hint}}
            </div>`;
    }}).join('');
}}

function render(statuses) {{
    const container = document.getElementById('platforms');
    container.innerHTML = statuses.map(s => {{
        const isLoggedIn = s.has_cookie && s.login_state !== 'running';
        const statusClass = s.login_state === 'running' ? 'status-running'
                          : (isLoggedIn ? 'status-logged-in' : 'status-not-logged-in');
        const statusText = s.login_state === 'running' ? '登录中...'
                         : (isLoggedIn ? '已登录' : '未登录');

        let actions = '';
        if (s.platform === 'bilibili') {{
            if (s.login_state === 'running') {{
                actions = `<button class="btn" disabled>等待登录…</button><button class="btn" onclick="checkCookie('${{s.platform}}')">检查登录态</button>`;
            }} else if (isLoggedIn) {{
                actions = `<button class="btn btn-success" onclick="checkCookie('${{s.platform}}')">验证登录态</button><button class="btn" onclick="startLogin('${{s.platform}}')">重新登录</button>`;
            }} else {{
                actions = `<button class="btn btn-primary" onclick="startLogin('${{s.platform}}')">打开浏览器登录</button><button class="btn" onclick="checkCookie('${{s.platform}}')">检查登录态</button>`;
            }}
        }} else if (isLoggedIn) {{
            actions = `<button class="btn btn-success" onclick="checkCookie('${{s.platform}}')">验证 Cookie</button>`;
        }} else {{
            actions = `<button class="btn btn-primary" onclick="startLogin('${{s.platform}}')">${{s.login_state === 'running' ? '等待完成...' : (s.platform === 'youtube' ? '用 Chrome 登录' : '扫码登录')}}</button>`;
        }}

        let qrHtml = '';
        if (s.qr_available) {{
            qrHtml = `
                <div class="qr-container" style="display:block;">
                    <img class="qr-image" src="/api/qr?platform=${{s.platform}}" alt="QR Code">
                    <div class="qr-status">请使用手机 APP 扫描上方二维码</div>
                </div>`;
        }}

        let cookieInfo = '';
        if (s.last_login) {{
            cookieInfo = `<div class="cookie-info">最后登录：${{s.last_login}}<br/>路径：${{s.cookie_path}}</div>`;
        }}

        let hint = '';
        if (s.platform === 'youtube' && !isLoggedIn && s.login_state !== 'running') {{
            hint = '<div class="hint">🔑 YouTube 会克隆本机 Chrome profile 继承登录态（Chrome 无需退出）。若 Chrome 里的 Google 会话仍有效则自动导出；已失效会弹出 Google 登录页，登录一次即可，之后发布走导出的登录态。</div>';
        }}
        if (s.platform === 'bilibili' && !isLoggedIn && s.login_state !== 'running') {{
            hint = '<div class="hint">💡 Bilibili 用浏览器 profile 持久化登录：点「打开浏览器登录」会弹一个浏览器，在 bilibili 完成登录后窗口会自动关闭并保存登录态</div>';
        }}
        if (s.login_state === 'running') {{
            hint = '<div class="hint">⏳ 登录进行中，请等待弹窗或继续操作...</div>';
        }}

        return `
            <div class="platform-card">
                <div class="platform-header">
                    <span class="platform-name">${{s.display_name}}</span>
                    <span class="platform-status ${{statusClass}}">${{statusText}}</span>
                </div>
                <div class="actions">${{actions}}</div>
                ${{qrHtml}}
                ${{cookieInfo}}
                ${{hint}}
            </div>`;
    }}).join('');
}}

// 自动轮询（每 3 秒）
refreshStatus();
setInterval(refreshStatus, 3000);

// 按 URL hash 初始化子页面（#docs 直接进图文页）
(function() {{
    const h = location.hash.slice(1);
    if (h === 'docs') {{
        const tabs = document.querySelectorAll('.nav-tab');
        if (tabs[1]) switchPage('docs', tabs[1]);
    }}
}})();
</script>
</body>
</html>"""
        self.send_html(html)


def main():
    _load_docs_state()
    print(f"🚀 VAAS 登录管理页已启动：http://localhost:{PORT}")
    print(f"   Ctrl+C 停止\n")

    try:
        httpd = ThreadedHTTPServer(("127.0.0.1", PORT), LoginHandler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 再见")


if __name__ == "__main__":
    main()

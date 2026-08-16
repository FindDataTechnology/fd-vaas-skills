#!/usr/bin/env python3
"""
YouTube 登录助手 — 复用本机 Chrome 的登录态。

与 sau_adapter 的 youtube_cookie_gen 不同：后者用 `launch + new_context()`，
开的是一个**全新隔离**的 patchright 上下文，看不到用户真实 Chrome 里已登录的
Google/YouTube 账号，被迫重新输密码 + 二步验证。

本脚本复用真实 Chrome profile 的登录态。但有两个坑：

1. 同一 Chrome profile 不能被两个进程同时打开（SingletonLock 冲突）；
2. Chrome 136+ 起，CDP（--remote-debugging-port，patchright/playwright 靠它驱动
   浏览器）在**默认 user-data-dir** 上会被 Chrome 直接忽略 —— 指着真 profile 启动
   会永久 hang。

解法：用 APFS clonefile（`cp -Rc`，写时复制、秒级）把 Chrome profile 克隆到临时
目录，在**克隆体**上启动 Chrome。克隆体不是默认目录 → CDP 正常；cookie 解密密钥
在 macOS Keychain（跟机器/应用绑定，不跟目录绑定）→ 克隆体里 cookie 照常解密，
登录态完整继承。**Chrome 不用退出，可以同时运行。**

打开 YouTube Studio，若已在 Chrome 登录则 URL 落在 /channel/，立即导出
storage_state → account.json，无需重新登录；未登录则等用户在弹出窗口里登录
（登录态同样会导出）。

用法:
  python3 youtube_login.py <account_json_path>          # 复用 Chrome profile 登录
  python3 youtube_login.py <account_json_path> --check  # 只检查 account.json 是否存在
"""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# macOS Chrome 默认 user-data-dir；其下 Default/ 是默认 profile
_CHROME_USER_DATA = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


def _clone_profile() -> Path:
    """把 Chrome profile APFS 克隆到临时目录（写时复制，秒级），返回克隆体路径。"""
    clone_root = Path(tempfile.mkdtemp(prefix="vaas-chrome-clone-"))
    clone = clone_root / "profile"
    r = subprocess.run(
        ["cp", "-Rc", str(_CHROME_USER_DATA), str(clone)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        shutil.rmtree(clone_root, ignore_errors=True)
        raise RuntimeError(f"cp -Rc 克隆失败（非 APFS？）: {r.stderr.strip()}")
    # 克隆体带着源 profile 的单实例锁，不删会拒绝启动
    for f in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        (clone / f).unlink(missing_ok=True)
    return clone


def check(account_file: Path) -> int:
    if account_file.exists() and account_file.stat().st_size > 0:
        print("LOGGED_IN (account.json 已存在)")
        return 0
    print("NOT_LOGGED_IN (account.json 不存在，请先登录)")
    return 1


def run_login(account_file: Path) -> int:
    if not _CHROME_USER_DATA.exists():
        print(f"❌ 找不到 Chrome user-data-dir: {_CHROME_USER_DATA}")
        print("   非 macOS 或 Chrome 未安装在默认位置。可改用 sau_adapter --login 走隔离登录。")
        return 1

    try:
        from patchright.sync_api import sync_playwright
    except ImportError as e:
        print(f"❌ patchright 未安装: {e}")
        return 1

    account_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"▶ 克隆 Chrome profile 并打开 YouTube Studio（继承已有登录态，无需退出 Chrome）")

    clone = None
    try:
        clone = _clone_profile()
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(clone),
                channel="chrome",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 820},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(f"⚠️ goto 未正常完成: {type(e).__name__}")
            time.sleep(3)  # 等跳转/重定向落定
            try:
                print(f"▶ 落地 URL: {page.url}")
            except Exception:
                pass

            # 已在 Chrome 登录 → URL 直接落在 /channel/
            if "/channel/" in page.url:
                print("✅ 检测到已登录 YouTube（继承自 Chrome profile），保存登录态")
            else:
                print("▶ Chrome profile 未登录 YouTube，请在弹出的浏览器里登录 Google")
                print("   登录成功进入频道页后会自动保存（最多等 10 分钟）")

            start = time.time()
            logged = False
            while time.time() - start < 600:
                try:
                    cur = page.url
                except Exception:
                    # 页面/浏览器已关
                    break
                if "/channel/" in cur:
                    time.sleep(2)  # 让 cookie 落定
                    logged = True
                    break
                # 浏览器被用户手动关掉
                try:
                    if not ctx.pages:
                        print("⚠️ 浏览器被关闭，结束")
                        break
                except Exception:
                    break
                time.sleep(2)

            if logged:
                ctx.storage_state(path=str(account_file))
                print(f"✅ YouTube 登录态已保存: {account_file}")
            else:
                print("⚠️ 未检测到登录（超时或浏览器已关闭），未保存")

            try:
                ctx.close()
            except Exception:
                pass
        return 0 if logged else 1
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return 1
    finally:
        if clone is not None:
            shutil.rmtree(clone.parent, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 youtube_login.py <account_json_path> [--check]")
        return 2
    account_file = Path(sys.argv[1]).expanduser()
    if "--check" in sys.argv:
        return check(account_file)
    return run_login(account_file)


if __name__ == "__main__":
    sys.exit(main())

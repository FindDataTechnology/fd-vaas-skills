#!/usr/bin/env python3
"""
Bilibili profile 登录助手。

Bilibili 不走 sau_adapter（上游用 biliup 二进制），而是用 patchright persistent
profile：浏览器打开 bilibili，用户登录后 cookie 写入 profile，发布时复用该 profile
的登录态。

用法:
  python3 bilibili_login.py <profile_dir>          # 有头登录，检测到登录态后自动关闭
  python3 bilibili_login.py <profile_dir> --check  # 只检查 profile 是否就绪（不启浏览器）
"""
import sys
import time
from pathlib import Path


def _profile_ready(profile_dir: Path) -> bool:
    """profile 是否已被一个真实浏览器初始化过（有 Default 子目录）。"""
    return profile_dir.exists() and (profile_dir / "Default").exists()


def check(profile_dir: Path) -> int:
    if _profile_ready(profile_dir):
        print("LOGGED_IN (profile 已就绪)")
        return 0
    print("NOT_LOGGED_IN (profile 不存在，请先登录)")
    return 1


def run_login(profile_dir: Path) -> int:
    try:
        from patchright.sync_api import sync_playwright
    except ImportError as e:
        print(f"❌ patchright 未安装: {e}")
        return 1

    profile_dir.mkdir(parents=True, exist_ok=True)
    print(f"▶ 打开 bilibili（profile: {profile_dir}）")

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 820},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://passport.bilibili.com/login", wait_until="domcontentloaded")
            print("▶ 浏览器已打开 bilibili 登录页，请扫码或输入账号登录")
            print("   登录成功后会自动关闭浏览器（最多等 10 分钟）")

            start = time.time()
            logged = False
            while time.time() - start < 600:
                time.sleep(3)
                # 用户手动关了浏览器 → 结束
                try:
                    if not ctx.pages:
                        print("⚠️ 浏览器被关闭，结束")
                        break
                except Exception:
                    break
                # 检测登录态：bilibili 登录后会种 DedeUserID / SESSDATA cookie
                try:
                    cookies = ctx.cookies("https://www.bilibili.com")
                    names = {c.get("name") for c in cookies}
                    if "DedeUserID" in names or "SESSDATA" in names:
                        logged = True
                        print("✅ 检测到 bilibili 登录态，保存 profile")
                        time.sleep(2)
                        break
                except Exception:
                    pass

            if not logged:
                print("⚠️ 未检测到登录态（超时或浏览器已关闭）")

            try:
                ctx.close()
            except Exception:
                pass
        return 0 if logged else 1
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return 1


def main():
    if len(sys.argv) < 2:
        print("用法: python3 bilibili_login.py <profile_dir> [--check]")
        return 2
    profile_dir = Path(sys.argv[1]).expanduser()
    if "--check" in sys.argv:
        return check(profile_dir)
    return run_login(profile_dir)


if __name__ == "__main__":
    sys.exit(main())

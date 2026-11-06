#!/usr/bin/env python3
"""
Bilibili profile 登录助手。

Bilibili 不走 sau_adapter（上游用 biliup 二进制），而是用 patchright persistent
profile：浏览器打开 bilibili，用户登录后 cookie 写入 profile，发布时复用该 profile
的登录态。

用法:
  python3 bilibili_login.py <profile_dir>          # 有头登录，检测到登录态后自动关闭
  python3 bilibili_login.py <profile_dir> --check  # 会话探针检测登录态（headless，不扫码）
"""
import sys
import time
from pathlib import Path

# 会话探针目标:创作中心（未登录会被重定向到 passport 登录页）。
# 探测原语与 bilibili.py 发布路径同源:页面出现「扫码登录」= 未登录。
_MEMBER_URL = "https://member.bilibili.com/v2#/platform/home"


def _profile_ready(profile_dir: Path) -> bool:
    """profile 是否已被一个真实浏览器初始化过（有 Default 子目录）。

    注意:这只是「目录存在」的粗检,真实登录态由 probe_session 判定(W4.2
    fail-closed:目录存在 ≠ 已登录——cookie 会过期)。
    """
    return profile_dir.exists() and (profile_dir / "Default").exists()


def probe_session(profile_dir: Path) -> bool:
    """真实会话探针:headless 打开创作中心,检查是否仍是登录态。

    判据 = 可观察事实（镜像 docs_login.py 的探针形态）:
      - 未登录页特征（「扫码登录」等字样）出现 → 未登录;
      - 页面加载失败/探针异常 → fail closed（按未登录处理,绝不假绿）。
    """
    if not _profile_ready(profile_dir):
        return False
    try:
        from patchright.sync_api import sync_playwright
    except ImportError as e:
        print(f"⚠️ patchright 未安装，无法探测会话（按未登录处理）: {e}")
        return False
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(_MEMBER_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)  # 等 SPA 渲染/重定向
                body = page.evaluate("document.body ? document.body.innerText.slice(0, 2000) : ''") or ""
                logged_in = not ("扫码登录" in body or "登录" in body[:200] and "退出" not in body)
                # 双保险:有 SESSDATA cookie 才算登录（会话级证据）
                if logged_in:
                    names = {c.get("name") for c in ctx.cookies("https://www.bilibili.com")}
                    logged_in = "SESSDATA" in names or "DedeUserID" in names
                return logged_in
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
    except Exception as e:
        # fail closed:探针异常（网络/浏览器崩溃）= 无法证明已登录 = 未登录
        print(f"⚠️ 会话探针异常（按未登录处理，fail closed）: {e}")
        return False


def check(profile_dir: Path) -> int:
    if not _profile_ready(profile_dir):
        print("NOT_LOGGED_IN (profile 不存在，请先登录)")
        return 1
    # W4.2:目录存在只说明 profile 初始化过,真实登录态以会话探针为准
    if probe_session(profile_dir):
        print("LOGGED_IN (会话探针确认登录态有效)")
        return 0
    print("NOT_LOGGED_IN (会话探针未确认登录态——profile 存在但 cookie 可能已过期，请重新登录)")
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

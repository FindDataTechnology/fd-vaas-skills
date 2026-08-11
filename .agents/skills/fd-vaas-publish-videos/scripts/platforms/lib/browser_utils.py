"""
浏览器自动化通用工具 (patchright 版)

bilibili.py 用的 patchright(sync API) 共享工具。legacy `.mjs` 版已在 Phase 3 删除，
本文件是唯一运行时实现。ego-browser 的 task-space 模型 -> launch_persistent_context + 持久 profile。
handOffTaskSpace/takeOverTaskSpace -> 阻塞 input()（浏览器窗口始终开着，用户直接操作）。
"""

import os
import time
import json

from patchright.sync_api import sync_playwright


def cli_log(msg=""):
    print(msg, flush=True)


def wait(seconds):
    if seconds > 0:
        time.sleep(seconds)


# ─── 浏览器生命周期 ──────────────────────────────────────
class Browser:
    """patchright 持久化上下文。登录态存在 profile_dir，跨次运行复用（同 ego-browser）。"""

    def __init__(self, profile_dir, headless=False, channel=None, viewport=None, proxy=None):
        self.profile_dir = profile_dir
        self.headless = headless
        self.channel = channel  # 'chrome' 用系统 Chrome；None 用 patchright 自带 chromium(stealth)
        self.viewport = viewport or {"width": 1440, "height": 900}
        self.proxy = proxy  # ✅ 支持 HTTP 代理（YouTube 等需翻墙的平台）
        self.pw = None
        self.context = None
        self.page = None

    def __enter__(self):
        os.makedirs(self.profile_dir, exist_ok=True)
        self.pw = sync_playwright().start()
        kwargs = {
            "user_data_dir": self.profile_dir,
            "headless": self.headless,
            "viewport": self.viewport,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if self.channel:
            kwargs["channel"] = self.channel
        # ✅ 代理设置（YouTube 等需要）
        if self.proxy:
            kwargs["proxy"] = {"server": self.proxy}
        self.context = self.pw.chromium.launch_persistent_context(**kwargs)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self

    def __exit__(self, *exc):
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        try:
            if self.pw:
                self.pw.stop()
        except Exception:
            pass

    # ── 原语 ──
    def goto(self, url, wait_until="domcontentloaded", then_wait=0):
        self.page.goto(url, wait_until=wait_until)
        wait(then_wait)

    def eval(self, js, arg=None):
        """页内执行 JS。arg 会作为函数参数传入：用 ([a, b]) => {...} 接收 [a, b]。"""
        if arg is None:
            return self.page.evaluate(js)
        return self.page.evaluate(js, arg)

    def screenshot(self, path=None):
        return self.page.screenshot(path=path)

    def set_input_files(self, selector, path):
        self.page.locator(selector).set_input_files(path)


# ─── 登录检测 ────────────────────────────────────────────
def is_logged_in(b, logged_markers, not_logged_markers, max_chars=1500):
    try:
        text = b.eval(f"document.body.innerText.slice(0, {max_chars})")
    except Exception as e:
        cli_log(f"⚠️  检查登录状态失败: {e}")
        return False
    has_in = any(m in text for m in logged_markers)
    has_out = any(m in text for m in not_logged_markers)
    # ✅ 修复：必须明确看到已登录标记才算登录成功
    # 避免页面加载时空白 → 误判为已登录 → 不等用户扫码就继续
    return has_in


def wait_for_login(b, logged_markers, not_logged_markers,
                   timeout=600, poll=3, hint="请在浏览器中扫码登录"):
    if is_logged_in(b, logged_markers, not_logged_markers):
        return True
    cli_log("⚠️  未检测到登录态")
    cli_log(f"👉  {hint}")
    cli_log("   登录完成后会自动继续，无需输入")
    start = time.time()
    count = 0
    while time.time() - start < timeout:
        wait(poll)
        count += 1
        if is_logged_in(b, logged_markers, not_logged_markers):
            cli_log("✅  登录成功！自动继续执行...")
            return True
        if count % 10 == 0:
            elapsed = round(time.time() - start)
            cli_log(f"⏳  等待登录中... (已等待 {elapsed} 秒)")
    cli_log(f"❌  等待登录超时（{timeout} 秒）")
    return False


# ─── 元素操作 ────────────────────────────────────────────
def click_by_text(b, texts, label, exact=False):
    """在 button/div/span/a 里按文本找并点击。镜像 .mjs 的 clickByText。"""
    text_list = texts if isinstance(texts, list) else [texts]
    js = """
    ([targets, exact]) => {
      const elements = document.querySelectorAll('button, div, span, a, label');
      for (const el of elements) {
        if (!el.offsetParent) continue;
        const text = (el.textContent || '').trim();
        // ✅ 修复：文本太长的跳过（避免匹配到 style/script 标签里的代码）
        if (text.length > 100) continue;
        for (const target of targets) {
          if ((exact && text === target) || (!exact && text.includes(target))) {
            el.click();
            return { found: true, text };
          }
        }
      }
      return { found: false };
    }
    """
    try:
        r = b.eval(js, [text_list, bool(exact)])
        if r and r.get("found"):
            cli_log(f"✅  {label} ({r['text']})")
            wait(1)
            return True
    except Exception as e:
        cli_log(f"⚠️  {label} 点击失败: {e}")
    return False


def safe_fill(b, selector, value, label="fill", use_exec_command=False):
    """填输入框。contenteditable 元素用 execCommand('insertText')。"""
    try:
        if use_exec_command:
            js = """
            ([sel, val]) => {
              const el = document.querySelector(sel);
              if (el) { el.focus(); document.execCommand('insertText', false, val); return true; }
              return false;
            }
            """
            b.eval(js, [selector, value])
        else:
            b.page.locator(selector).fill(value)
        cli_log(f"✅  {label}")
        wait(0.3)
        return True
    except Exception as e:
        cli_log(f"⚠️  {label} 无法自动完成，请手动输入: {e}")
        return False


def upload_file(b, selector, path, retries=2, label="上传文件", first=True):
    """给 file input 设置文件。selector 对应一个 <input type=file>。
    first=True: 多个匹配时取第一个（避免 strict 报错，比如 B站有2个相同 input）
    """
    last = None
    for attempt in range(1, retries + 1):
        try:
            if first:
                b.page.locator(selector).first.set_input_files(path)
            else:
                b.set_input_files(selector, path)
            return True
        except Exception as e:
            last = e
            if attempt < retries:
                cli_log(f"⚠️  {label} 失败 ({attempt}/{retries}): {e}")
                wait(2)
    cli_log(f"⚠️  {label} 失败，可能需手动操作: {last}")
    return False


# ─── selector / keyboard 原语（补 xiaohongshu/bilibili 等用到的）──
def click_selector(b, selector, label="click", timeout=10000):
    """按 CSS / xpath= 选择器点击。镜像 ego-browser 的 click(sel)。"""
    try:
        b.page.locator(selector).first.click(timeout=timeout)
        cli_log(f"✅  {label}")
        return True
    except Exception as e:
        cli_log(f"⚠️  {label} 失败: {e}")
        return False


def fill_input(b, selector, value, label="fill"):
    """填普通 input/textarea。contenteditable 用 safe_fill(use_exec_command=True)。"""
    try:
        b.page.locator(selector).first.fill(value)
        cli_log(f"✅  {label}")
        wait(0.3)
        return True
    except Exception as e:
        cli_log(f"⚠️  {label} 失败: {e}")
        return False


def wait_for_selector(b, selector, timeout=60):
    """等元素出现。timeout 秒。镜像 ego-browser 的 waitForElement。"""
    try:
        b.page.wait_for_selector(selector, timeout=timeout * 1000)
        return True
    except Exception:
        return False


def press_key(b, key):
    b.page.keyboard.press(key)


def type_text(b, text, delay=50):
    b.page.keyboard.type(text, delay=delay)


def page_url(b):
    return b.page.url


# ─── 重试 / 分步 ─────────────────────────────────────────
def with_retry(fn, max_retries=3, name="operation", delay=2):
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < max_retries:
                cli_log(f"⚠️  {name} 失败 (尝试 {attempt}/{max_retries}): {e}")
                cli_log(f"   {delay} 秒后重试...")
                wait(delay)
            else:
                cli_log(f"❌  {name} 失败 (已重试 {max_retries} 次): {e}")
    raise last


class StepRunner:
    def __init__(self):
        self.steps = []
        self.results = []

    def add_step(self, name, fn, required=True, max_retries=2):
        self.steps.append({"name": name, "fn": fn, "required": required, "max_retries": max_retries})
        return self

    def run_all(self):
        cli_log("━" * 41)
        cli_log(f"开始执行流程，共 {len(self.steps)} 个步骤")
        cli_log("━" * 41)
        for i, step in enumerate(self.steps):
            cli_log(f"\n▶ [{i + 1}/{len(self.steps)}] {step['name']}")
            try:
                with_retry(step["fn"], max_retries=step["max_retries"], name=step["name"])
                self.results.append({"step": step["name"], "success": True})
                cli_log(f"✅ {step['name']} 完成")
            except Exception as e:
                self.results.append({"step": step["name"], "success": False, "error": str(e)})
                if step["required"]:
                    cli_log(f"❌ {step['name']} 失败，终止流程")
                    cli_log(f"   错误: {e}")
                    raise
                cli_log(f"⚠️  {step['name']} 失败，继续执行（非必需步骤）")
        cli_log("\n" + "━" * 41)
        cli_log("所有步骤执行完成")
        cli_log("━" * 41)
        return self.results


# ─── 用户交接 ────────────────────────────────────────────
def handoff(msg):
    """阻塞等用户完成手动操作后回车继续。对应 ego-browser 的 handOffTaskSpace。"""
    cli_log("\n" + "━" * 41)
    cli_log("⚠️  需要你操作")
    cli_log("   " + msg)
    cli_log("━" * 41)
    try:
        input("\n👉  完成后按回车继续... ")
    except EOFError:
        # 非交互环境（CI）下不阻塞
        pass


def screenshot_confirm(b, prompt, path=None):
    cli_log("\n📸  截取当前页面...")
    try:
        b.screenshot(path)
    except Exception:
        cli_log("⚠️  截图失败，请直接查看浏览器窗口")
    handoff(prompt)


# ─── profile 目录 ───────────────────────────────────────
def default_profile_dir(platform, vaas_root=None):
    vaas = vaas_root or os.environ.get("VAAS_ROOT") or os.path.expanduser("~/VAAS")
    return os.path.join(vaas, ".profiles", platform)

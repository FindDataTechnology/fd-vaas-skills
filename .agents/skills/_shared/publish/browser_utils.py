"""
浏览器自动化通用工具 (patchright 版)

镜像 lib/browser-utils.mjs，但底层换成 patchright(sync API)。
ego-browser 的 task-space 模型 -> launch_persistent_context + 持久 profile。
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
        # 授予剪贴板权限:paste_text 用 navigator.clipboard.writeText 灌正文(快、保留换行、知乎可渲染 markdown)
        try:
            self.context.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception:
            pass
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


# ─── 非交互(Claude 后台运行)用的等待原语 ──────────────────
def wait_until(predicate, timeout=300, poll=3, hint=""):
    """轮询 predicate() 直到返回 True 或超时。无 stdin 依赖,适配 Claude 非交互 Bash。"""
    start = time.time()
    last_log = 0
    while time.time() - start < timeout:
        try:
            if predicate():
                return True
        except Exception:
            pass
        elapsed = int(time.time() - start)
        if hint and elapsed - last_log >= 30:
            cli_log(f"⏳  {hint} ({elapsed}s)")
            last_log = elapsed
        wait(poll)
    return False


def wait_for_file(path, timeout=600, poll=2, hint=""):
    """轮询直到 path 文件出现(Claude touch 它来放行),出现后删除。无 stdin 依赖。"""
    start = time.time()
    last_log = 0
    while time.time() - start < timeout:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
            return True
        elapsed = int(time.time() - start)
        if hint and elapsed - last_log >= 30:
            cli_log(f"⏳  {hint} ({elapsed}s) - 放行: touch {path}")
            last_log = elapsed
        wait(poll)
    return False


def login_or_wait(b, editor_url, check_fn, timeout=300, hint="请在浏览器扫码登录"):
    """打开编辑器;若 check_fn() 返回 False,提示并轮询等待登录完成,再重新打开编辑器。"""
    b.goto(editor_url, then_wait=4)
    if check_fn():
        return True
    cli_log(f"⚠️  未登录,{hint}")
    ok = wait_until(check_fn, timeout=timeout, poll=3, hint=hint)
    if ok:
        b.goto(editor_url, then_wait=4)
    return ok and check_fn()


def confirm_gate(b, confirm_file, screenshot_path=None, hint="确认发布", timeout=7200):
    """发布前确认门:截图(可选存路径给 Claude 读取)-> 轮询等待 confirm_file 出现 -> 放行。

    无 stdin 依赖:Claude 在后台跑该脚本,看到「等待确认」后问你,你说确认 -> Claude touch confirm_file。
    """
    if screenshot_path:
        try:
            b.screenshot(screenshot_path)
            cli_log(f"📸  预览截图已存: {screenshot_path}")
        except Exception:
            cli_log("⚠️  截图失败,请直接看浏览器窗口")
    cli_log(f"⏸️  等待你确认 {hint}:touch {confirm_file}")
    if not wait_for_file(confirm_file, timeout=timeout, poll=2, hint=f"等待确认 {hint}"):
        cli_log(f"⚠️  确认超时({timeout}s),未发布")
        return False
    cli_log(f"▶  收到放行信号,继续 {hint}")
    return True


# ─── profile 目录 ───────────────────────────────────────
def default_profile_dir(platform, vaas_root=None):
    vaas = vaas_root or os.environ.get("VAAS_ROOT") or os.path.expanduser("~/VAAS")
    return os.path.join(vaas, ".profiles", platform)


# ─── 正文灌入(剪贴板粘贴优先)────────────────────────────
def _mod_key():
    """macOS 用 Meta,Windows/Linux 用 Control。"""
    import sys
    return "Meta" if sys.platform == "darwin" else "Control"


def paste_text(b, text, editor_selector=None, select_all_first=True, label="正文"):
    """把 text 灌进当前页面 contenteditable 编辑器。

    优先剪贴板粘贴(瞬时、保留换行;知乎专栏还能渲染 markdown);
    失败回退 execCommand('insertText');再失败回退逐行 typeText(慢但兜底)。
    """
    mod = _mod_key()
    # 1) 聚焦编辑器
    if editor_selector:
        try:
            b.page.locator(editor_selector).first.click(timeout=8000)
            wait(0.3)
        except Exception as e:
            cli_log(f"⚠️  {label}: 聚焦编辑器失败 {e}")
    if select_all_first:
        try:
            b.page.keyboard.press(f"{mod}+a")
            wait(0.1)
        except Exception:
            pass
    # 2) 写剪贴板
    ok = False
    try:
        b.page.evaluate("(t)=>navigator.clipboard.writeText(t)", text)
        ok = True
    except Exception as e:
        cli_log(f"⚠️  {label}: clipboard.writeText 失败,尝试 pbcopy: {e}")
    if not ok and _mod_key() == "Meta":
        try:
            import subprocess
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            ok = True
        except Exception as e:
            cli_log(f"⚠️  {label}: pbcopy 失败: {e}")
    # 3) 粘贴
    if ok:
        try:
            b.page.keyboard.press(f"{mod}+v")
            wait(1.2)
            cli_log(f"✅  {label}: 已粘贴({len(text)} 字)")
            return "paste"
        except Exception as e:
            cli_log(f"⚠️  {label}: 粘贴失败,回退 insertText: {e}")
    # 4) 回退:execCommand insertText
    try:
        js = """
        ([sel, val]) => {
          const el = sel ? document.querySelector(sel) : document.activeElement;
          if (!el) return 'no-el';
          el.focus();
          document.execCommand('selectAll', false, null);
          document.execCommand('insertText', false, val);
          return 'insertText';
        }
        """
        r = b.eval(js, [editor_selector, text])
        if r and r != "no-el":
            cli_log(f"✅  {label}: insertText({len(text)} 字)")
            return r
    except Exception as e:
        cli_log(f"⚠️  {label}: insertText 失败,回退 typeText: {e}")
    # 5) 最后兜底:逐行 typeText
    try:
        for line in text.split("\n")[:300]:
            if line.strip():
                b.page.keyboard.type(line, delay=5)
            b.page.keyboard.press("Enter")
        cli_log(f"✅  {label}: typeText 逐行({len(text)} 字)")
        return "typeText"
    except Exception as e:
        cli_log(f"❌  {label}: 全部灌入方式失败: {e}")
        return "failed"


def fill_title(b, selector, title, label="标题"):
    """填标题:点击 -> 全选删 -> 填值(普通 input/textarea 用 fill,contenteditable 用 paste)。"""
    try:
        loc = b.page.locator(selector).first
        loc.click(timeout=10000)
        wait(0.3)
        # 先试 fill(普通 input/textarea)
        try:
            loc.fill(title)
            cli_log(f"✅  {label}: {title[:40]}")
            return True
        except Exception:
            pass
        # contenteditable:全选删 -> 粘贴
        mod = _mod_key()
        b.page.keyboard.press(f"{mod}+a")
        b.page.keyboard.press("Delete")
        return paste_text(b, title, editor_selector=selector, select_all_first=False, label=label) != "failed"
    except Exception as e:
        cli_log(f"⚠️  {label} 填写失败: {e}")
        return False


def fill_hidden(b, selector, value, label="填隐藏域"):
    """填 hidden input/textarea(如公众号 #title):locator.fill 对不可见元素超时,直接 js 赋值 + input 事件。"""
    try:
        js = """
        ([sel, val]) => {
          const el = document.querySelector(sel);
          if (!el) return false;
          el.value = val;
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        }
        """
        if b.eval(js, [selector, value]):
            cli_log(f"✅  {label}(js): {value[:40]}")
            return True
        cli_log(f"⚠️  {label}: 未找到 {selector}")
        return False
    except Exception as e:
        cli_log(f"⚠️  {label} 失败: {e}")
        return False


def paste_html(b, text, editor_selector, label="正文"):
    """按行转 <p> 后用 text/html 剪贴板粘贴 —— ProseMirror 类编辑器(公众号)粘纯文本会丢 \\n。

    每行 -> <p>line</p>,空行 -> <p><br></p>;ClipboardItem({'text/html': blob}) 写入,再 Mod+v。
    失败回退 paste_text(可能丢换行,但内容能进)。
    """
    import html as _html
    lines = text.split("\n")
    html_body = "".join(
        f"<p>{_html.escape(l)}</p>" if l.strip() else "<p><br></p>" for l in lines
    )
    mod = _mod_key()
    try:
        b.page.locator(editor_selector).first.click(timeout=8000)
        wait(0.3)
        b.page.keyboard.press(f"{mod}+a")
        b.page.keyboard.press("Delete")
        js = """
        async (htmlStr) => {
          const blob = new Blob([htmlStr], { type: 'text/html' });
          await navigator.clipboard.write([new ClipboardItem({ 'text/html': blob })]);
          return true;
        }
        """
        b.eval(js, html_body)
        b.page.keyboard.press(f"{mod}+v")
        wait(1.5)
        cli_log(f"✅  {label}: HTML 粘贴({len(text)} 字, {len(lines)} 行)")
        return True
    except Exception as e:
        cli_log(f"⚠️  {label}: HTML 粘贴失败({e}),回退纯文本粘贴")
        return paste_text(b, text, editor_selector=editor_selector, label=label) != "failed"


def upload_images(b, selector, paths, label="上传图片"):
    """给 input[type=file] 设置一张或多张图。paths 可为 str 或 list。"""
    if isinstance(paths, str):
        paths = [paths]
    paths = [p for p in paths if p and os.path.exists(p)]
    if not paths:
        cli_log(f"⚠️  {label}: 无有效图片路径")
        return False
    try:
        b.page.locator(selector).first.set_input_files(paths)
        cli_log(f"✅  {label}: {len(paths)} 张")
        return True
    except Exception as e:
        cli_log(f"⚠️  {label} 失败: {e}")
        return False


def readback(b, selector, n=80, label="正文读回"):
    """读 contenteditable 编辑器前 n 字,确认正文落位。"""
    try:
        js = """
        (sel) => {
          const el = document.querySelector(sel)
            || document.querySelector('iframe')?.contentDocument?.querySelector('[contenteditable="true"]');
          return (el?.innerText || '').slice(0, 80);
        }
        """
        r = b.eval(js, selector)
        cli_log(f"📋  {label}: {r}")
        return r
    except Exception as e:
        cli_log(f"⚠️  {label} 失败: {e}")
        return ""


def publish_and_verify(b, click_texts, url_pattern, label="发布", timeout=30, auto_publish=False,
                       confirm_file=None, screenshot_path=None):
    """点发布按钮(文本匹配)并按 URL 正则验证。

    confirm_file 给定(Claude 非交互后台):用 confirm_gate 截图+等 sentinel 放行。
    confirm_file 为 None(TTY):用 screenshot_confirm(input 回车)。
    auto_publish=True:跳过确认门直接点。"""
    if not auto_publish:
        if confirm_file:
            if not confirm_gate(b, confirm_file, screenshot_path=screenshot_path, hint=label):
                return False, b.page.url
        else:
            screenshot_confirm(b, f"检查标题/正文/封面/标签无误后,回复或回车继续点「{label}」;或自己在浏览器点发布后回车")
    ok = click_by_text(b, click_texts, label, exact=False)
    if not ok:
        cli_log(f"⚠️  未找到「{label}」按钮,请在浏览器手动点击")
        if confirm_file:
            cli_log(f"⏸️  手动点完后 touch {confirm_file} 让脚本继续验证")
            wait_for_file(confirm_file, timeout=300, hint="等待手动发布")
        else:
            handoff(f"请在浏览器手动点「{label}」,完成后回车继续")
    # 验证 URL
    for _ in range(timeout):
        wait(1)
        url = b.page.url
        if url_pattern.search(url):
            cli_log(f"✅  {label} 成功: {url}")
            return True, url
    cli_log(f"⚠️  {label} 未在 {timeout}s 内确认成功(当前 URL: {b.page.url})")
    return False, b.page.url

#!/usr/bin/env python3
"""
note_adapter.py — 图文笔记薄适配层：复用 fd-vaas-publish-videos vendored 的 social-auto-upload 上游。

原则（用户定）：上游有图文(Note)实现的平台走这里，没有的平台才用自己的逻辑。
当前上游覆盖：
  - xiaohongshu → XiaoHongShuNote（标题≤20、正文≤1000、图片必填）
  - douyin      → DouYinNote（标题≤20、正文≤1000、图片≤35 必填，可带 bgm）
  - kuaishou    → KSNote（标题≤20、图片必填）
上游 TencentNote（视频号图文）是 skeleton（switch_to_note_mode 未实现）→ 不可用，不注册。

上游目录不重复 vendor：直接引用兄弟 skill 的
  ../../fd-vaas-publish-videos/scripts/upstream
登录态与视频发布共享同一 account.json（cookies/<platform>_uploader/account.json）——
在 fd-vaas-login 或 sau_adapter 扫过一次码，视频+图文通用。

用法：
  # 发布图文（图片必填，逗号分隔多张）
  python3 note_adapter.py --platform xiaohongshu --title "..." --note-file body.txt --images "a.jpg,b.jpg" --tags "x,y"
  # 登录（与视频发布同一 cookie，已登录过会提示）
  python3 note_adapter.py --platform douyin --login
  # 校验 cookie
  python3 note_adapter.py --platform xiaohongshu --login-check

发布确认闸（enforce-publish-confirmation-gate W1.3）：
  上游图文路径同样 MUST 过人工确认闸才允许真实上传——与自有 patchright 平台
  (browser_utils.confirm_gate) 同形态：给 --confirm-file 哨兵(如
  <系统临时目录>/vaas-doc-<platform>.go，touch 即放行)，未给且非 TTY 即失败关闭；
  --auto-publish 为显式旁路(回执须标注 auto_publish)。
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import importlib
import os
import sys
import tempfile
from pathlib import Path

# ── 定位兄弟 skill 的 vendor 上游并加入 sys.path ─────────────
_HERE = Path(__file__).resolve().parent          # fd-vaas-publish-docs/scripts/
_SKILLS = _HERE.parents[1]                        # .agents/skills/
_UPSTREAM = _SKILLS / "fd-vaas-publish-videos" / "scripts" / "upstream"
if not (_UPSTREAM / "uploader").is_dir():
    print(f"❌ 找不到 vendored 上游: {_UPSTREAM}")
    print("   图文上游实现依赖 fd-vaas-publish-videos skill 的 scripts/upstream/，")
    print("   请确认该 skill 已安装（.agents/skills/fd-vaas-publish-videos/）。")
    sys.exit(1)
if str(_UPSTREAM) not in sys.path:
    sys.path.insert(0, str(_UPSTREAM))

# 共享发布库（browser_utils.confirm_gate——与自有平台同形态的确认闸单一实现源）
_SHARED_PUBLISH = _SKILLS / "_shared" / "publish"
if str(_SHARED_PUBLISH) not in sys.path:
    sys.path.insert(0, str(_SHARED_PUBLISH))

# 与 sau_adapter.py 一致：conf.BASE_DIR = scripts/upstream/
os.environ.setdefault("VAAS_ROOT", str(_UPSTREAM.parents[3]))

# ── 平台注册表（account_file 相对 upstream/ 根，与视频发布共享） ──
REGISTRY = {
    "xiaohongshu": {
        "module": "uploader.xiaohongshu_uploader.main",
        "note_class": "XiaoHongShuNote",
        "login_setup": "xiaohongshu_setup",
        "account_file": "cookies/xiaohongshu_uploader/account.json",
        "title_max": 20,
        "note_max": 1000,
        "max_images": 9,
    },
    "douyin": {
        "module": "uploader.douyin_uploader.main",
        "note_class": "DouYinNote",
        "login_setup": "douyin_setup",
        "account_file": "cookies/douyin_uploader/account.json",
        "title_max": 20,
        "note_max": 1000,
        "max_images": 35,
    },
    "kuaishou": {
        "module": "uploader.ks_uploader.main",
        "note_class": "KSNote",
        "login_setup": "ks_setup",
        # 与视频发布(sau_adapter)同一文件:快手视频/图文共享登录态
        "account_file": "cookies/kuaishou_creator/account.json",
        "title_max": 20,
        "note_max": 0,  # 上游无硬限
        "max_images": 0,  # 上游无硬限
    },
}


def _account_path(platform: str) -> Path:
    path = _UPSTREAM / REGISTRY[platform]["account_file"]
    if not path.exists() and platform == "kuaishou":
        # 迁移兼容：旧路径 cookies/kuaishou_creator.json（与视频侧同一文件，语义一致）
        legacy = _UPSTREAM / "cookies" / "kuaishou_creator.json"
        if legacy.exists():
            return legacy
    return path


# ── 发布确认闸（W1.3）：与自有 patchright 平台同一实现源（browser_utils.confirm_gate）──
# browser_utils 顶层 import patchright，故闸在发布路径里惰性加载；
# 加载失败 = 失败关闭（无闸可依赖时绝不放行），绝不静默裸奔。
def gate_file(platform: str, explicit: str = "") -> str:
    """确认哨兵路径：--confirm-file 优先；缺省 <系统临时目录>/vaas-doc-<platform>.go。

    W5.1：不硬编码 POSIX /tmp——VAAS_GATE_DIR env 覆盖 ?? tempfile.gettempdir()，
    与 confirm-gate.mjs / browser_utils.default_gate_file 同命名同语义。
    """
    e = (explicit or "").strip()
    if e:
        return e
    base = os.environ.get("VAAS_GATE_DIR") or tempfile.gettempdir()
    return os.path.join(base, f"vaas-doc-{platform}.go")


def gate_publish(platform: str, confirm_file: str, auto_publish: bool, timeout: int = 7200) -> bool:
    """真实上传前的人工确认闸。返回 True=放行，False=拒绝（调用方必须 exit 非零、零上传）。

    - auto_publish: 显式旁路参数才存在（--auto-publish）；回执必须标注 auto_publish。
    - confirm_file 空 → 解析成默认哨兵路径（不拿空串去挂满 timeout）。
    - 哨兵出现=确认放行（消费删除）；超时=拒绝，不存在「超时后自动发布」。
    """
    if auto_publish:
        print("⚠️ --auto-publish 显式旁路人工确认闸（distribution 回执须标注 auto_publish: true）")
        return True
    credential = gate_file(platform, confirm_file)
    try:
        from browser_utils import confirm_gate  # noqa: 惰性:login/login-check 路径不依赖 patchright
    except Exception as e:
        print(f"❌ 确认闸共享实现 browser_utils 加载失败——按未确认处理(fail closed): {e}")
        return False
    return confirm_gate(None, credential, hint=f"发布 {platform} 图文", timeout=timeout)


def _parse_schedule(s: str | None) -> tuple[_dt.datetime | int, str]:
    """返回 (publish_date, strategy_value)。strategy_value ∈ immediate/scheduled。"""
    if not s:
        return 0, "immediate"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return _dt.datetime.strptime(s.strip(), fmt), "scheduled"
        except ValueError:
            continue
    raise ValueError(f"无法解析 --schedule: {s}（期望 YYYY-MM-DD HH:MM）")


def _resolve_strategy_const(mod, platform: str, strategy_value: str):
    prefix = {"xiaohongshu": "XIAOHONGSHU", "douyin": "DOUYIN", "kuaishou": "KUAISHOU"}[platform]
    suffix = "IMMEDIATE" if strategy_value == "immediate" else "SCHEDULED"
    return getattr(mod, f"{prefix}_PUBLISH_STRATEGY_{suffix}", strategy_value)


def _load_module(platform: str):
    return importlib.import_module(REGISTRY[platform]["module"])


def do_login(platform: str, headless: bool) -> int:
    """调上游 <platform>_setup 扫码登录（与视频发布同一 account.json）。"""
    cfg = REGISTRY[platform]
    mod = _load_module(platform)
    setup = getattr(mod, cfg["login_setup"])
    account_file = str(_account_path(platform))
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)
    print(f"▶ {platform} 扫码登录 → {account_file}（与视频发布共享）")
    result = asyncio.run(setup(account_file, handle=True, headless=headless))
    if isinstance(result, dict):
        ok = result.get("success", False)
        print(("✅ 登录成功" if ok else "❌ 登录失败") + f": {result.get('message', '')}")
        return 0 if ok else 1
    print("✅ 登录成功" if result else "❌ 登录失败")
    return 0 if result else 1


def do_login_check(platform: str) -> int:
    cfg = REGISTRY[platform]
    account_file = _account_path(platform)
    if not account_file.exists():
        print(f"❌ cookie 不存在: {account_file}（先在 fd-vaas-login 扫码，或 --login）")
        return 1
    mod = _load_module(platform)
    cookie_auth = getattr(mod, "cookie_auth", None)
    if cookie_auth is None:
        print("⚠ 该平台上游无 cookie_auth，跳过校验（cookie 文件存在）")
        return 0
    import inspect
    ok = asyncio.run(cookie_auth(str(account_file))) if inspect.iscoroutinefunction(cookie_auth) else cookie_auth(str(account_file))
    print("✅ cookie 有效" if ok else "❌ cookie 已失效，请重新扫码")
    return 0 if ok else 1


def do_publish(args) -> int:
    platform = args.platform
    cfg = REGISTRY[platform]
    account_file = _account_path(platform)

    if not account_file.exists():
        print(f"❌ cookie 不存在: {account_file}")
        print(f"  先在 fd-vaas-login (localhost:8766) 扫码，或: python3 {Path(__file__).name} --platform {platform} --login")
        return 1

    # 图片：必填，逗号分隔
    images = [s.strip() for s in (args.images or "").split(",") if s.strip()]
    images = [s for s in images if Path(s).exists()]
    if not images:
        print(f"❌ 图文发布必须给图片（--images a.jpg,b.jpg），且文件要存在。收到: {args.images or '(空)'}")
        return 1
    if cfg["max_images"] and len(images) > cfg["max_images"]:
        print(f"⚠️ 图片 {len(images)} 张 > 上限 {cfg['max_images']}，截取前 {cfg['max_images']} 张")
        images = images[: cfg["max_images"]]

    # 正文
    if args.note_file:
        note = Path(args.note_file).read_text(encoding="utf-8").strip()
    else:
        note = (args.note or "").strip()
    if cfg["note_max"] and len(note) > cfg["note_max"]:
        print(f"⚠️ 正文 {len(note)} > {cfg['note_max']} 字，截断")
        note = note[: cfg["note_max"] - 1] + "…"

    # 标题：必填，≤20
    title = (args.title or "").strip() or note[: cfg["title_max"]]
    if len(title) > cfg["title_max"]:
        print(f"⚠️ 标题 {len(title)} > {cfg['title_max']} 字，截断")
        title = title[: cfg["title_max"] - 1] + "…"

    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]

    mod = _load_module(platform)
    NoteCls = getattr(mod, cfg["note_class"])
    publish_date, strategy_value = _parse_schedule(args.schedule)
    publish_strategy = _resolve_strategy_const(mod, platform, strategy_value)

    kwargs = dict(
        image_paths=images,
        note=note,
        tags=tags,
        publish_date=publish_date,
        account_file=str(account_file),
        title=title,
        publish_strategy=publish_strategy,
        headless=args.headless,
    )
    if platform == "douyin" and args.bgm:
        kwargs["bgm"] = args.bgm

    print(f"\n━━━ {platform} 上游图文发布 ━━━")
    print(f"  标题:   {title}")
    print(f"  正文:   {len(note)} 字")
    print(f"  图片:   {len(images)} 张")
    print(f"  标签:   {tags or []}")
    print(f"  cookie: {account_file}（与视频发布共享）")
    print(f"  策略:   {strategy_value}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if args.dry_run:
        print("🔍 dry-run：参数已就绪，不执行上传")
        return 0

    # W1.3：人工确认闸——放在构造/启动上游浏览器之前，未确认时零上传请求发出
    if not gate_publish(platform, args.confirm_file, args.auto_publish):
        print(f"❌ {platform} 图文未获人工确认，已拒绝（零上传）。补齐方法见上方确认闸提示。")
        return 1

    try:
        app = NoteCls(**kwargs)
    except TypeError as e:
        print(f"❌ 构造 {cfg['note_class']} 失败（上游签名可能已变，跑 fd-vaas-publish-videos 的 sync-upstream.sh）: {e}")
        return 2

    try:
        asyncio.run(app.main())
        print(f"\n✅ {platform} 图文发布流程结束")
        return 0
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        print(f"\n❌ {platform} 图文发布失败: {e}")
        traceback.print_exc()
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="图文笔记薄适配层（复用 fd-vaas-publish-videos 的上游 Note 实现）")
    ap.add_argument("--platform", required=True, choices=list(REGISTRY.keys()))
    ap.add_argument("--title", help="标题（≤20 字，必填；缺省取正文前 20 字）")
    ap.add_argument("--note", default="", help="正文（直接传文本）")
    ap.add_argument("--note-file", help="正文文件（优先于 --note）")
    ap.add_argument("--images", default="", help="图片路径，逗号分隔（必填）")
    ap.add_argument("--tags", default="", help="标签，逗号分隔")
    ap.add_argument("--bgm", default="", help="背景音乐（douyin）")
    ap.add_argument("--schedule", default="", help="定时发布 YYYY-MM-DD HH:MM")
    ap.add_argument("--headless", action="store_true", help="无头模式（默认 headed 便于处理验证码）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--login", action="store_true", help="扫码登录（与视频发布共享 cookie）")
    ap.add_argument("--login-check", action="store_true", help="只校验 cookie 是否有效")
    # W1.3 确认闸参数（与自有平台 patchright 脚本同形态）
    ap.add_argument("--confirm-file", default="", help="人工确认哨兵文件（touch 即放行；缺省用系统临时目录 vaas-doc-<platform>.go）")
    ap.add_argument("--auto-publish", action="store_true", help="显式旁路人工确认闸（回执须标注 auto_publish）")
    args = ap.parse_args()

    if args.login:
        return do_login(args.platform, args.headless)
    if args.login_check:
        return do_login_check(args.platform)
    return do_publish(args)


if __name__ == "__main__":
    sys.exit(main())

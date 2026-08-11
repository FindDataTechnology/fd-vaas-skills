#!/usr/bin/env python3
"""
sau_adapter.py — 薄适配层：把 VAAS 的发布 CLI 翻译成 social-auto-upload 上游构造调用。

这是「Vendor + 薄适配层」的适配层。上游 uploader/ 是 canonical（sync-upstream.sh 同步），
本文件只做三件事：
  1. 把 --file/--title/--desc/--tags/--cover*/--thumbnail/--schedule 翻译成
     上游 <Platform>Video(title, file_path, tags, publish_date, account_file,
                           thumbnail_path, desc, ...) 构造参数
  2. 解析 account_file（cookies/<platform>_uploader/account.json）；缺失就提示 --login
  3. asyncio.run(app.main()) 跑上游的发布流程

CLI 与原 <platform>.py 保持兼容（publish.mjs 无需改参数组装），只是 runtime 入口换了。

支持的 Playwright 平台：xiaohongshu / douyin / kuaishou / weixin / youtube
bilibili 走上游 biliup 二进制（非 Playwright），本适配层暂不覆盖，仍由原 bilibili.py 处理。

用法：
  # 发布
  python3 sau_adapter.py --platform xiaohongshu --file x.mp4 --title "..." --desc "..." --tags "a,b" --cover c.jpg
  # 登录（扫码，生成 cookies/<platform>_uploader/account.json）
  python3 sau_adapter.py --platform xiaohongshu --login
  # 从已有 .profiles/<platform>/ 迁移登录态到 cookies JSON
  python3 sau_adapter.py --platform xiaohongshu --migrate-profile
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import importlib
import os
import sys
from pathlib import Path

# ── 定位上游 vendor 目录并加入 sys.path ──────────────────────
_HERE = Path(__file__).resolve().parent
_UPSTREAM = _HERE.parent / "upstream"  # scripts/upstream/
if str(_UPSTREAM) not in sys.path:
    sys.path.insert(0, str(_UPSTREAM))

# conf.BASE_DIR = scripts/upstream/，上游 uploader/__init__ 会在 cookies/ 建目录
os.environ.setdefault("VAAS_ROOT", str(_UPSTREAM.parents[3]))

# ── 平台注册表 ───────────────────────────────────────────────
# account_file 相对 upstream/ 根；thumbnail 映射决定 --cover/--thumbnail 进哪个构造参数
REGISTRY = {
    "xiaohongshu": {
        "module": "uploader.xiaohongshu_uploader.main",
        "video_class": "XiaoHongShuVideo",
        "login_setup": "xiaohongshu_setup",
        "account_file": "cookies/xiaohongshu_uploader/account.json",
        "thumb_mode": "single",  # thumbnail_path
    },
    "douyin": {
        "module": "uploader.douyin_uploader.main",
        "video_class": "DouYinVideo",
        "login_setup": "douyin_setup",
        "account_file": "cookies/douyin_uploader/account.json",
        "thumb_mode": "dual",  # thumbnail_landscape_path + thumbnail_portrait_path
    },
    "kuaishou": {
        "module": "uploader.ks_uploader.main",
        "video_class": "KSVideo",
        "login_setup": "ks_setup",
        "account_file": "cookies/kuaishou_creator.json",
        "thumb_mode": "single",
    },
    "weixin": {
        "module": "uploader.tencent_uploader.main",
        "video_class": "TencentVideo",
        "login_setup": "tencent_setup",
        "account_file": "cookies/tencent_uploader/account.json",
        "thumb_mode": "single",
    },
    "youtube": {
        "module": "uploader.youtube_uploader.main",
        "video_class": "YouTubeVideo",
        "login_setup": "youtube_setup",
        "account_file": "cookies/youtube_uploader/account.json",
        "thumb_mode": "youtube",  # thumbnail_path + visibility
    },
}


def _account_path(platform: str) -> Path:
    rel = REGISTRY[platform]["account_file"]
    return _UPSTREAM / rel


def _parse_schedule(s: str | None) -> tuple[_dt.datetime | int, str, str]:
    """返回 (publish_date, strategy_const_name, strategy_value)。
    strategy_const_name 是上游模块里的常量名，strategy_value 是 immediate/scheduled。"""
    if not s:
        return 0, None, "immediate"
    # 支持 "YYYY-MM-DD HH:MM" 或 "YYYY-MM-DD HH:MM:SS"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = _dt.datetime.strptime(s.strip(), fmt)
            return dt, None, "scheduled"
        except ValueError:
            continue
    raise ValueError(f"无法解析 --schedule: {s}（期望 YYYY-MM-DD HH:MM）")


def _resolve_strategy_const(mod, platform: str, strategy_value: str):
    """从上游模块里取 *_PUBLISH_STRATEGY_IMMEDIATE/SCHEDULED 常量。"""
    if strategy_value == "immediate":
        suffix = "IMMEDIATE"
    else:
        suffix = "SCHEDULED"
    # 模块常量前缀：XIAOHONGSHU / DOUYIN / KUAISHOU / TENCENT（weixin 走 tencent）
    prefix_map = {
        "xiaohongshu": "XIAOHONGSHU",
        "douyin": "DOUYIN",
        "kuaishou": "KUAISHOU",
        "weixin": "TENCENT",
        "youtube": "YOUTUBE",
    }
    name = f"{prefix_map[platform]}_PUBLISH_STRATEGY_{suffix}"
    return getattr(mod, name, strategy_value)


def _build_thumb_kwargs(platform: str, args) -> dict:
    mode = REGISTRY[platform]["thumb_mode"]
    kw = {}
    if mode == "single":
        if args.cover:
            kw["thumbnail_path"] = args.cover
    elif mode == "dual":  # douyin
        if args.cover_horizontal:
            kw["thumbnail_landscape_path"] = args.cover_horizontal
        if args.cover_vertical:
            kw["thumbnail_portrait_path"] = args.cover_vertical
        # 单传 --cover 时当竖封面
        if args.cover and not args.cover_vertical:
            kw["thumbnail_portrait_path"] = args.cover
    elif mode == "youtube":
        if args.thumbnail:
            kw["thumbnail_path"] = args.thumbnail
        elif args.cover:
            kw["thumbnail_path"] = args.cover
        if args.visibility:
            kw["visibility"] = args.visibility
    return kw


def do_login(platform: str, headless: bool) -> int:
    """调上游 <platform>_setup(account_file, handle=True) 走扫码登录。"""
    cfg = REGISTRY[platform]
    mod = importlib.import_module(cfg["module"])
    setup = getattr(mod, cfg["login_setup"])
    account_file = str(_account_path(platform))
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)
    print(f"▶ {platform} 扫码登录 → {account_file}")
    # 上游 setup 签名：setup(account_file, handle=False, return_detail=False, headless=...)
    result = asyncio.run(setup(account_file, handle=True, headless=headless))
    if isinstance(result, dict):
        ok = result.get("success", False)
        print(("✅ 登录成功" if ok else "❌ 登录失败") + f": {result.get('message','')}")
        return 0 if ok else 1
    print("✅ 登录成功" if result else "❌ 登录失败")
    return 0 if result else 1


def do_migrate_profile(platform: str) -> int:
    """从 .profiles/<platform>/ 持久 profile 导出 storage_state → cookies JSON。"""
    try:
        from patchright.sync_api import sync_playwright
    except ImportError:
        print("❌ 需先安装 patchright: pip install patchright && patchright install chromium")
        return 1

    vaas = Path(os.environ.get("VAAS_ROOT", os.getcwd())).resolve()
    # .profiles 在 scripts/platforms/.profiles/<platform> 或 scripts/.profiles/<platform>
    candidates = [
        _HERE / ".profiles" / platform,
        _HERE.parent / ".profiles" / platform,
    ]
    profile = next((c for c in candidates if c.exists()), None)
    if not profile:
        print(f"❌ 找不到 .profiles/{platform}/，无法迁移。请改用 --login 扫码登录。")
        return 1

    account_file = _account_path(platform)
    account_file.parent.mkdir(parents=True, exist_ok=True)

    # 平台域名（导出 cookie 前先访问，确保 cookie 落到 context）
    domains = {
        "xiaohongshu": "https://creator.xiaohongshu.com",
        "douyin": "https://creator.douyin.com",
        "kuaishou": "https://cp.kuaishou.com",
        "weixin": "https://channels.weixin.qq.com",
        "youtube": "https://www.youtube.com",
    }
    url = domains.get(platform, "about:blank")

    print(f"▶ 从 {profile} 导出登录态 → {account_file}")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  ⚠ 访问 {url} 失败（仍尝试导出 cookie）: {e}")
        page.wait_for_timeout(2000)
        ctx.storage_state(path=str(account_file))
        ctx.close()
    print(f"✅ 已导出。验证: python3 {Path(__file__).name} --platform {platform} --login-check")
    return 0


def do_login_check(platform: str, headless: bool) -> int:
    """只验 cookie 是否有效，不扫码。"""
    cfg = REGISTRY[platform]
    mod = importlib.import_module(cfg["module"])
    account_file = str(_account_path(platform))
    if not Path(account_file).exists():
        print(f"❌ cookie 不存在: {account_file}（先 --login 或 --migrate-profile）")
        return 1
    cookie_auth = getattr(mod, "cookie_auth", None)
    if cookie_auth is None:
        print("⚠ 该平台上游无 cookie_auth，跳过校验")
        return 0
    ok = asyncio.run(cookie_auth(account_file)) if _is_async(cookie_auth) else cookie_auth(account_file)
    print("✅ cookie 有效" if ok else "❌ cookie 已失效，请 --login 重新扫码")
    return 0 if ok else 1


def _is_async(fn) -> bool:
    import inspect
    return inspect.iscoroutinefunction(fn)


def do_publish(args) -> int:
    platform = args.platform
    cfg = REGISTRY[platform]
    account_file = str(_account_path(platform))

    if not Path(account_file).exists():
        print(f"❌ cookie 不存在: {account_file}")
        print(f"  先登录: python3 {Path(__file__).name} --platform {platform} --login")
        print(f"  或迁移: python3 {Path(__file__).name} --platform {platform} --migrate-profile")
        return 1

    mod = importlib.import_module(cfg["module"])
    VideoCls = getattr(mod, cfg["video_class"])
    publish_date, _, strategy_value = _parse_schedule(args.schedule)
    publish_strategy = _resolve_strategy_const(mod, platform, strategy_value)

    # 基础参数（所有平台共有）
    kwargs = dict(
        title=args.title,
        file_path=args.file,
        tags=[t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else [],
        publish_date=publish_date,
        account_file=account_file,
        publish_strategy=publish_strategy,
        desc=args.desc or "",
        headless=args.headless,
    )
    # youtube 构造签名不同（无 publish_date/publish_strategy，用 visibility）
    if platform == "youtube":
        kwargs.pop("publish_date")
        kwargs.pop("publish_strategy")
        kwargs.pop("desc")
        kwargs["description"] = args.desc or ""
    # 平台特有封面参数
    kwargs.update(_build_thumb_kwargs(platform, args))

    # 过滤掉值为 None 的，避免覆盖上游默认值
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    print(f"\n━━━ {platform} 上游发布 ━━━")
    print(f"  视频:   {args.file}")
    print(f"  标题:   {args.title}")
    print(f"  描述:   {args.desc or '(无)'}")
    print(f"  标签:   {kwargs.get('tags') or []}")
    print(f"  封面:   {_build_thumb_kwargs(platform, args) or '(无)'}")
    print(f"  cookie: {account_file}")
    print(f"  策略:   {strategy_value}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if args.dry_run:
        print("🔍 dry-run：参数已就绪，不执行上传")
        return 0

    try:
        app = VideoCls(**kwargs)
    except TypeError as e:
        print(f"❌ 构造 {cfg['video_class']} 失败（上游签名可能已变，跑 sync-upstream.sh）: {e}")
        return 2

    try:
        asyncio.run(app.main())
        print(f"\n✅ {platform} 发布流程结束")
        return 0
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        print(f"\n❌ {platform} 发布失败: {e}")
        traceback.print_exc()
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="social-auto-upload 薄适配层（VAAS 发布入口）")
    ap.add_argument("--platform", required=True, choices=list(REGISTRY.keys()))
    ap.add_argument("--file", help="视频文件路径")
    ap.add_argument("--title", help="标题")
    ap.add_argument("--desc", default="")
    ap.add_argument("--tags", default="")
    ap.add_argument("--cover", default="", help="封面（竖/通用）")
    ap.add_argument("--cover-horizontal", default="", help="横封面（douyin）")
    ap.add_argument("--cover-vertical", default="", help="竖封面（douyin）")
    ap.add_argument("--thumbnail", default="", help="缩略图（youtube）")
    ap.add_argument("--visibility", default="", help="可见性（youtube: public/unlisted/private）")
    ap.add_argument("--schedule", default="", help="定时发布 YYYY-MM-DD HH:MM")
    ap.add_argument("--headless", action="store_true", help="无头模式（默认 headed 便于处理验证码）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--login", action="store_true", help="扫码登录，生成 cookie JSON")
    ap.add_argument("--login-check", action="store_true", help="只校验 cookie 是否有效")
    ap.add_argument("--migrate-profile", action="store_true", help="从 .profiles/ 导出登录态到 cookie JSON")
    args = ap.parse_args()

    headless = args.headless

    if args.login:
        return do_login(args.platform, headless)
    if args.login_check:
        return do_login_check(args.platform, headless)
    if args.migrate_profile:
        return do_migrate_profile(args.platform)

    if not args.file or not args.title:
        ap.error("发布模式需要 --file 和 --title（或用 --login/--migrate-profile）")
    return do_publish(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""校验平台登记的四方一致性（enforce-publish-confirmation-gate W3.2）。

对账源（platform-registry.json 为 canonical，spec「平台健康登记」）：
  1. _shared/publish/platform-registry.json  — 路由 + 定时能力单一可机读源
  2. login-manager.py PLATFORM_REGISTRY      — 登录面板 key 直接拼 `--platform`
  3. sau_adapter.py REGISTRY                 — 视频适配层（9 上游平台 + 标志位）
  4. fd-vaas-publish-videos/scripts/publish.mjs SAU_PLATFORMS — 视频编排清单
  5. fd-vaas-publish-docs/scripts/publish.mjs PLATFORMS       — 图文编排清单
  6. .env.example PLATFORMS_DOCS             — 默认图文平台（broken 必须剔除）

为什么要有这个检查：login-manager 的 registry key 会被直接拼进
`sau_adapter.py --platform <key>`，起个别名（比如 weibo_video）不会报「未知平台」
那样直白的错，而是在深处 KeyError / 静默走错分支。加平台时极易踩。
registry 陈旧而本检查报绿 = 假绿（比没有检查更糟），故 registry 纳入强对账。

用法：
    python3 scripts/check-registry-consistency.py
退出码 0 = 一致；1 = 有不一致。
"""
from __future__ import annotations

import ast
import datetime as _dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
LOGIN_MANAGER = HERE / "login-manager.py"
SAU_ADAPTER = SKILLS / "fd-vaas-publish-videos" / "scripts" / "platforms" / "sau_adapter.py"
VIDEOS_PUBLISH_MJS = SKILLS / "fd-vaas-publish-videos" / "scripts" / "publish.mjs"
DOCS_PUBLISH_MJS = SKILLS / "fd-vaas-publish-docs" / "scripts" / "publish.mjs"
PLATFORM_REGISTRY_JSON = SKILLS / "_shared" / "publish" / "platform-registry.json"
ENV_EXAMPLE = SKILLS.parent.parent / ".env.example"
LOGIN_STATE = HERE / ".login_state.json"
# 登录态验真的最长容忍期：超过就视为「没人复验」，闸门报红（不是靠人记得）
COOKIE_CHECK_MAX_AGE_DAYS = 14

# 不经 sau_adapter 的平台（走自有 profile / 独立脚本）
ADAPTER_EXEMPT = {"bilibili"}


def extract_login_keys(path: Path) -> list[str]:
    """从 login-manager.py 源码里静态取出 PLATFORM_REGISTRY 的顶层 key。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == "PLATFORM_REGISTRY":
                    return [k.value for k in node.value.keys]
    raise RuntimeError(f"未在 {path} 找到 PLATFORM_REGISTRY")


def extract_adapter_registry(path: Path) -> dict[str, dict]:
    """从 sau_adapter.py 静态取出 REGISTRY：平台 → {no_strategy, no_publish_date} 标志。

    标志位决定定时能力真相（no_strategy 上游签名没有 publish_strategy，
    youtube 无 publish_date），是 registry videos.schedule 的对账基准。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == "REGISTRY":
                    out: dict[str, dict] = {}
                    for k, v in zip(node.value.keys, node.value.values):
                        flags = {}
                        if isinstance(v, ast.Dict):
                            for kk, vv in zip(v.keys, v.values):
                                if isinstance(kk, ast.Constant) and kk.value in (
                                    "no_strategy", "no_publish_date"
                                ) and isinstance(vv, ast.Constant):
                                    flags[kk.value] = bool(vv.value)
                        out[k.value] = flags
                    return out
    raise RuntimeError(f"未在 {path} 找到 REGISTRY")


def extract_mjs_platforms(path: Path, var: str) -> set[str]:
    """从 publish.mjs 提取平台清单。

    var="SAU_PLATFORMS" → `new Set([ ... ])` 字符串集合；
    var="PLATFORMS"     → `{ key: {...}, ... }` 对象字面量的 key。
    """
    src = path.read_text(encoding="utf-8")
    start = src.find(f"const {var}")
    if start == -1:
        raise RuntimeError(f"未在 {path} 找到 {var}")
    if f"const {var} = new Set" in src[start:start + 40]:
        end = src.find("])", start)
        block = src[start:end]
        return set(re.findall(r'"([a-z_]+)"', block))
    # 对象字面量：取到收尾 `};`，key 形如行首两空格 + 标识符 + `:`
    end = src.find("};", start)
    block = src[start:end]
    return set(re.findall(r"\n  ([a-z_]+):\s*\{", block))


def load_platform_registry(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))["platforms"]
    except Exception as e:
        raise RuntimeError(f"platform-registry.json 读取/解析失败（registry 是 canonical 源，坏了必须先修）: {e}")


def expected_schedule(platform: str, adapter: dict[str, dict]) -> bool:
    """按运行时真相推导定时能力：adapter 平台看 no_strategy/youtube 特例；自有平台 False。"""
    if platform in ADAPTER_EXEMPT:
        return False  # bilibili.py 不支持 --schedule
    flags = adapter.get(platform)
    if flags is None:
        return False
    if flags.get("no_strategy") or flags.get("no_publish_date"):
        return False
    if platform == "youtube":  # 上游 YouTubeVideo 无 publish_date（adapter do_publish 特例 pop）
        return False
    return True


def check_cookie_freshness(registry: dict) -> list[str]:
    """登录态验真的新鲜度交叉校验（harden-login-session-truth 优化项 1）。

    为什么需要：registry 的 cookieCheck 与 lastVerified 语义不同——后者是选择器
    探测戳（probe.py 写），前者才是「这个 cookie 平台还认不认」。两者混用一个字段
    就会出现「面板绿、机读空」的分裂；而 cookie 文件存在 ≠ 有效（同一天实测：
    同样 27 天的 douyin/xiaohongshu 有效，kuaishou/weixin 已死）。

    只做两条，都可机读判定：
      1. .login_state.json 有记录、registry 却是 null → 漂移
      2. checkedAt 早于 MAX_AGE → 陈旧，等于没人复验
    """
    errors: list[str] = []
    state: dict = {}
    try:
        if LOGIN_STATE.exists():
            state = json.loads(LOGIN_STATE.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{LOGIN_STATE.name} 解析失败（{type(e).__name__}: {e}）—— 登录态真值源不可读即视为不一致。"]

    today = _dt.date.today()
    for platform, rec in sorted(state.items()):
        entry = registry.get(platform) or {}
        cc = entry.get("cookieCheck")
        if not isinstance(cc, dict):
            errors.append(
                f"platform-registry.json '{platform}' 缺 cookieCheck，但 .login_state.json 已有验真记录"
                f"（{rec.get('checked_at')}）—— 把验真结果写入 registry.cookieCheck 后重跑。"
            )
            continue
        checked = str(cc.get("checkedAt") or "")
        try:
            age = (today - _dt.date.fromisoformat(checked)).days
        except ValueError:
            errors.append(
                f"platform-registry.json '{platform}'.cookieCheck.checkedAt='{checked}' 不是 YYYY-MM-DD。"
            )
            continue
        if age > COOKIE_CHECK_MAX_AGE_DAYS:
            errors.append(
                f"platform-registry.json '{platform}' 登录态验真已 {age} 天（阈值 {COOKIE_CHECK_MAX_AGE_DAYS}）"
                f"—— 跑 sau_adapter --login-check 后刷新 cookieCheck。"
            )
    return errors


def main() -> int:
    errors: list[str] = []

    login_keys = extract_login_keys(LOGIN_MANAGER)
    adapter = extract_adapter_registry(SAU_ADAPTER)
    adapter_keys = set(adapter)
    mjs_video_keys = extract_mjs_platforms(VIDEOS_PUBLISH_MJS, "SAU_PLATFORMS")
    mjs_docs_keys = extract_mjs_platforms(DOCS_PUBLISH_MJS, "PLATFORMS")
    registry = load_platform_registry(PLATFORM_REGISTRY_JSON)
    reg_video = {p for p, v in registry.items() if "videos" in v}
    reg_docs = {p for p, v in registry.items() if "docs" in v}

    env_defaults_docs: set[str] = set()
    if ENV_EXAMPLE.exists():
        m = re.search(r"^PLATFORMS_DOCS=(\S+)", ENV_EXAMPLE.read_text(encoding="utf-8"), re.M)
        if m:
            env_defaults_docs = {s for s in m.group(1).split(",") if s}

    print(f"platform-registry 平台数: {len(registry)}（videos {len(reg_video)} / docs {len(reg_docs)}）")
    print(f"login-manager 平台数: {len(login_keys)}")
    print(f"sau_adapter  平台数: {len(adapter_keys)}")
    print(f"publish.mjs  视频平台数: {len(mjs_video_keys)} / 图文平台数: {len(mjs_docs_keys)}")

    # 1) login-manager 的 key 必须能被 adapter 接受（豁免的除外）
    for k in login_keys:
        if k in ADAPTER_EXEMPT:
            continue
        if k not in adapter_keys:
            errors.append(
                f"login-manager 的 '{k}' 不在 sau_adapter REGISTRY 里 —— "
                f"它会被拼成 `--platform {k}` 而报 KeyError。key 必须与 adapter 一致，显示名放 name 字段。"
            )

    # 2) mjs 侧声明走 adapter 的平台，adapter 必须真的支持
    for k in sorted(mjs_video_keys):
        if k not in adapter_keys:
            errors.append(
                f"publish.mjs 的 SAU_PLATFORMS 含 '{k}'，但 sau_adapter REGISTRY 没有它（会找不到 script）。"
            )

    # 3) registry 视频域 ↔ (SAU_PLATFORMS ∪ 自有平台)：registry 缺路由 = 新平台漏登（spec「新增平台不再漏登」）
    video_expected = mjs_video_keys | ADAPTER_EXEMPT
    for k in sorted(reg_video - video_expected):
        errors.append(
            f"platform-registry.json 有视频路由 '{k}'，但 publish.mjs SAU_PLATFORMS / 自有平台集合里没有它（registry 与运行时脱节）。"
        )
    for k in sorted(video_expected - reg_video):
        errors.append(
            f"运行时可发布的视频平台 '{k}'（SAU_PLATFORMS/自有）在 platform-registry.json 没有视频路由条目 —— registry 必须全覆盖，请补 entries。"
        )

    # 4) registry 图文域 ↔ docs publish.mjs PLATFORMS
    for k in sorted(reg_docs - mjs_docs_keys):
        errors.append(
            f"platform-registry.json 有图文路由 '{k}'，但 fd-vaas-publish-docs publish.mjs PLATFORMS 没有它。"
        )
    for k in sorted(mjs_docs_keys - reg_docs):
        errors.append(
            f"docs publish.mjs PLATFORMS 含 '{k}'，但 platform-registry.json 没有图文路由条目 —— registry 必须全覆盖。"
        )

    # 5) 定时能力三方对账：registry videos.schedule 必须等于运行时真相（adapter 标志位 / 自有平台 False）
    for k in sorted(reg_video):
        declared = registry[k]["videos"].get("schedule")
        truth = expected_schedule(k, adapter)
        if declared is not truth:
            errors.append(
                f"platform-registry.json '{k}'.videos.schedule={declared}，与运行时真相不符（应为 {truth}；"
                f"依据: {'自有平台不支持 --schedule' if k in ADAPTER_EXEMPT else 'sau_adapter no_strategy/no_publish_date/youtube 特例'}）。"
            )

    # 6) broken 平台不得进默认发布集合（spec「默认排除 broken」）
    broken = {p for p, v in registry.items() if v.get("selectorStatus") == "broken"}
    for k in sorted(broken & env_defaults_docs):
        errors.append(
            f"'.env.example' 默认 PLATFORMS_DOCS 含 broken 平台 '{k}'（registry selectorStatus=broken）—— 必须重验通过后才可回归默认集。"
        )

    # 7) 登录态验真新鲜度（cookieCheck 与 .login_state.json 不得分裂）
    errors.extend(check_cookie_freshness(registry))

    # 提示级（不算错——可能是只给 login 用）
    only_adapter = sorted(adapter_keys - mjs_video_keys)
    if only_adapter:
        print(f"ℹ  adapter 有、mjs 未声明（可发布但入口未列）: {only_adapter}")

    if errors:
        print("\n❌ 注册表不一致:")
        for e in errors:
            print(f"   - {e}")
        return 1

    print("\n✅ 注册表一致：platform-registry.json ↔ login-manager ↔ sau_adapter ↔ publish.mjs(视频/图文) ↔ .env.example")
    return 0


if __name__ == "__main__":
    sys.exit(main())

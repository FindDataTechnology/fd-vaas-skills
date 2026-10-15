#!/usr/bin/env python3
"""
litellm-bridge.py — Unified CLI bridge for VAAS multi-modal generation.

Provides a single CLI interface for:
  - TTS (text-to-speech)    via litellm.speech() or direct provider
  - Image generation        via litellm.image_generation() or direct provider
  - Video generation        via provider-specific SDK / API

Reads model/provider configuration from VAAS/.env (TTS_PROVIDER, IMAGE_MODEL, etc.)
but all settings can be overridden on the command line.

Outputs a single JSON object to stdout on success.
Exits non-zero on failure, with error info on stderr.

Usage:
  python litellm-bridge.py tts --text "..." --output /tmp/out.mp3
  python litellm-bridge.py image --prompt "..." --output /tmp/out.png
  python litellm-bridge.py video --prompt "..." --output /tmp/out.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# .env loading — walk up from script dir to find VAAS/.env
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
VAAS_ROOT = SCRIPT_DIR.parent  # VAAS/

# Add script dir to sys.path so we can import helper modules as siblings
import sys

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_env() -> dict[str, str]:
    """Load .env from VAAS root (if exists). Already-set env vars win."""
    env_path = VAAS_ROOT / ".env"
    if not env_path.exists():
        return dict(os.environ)
    # Use python-dotenv if available, otherwise hand-parse
    try:
        from dotenv import dotenv_values

        parsed = dotenv_values(env_path)
    except ImportError:
        parsed = {}
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            parsed[k] = v
    # Already-set environment variables take precedence
    for k, v in os.environ.items():
        parsed[k] = v
    return parsed


ENV = load_env()


def env_get(key: str, default: str = "") -> str:
    """Case-insensitive env lookup (matches existing VAAS .env conventions)."""
    val = ENV.get(key)
    if val:
        return val
    # case-insensitive fallback
    for k, v in ENV.items():
        if k.lower() == key.lower() and v:
            return v
    return default


def _reject_provider(provider: str, kind: str) -> None:
    """未受支持的 provider 显式拒绝：不静默回落，列出受支持的两条自有路径。

    （历史上此处走 litellm 兜底任意第三方 provider；词元已是自有网关，
    litellm 已退役——见 openspec change vaas-ciyuan-lane-providers。）
    """
    raise SystemExit(
        f"Error: {kind} provider '{provider}' is not supported. "
        "Supported providers: volcengine, ciyuan."
    )


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


def cmd_tts(args: argparse.Namespace) -> int:
    text = args.text or args.input
    if not text:
        print("Error: --text is required", file=sys.stderr)
        return 2

    model = args.model or env_get("TTS_MODEL", "seed-tts-2.0")
    voice = args.voice or env_get("TTS_VOICE", "alloy")
    provider = env_get("TTS_PROVIDER", "volcengine").lower()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()

    if provider == "volcengine":
        # ponytail: volcengine direct — litellm doesn't support ByteDance TTS with
        # word-level timestamps. We call openspeech.bytedance.com directly.
        from _volcengine_tts import synthesize as volc_synth  # type: ignore

        result = volc_synth(
            text=text,
            model=model,
            voice=voice,
            speed=args.speed,
            format=args.format or "mp3",
            enable_subtitle=not args.no_subtitle,
            api_key=args.api_key or env_get("vol_agent_api_key") or env_get("ARK_API_KEY") or "",
            base_url=args.base_url or env_get("ARK_TTS_BASE_URL")
            or "https://openspeech.bytedance.com/api/v3/plan/tts",
            output_path=out_path,
        )
    elif provider == "ciyuan":
        # 萬星·词元车道：POST /v1/audio/speech（OpenAI 音频形状），stdlib HTTP。
        # 逐字时间戳（captions）是 volcengine 直连专属，此档不可用——如实降级。
        from _ciyuan_tts import synthesize as ciyuan_synth  # type: ignore

        result = ciyuan_synth(
            text=text,
            model=model,
            voice=voice,
            speed=args.speed,
            format=args.format or "wav",
            enable_subtitle=False,
            api_key=args.api_key or env_get("CIYUAN_API_KEY") or "",
            base_url=args.base_url or env_get("CIYUAN_BASE_URL") or "",
            output_path=out_path,
        )
    else:
        _reject_provider(provider, "TTS")

    # Write captions if requested and available
    if result.get("captions") and args.captions:
        cap_path = Path(args.captions)
        cap_path.parent.mkdir(parents=True, exist_ok=True)
        cap_path.write_text(json.dumps(result["captions"], ensure_ascii=False, indent=2))
        result["captions_path"] = str(cap_path)
        result["captions_count"] = len(result["captions"])

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------


def cmd_image(args: argparse.Namespace) -> int:
    if not args.prompt:
        print("Error: --prompt is required", file=sys.stderr)
        return 2

    model = args.model or env_get("IMAGE_MODEL", "doubao-seedream-5.0-lite")
    provider = env_get("IMAGE_PROVIDER", "volcengine").lower()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()

    if provider == "volcengine":
        # ponytail: volcengine direct — Agent Plan image API supports
        # reference images, web search, and model routing that litellm
        # doesn't fully cover. We call the API directly.
        from _volcengine_image import generate as volc_gen  # type: ignore

        result = volc_gen(
            prompt=args.prompt,
            model=model,
            size=args.size or "2K",
            output_format=args.output_format or "jpeg",
            n=args.n or 1,
            api_key=args.api_key
            or env_get("vol_agent_api_key")
            or env_get("ARK_API_KEY")
            or "",
            base_url=args.base_url
            or env_get("SEEDREAM_BASE_URL")
            or "https://ark.cn-beijing.volces.com/api/plan/v3",
            output_path=out_path,
        )
    elif provider == "ciyuan":
        # 萬星·词元车道：POST /v1/images/generations，解析 data[].b64_json 落盘。
        # 多图按 n 拆输出路径；非 JSON 应答（已知 gpt-image-* 返 HTML）在客户端
        # 内即报错，绝不从 HTML 猜 URL。
        from _ciyuan_image import generate as ciyuan_img  # type: ignore

        n = args.n or 1
        out_paths = [out_path.with_name(f"{out_path.stem}_{i:02d}{out_path.suffix}") for i in range(n)]
        result = ciyuan_img(
            prompt=args.prompt,
            model=model,
            size=args.size,
            n=n,
            output_paths=out_paths,
            api_key=args.api_key or env_get("CIYUAN_API_KEY") or "",
            base_url=args.base_url or env_get("CIYUAN_BASE_URL") or "",
        )
        result["model"] = model
    else:
        _reject_provider(provider, "image")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Video generation
# ---------------------------------------------------------------------------


def cmd_video(args: argparse.Namespace) -> int:
    if not args.prompt and not args.status_task_id:
        print("Error: --prompt (or --status) is required", file=sys.stderr)
        return 2

    model = args.model or env_get("VIDEO_MODEL", "doubao-seedance-2.0")
    provider = env_get("VIDEO_PROVIDER", "volcengine").lower()

    out_path = Path(args.output or "")
    if out_path != Path(""):
        out_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()

    if provider == "volcengine":
        # ponytail: volcengine video is async Agent Plan API — not covered by litellm.
        # Direct call via our own helper, with polling.
        from _volcengine_video import generate as volc_video  # type: ignore
        from _volcengine_video import task_status as volc_status  # type: ignore

        api_key = (
            args.api_key
            or env_get("vol_agent_api_key")
            or env_get("ARK_API_KEY")
            or ""
        )
        base_url = (
            args.base_url
            or env_get("SEEDANCE_BASE_URL")
            or "https://ark.cn-beijing.volces.com/api/plan/v3"
        )

        if args.status_task_id:
            result = volc_status(
                task_id=args.status_task_id,
                api_key=api_key,
                base_url=base_url,
                output_path=out_path if out_path != Path("") else None,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        result = volc_video(
            prompt=args.prompt,
            model=model,
            duration=args.duration or 5,
            ratio=args.ratio or "adaptive",
            resolution=args.resolution or "720p",
            api_key=api_key,
            base_url=base_url,
            output_path=out_path,
            wait=not args.async_mode,
            timeout=args.timeout or 600,
        )
    elif provider == "ciyuan":
        # 萬星·词元车道：异步任务协议（创建→轮询→下载 video_url），stdlib HTTP。
        # 两阶段防重复计费：--async 只提交不等待；--status 只查态（客户端超时
        # 重试的是查询，不是付费的提交）。
        from _ciyuan_video import submit as ciyuan_submit  # type: ignore
        from _ciyuan_video import poll as ciyuan_poll  # type: ignore
        from _ciyuan_video import download as ciyuan_download  # type: ignore

        api_key = args.api_key or env_get("CIYUAN_API_KEY") or ""
        base_url = args.base_url or env_get("CIYUAN_BASE_URL") or ""

        if args.status_task_id:
            final = ciyuan_poll(
                task_id=args.status_task_id,
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=args.timeout or 600,
                interval_seconds=10,
            )
            result = {
                "ok": final.get("status") == "succeeded",
                "provider": "ciyuan",
                "task_id": args.status_task_id,
                "status": final.get("status"),
                "model": final.get("model"),
                "usage": final.get("usage"),
                "video_url": (final.get("content") or {}).get("video_url"),
            }
            if result["ok"] and out_path != Path(""):
                if not result.get("video_url"):
                    print("Error: task succeeded but no video_url in response", file=sys.stderr)
                    return 3
                result.update(ciyuan_download(video_url=result["video_url"], output_path=out_path))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if not args.prompt:
            print("Error: --prompt is required", file=sys.stderr)
            return 2
        sub = ciyuan_submit(
            prompt=args.prompt,
            model=model,
            duration=args.duration,
            ratio=args.ratio,
            resolution=args.resolution,
            first_frame=args.first_frame,
            last_frame=args.last_frame,
            api_key=api_key,
            base_url=base_url,
        )
        if args.async_mode:
            result = {
                "ok": True, "provider": "ciyuan", "submitted": True,
                **sub, "api_latency_ms": round((time.time() - start) * 1000),
            }
        else:
            final = ciyuan_poll(
                task_id=sub["task_id"], api_key=api_key, base_url=base_url,
                timeout_seconds=args.timeout or 600, interval_seconds=10,
            )
            if final.get("status") != "succeeded":
                print(
                    json.dumps({"ok": False, "provider": "ciyuan", **sub,
                                "status": final.get("status"), "detail": final}, ensure_ascii=False)[:1500],
                    file=sys.stderr,
                )
                return 3
            video_url = (final.get("content") or {}).get("video_url")
            if not video_url:
                print("Error: task succeeded but no video_url in response", file=sys.stderr)
                return 3
            result = {
                "ok": True, "provider": "ciyuan", "model": model,
                "task_id": sub["task_id"], "status": "succeeded",
                **ciyuan_download(video_url=video_url, output_path=out_path),
                "usage": final.get("usage"),
                "api_latency_ms": round((time.time() - start) * 1000),
            }
    else:
        # 未受支持的 provider：显式拒绝，不静默回落（两条自有路径：volcengine/ciyuan）。
        print(
            f"Error: video generation for provider '{provider}' is not supported. "
            "Supported providers: volcengine, ciyuan.",
            file=sys.stderr,
        )
        return 3

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="litellm-bridge",
        description="Unified multi-modal generation bridge (TTS / image / video)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # --- tts ---
    t = sub.add_parser("tts", help="Text-to-speech synthesis")
    t.add_argument("--text", "--input", dest="text", help="Text to synthesize")
    t.add_argument("--model", help="Model name (e.g. openai/tts-1, seed-tts-2.0)")
    t.add_argument("--voice", help="Voice name (e.g. alloy, zh-CN-Yunxia)")
    t.add_argument("--speed", type=float, help="Speech speed multiplier")
    t.add_argument("--format", "--response-format", dest="format", help="Output format: mp3/wav/etc")
    t.add_argument("--output", required=True, help="Output audio file path")
    t.add_argument("--captions", help="Output captions JSON path (if supported)")
    t.add_argument("--no-subtitle", action="store_true", help="Disable word-level timestamps")
    t.add_argument("--api-key", help="API key override")
    t.add_argument("--base-url", help="API base URL override")
    t.set_defaults(func=cmd_tts)

    # --- image ---
    i = sub.add_parser("image", help="Image generation")
    i.add_argument("--prompt", required=True, help="Image description")
    i.add_argument("--model", help="Model name (e.g. dall-e-3, doubao-seedream-5.0-lite)")
    i.add_argument("--size", help="Image size (e.g. 1024x1024, 2K)")
    i.add_argument("--output-format", help="Output format: png/jpeg")
    i.add_argument("-n", type=int, help="Number of images to generate")
    i.add_argument("--output", required=True, help="Output image file path")
    i.add_argument("--api-key", help="API key override")
    i.add_argument("--base-url", help="API base URL override")
    i.set_defaults(func=cmd_image)

    # --- video ---
    v = sub.add_parser("video", help="Video generation")
    v.add_argument("--prompt", help="Video description")
    v.add_argument("--model", help="Model name")
    v.add_argument("--duration", type=int, help="Video duration in seconds")
    v.add_argument("--ratio", help="Aspect ratio (16:9, 9:16, 1:1, etc.)")
    v.add_argument("--resolution", help="Resolution (480p, 720p, 1080p, 4k)")
    v.add_argument("--first-frame", dest="first_frame", help="First frame image URL (ciyuan lane)")
    v.add_argument("--last-frame", dest="last_frame", help="Last frame image URL (ciyuan lane)")
    v.add_argument("--output", help="Output video file path")
    v.add_argument("--async", dest="async_mode", action="store_true", help="Submit only, don't wait")
    v.add_argument("--status", dest="status_task_id", help="Query task status by task id (no submission)")
    v.add_argument("--timeout", type=int, help="Max wait time in seconds")
    v.add_argument("--api-key", help="API key override")
    v.add_argument("--base-url", help="API base URL override")
    v.set_defaults(func=cmd_video)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

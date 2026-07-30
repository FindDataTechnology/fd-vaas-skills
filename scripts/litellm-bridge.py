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
    else:
        # litellm path — providers: openai, azure, vertex_ai, elevenlabs, minimax, polly
        from litellm import speech  # type: ignore

        kwargs: dict = {}
        if args.speed is not None:
            kwargs["speed"] = float(args.speed)
        if args.format:
            kwargs["response_format"] = args.format
        if args.api_key:
            kwargs["api_key"] = args.api_key
        if args.base_url:
            kwargs["api_base"] = args.base_url

        response = speech(
            model=model,
            voice=voice,
            input=text,
            **kwargs,
        )
        response.stream_to_file(str(out_path))

        result = {
            "ok": True,
            "provider": provider,
            "model": model,
            "voice": voice,
            "text": text,
            "local_path": str(out_path),
            "file_size_bytes": out_path.stat().st_size,
            "api_latency_ms": round((time.time() - start) * 1000),
        }

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
    else:
        from litellm import image_generation  # type: ignore

        kwargs: dict = {}
        if args.size:
            kwargs["size"] = args.size
        if args.output_format:
            kwargs["response_format"] = args.output_format
        if args.n:
            kwargs["n"] = args.n
        if args.api_key:
            kwargs["api_key"] = args.api_key
        if args.base_url:
            kwargs["api_base"] = args.base_url

        response = image_generation(prompt=args.prompt, model=model, **kwargs)

        # Save first image
        images = []
        if hasattr(response, "data") and response.data:
            for i, img in enumerate(response.data):
                img_path = out_path
                if len(response.data) > 1:
                    img_path = out_path.with_name(f"{out_path.stem}_{i:02d}{out_path.suffix}")
                if img.url:
                    import urllib.request

                    urllib.request.urlretrieve(img.url, img_path)
                elif img.b64_json:
                    import base64

                    img_path.write_bytes(base64.b64decode(img.b64_json))
                images.append(
                    {
                        "local_path": str(img_path),
                        "url": img.url if img.url else None,
                    }
                )

        result = {
            "ok": True,
            "provider": provider,
            "model": model,
            "prompt": args.prompt,
            "size": args.size,
            "count": len(images),
            "images": images,
            "api_latency_ms": round((time.time() - start) * 1000),
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Video generation
# ---------------------------------------------------------------------------


def cmd_video(args: argparse.Namespace) -> int:
    if not args.prompt:
        print("Error: --prompt is required", file=sys.stderr)
        return 2

    model = args.model or env_get("VIDEO_MODEL", "doubao-seedance-2.0")
    provider = env_get("VIDEO_PROVIDER", "volcengine").lower()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()

    if provider == "volcengine":
        # ponytail: volcengine video is async Agent Plan API — not covered by litellm.
        # Direct call via our own helper, with polling.
        from _volcengine_video import generate as volc_video  # type: ignore

        result = volc_video(
            prompt=args.prompt,
            model=model,
            duration=args.duration or 5,
            ratio=args.ratio or "adaptive",
            resolution=args.resolution or "720p",
            api_key=args.api_key
            or env_get("vol_agent_api_key")
            or env_get("ARK_API_KEY")
            or "",
            base_url=args.base_url
            or env_get("SEEDANCE_BASE_URL")
            or "https://ark.cn-beijing.volces.com/api/plan/v3",
            output_path=out_path,
            wait=not args.async_mode,
            timeout=args.timeout or 600,
        )
    else:
        # For non-volcengine providers, try litellm.video_generation if available,
        # otherwise error out with a clear message.
        try:
            from litellm import video_generation  # type: ignore
        except ImportError:
            print(
                f"Error: video generation via litellm not available for provider '{provider}'. "
                "Use VIDEO_PROVIDER=volcengine or check litellm docs.",
                file=sys.stderr,
            )
            return 3

        response = video_generation(prompt=args.prompt, model=model)
        result = {
            "ok": True,
            "provider": provider,
            "model": model,
            "prompt": args.prompt,
            "response": str(response),
            "api_latency_ms": round((time.time() - start) * 1000),
        }

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
    v.add_argument("--prompt", required=True, help="Video description")
    v.add_argument("--model", help="Model name")
    v.add_argument("--duration", type=int, help="Video duration in seconds")
    v.add_argument("--ratio", help="Aspect ratio (16:9, 9:16, 1:1, etc.)")
    v.add_argument("--resolution", help="Resolution (480p, 720p, 1080p, 4k)")
    v.add_argument("--output", required=True, help="Output video file path")
    v.add_argument("--async", dest="async_mode", action="store_true", help="Submit only, don't wait")
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

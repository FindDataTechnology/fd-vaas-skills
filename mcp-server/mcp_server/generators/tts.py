"""
TTS (Text-to-Speech) generator wrapper.

Wraps litellm-bridge.py tts command via subprocess.

Truthfulness contract (vaas-primitives-correctness):
- duration_ms is measured from the produced file (wave/mutagen), never taken
  from upstream metadata (which was api latency in disguise).
- speed is honest: providers that can't honor it produce warnings, not silence.
- an unknown voice is a hard failure when a manifest lists voices: upstreams
  would otherwise silently fall back to a default voice (200 false-green).
- idempotency_key makes re-runs return the existing asset without re-billing.
"""

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Optional

from ..db import insert_content, generate_id, get_asset_by_slug, delete_asset, scoped_asset_slug
from ..utils import generate_slug, ensure_directory, get_relative_path, VAAS_ROOT, DOWNLOADS_DIR
from .runtime import finish, prepare, run_bridge

# Path to litellm-bridge.py
SCRIPTS_DIR = VAAS_ROOT / "scripts"
LITELLM_BRIDGE = SCRIPTS_DIR / "litellm-bridge.py"

MANIFEST_PATH = Path(__file__).with_name("voices_manifest.json")

# Providers whose upstream actually honors the speed parameter.
SPEED_SUPPORTED_PROVIDERS = {"volcengine"}


def _load_manifest(path=MANIFEST_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return {"providers": {}}


def _validate_voice(provider: str, voice: Optional[str]) -> Optional[str]:
    """Hard-check the requested voice against the manifest; return default if unset."""
    manifest = _load_manifest()
    prov = (manifest.get("providers") or {}).get(provider)
    if prov is None:
        # unknown provider: nothing to validate against
        return voice
    models = prov.get("models") or []
    active = [m for m in models if str(m.get("status", "")).startswith("active")]
    listed = [v.get("id") for m in active for v in (m.get("voices") or []) if v.get("id")]
    if not listed:
        return voice
    if voice is None:
        for m in active:
            for v in (m.get("voices") or []):
                if v.get("default"):
                    return v["id"]
        return listed[0]
    if voice not in listed:
        raise ValueError(
            f"voice '{voice}' is not available for provider '{provider}' "
            f"(known voices: {listed}); refusing to let the upstream fall back "
            f"silently — see the models_voices tool"
        )
    return voice


def _probe_duration_seconds(path_str: str, audio_format: str) -> float:
    """Measure audio duration from the produced file. Raises if it can't measure."""
    fmt = (audio_format or "").lower()
    if fmt == "wav":
        import wave
        with wave.open(path_str, "rb") as w:
            if w.getframerate():
                return w.getnframes() / float(w.getframerate())
        raise RuntimeError(f"cannot measure wav duration: {path_str}")
    try:
        from mutagen import File as MutagenFile
    except ImportError as e:
        raise RuntimeError(
            "audio duration measurement needs 'mutagen' for non-wav formats "
            "(add it to image dependencies)"
        ) from e
    audio = MutagenFile(path_str)
    if audio is None or not getattr(audio, "info", None) or not getattr(audio.info, "length", None):
        raise RuntimeError(f"cannot measure audio duration: {path_str}")
    return float(audio.info.length)


def synthesize(
    text: Optional[str] = None,
    file_path: Optional[str] = None,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    format: str = "mp3",
    slug: Optional[str] = None,
    enable_subtitles: bool = True,
    idempotency_key: Optional[str] = None,
) -> dict:
    """
    Synthesize speech from text.

    Args:
        text: Text to synthesize (required if file_path not provided)
        file_path: Path to text file (required if text not provided)
        voice: Voice ID (validated against values manifest when known)
        speed: Speech speed multiplier (0.25-4.0, only honored by some providers;
               others get a warnings entry instead of silent no-op)
        format: Output format (mp3/wav, default mp3)
        slug: Custom slug (auto-generated if not provided)
        enable_subtitles: Enable word-level timestamps (default True;
               volcengine only on current calibers)
        idempotency_key: Optional caller key; a second call with the same key
               returns the existing asset without re-generating or re-billing.

    Returns:
        Dict with id, slug, file_path, duration_ms (measured), api_latency_ms,
        captions_path, voice (as echoed), voice_requested, warnings, and (on
        replay) idempotent_replay.

    Raises:
        ValueError: If neither text nor file_path provided, or voice unknown.
        RuntimeError: If TTS synthesis fails, or duration cannot be measured.
    """
    if not text and not file_path:
        raise ValueError("Either text or file_path must be provided")

    # Tenant + credential context (guards params first)
    ctx = prepare("tts", {
        "text": text, "file_path": file_path, "voice": voice, "slug": slug,
    })
    owner = ctx["owner"]
    provider_actual = ctx["resolved"].get("provider") or "env"

    # ── Idempotent replay: same key + same owner → return the cached asset.
    # Caller-provided slugs were used as the inserted slug historically, so the
    # replay lookup must cover both the idem slug AND the caller slug —
    # otherwise a retry re-inserts the caller slug and hits its UNIQUE index.
    idem_slug = None
    if idempotency_key or slug:
        replay = None
        if idempotency_key:
            digest = hashlib.sha256(f"{owner}\0tts\0{idempotency_key}".encode()).hexdigest()[:20]
            idem_slug = f"idem-{digest}"
            replay = get_asset_by_slug(idem_slug, owner=owner)
        if replay is None and slug:
            replay = get_asset_by_slug(scoped_asset_slug(slug, owner), owner=owner)
        if replay:
            relative = replay.get("file_path") or ""
            if replay.get("stage") != "failed" and relative:
                abs_path = (DOWNLOADS_DIR / relative)
                if abs_path.exists():
                    meta = replay.get("metadata") or {}
                    return {
                        "id": replay["id"],
                        "slug": replay["slug"],
                        "file_path": relative,
                        "duration_ms": meta.get("duration_ms"),
                        "captions_path": None,
                        "voice": meta.get("voice"),
                        "voice_requested": meta.get("voice_requested"),
                        "model": meta.get("model"),
                        "warnings": [],
                        "idempotent_replay": True,
                    }
            # stale/failed record: remove and regenerate
            delete_asset(replay["id"])

    # Validate voice against the manifest (defends against upstream silent fallback)
    voice_requested = _validate_voice(provider_actual, voice)

    # Generate slug if not provided
    if not slug:
        if idem_slug:
            slug = idem_slug
        elif text:
            prefix = text[:20].lower().replace(" ", "-")
            prefix = "".join(c for c in prefix if c.isalnum() or c == "-")
            slug = generate_slug(prefix or "audio")
        else:
            slug = generate_slug("audio")

    # Create output directory
    output_dir = ensure_directory("audio", slug)
    audio_path = output_dir / f"{slug}.{format}"
    captions_path = output_dir / "captions.json" if enable_subtitles else None

    # Build command
    cmd = [
        "python", str(LITELLM_BRIDGE), "tts",
        "--output", str(audio_path)
    ]

    if text:
        cmd.extend(["--text", text])
    elif file_path:
        cmd.extend(["--input", file_path])

    if voice_requested:
        cmd.extend(["--voice", voice_requested])

    if speed is not None:
        cmd.extend(["--speed", str(speed)])

    if format:
        cmd.extend(["--format", format])

    if captions_path:
        cmd.extend(["--captions", str(captions_path)])

    if not enable_subtitles:
        cmd.append("--no-subtitle")

    # Execute subprocess
    try:
        stdout = run_bridge(cmd, ctx)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"TTS synthesis failed: {e.stderr}")

    # Parse output
    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse TTS output: {e}")

    # Warnings speak where the platform silently deviates
    warnings: list[str] = []
    if speed is not None and provider_actual not in SPEED_SUPPORTED_PROVIDERS:
        warnings.append(
            f"speed={speed} is not honored by provider '{provider_actual}'; "
            f"audio was generated at the upstream's default speed"
        )
    manifest = _load_manifest()
    prov_manifest = (manifest.get("providers") or {}).get(provider_actual) or {}
    if enable_subtitles and prov_manifest.get("captions_supported") is False:
        warnings.append(
            f"provider '{provider_actual}' does not support word-level captions; "
            f"request proceeded without captions"
        )

    # Measure real duration from the produced file (never trust upstream fields)
    duration_seconds = _probe_duration_seconds(str(audio_path), format)
    duration_ms = round(duration_seconds * 1000)

    # Insert into database
    content_id = generate_id()
    metadata = {
        "voice": output.get("voice"),
        "voice_requested": voice_requested,
        "model": output.get("model"),
        "speed": speed,
        "format": format,
        "text_length": len(text) if text else None,
        "duration_ms": duration_ms,
        "api_latency_ms": output.get("api_latency_ms"),
        "idempotency_key": idempotency_key,
        "warnings": warnings,
    }

    scoped = scoped_asset_slug(slug, ctx["owner"])
    insert_content(
        id=content_id,
        type="audio",
        slug=scoped,
        file_path=get_relative_path("audio", slug, f"{slug}.{format}"),
        metadata=metadata,
        status="rendered",
        owner=ctx["owner"],
    )

    chars = float(len(text)) if text else float(metadata["text_length"] or 0)
    result = {
        "id": content_id,
        "slug": scoped,
        "file_path": get_relative_path("audio", slug, f"{slug}.{format}"),
        "duration_ms": duration_ms,
        "api_latency_ms": output.get("api_latency_ms"),
        "captions_path": get_relative_path("audio", slug, "captions.json") if captions_path and captions_path.exists() else None,
        "voice": output.get("voice"),
        "voice_requested": voice_requested,
        "model": output.get("model"),
        "warnings": warnings,
    }
    result.update(finish(ctx, "generate_voice", provider_actual,
                         output.get("model"), chars, "char", content_id))
    return result

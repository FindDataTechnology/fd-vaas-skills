"""
Long-form voiceover assembly (vaas-media-pipeline W2.1).

Per-segment TTS (reusing the corrected primitive in generators/tts.py) with:
- per-segment bounded retries
- honest over-window reporting with text-compression guidance
  (never tempo-hack the audio — quality was vetoed on that ground)
- deterministic adelay alignment + ffmpeg mix into one track
- real (measured) total duration
"""

import json
import math
import subprocess
from pathlib import Path
from typing import Optional

from ..db import insert_content, generate_id, get_asset_by_slug, delete_asset, scoped_asset_slug
from ..hosting import current_owner
from ..utils import ensure_directory, get_relative_path, VAAS_ROOT
from .tts import synthesize, _probe_duration_seconds

MAX_SEGMENT_RETRIES = 2          # total attempts = 3
CONTAINER_TOTAL_SLACK_S = 0.5    # padding headroom inside declared window


def _suggest_compression(text: str, actual_s: float, target_s: float) -> dict:
    """Give a usable edit guidance instead of lying to the mixer.

    Estimate chars/sec from what we actually produced, return the char count
    the text would have to be to fit the window with margin.
    """
    if actual_s <= 0:
        return {"actual_s": actual_s, "target_s": target_s, "suggestion": "skip"}
    cps = len(text) / actual_s
    allowed = max(1, int(target_s * 0.94 * cps))
    return {
        "actual_s": round(actual_s, 2),
        "target_s": target_s,
        "current_chars": len(text),
        "estimated_budget_chars": allowed,
        "suggestion": (
            f"台词需要压到约 {allowed} 字（当前 {len(text)} 字）；"
            f"按当前语速 {cps:.1f} 字/秒，窗口仅有 {target_s}s"
        ),
    }


def _ffmpeg_assemble(files: list[tuple[Path, float]], out: Path, format: str,
                     total_s: float) -> None:
    """Mix N files at start-time offsets into one track, bounded to total_s.

    files: [(path, start_seconds)] — start seconds already include any helped
    overlaps (none here; we place segments sequentially).

    The output is capped with -t total_s: `apad` alone pads silence forever,
    so without an explicit bound the muxer never terminates.
    """
    if not files:
        raise RuntimeError("no segments to assemble")
    cmd = ["ffmpeg", "-y"]
    for p, _ in files:
        cmd += ["-i", str(p)]
    chains = []
    labels = []
    for i, (_, start) in enumerate(files):
        ms = int(round(start * 1000))
        chains.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    fc = ";".join(chains) + f";{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad[aout]"
    cmd += ["-filter_complex", fc, "-map", "[aout]",
            "-t", f"{max(0.1, total_s):.3f}", "-ar", "44100", "-ac", "2"]
    if format == "mp3":
        cmd += ["-b:a", "128k"]
    cmd += [str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"ffmpeg assemble failed: {proc.stderr[-400:]}")


def assemble(
    segments: list[dict],
    voice: Optional[str] = None,
    format: str = "mp3",
    slug: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    max_segment_retries: int = MAX_SEGMENT_RETRIES,
) -> dict:
    """
    Assemble a long voiceover from a script plan.

    Args:
        segments: ordered list of {text, window_s} (window_s optional → will
            be sized from the produced audio length), optionally 'label'.
        voice / format: passed through to per-segment TTS.
        slug: output slug; defaults to 'assemble-<hash>' of the input.
        idempotency_key: replay-safe over the whole plan.
        max_segment_retries: attempts per failing segment before giving up.

    Returns:
        { slug, file_path, duration_ms, target_duration_ms, count,
          segments: [{i, text, duration_ms, window_s, over_window, suggestion}],
          warnings, requested/current totals }

    Raises:
        ValueError / RuntimeError on structural error or persistent TTS failure
        (with the failing segment index embedded, never half-written state).
    """
    if not segments:
        raise ValueError("segments must not be empty")
    if not all(isinstance(s, dict) and s.get("text") for s in segments):
        raise ValueError("each segment must be {text: ..., window_s?: ...}")

    # deterministic slug from the plan + voice (so replays dedupe naturally)
    import hashlib
    plan_key = json.dumps(
        {"segs": segments, "voice": voice, "format": format,
         "idem": idempotency_key or ""},
        ensure_ascii=False, sort_keys=True,
    )
    if not slug:
        slug = f"assemble-{hashlib.sha256(plan_key.encode()).hexdigest()[:12]}"

    out_dir = ensure_directory("audio", slug)
    out_path = out_dir / f"{slug}.{format}"

    # ── Plan-level replay: same slug + owner + intact file → no re-synthesis,
    # no re-billing. A failed/partial record is deleted and regenerated.
    owner = current_owner()
    scoped = scoped_asset_slug(slug, owner)
    replay = get_asset_by_slug(scoped, owner=owner)
    if replay is not None:
        rel = replay.get("file_path") or ""
        meta = replay.get("metadata") or {}
        abs_p = (VAAS_ROOT / "downloads" / rel) if rel else None
        if replay.get("stage") != "failed" and abs_p is not None and abs_p.exists():
            return {
                "id": replay["id"],
                "slug": replay["slug"],
                "file_path": rel,
                "duration_ms": meta.get("duration_ms"),
                "target_duration_ms": meta.get("target_ms"),
                "count": meta.get("segment_count"),
                "segments": meta.get("segments") or [],
                "warnings": ["idempotent replay: whole plan reused, no re-billing"],
                "idempotent_replay": True,
            }
        delete_asset(replay["id"])

    per_result = []
    seg_files: list[tuple[Path, float]] = []
    cursor = 0.0
    covered_s = 0.0
    total_target_ms = 0

    for i, seg in enumerate(segments):
        text = seg["text"].strip()
        window_s = seg.get("window_s")

        attempt = 0
        err = None
        result = None
        while attempt <= max_segment_retries:
            attempt += 1
            try:
                result = synthesize(
                    text=text, voice=voice, format=format,
                    slug=f"{slug}-seg{i:02d}",
                    idempotency_key=f"assemble:{slug}:{i}",
                    enable_subtitles=False,
                )
                err = None
                break
            except Exception as ex:  # noqa: BLE001 — gate keeps semantics
                err = ex
        if result is None:
            raise RuntimeError(
                f"voiceover_assemble failed at segment {i} after "
                f"{max_segment_retries + 1} attempts: {err}"
            )

        fpath = Path(VAAS_ROOT / "downloads" / result["file_path"])
        if not fpath.exists():
            raise RuntimeError(f"segment {i} output missing: {fpath}")

        dur_ms = result["duration_ms"]
        if dur_ms is None:
            raise RuntimeError(f"segment {i} has no measured duration")

        dur_s = dur_ms / 1000.0
        over = window_s is not None and dur_s > float(window_s)
        entry = {
            "i": i,
            "text": text[:60] + ("…" if len(text) > 60 else ""),
            "duration_ms": dur_ms,
            "window_s": window_s,
            "over_window": bool(over),
        }
        if over:
            entry["suggestion"] = _suggest_compression(text, dur_s, float(window_s))
        if window_s is not None:
            total_target_ms += int(round(float(window_s) * 1000))
        else:
            total_target_ms += dur_ms

        per_result.append(entry)
        seg_files.append((fpath, cursor))
        covered_s = max(covered_s, cursor + dur_s)
        # cursor advance: real duration + headroom inside the target window
        target_s = float(window_s) if window_s is not None else dur_s + CONTAINER_TOTAL_SLACK_S
        cursor += max(dur_s, min(target_s, dur_s + CONTAINER_TOTAL_SLACK_S))

    _ffmpeg_assemble(seg_files, out_path, format, total_s=covered_s)

    assembled_ms = round(_probe_duration_seconds(str(out_path), format) * 1000)

    content_id = generate_id()
    insert_content(
        id=content_id,
        type="audio",
        slug=scoped,
        file_path=get_relative_path("audio", slug, f"{slug}.{format}"),
        metadata={
            "kind": "voiceover_assembly",
            "segments": per_result,
            "segment_count": len(per_result),
            "voice": voice,
            "format": format,
            "duration_ms": assembled_ms,
            "target_ms": total_target_ms,
            "idempotency_key": idempotency_key,
        },
        status="rendered",
        owner=owner,
    )

    warnings = []
    any_over = [e for e in per_result if e["over_window"]]
    if any_over:
        warnings.append(
            f"{len(any_over)} segment(s) exceeded their declared window; "
            f"edit text per suggestion then re-run to enforce total <= target"
        )

    return {
        "id": content_id,
        "slug": scoped,
        "file_path": get_relative_path("audio", slug, f"{slug}.{format}"),
        "duration_ms": assembled_ms,
        "target_duration_ms": total_target_ms,
        "count": len(per_result),
        "segments": per_result,
        "warnings": warnings,
    }

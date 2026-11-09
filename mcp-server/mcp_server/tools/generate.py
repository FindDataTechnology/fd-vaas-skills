"""
generate_* namespace: asset generation, dispatched through the generation registry.

同步 generate_video（seedance dispatch 版）已退役：异步面走
generate_video_submit / video_job_status，本地确定性出片走 render_video。
generate_cover 保留为内部实现入口（render_still(kind="cover") 调用），
不再出现在注册面。
"""

import json
import shutil
from typing import Optional

from ..registry import dispatch
from ..hosting import current_owner
from ..generators.video import submit as _video_submit, poll as _video_poll


def generate_video_submit(
    prompt: str,
    duration: Optional[int] = None,
    ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    first_frame: Optional[str] = None,
    last_frame: Optional[str] = None,
    slug: Optional[str] = None,
) -> dict:
    """Submit an async video job; returns a job id in seconds.

    Poll video_job_status until succeeded/failed. Client timeouts may safely
    retry this call's sibling status tool — never resubmit.
    """
    return _video_submit(
        prompt=prompt, duration=duration, ratio=ratio, resolution=resolution,
        first_frame=first_frame, last_frame=last_frame, slug=slug,
    )


def video_job_status(job_id: str) -> dict:
    """Poll one async video job by id (running/succeeded/failed/expired).

    On success the returned payload carries asset_id and a signed download_url.

    Tenant scoping enforced here (generation-jobs: cross-tenant invisible):
    hosted callers only ever see their own jobs; local stdio resolves to the
    service owner and sees the whole table as before.
    """
    return _video_poll(job_id, owner=current_owner())


def generate_voice(
    text: Optional[str] = None,
    file_path: Optional[str] = None,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    format: str = "mp3",
    slug: Optional[str] = None,
    enable_subtitles: bool = True,
    idempotency_key: Optional[str] = None,
    name: str = "tts",
) -> dict:
    """Generate speech from text using TTS (registry method: tts).

    Pass idempotency_key to make the call replay-safe: a second call with the
    same key returns the existing asset (idempotent_replay=True) instead of
    re-generating and re-billing.
    """
    return dispatch("voice", name, {
        "text": text, "file_path": file_path, "voice": voice, "speed": speed,
        "format": format, "slug": slug, "enable_subtitles": enable_subtitles,
        "idempotency_key": idempotency_key,
    })


def generate_image(
    prompt: str,
    size: Optional[str] = None,
    output_format: str = "jpeg",
    n: int = 1,
    slug: Optional[str] = None,
    name: str = "seedream",
) -> dict:
    """Generate images from a text prompt (registry method: seedream).

    reference_image (img2img) is not on this surface: no lane has an E2E-
    proven path, so the parameter was removed instead of advertised.
    """
    return dispatch("image", name, {
        "prompt": prompt, "size": size, "output_format": output_format,
        "n": n, "slug": slug,
    })


def generate_cover(
    title: str,
    subtitle: Optional[str] = None,
    tags: Optional[str] = None,
    orientation: str = "horizontal",
    size: Optional[str] = None,
    template: str = "brand",
    slug: Optional[str] = None,
    name: str = "brand",
) -> dict:
    """Generate a brand-consistent cover image via chromium single-frame (registry method: brand).

    内部入口：由 render_still(kind="cover") 调用，不再注册为独立工具。
    """
    return dispatch("cover", name, {
        "title": title, "subtitle": subtitle, "tags": tags,
        "orientation": orientation, "size": size, "template": template, "slug": slug,
    })


def models_voices() -> dict:
    """List available generation models and voices per provider (truth table).

    Read before choosing a voice/model: shows capabilities (speed/captions
    support), current status, and pricing notes per lane. The manifest at
    generators/voices_manifest.json is the source of truth for this tool.
    Each provider block also carries its lane health
    (health/reason_class/last_verified, from lane_health.json).
    """
    from ..generators.manifest import load_manifest
    from ..lane_health import lane_health as _lh

    doc = load_manifest()
    for pname, prov in (doc.get("providers") or {}).items():
        prov["lane"] = _lh("voice", pname)
    return doc


def voiceover_assemble(
    segments: Optional[list] = None,
    voice: Optional[str] = None,
    format: str = "mp3",
    slug: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    bgm: Optional[dict] = None,
) -> dict:
    """Assemble a long voiceover from a script plan (vaas-pipeline W2).

    segments: ordered [{text, window_s?}]. Per-segment TTS with bounded retries;
    over-window segments get edit suggestions (never tempo-hacked). Deterministic
    plan slug; same plan + idempotency_key replays without re-billing.

    bgm（W4.3）: {asset_id|path, volume?, fade_out?} — 成片后混入背景音乐，
    语义与 render_video 的 bgm 一致：BGM 短于成片自动循环补长，长于成片在
    成片时长处收尾（-t covered_s 纪律）；volume 默认 0.2，fade_out 默认 true。
    未显式给 slug 时，bgm 签名折入确定性 slug（同计划不同 BGM 不串重放键）。
    """
    from ..db import get_asset_by_slug, record_asset_history
    from ..db.models import update_asset_metadata
    from ..hosting import current_owner
    from ..generators.voiceover import assemble
    from ..utils import VAAS_ROOT
    from .render import _bgm_signature, mix_bgm_onto_audio, resolve_bgm

    owner = current_owner()
    bgm_spec = resolve_bgm(bgm, owner)

    if bgm_spec is not None and not slug:
        # 折叠 bgm 签名进确定性 slug，让重放键区分不同 BGM（generators/
        # voiceover 的 plan_key 无法从外部扩展，故在此预派生 slug）
        import hashlib
        plan_key = json.dumps(
            {"segs": segments, "voice": voice, "format": format,
             "idem": idempotency_key or "", "bgm": _bgm_signature(bgm_spec)},
            ensure_ascii=False, sort_keys=True)
        slug = f"assemble-{hashlib.sha256(plan_key.encode()).hexdigest()[:12]}"

    result = assemble(segments=segments or [], voice=voice, format=format,
                      slug=slug, idempotency_key=idempotency_key)

    if bgm_spec is None:
        return result

    # ── BGM 混流（W4.3）：干声备份 + 原地补混 + 账本 metadata 补丁 ──────────
    rel = result.get("file_path") or ""
    voice_abs = VAAS_ROOT / "downloads" / rel
    if not voice_abs.is_file():
        raise RuntimeError(f"voiceover_assemble bgm mix: assembled file missing: {voice_abs}")
    duration_ms = result.get("duration_ms")
    if not duration_ms:
        raise RuntimeError("voiceover_assemble bgm mix: assembled duration unknown")

    sig = _bgm_signature(bgm_spec)
    asset = get_asset_by_slug(result["slug"], owner=owner)
    meta_bgm = ((asset or {}).get("metadata") or {}).get("bgm")
    if meta_bgm and all(meta_bgm.get(k) == v for k, v in sig.items()):
        # 幂等重放/重试：同一 BGM 已混过，不叠混
        result["bgm"] = meta_bgm
        return result

    voiceonly = voice_abs.with_name(voice_abs.stem + ".voiceonly" + voice_abs.suffix)
    if not voiceonly.exists():
        # 干声备份：换 BGM 重跑时永远从干声出发（显式 slug + 换 BGM 的重混语义）
        shutil.copyfile(voice_abs, voiceonly)

    mix_bgm_onto_audio(voiceonly, bgm_spec["file"], voice_abs,
                       duration_ms / 1000.0, bgm_spec, format)

    patch = {**sig, "title": bgm_spec.get("title"),
             "license": bgm_spec.get("license"),
             "attribution": bgm_spec.get("attribution")}
    if asset:
        update_asset_metadata(asset["id"], {"bgm": patch})
        record_asset_history(asset["id"], "bgm:mixed",
                             json.dumps(sig, ensure_ascii=False))

    warnings = result.setdefault("warnings", [])
    warnings.append(f"bgm mixed onto assembly ({sig['ref']})")
    result["bgm"] = patch
    return result


def reference_clips_check(regenerate_all: bool = False) -> dict:
    """Review reference clips for every active voice; regenerate missing/recycled.

    Run after upstream/model changes to produce a per-voice diff report.
    """
    from ..generators.references import reference_clips_check as _check
    return _check(regenerate_all=regenerate_all)

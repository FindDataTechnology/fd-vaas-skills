"""
render_* namespace: the presentation render plane.

Three tools share one asset ledger convention (insert_content + download_url):
  render_video     — storyboard 模式（确定性逐帧出片，原 video_compose 实现）
                     或 type 模式（fd-vaas-video-creator 类型管线，subprocess）
  render_still     — cover（Remotion 静帧）/ chart / graphic（占位）
  render_document  — pdf / longimage（占位，chromium print 内核后续波次接入）

Storyboard renderer (ported from attic compose_video.py, vaas-media-pipeline W3):
Storyboard = scene list. Every frame is re-rendered from time t alone, so the
render is perfectly reproducible (same storyboard → same byte stream).

Scene kinds:
  html_intro / html_outro — a full HTML page obeying the VAAS seek contract:
        window.__DURATION__, window.__SIZE__=[w,h], window.seek(t), data-stage,
        no external assets, inline CSS/JS only.
  kenburns        — a list of screenshot paths moving slowly (zoom/pan),
        driven strictly by t. Images are inlined as data: URIs because the
        page is loaded with set_content (about:blank origin cannot fetch
        file:// or relative subresources).
  html_full       — caller-supplied full-page HTML obeying the same contract.

Voice audio (optional) is a pre-rendered mp3/wav; -shortest trims to the
shorter side, so the audio must be at least as long as the planned video.

BGM (W4): storyboard 模式支持 bgm={asset_id|path, volume, fade_out}，视频合成
后 ffmpeg amix 混流（BGM -stream_loop 补长、-t 在视频时长处收尾、fade_out=afade
出）。种子曲库随镜像分发（templates/bgm/），首启注册为全局可见 bgm 资产。
"""

import base64
import json
import mimetypes
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..db import (generate_id, insert_content, insert_asset, record_usage,
                  scoped_asset_slug, get_asset, get_asset_by_slug, delete_asset)
from ..utils import (VAAS_ROOT, DOWNLOADS_DIR, ensure_directory,
                     ensure_directory_rel, get_relative_path, generate_slug)
from ..hosting import current_owner, download_url, is_hosted, SERVICE_OWNER
from ..generators.runtime import prepare, run_bridge
from ._scene_guard import find_external_refs, install_route_guard

FPS_DEFAULT = 30
FONT_STACK = ("'PingFang SC','Hiragino Sans GB','Noto Sans CJK SC','Noto Sans SC',"
              "'Microsoft YaHei',sans-serif")
VAT_CSS_FALLBACK = (
    "background:linear-gradient(160deg,#070a20,#141a4d 60%,#3b2a8f);"
    f"color:#fff;font-family:{FONT_STACK};"
)

# fd-vaas-video-creator 类型管线（render_video type 模式的外部执行体）
VIDEO_CREATOR_SCRIPTS = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-video-creator" / "scripts"
REMOTION_APP = VAAS_ROOT / "remotion-app"
FD_VIDEOS_DIR = DOWNLOADS_DIR / "fd-videos"

STORYBOARD_SCENE_KINDS = ("html_intro", "html_outro", "kenburns", "html_full")


INTRO_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script>window.__DURATION__={dur};window.__SIZE__=[{w},{h}];</script>
<style>
  html,body{{margin:0;padding:0;background:#070a20}}
  [data-stage]{{position:relative;width:{w}px;height:{h}px;overflow:hidden;{css}}}
  .panel{{position:absolute;left:8%;right:8%;top:35%;text-align:center;font-size:56px;font-weight:700;letter-spacing:4px}}
  .sub{{position:absolute;left:10%;right:10%;top:52%;text-align:center;font-size:30px;opacity:.8}}
</style></head>
<body><div data-stage>
  <div class="panel" id="title"></div>
  <div class="sub" id="sub"></div>
</div>
<script>
  const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
  const titleEl=document.getElementById('title');
  const subEl=document.getElementById('sub');
  window.seek=function(t){{
    const p=clamp(t/window.__DURATION__,0,1);
    {title_js}
    {sub_js}
  }};
  window.seek(0);
</script></body></html>
"""


def _js_str(value: str) -> str:
    """JSON-encode a Python string so it is a safe JS literal (quotes, newlines)."""
    return json.dumps(value, ensure_ascii=False)


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _scene_html(scene: dict) -> str:
    dur = float(scene["duration_s"])
    w, h = scene.get("size") or [1280, 720]
    title = scene.get("title", "")
    sub = scene.get("sub", "")
    return INTRO_HTML.format(
        dur=dur, w=w, h=h,
        css=scene.get("css") or VAT_CSS_FALLBACK,
        title_js=(f"titleEl.textContent={_js_str(title)};"
                  "titleEl.style.opacity=String(p);"
                  "titleEl.style.transform='translateY('+(1-p)*30+'px)';"),
        sub_js=(f"subEl.textContent={_js_str(sub)};"
                "subEl.style.opacity=String(Math.max(0,p-0.25)/0.75||0);"),
    )


def _scene_kenburns_html(scene: dict) -> str:
    dur = float(scene["duration_s"])
    w, h = scene.get("size") or [1920, 1080]
    imgs = scene.get("images") or []
    if not imgs:
        raise ValueError("kenburns scene needs non-empty images")
    srcs = []
    for p in imgs:
        path = Path(p).expanduser()
        if not path.is_file():
            raise ValueError(f"kenburns image not found: {p}")
        srcs.append(_data_uri(path))
    motion = scene.get("motion", "pan_down")
    transform = {
        "pan_down": "'translate(0,'+(-rel*6)+'%) scale('+(1+rel*0.04)+')'",
        "zoom_in": "'scale('+(1+rel*0.08)+')'",
        "pan_right": "'translate('+(-rel*5)+'%,0) scale(1.06)'",
    }.get(motion, "'translate(0,'+(-rel*6)+'%) scale('+(1+rel*0.04)+')'")
    img_tags = "".join(
        f'<img class="frame" src="{s}" id="img{i}"'
        + ("" if i == 0 else ' style="display:none"') + ">"
        for i, s in enumerate(srcs)
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script>window.__DURATION__={dur};window.__SIZE__=[{w},{h}];</script>
<style>
  html,body{{margin:0;padding:0;background:#000}}
  [data-stage]{{position:relative;width:{w}px;height:{h}px;overflow:hidden;background:#000}}
  .frame{{position:absolute;top:-4%;left:-4%;width:108%;height:108%;object-fit:cover;transition:none}}
  .cap{{position:absolute;left:6%;bottom:6%;color:#fff;font:700 44px/1.4 {FONT_STACK};
        text-shadow:0 2px 12px rgba(0,0,0,.7);opacity:0}}
</style></head>
<body><div data-stage>
  {img_tags}
  <div class="cap" id="cap">{scene.get("caption", "")}</div>
</div>
<script>
  const D=window.__DURATION__, N={len(srcs)};
  const cap=document.getElementById('cap');
  const imgs=[]; for(let i=0;i<N;i++) imgs.push(document.getElementById('img'+i));
  window.seek=function(t){{
    const seg=D/N;
    const i=Math.min(N-1,Math.floor(t/seg));
    const rel=(t-i*seg)/seg;
    imgs.forEach((im,j)=>{{ im.style.display = j===i ? 'block' : 'none'; }});
    const im=imgs[i];
    im.style.transform={transform};
    cap.style.opacity=String(Math.min(1,rel*4));
  }};
  window.seek(0);
</script></body></html>"""


def _launch_kwargs() -> dict:
    """Playwright launch args.

    VAAS_CHROMIUM_EXECUTABLE pins a browser; otherwise a system chromium
    (/usr/bin/chromium) wins over the playwright-managed download, so the
    image does not need `playwright install` (offline-friendly).
    """
    kwargs = {"args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]}
    exe = os.getenv("VAAS_CHROMIUM_EXECUTABLE")
    if not exe and Path("/usr/bin/chromium").is_file():
        exe = "/usr/bin/chromium"
    if exe:
        kwargs["executable_path"] = exe
    return kwargs


def _render_html_frames(html: str, duration_s: float, size, out_dir: Path,
                        fps: int, start_index: int = 0) -> list[Path]:
    """Render one scene's frames into the SHARED frame sequence (continuous numbering)."""
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = int(round(duration_s * fps))
    if frames <= 0:
        return []
    files: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**_launch_kwargs())
        page = browser.new_page(viewport={"width": size[0], "height": size[1]},
                                device_scale_factor=1)
        install_route_guard(page)  # W6.1b：场景页断网兜底（拦静态校验不可见的动态外链）
        page.goto("about:blank")
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(150)
        for i in range(frames):
            t = i / fps
            page.evaluate(f"(window.seek||function(t){{}})({t})")
            f = out_dir / f"frame_{start_index + i:05d}.png"
            page.screenshot(path=str(f))
            files.append(f)
        browser.close()
    return files


def _ffmpeg(frames_dir: Path, audio: Optional[Path], out: Path, fps: int) -> None:
    cmd = ["ffmpeg", "-y", "-framerate", str(fps),
           "-i", str(frames_dir / "frame_%05d.png")]
    if audio is not None:
        cmd += ["-i", str(audio)]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast"]
    if audio is not None:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += ["-movflags", "+faststart", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"ffmpeg compose failed: {proc.stderr[-400:]}")


def _validate_storyboard_assets(storyboard: dict, voice_path: Optional[str],
                                bgm_path: Optional[str] = None) -> None:
    """Fail fast with ONE error naming every missing input file.

    折入自 assets_validate_paths 的路径校验逻辑：渲染前收集全部缺失文件，
    报错一次性列出（而不是跑到第 N 帧才在某个场景里炸掉）。
    """
    missing: list[str] = []
    for i, scene in enumerate(storyboard.get("scenes") or []):
        for p in (scene.get("images") or []):
            if not Path(p).expanduser().is_file():
                missing.append(f"scenes[{i}].images: {p}")
    vp = voice_path or storyboard.get("voice_path")
    if vp and not Path(vp).expanduser().is_file():
        missing.append(f"voice_path: {vp}")
    if bgm_path and not Path(bgm_path).expanduser().is_file():
        missing.append(f"bgm path: {bgm_path}")
    if missing:
        raise ValueError(
            "render_video input validation failed — missing file(s):\n  "
            + "\n  ".join(missing)
        )


def _build_scene_htmls(scenes: list[dict], size) -> list[str]:
    """每场景 → 待渲染 HTML（kind 分发；W6.1a 先全量建好再校验，磁盘零写入）。"""
    htmls: list[str] = []
    for i, scene in enumerate(scenes):
        kind = scene.get("kind", "html_intro")
        if kind in ("html_intro", "html_outro"):
            htmls.append(_scene_html({**scene, "size": size}))
        elif kind == "kenburns":
            htmls.append(_scene_kenburns_html({**scene, "size": size}))
        elif kind == "html_full":
            html = scene.get("html") or ""
            if not html:
                raise ValueError(
                    f"scene {i} kind=html_full needs scene.html inline content")
            htmls.append(html)
        else:
            raise ValueError(f"unknown scene kind: {kind}")
    return htmls


def _assert_scenes_offline(scene_htmls: list[str], scenes: list[dict]) -> None:
    """W6.1a 外置场景硬校验：场景 HTML 含 http(s)/file 外链即抛错。

    一次性列全所有场景的违规资源 URL（同 _validate_storyboard_assets 的
    「报错一次列全」纪律）；调用点在任何磁盘写入之前，违规不产生部分产物。
    """
    violations = [
        f"scene {i} ({scenes[i].get('kind', 'html_intro')}): {ref}"
        for i, html in enumerate(scene_htmls)
        for ref in find_external_refs(html)
    ]
    if violations:
        raise ValueError(
            "storyboard scene html contains external resource reference(s) — "
            "external assets must be inlined as data: URIs (rendering is "
            "offline):\n  " + "\n  ".join(f"- {v}" for v in violations))


def compose_storyboard(
    storyboard: dict,
    slug: Optional[str] = None,
    format: str = "mp4",
    voice_path: Optional[str] = None,
    fps: int = FPS_DEFAULT,
    bgm: Optional[dict] = None,
) -> dict:
    """
    Compose one video from a storyboard, deterministically (render_video 的
    storyboard 模式实现；移植自 attic compose_video.py::compose，函数体逻辑不变).

    storyboard = {"size": [w,h] (default 1080x1920),
                  "scenes": [
                    {"kind":"html_intro","duration_s":4,"title":"...","sub":"..."},
                    {"kind":"kenburns","duration_s":8,"images":[...],"caption":"..."},
                    {"kind":"html_outro","duration_s":3,"title":"...","sub":"..."}
                  ]}

    bgm（W4.2）：已解析的 bgm spec（resolve_bgm 产物；传原始 {asset_id|path,...}
    会在内部补解析）。视频合成后混流 BGM，计划重放键折叠 bgm 签名——同一
    storyboard 配不同 BGM 是不同重放键。
    """
    scenes = list(storyboard.get("scenes") or [])
    if not scenes:
        raise ValueError("storyboard.scenes must not be empty")
    size = storyboard.get("size") or [1080, 1920]
    if voice_path is None:
        voice_path = storyboard.get("voice_path")

    # fail fast on identity before spending seconds on rendering
    owner = current_owner()

    if bgm is not None and "file" not in bgm:
        bgm = resolve_bgm(bgm, owner)

    if storyboard.get("html_intro"):
        scenes = [{"kind": "html_full",
                   "duration_s": storyboard.get("intro_duration_s", 4),
                   "html": storyboard["html_intro"]}] + scenes

    if not slug:
        import hashlib
        plan = json.dumps(
            storyboard if bgm is None else {"storyboard": storyboard,
                                            "bgm": _bgm_signature(bgm)},
            ensure_ascii=False, sort_keys=True)
        slug = f"compose-{hashlib.sha256(plan.encode()).hexdigest()[:12]}"

    # ── Plan-level replay: this renderer is deterministic, so an identical
    # storyboard must return the existing asset instead of colliding on the
    # (globally unique) slug; a failed/partial record is replaced.
    scoped = scoped_asset_slug(slug, owner)
    replay = get_asset_by_slug(scoped, owner=owner)
    if replay is not None:
        rel = replay.get("file_path") or ""
        meta = replay.get("metadata") or {}
        if replay.get("stage") != "failed" and rel and (VAAS_ROOT / "downloads" / rel).exists():
            result = {
                "id": replay["id"], "slug": replay["slug"], "file_path": rel,
                "duration_ms": meta.get("duration_ms"),
                "scenes": meta.get("scenes"), "frames": meta.get("frames"),
                "format": format, "idempotent_replay": True,
            }
            if is_hosted():
                url = download_url(replay["id"], owner)
                if url:
                    result["download_url"] = url
            return result
        delete_asset(replay["id"])

    # ── W6.1a 外置场景硬校验：先建全部场景 HTML 扫外链，命中即抛——此刻磁盘
    # 零写入（帧目录不建、账本行不写），违规不产生任何部分产物。重放语义不变：
    # 已成功渲染过的计划必然合规，上一段前置 return 已短路。
    scene_htmls = _build_scene_htmls(scenes, size)
    _assert_scenes_offline(scene_htmls, scenes)

    out_dir = ensure_directory("video", slug)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    total_frames = 0
    for i, html in enumerate(scene_htmls):
        produced = _render_html_frames(html, float(scenes[i]["duration_s"]),
                                       size, frames_dir, fps,
                                       start_index=total_frames)
        if not produced:
            raise RuntimeError(f"scene {i} produced no frames")
        total_frames += len(produced)

    if not total_frames:
        raise RuntimeError("no frames rendered")

    audio_p = Path(voice_path) if voice_path else None
    if audio_p and not audio_p.is_file():
        raise ValueError(f"voice file missing: {voice_path}")

    out_path = out_dir / f"{slug}.{format}"
    if bgm is not None:
        # 先出无 BGM 的成片中间体，再混流到正式产物（文件名保持稳定）
        pre_path = out_dir / f"{slug}.prebgm.{format}"
        _ffmpeg(frames_dir, audio_p, pre_path, fps)
        try:
            _mix_bgm_onto_video(pre_path, bgm, out_path)
        finally:
            pre_path.unlink(missing_ok=True)
    else:
        _ffmpeg(frames_dir, audio_p, out_path, fps)

    # the storyboard is the source of truth: keep it, drop the PNG frames
    (out_dir / "storyboard.json").write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(frames_dir, ignore_errors=True)

    probed_s = _ffprobe_seconds(out_path)
    duration_ms = int(probed_s * 1000) if probed_s else None

    rel_path = get_relative_path("video", slug, f"{slug}.{format}")
    content_id = generate_id()
    metadata = {"kind": "video_compose", "duration_ms": duration_ms,
                "scenes": len(scenes), "fps": fps, "size": size,
                "frames": total_frames, "voice": bool(audio_p),
                "generator": "playwright+ffmpeg", "deterministic": True}
    if bgm is not None:
        metadata["bgm"] = {**_bgm_signature(bgm),
                           "title": bgm.get("title"),
                           "license": bgm.get("license"),
                           "attribution": bgm.get("attribution")}
    insert_content(
        id=content_id, type="video", slug=scoped, file_path=rel_path,
        metadata=metadata,
        status="rendered", owner=owner,
    )
    record_usage(
        owner=owner, tool="render_video", provider="local",
        model="playwright+ffmpeg", units=round(total_frames / fps, 3),
        unit_type="second", credential_source="local", asset_id=content_id,
    )

    result = {
        "id": content_id, "slug": scoped, "file_path": rel_path,
        "duration_ms": duration_ms, "scenes": len(scenes),
        "frames": total_frames, "format": format,
    }
    if is_hosted():
        url = download_url(content_id, owner)
        if url:
            result["download_url"] = url
    return result


# ─── BGM：种子曲库 + 参数解析 + 混流（W4） ─────────────────────────────────

BGM_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "bgm"
BGM_VOLUME_DEFAULT = 0.2
BGM_FADE_OUT_DEFAULT = True
BGM_FADE_SECONDS = 3.0


def normalize_bgm(bgm) -> Optional[dict]:
    """Validate a bgm parameter block (no IO); None passes through as None.

    Accepted shape: {asset_id: str} XOR {path: str}, plus volume (0 < v <= 1,
    default 0.2) and fade_out (bool, default True).
    """
    if bgm is None:
        return None
    if not isinstance(bgm, dict):
        raise ValueError("bgm must be a dict {asset_id|path, volume?, fade_out?}")
    unknown = set(bgm) - {"asset_id", "path", "volume", "fade_out"}
    if unknown:
        raise ValueError(f"bgm has unknown keys: {sorted(unknown)}; "
                         "allowed: asset_id, path, volume, fade_out")
    asset_id = bgm.get("asset_id")
    path = bgm.get("path")
    if asset_id and path:
        raise ValueError("bgm accepts asset_id or path, not both")
    if not asset_id and not path:
        raise ValueError("bgm requires asset_id (asset ledger reference) or path (audio file)")
    volume = bgm.get("volume", BGM_VOLUME_DEFAULT)
    if isinstance(volume, bool) or not isinstance(volume, (int, float)) \
            or not 0 < float(volume) <= 1:
        raise ValueError("bgm.volume must be a number in (0, 1] (default 0.2)")
    fade_out = bgm.get("fade_out", BGM_FADE_OUT_DEFAULT)
    if not isinstance(fade_out, bool):
        raise ValueError("bgm.fade_out must be a boolean")
    return {
        "ref": {"asset_id": str(asset_id)} if asset_id else {"path": str(path)},
        "volume": round(float(volume), 4),
        "fade_out": fade_out,
    }


def ensure_bgm_library() -> list[dict]:
    """Register the shipped seed BGM library as globally visible bgm assets.

    幂等：slug 确定性（bgm-seed-<stem>），重复调用/重启不重复插。每条曲目
    owner=service（平台全局，租户隔离规则见 db._owner_visible 的 bgm 豁免），
    文件复制到 downloads/bgm/ 以走签名下载；metadata 落 duration_seconds /
    license / source（授权来源必填，取自随包 licenses.json）。首启由 main()
    调用；bgm asset_id 解析路径也会兜底触发。
    """
    manifest_path = BGM_TEMPLATE_DIR / "licenses.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dest_dir = ensure_directory_rel("bgm")
    out = []
    for track in manifest.get("tracks") or []:
        fname = track.get("file") or ""
        src = BGM_TEMPLATE_DIR / fname
        if not fname or not src.is_file():
            continue  # 清单与包内容不一致时不阻断启动
        dest = dest_dir / fname
        if not dest.exists():
            shutil.copyfile(src, dest)
        slug = f"bgm-seed-{Path(fname).stem}"
        existing = get_asset_by_slug(slug, owner=None)
        if existing is not None:
            out.append({"slug": slug, "id": existing["id"], "inserted": False})
            continue
        asset_id = insert_asset(
            type="bgm", slug=slug, file_path=f"bgm/{fname}",
            metadata={"kind": "bgm_seed", "seed": True,
                      "title": track.get("title"), "artist": track.get("artist"),
                      "duration_seconds": track.get("duration_seconds"),
                      "license": track.get("license"),
                      "license_url": track.get("license_url"),
                      "source": track.get("source"),
                      "attribution": track.get("attribution")},
            stage="rendered", title=track.get("title") or slug,
            owner=SERVICE_OWNER)
        out.append({"slug": slug, "id": asset_id, "inserted": True})
    return out


def resolve_bgm(bgm, owner: Optional[str] = None) -> Optional[dict]:
    """Validate + resolve a bgm block into a mixable spec (absolute file).

    asset_id 引用走资产账本：本人 bgm 资产或平台种子曲库（owner=service，全局
    可见）可引用；他人资产拒绝并提示不存在（不泄露存在性）。path 引用与
    voice_path / kenburns images 同一信任级别，直接指向宿主文件。
    """
    spec = normalize_bgm(bgm)
    if spec is None:
        return None
    ref = spec["ref"]
    if "path" in ref:
        p = Path(ref["path"]).expanduser()
        if not p.is_file():
            raise ValueError(f"bgm path not found: {ref['path']}")
        return {**spec, "asset_id": None, "path": ref["path"], "file": p,
                "title": None, "license": None, "attribution": None}

    if not ref["asset_id"]:
        raise ValueError("bgm.asset_id must not be empty")
    ensure_bgm_library()  # 兜底：种子曲库首用即注册（幂等，开销为一次查重）
    asset = get_asset(ref["asset_id"], owner=owner)
    if asset and asset.get("type") != "bgm":
        raise ValueError(f"asset is not a bgm asset: {ref['asset_id']}")
    if not asset:
        raise ValueError(f"bgm asset not found: {ref['asset_id']}")
    rel = asset.get("file_path") or ""
    abs_p = (VAAS_ROOT / "downloads" / rel) if rel else None
    if not abs_p or not abs_p.is_file():
        raise ValueError(f"bgm asset file missing: {ref['asset_id']} ({rel})")
    meta = asset.get("metadata") or {}
    return {**spec, "asset_id": asset["id"], "path": None, "file": abs_p,
            "title": meta.get("title") or asset.get("title"),
            "license": meta.get("license"),
            "attribution": meta.get("attribution")}


def _bgm_signature(spec: dict) -> dict:
    """Logical signature of a resolved bgm spec (replay key / ledger metadata)."""
    ref = f"asset:{spec['asset_id']}" if spec.get("asset_id") else f"path:{spec.get('path')}"
    return {"ref": ref, "volume": spec["volume"], "fade_out": spec["fade_out"]}


def _bgm_volume_chain(spec: dict, duration_s: float, label: str = "bgm") -> str:
    """[1:a] 处理链：音量 + 可选收尾 fade（afade 在视频/成片时长处出）。"""
    chain = f"[1:a]volume={spec['volume']}"
    fade_d = min(BGM_FADE_SECONDS, max(0.0, duration_s))
    if spec["fade_out"] and fade_d > 0:
        st = max(0.0, duration_s - fade_d)
        chain += f",afade=t=out:st={st:.3f}:d={fade_d:.3f}"
    return chain + f"[{label}]"


def _ffprobe_seconds(path: Path) -> Optional[float]:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        try:
            return float(r.stdout.strip())
        except ValueError:
            return None
    return None


def _has_audio_stream(path: Path) -> bool:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def mix_bgm_onto_audio(voice: Path, bgm: Path, out: Path,
                       duration_s: float, spec: dict, format: str) -> None:
    """Audio-only BGM mix（voiceover_assemble W4.3 的混流原语）。

    BGM -stream_loop 补长、amix duration=first 以干声为准、-t duration_s 收尾
    （-t covered_s 纪律：BGM 长于成片在成片时长处收尾）、normalize=0 不压干声。
    先写临时文件再原子替换（out 可能就是干声文件本身）。
    """
    chain = _bgm_volume_chain(spec, duration_s) \
        + ";[0:a][bgm]amix=inputs=2:duration=first:normalize=0[aout]"
    tmp = out.with_name(out.stem + ".bgm-mixing" + out.suffix)
    cmd = ["ffmpeg", "-y", "-i", str(voice), "-stream_loop", "-1", "-i", str(bgm),
           "-filter_complex", chain, "-map", "[aout]",
           "-t", f"{max(0.1, duration_s):.3f}", "-ar", "44100", "-ac", "2"]
    if format == "mp3":
        cmd += ["-b:a", "128k"]
    cmd += [str(tmp)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp.exists():
        raise RuntimeError(f"ffmpeg bgm mix failed: {proc.stderr[-400:]}")
    os.replace(tmp, out)


def _mix_bgm_onto_video(video: Path, spec: dict, out: Path) -> None:
    """Mix BGM onto a finished video (W4.2，视频合成后的第二道 ffmpeg)。

    有旁白：[0:a][bgm]amix duration=first；无旁白：直接挂 [bgm]。BGM 以
    -stream_loop 无限补长，-t 在视频时长处收尾；视频流 -c:v copy 不重编码。
    """
    duration_s = _ffprobe_seconds(video)
    if not duration_s or duration_s <= 0:
        raise RuntimeError("cannot determine video duration for bgm mix")
    bgm_chain = _bgm_volume_chain(spec, duration_s)
    if _has_audio_stream(video):
        fc = bgm_chain + ";[0:a][bgm]amix=inputs=2:duration=first:normalize=0[aout]"
        out_label = "[aout]"
    else:
        fc = bgm_chain
        out_label = "[bgm]"
    cmd = ["ffmpeg", "-y", "-i", str(video), "-stream_loop", "-1",
           "-i", str(spec["file"]),
           "-filter_complex", fc, "-map", "0:v", "-map", out_label,
           "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
           "-t", f"{duration_s:.3f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"ffmpeg bgm mix failed: {proc.stderr[-400:]}")


# ─── render_video type 模式：fd-vaas-video-creator 类型管线 ────────────────

def _list_video_types() -> list[str]:
    types_dir = VIDEO_CREATOR_SCRIPTS.parent / "types"
    if not types_dir.is_dir():
        return []
    return sorted(p.name for p in types_dir.iterdir()
                  if (p / "type.json").is_file())


def _render_typed_video(type: str, script: str, inputs: Optional[dict],
                        slug: Optional[str], owner: str) -> dict:
    """Run the fd-vaas-video-creator type pipeline via subprocess.

    调用方式参照原 skills/voiceover.py::create_voiceover_video：
    node new-task.mjs 建任务目录（downloads/fd-videos/<slug>/）→
    node task-render.mjs 跑类型 pipeline（tts/scene-align/preflight/render），
    cwd=remotion-app、env 注入凭据 overlay（hosted 模式）。
    """
    known = _list_video_types()
    if known and type not in known:
        raise ValueError(f"unknown video type: {type}. Available: {known}")

    if not script:
        raise ValueError("render_video(type=...) requires script (口播稿文本或路径)")
    inputs = dict(inputs or {})

    script_file = Path(script).expanduser()
    if script_file.is_file():
        script_arg = str(script_file)
    else:
        # script 是内联文本 → 落临时文件再交给 new-task.mjs（file 输入约定）
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", prefix=f"vaas-script-{type}-",
            delete=False, encoding="utf-8")
        tmp.write(script)
        tmp.close()
        script_arg = tmp.name

    cmd1 = ["node", str(VIDEO_CREATOR_SCRIPTS / "new-task.mjs"),
            "--slug", slug, "--type", type, "--script", script_arg]
    for key, value in inputs.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        cmd1 += [f"--{key}", str(value)]

    ctx = prepare("video", {
        "type": type, "slug": slug, "script": script, "inputs": inputs,
    })
    env = {**os.environ, **ctx["env"]} if ctx["env"] else None

    try:
        subprocess.run(cmd1, capture_output=True, text=True, check=True,
                       cwd=str(REMOTION_APP), env=env)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"task init failed: {(e.stderr or e.stdout)[-800:]}")

    cmd2 = ["node", str(VIDEO_CREATOR_SCRIPTS / "task-render.mjs"), "--slug", slug]
    try:
        proc = subprocess.run(cmd2, capture_output=True, text=True, check=True,
                              cwd=str(REMOTION_APP), env=env)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"task render failed: {(e.stderr or e.stdout)[-800:]}")

    task_dir = FD_VIDEOS_DIR / slug
    task_json_path = task_dir / "task.json"
    task_json = {}
    if task_json_path.exists():
        try:
            task_json = json.loads(task_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            task_json = {}

    mp4 = task_dir / f"{slug}.mp4"
    if not mp4.exists():
        raise RuntimeError(
            f"task render finished but output missing: {mp4}; "
            f"stdout tail: {proc.stdout[-400:]}")

    content_id = generate_id()
    rel_path = get_relative_path("fd-videos", slug, f"{slug}.mp4")
    insert_content(
        id=content_id, type="video", slug=slug, file_path=rel_path,
        metadata={"kind": "video_type", "type": type,
                  "task_json": task_json,
                  "composition": task_json.get("composition"),
                  "duration_sec": (task_json.get("render") or {}).get("totalDurationSec")},
        status="rendered", owner=owner,
    )
    source = ctx["resolved"].get("source") or "env"
    record_usage(owner=owner, tool="render_video", provider="local",
                 model="fd-vaas-video-creator", units=1, unit_type="render",
                 credential_source=source, asset_id=content_id)

    result = {
        "id": content_id, "slug": slug, "file_path": rel_path,
        "duration_sec": (task_json.get("render") or {}).get("totalDurationSec"),
        "type": type, "status": "rendered", "credential_source": source,
    }
    if is_hosted():
        url = download_url(content_id, owner)
        if url:
            result["download_url"] = url
    return result


def render_video(
    storyboard: Optional[dict] = None,
    type: Optional[str] = None,
    script: Optional[str] = None,
    inputs: Optional[dict] = None,
    slug: Optional[str] = None,
    format: Optional[str] = None,
    voice_path: Optional[str] = None,
    fps: Optional[int] = None,
    bgm: Optional[dict] = None,
) -> dict:
    """Render a video: storyboard 模式（确定性逐帧）或 type 模式（类型管线）。

    Two mutually exclusive modes:
      1. storyboard={size, scenes:[...]} — 确定性渲染，场景 kind ∈
         html_intro/html_outro/kenburns/html_full，逐帧由 window.seek(t)
         重放，同一 storyboard → 同一字节流；计划级重放键 scoped_asset_slug。
      2. type="carousel|listicle|data-viz|kinetic-quote|news-flash" +
         script（口播稿文本或路径）+ inputs（类型输入 dict，见
         types/<id>/type.json）— 走 fd-vaas-video-creator 管线 subprocess。

    bgm（W4.2，storyboard 模式专用）: {asset_id|path, volume?, fade_out?} —
    视频合成后混流背景音乐；BGM 短于视频自动循环补长，长于视频在视频时长处
    收尾；volume 默认 0.2，fade_out 默认 true（afade 出）。asset_id 引用
    assets 账本 type=bgm 资产（本人资产或全局种子曲库）。

    同时提交 storyboard 与 type 是明确错误；输入文件缺失时报错会列出
    具体缺失清单（kenburns images / voice_path / bgm path）。
    """
    if storyboard is not None and type is not None:
        raise ValueError(
            "render_video: storyboard and type are mutually exclusive — "
            "pass exactly one mode (storyboard=... OR type=...)")
    if storyboard is None and type is None:
        raise ValueError(
            "render_video: no mode given — pass storyboard={size, scenes:[...]} "
            "OR type=<carousel|listicle|data-viz|kinetic-quote|news-flash>")
    if type is not None and bgm is not None:
        raise ValueError(
            "render_video: bgm mixing is not wired for type mode in this wave "
            "— pass storyboard=... to use bgm")

    owner = current_owner()

    if storyboard is not None:
        bgm_norm = normalize_bgm(bgm)
        _validate_storyboard_assets(
            storyboard if isinstance(storyboard, dict) else {}, voice_path,
            bgm_path=bgm_norm["ref"]["path"] if bgm_norm and "path" in bgm_norm["ref"] else None)
        return compose_storyboard(
            storyboard=storyboard, slug=slug, format=format or "mp4",
            voice_path=voice_path, fps=fps or FPS_DEFAULT,
            bgm=resolve_bgm(bgm, owner),
        )

    if not slug:
        slug = generate_slug(f"{type}-video")
    if FD_VIDEOS_DIR is not None and (FD_VIDEOS_DIR / slug).exists():
        raise ValueError(
            f"task dir already exists for slug '{slug}' — the type pipeline "
            f"requires a fresh slug (delete {FD_VIDEOS_DIR / slug} or pick another)")
    return _render_typed_video(type=type, script=script, inputs=inputs,
                               slug=slug, owner=owner)


# ─── render_still / render_document：分发骨架（内核后续波次填） ────────────

def render_still(kind: str, spec: dict, slug: Optional[str] = None) -> dict:
    """Render one still image; kind = cover | chart | graphic.

    cover  — CoverBrand 静帧（走原 generate_cover 的 remotion 静帧路径，
             spec: {title, subtitle?, tags?, orientation?, size?, template?}）
    chart  — 图表静帧（tools/still_chart.py::render_chart，本波占位）
    graphic— 通用图形静帧（tools/still_graphic.py::render_graphic，本波占位）
    """
    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")
    if kind == "cover":
        # 原实现保留在 tools/generate.py::generate_cover（registry cover/brand
        # → skills/cover.py），render_still 只是从注册面摘除后的内部分发入口。
        from .generate import generate_cover
        allowed = ("title", "subtitle", "tags", "orientation", "size", "template")
        unknown = set(spec) - set(allowed)
        if unknown:
            raise ValueError(f"cover spec has unknown keys: {sorted(unknown)}; "
                             f"allowed: {list(allowed)}")
        if not spec.get("title"):
            raise ValueError("cover spec requires title")
        return generate_cover(
            title=spec["title"], subtitle=spec.get("subtitle"),
            tags=spec.get("tags"), orientation=spec.get("orientation") or "horizontal",
            size=spec.get("size"), template=spec.get("template") or "brand",
            slug=slug,
        )
    if kind == "chart":
        from .still_chart import render_chart
        return render_chart(spec, slug=slug)
    if kind == "graphic":
        from .still_graphic import render_graphic
        return render_graphic(spec, slug=slug)
    raise ValueError(f"unknown still kind: {kind}. Available: cover, chart, graphic")


def render_document(source: str, format, template: Optional[str] = None,
                    slug: Optional[str] = None) -> dict:
    """Render a document: format ∈ {pdf, longimage}，或两者的列表.

    source 为 md 或 html 文本/路径；template 未指定用 "default"。format 接受
    字符串或列表（W3 内核已支持多格式，每份产物独立落账）；非法值报错不变。
    """
    valid = ("pdf", "longimage")
    if isinstance(format, str):
        formats = (format,)
    elif isinstance(format, (list, tuple)) and format:
        formats = tuple(format)
    else:
        raise ValueError(
            f"format must be {list(valid)} (string or list), got: {format!r}")
    unknown = next((f for f in formats if f not in valid), None)
    if unknown:
        raise ValueError(f"unknown document format: {unknown}. Available: pdf, longimage")
    if not source:
        raise ValueError("source is required (markdown/html text or path)")
    from .doc_render import render_document as _render
    return _render(source=source, format=format,
                   template=template or "default", slug=slug)

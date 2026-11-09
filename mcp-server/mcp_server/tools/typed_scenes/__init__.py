"""
Typed-scene builders（add-typed-video-html-renderer W1.1）。

render_video type 模式的 HTML 渲染脊柱：type.json 注册表 gate + builder 契约
+ 分段/对齐底座，产出 storyboard 模式的 seek 契约场景序列，再交
tools/render.py::compose_storyboard 走同一确定性逐帧实现路径（计划级重放 /
外链硬校验 / 账本 / 计价全部生效；hosted 与本地行为一致）。

Builder 契约（并行波次按此实现，签名要稳）—— builders/<type_id>.py 导出
BUILDER（AbstractBuilder 实例），自动发现零改动注册：

  validate_inputs(inputs, segments) -> None
      结构数对照等前置校验；不合法 raise ValueError 列全对照（渲染前、零
      产物）。常在 TTS 花费之前以骨架 Segment（duration_s=0、无句表）调用，
      结构校验不需要时长。
  build(segments, inputs, size, theme) -> list[dict]
      产出 storyboard 场景序列（kind ∈ html_intro/html_outro/kenburns/
      html_full + duration_s + data-stage + seek 契约）。动效必须由
      window.seek(t) 纯函数驱动；颜色字体取 theme（brand 变量 + palette）；
      场景 HTML 走品牌 CSS wrapper（theme.py）；零外链（compose 的
      _assert_scenes_offline 硬校验兜底）。

契约 v2（adopt-hyperframes-video-renderer W3.1，增量、不破坏旧路径）：

  build_composition(segments, inputs, size, theme) -> dict
      返回 {"visual": [clip…], "subtitle": [clip…]}；visual clip 形如
      {"start", "duration", "html", "seek_js"?}（seek_js 为
      "function(lt){…}" 纯函数，localT 相对 clip 起点），字幕 clip 形如
      {"start", "duration", "text"}。动画仍由逐帧 seek 驱动，但不整页；
      片段由 composition.build_composition_html 统一装进 HyperFrames
      composition（窗口判到才调本 clip 的 seek_js）。旧 build() 保留到
      W4 切流后再删；未实现 v2 的 builder 在 TTS 花费前就被拒。

type 模式计划键（W1.4）：type+script+inputs+voice_path+bgm 全折入
（typed_plan_slug，同输入重放免费，接既有 scoped slug 纪律）。
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

from ...utils import DOWNLOADS_DIR, VAAS_ROOT, ensure_directory_rel
from ..composition import (AUDIO_TRACK_INDEX, BGM_TRACK_INDEX,
                           SUBTITLE_TRACK_INDEX, VISUAL_TRACK_INDEX,
                           build_composition_html)
from .alignment import (FPS_DEFAULT, TAIL_PAD_FRAMES_DEFAULT, Segment,
                        align_tts, align_voice_path, apply_tail_pad,
                        concat_audio, skeleton_segments, split_script)
from .theme import load_theme

# fd-vaas-video-creator 类型注册表（type.json 的单一事实源）
VIDEO_TYPES_DIR = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-video-creator" / "types"


class AbstractBuilder:
    """Typed-scene builder 基类（契约见模块 docstring；子类覆写方法）。"""

    type_id: str = ""

    def validate_inputs(self, inputs: dict, segments: list[Segment]) -> None:
        raise NotImplementedError

    def build(self, segments: list[Segment], inputs: dict,
              size: list[int], theme: dict) -> list[dict]:
        raise NotImplementedError

    def build_composition(self, segments: list[Segment], inputs: dict,
                          size: list[int], theme: dict) -> dict:
        """契约 v2：返回 {"visual": [clip…], "subtitle": [clip…]}。

        默认未实现——builders/* 由并行波次逐个迁移；未迁移的 builder 在
        build_typed_composition 的 TTS 花费之前就以 NotImplementedError
        被拒（不会白烧 TTS）。旧 build() 路径不受影响。
        """
        raise NotImplementedError(
            f"builder '{self.type_id}' 尚未实现 build_composition（契约 v2）"
            "——迁移完成前该类型继续走 build() / storyboard 路径")


# type_id -> builder 实例（builders/__init__ 自动发现填充）
BUILDER_REGISTRY: dict[str, AbstractBuilder] = {}


def register(builder: AbstractBuilder) -> None:
    """注册一个 builder（重复注册同 type_id 显式报错，防并行波次撞车）。"""
    if not getattr(builder, "type_id", ""):
        raise TypeError("builder must declare a non-empty type_id")
    prev = BUILDER_REGISTRY.get(builder.type_id)
    if prev is not None and prev is not builder:
        raise ValueError(f"duplicate builder registration for type '{builder.type_id}'")
    BUILDER_REGISTRY[builder.type_id] = builder


# ─── type.json 注册表 gate ─────────────────────────────────────────────────

def list_video_types() -> list[str]:
    if not VIDEO_TYPES_DIR.is_dir():
        return []
    return sorted(p.name for p in VIDEO_TYPES_DIR.iterdir()
                  if (p / "type.json").is_file())


def load_type_json(type_id: str) -> dict:
    """读 type.json；未注册 type → ValueError 列可用类型清单（W7.6 指路
    报错的窄化形态，保留该语义）。"""
    known = list_video_types()
    if type_id not in known:
        raise ValueError(f"unknown video type: {type_id}. Available: {known}")
    return json.loads((VIDEO_TYPES_DIR / type_id / "type.json").read_text(
        encoding="utf-8"))


def _gate_type(type_id: str) -> dict:
    """type.json 三道 gate：注册存在 → renderer ∈ {html, hyperframes} →
    builder 已注册。

    renderer 同时接受 "html" 与 "hyperframes"：并行波次里 storyboard 路径
    （W1）与 composition 路径（W3/W4）共存，避免迁移窗口内同一 type 改值
    撞车；切流完成后再收敛为单一值。
    """
    type_json = load_type_json(type_id)
    if type_json.get("renderer") not in ("html", "hyperframes"):
        raise ValueError(
            f"video type '{type_id}' is not an html-renderer type "
            f"(renderer={type_json.get('renderer')!r}) — 本 change 的 type "
            '模式只服务 type.json 声明 "renderer": "html" | "hyperframes" 的类型')
    if type_id not in BUILDER_REGISTRY:
        raise ValueError(
            f"no scene builder registered for video type '{type_id}'. "
            f"Available builders: {sorted(BUILDER_REGISTRY) or '(none)'}")
    return type_json


# ─── 计划键（W1.4） ────────────────────────────────────────────────────────

def typed_plan_slug(type_id: str, script: str, inputs: Optional[dict],
                    voice_path: Optional[str], bgm: Optional[dict]) -> str:
    """type 模式计划哈希：type+script+inputs+voice_path+bgm 全折入。

    同输入 → 同 slug → compose 的计划级重放键命中（scoped slug 纪律），
    重放不重新补图/合成/计费。raw bgm 折入（asset_id/path 引用本身就是
    稳定签名；解析出的绝对路径不折，避免宿主布局漂移打散重放键）。
    """
    plan = json.dumps(
        {"mode": "typed", "type": type_id, "script": script,
         "inputs": inputs, "voice_path": voice_path, "bgm": bgm},
        ensure_ascii=False, sort_keys=True, default=str)
    return f"typed-{hashlib.sha256(plan.encode()).hexdigest()[:12]}"


# ─── 画幅 ──────────────────────────────────────────────────────────────────

def _parse_orientation(inputs: dict, type_json: dict) -> list[int]:
    """inputs.orientation（type.json inputs.orientation.enum/default）→ [w, h]。"""
    spec = (type_json.get("inputs") or {}).get("orientation") or {}
    allowed = [str(v) for v in (spec.get("enum") or ["1080x1920", "1920x1080"])]
    value = str(inputs.get("orientation") or spec.get("default") or allowed[0])
    if value not in allowed:
        raise ValueError(
            f"inputs.orientation must be one of {allowed}, got: {value!r}")
    w, _, h = value.partition("x")
    return [int(w), int(h)]


def _read_script(script: str) -> str:
    """script 为文件路径则读文本，否则视为内联口播稿。

    内联稿常含换行与数百字节 UTF-8，Linux 上 Path(...).is_file() 会抛
    ENAMETOOLONG（macOS 静默返回 False）；先做保守形状判定再探文件系统，
    避免把长文案当路径名（CI 首跑实证）。
    """
    from pathlib import Path
    if "\n" in script or "\r" in script or len(script.encode("utf-8")) > 240:
        return script
    p = Path(script).expanduser()
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return script


# ─── 主入口 ────────────────────────────────────────────────────────────────

def build_typed_storyboard(type_id: str, script: str, inputs: Optional[dict],
                           voice_path: Optional[str] = None,
                           bgm: Optional[dict] = None,
                           owner: Optional[str] = None) -> tuple[dict, dict]:
    """type 模式：分段 → 对齐（voice_path 优先，否则逐段 TTS）→ builder 产出
    seek 契约场景序列 → (storyboard, meta)。

    storyboard 供 compose_storyboard（voice_path 为 TTS 路径时折入
    storyboard.voice_path，compose 自取）；meta 含 segments 对齐表 / 计费
    口径 / type，供账本 metadata。
    """
    if not script:
        raise ValueError("render_video(type=...) requires script (口播稿文本或路径)")
    inputs = dict(inputs or {})

    type_json = _gate_type(type_id)
    builder = BUILDER_REGISTRY[type_id]

    plan_slug = typed_plan_slug(type_id, script, inputs, voice_path, bgm)

    raw = split_script(_read_script(script))
    # 结构数对照在 TTS 花费之前（骨架 Segment，渲染前零产物）
    builder.validate_inputs(inputs, skeleton_segments(raw))

    if voice_path:
        segments = align_voice_path(voice_path, raw)
        voice_mode, voice_ref = "voice_path", voice_path
        billing_tts = None
    else:
        segments = align_tts(raw, idem_base=plan_slug)
        # 逐段 TTS → 单一全轨（compose 的 -shortest 契约吃单文件）
        audio_dir = ensure_directory_rel("audio", plan_slug)
        full_voice = concat_audio([s["audio_path"] for s in segments],
                                  DOWNLOADS_DIR / audio_dir / f"{plan_slug}.voice.mp3")
        voice_mode = "tts"
        voice_ref = f"audio/{plan_slug}/{full_voice.name}"
        billing_tts = [
            {"name": s["name"], "chars": len(s["text"]),
             "duration_ms": round(s["duration_s"] * 1000),
             "asset": s["audio_path"]}
            for s in segments
        ]

    size = _parse_orientation(inputs, type_json)
    theme = load_theme()
    scenes = builder.build(segments, inputs, size, theme)

    tail_pad = int((type_json.get("defaults") or {}).get(
        "tailPad", TAIL_PAD_FRAMES_DEFAULT))
    scenes = apply_tail_pad(scenes, tail_pad)

    storyboard = {"size": size, "scenes": scenes,
                  "voice_path": voice_ref}

    scene_seconds = round(sum(float(s["duration_s"]) for s in scenes), 3)
    meta = {
        "type": type_id,
        "renderer": "html",
        "composition": type_json.get("composition"),
        "plan_slug": plan_slug,
        "size": size,
        "tail_pad_frames": tail_pad,
        "voice_mode": voice_mode,
        "voice_path": voice_ref,
        "segments": [
            {"name": s["name"], "text": s["text"],
             "duration_s": s["duration_s"], "sentences": s["sentences"],
             "chars": len(s["text"])}
            for s in segments
        ],
        "billing": {
            "mode": voice_mode,
            "chars": sum(len(s["text"]) for s in raw),
            "tts_segments": billing_tts,
            "scene_seconds": scene_seconds,
            "unit_type": "second",  # render_video usage 行计价口径（frame→秒）
        },
        "bgm": bgm,
    }
    return storyboard, meta


# ─── composition 路径（契约 v2，W3.1） ─────────────────────────────────────

def _composition_clips(parts: dict, key: str, type_id: str) -> list[dict]:
    """builder.build_composition 产物的片段清单（缺 start/duration 早报错）。"""
    clips = parts.get(key) or []
    if not isinstance(clips, list):
        raise ValueError(
            f"{type_id}.build_composition 返回的 {key} 必须是 list，"
            f"收到 {type(clips).__name__}")
    out: list[dict] = []
    for i, clip in enumerate(clips):
        if not isinstance(clip, dict):
            raise ValueError(
                f"{type_id}.build_composition {key}[{i}] 必须是 dict，"
                f"收到 {type(clip).__name__}")
        missing = [k for k in ("start", "duration") if k not in clip]
        if missing:
            raise ValueError(
                f"{type_id}.build_composition {key}[{i}] 缺 {missing} —— clip "
                "契约：visual {start, duration, html, seek_js?} / "
                "subtitle {start, duration, text}")
        out.append(dict(clip))
    return out


def _asset_name(role: str, ref) -> str:
    """素材在渲染作业内的文件名（voice.mp3 / bgm.mp3；确定性、防撞名）。"""
    suffix = Path(str(ref)).suffix.lower() or ".mp3"
    return f"{role}{suffix}"


def _resolve_composition_bgm(bgm, owner: Optional[str]):
    """bgm 参数 → 可混流的绝对文件 spec（已解析的 dict 原样透传）。

    path 引用不触达账本；asset_id 引用走 render.resolve_bgm 的资产账本
    （本人 bgm 或平台种子曲库），与 compose_storyboard 同一解析口径。
    """
    if bgm is None:
        return None
    if isinstance(bgm, dict) and bgm.get("file"):
        return dict(bgm)
    from ..render import resolve_bgm  # 延迟 import：避免把账本依赖拖进本模块
    return resolve_bgm(bgm, owner)


def build_typed_composition(type_id: str, script: str, inputs: Optional[dict],
                            voice_path: Optional[str] = None,
                            bgm: Optional[dict] = None,
                            owner: Optional[str] = None) -> tuple[str, dict]:
    """type 模式（契约 v2）：分段/对齐 → builder 片段 → HyperFrames
    composition HTML。

    分段/对齐逻辑与 build_typed_storyboard 完全一致（voice_path 优先 →
    ffprobe 比例分摊；否则逐段 TTS + concat 全轨），结构校验仍在 TTS 之前
    （骨架 Segment）。区别只在产出面：builder 返回 visual/subtitle 片段，
    这里组装旁白/BGM 音频轨，交 composition.build_composition_html 编译成
    中性 composition。

    返回 (composition_html, meta)；meta 沿用 storyboard 路径的结构
    （segments/billing/voice_mode/plan_slug），另加 engine="hyperframes"、
    scene_seconds、fps、duration_s 与 assets（渲染面上传清单：
    [{role, path, source}]，source 为绝对路径或 downloads 相对引用）。
    """
    if not script:
        raise ValueError("render_video(type=...) requires script (口播稿文本或路径)")
    inputs = dict(inputs or {})

    type_json = _gate_type(type_id)
    builder = BUILDER_REGISTRY[type_id]
    # 未迁移 builder 在 TTS 花费之前就拒（默认实现 = 契约 v2 未实现）
    if type(builder).build_composition is AbstractBuilder.build_composition:
        raise NotImplementedError(
            f"builder '{type_id}' 尚未实现 build_composition（契约 v2）——"
            "该类型继续走 build() / storyboard 路径（render_video 当前仍用 "
            "W1 路径，W4 切流后统一）")

    plan_slug = typed_plan_slug(type_id, script, inputs, voice_path, bgm)

    raw = split_script(_read_script(script))
    # 结构数对照在 TTS 花费之前（骨架 Segment，渲染前零产物）
    builder.validate_inputs(inputs, skeleton_segments(raw))

    if voice_path:
        segments = align_voice_path(voice_path, raw)
        voice_mode, voice_ref = "voice_path", voice_path
        billing_tts = None
    else:
        segments = align_tts(raw, idem_base=plan_slug)
        # 逐段 TTS → 单一全轨（与 storyboard 路径同一产物口径）
        audio_dir = ensure_directory_rel("audio", plan_slug)
        full_voice = concat_audio([s["audio_path"] for s in segments],
                                  DOWNLOADS_DIR / audio_dir / f"{plan_slug}.voice.mp3")
        voice_mode = "tts"
        voice_ref = f"audio/{plan_slug}/{full_voice.name}"
        billing_tts = [
            {"name": s["name"], "chars": len(s["text"]),
             "duration_ms": round(s["duration_s"] * 1000),
             "asset": s["audio_path"]}
            for s in segments
        ]

    # 旁白整轨时长 = 逐段实测时长之和（voice_path 路径即 ffprobe 总时长；
    # TTS 路径即 concat 前的段和，避免再探一次盘）
    audio_s = round(sum(float(s["duration_s"]) for s in segments), 4)

    size = _parse_orientation(inputs, type_json)
    theme = load_theme()

    parts = builder.build_composition(segments, inputs, size, theme)
    if not isinstance(parts, dict):
        raise ValueError(
            f"{type_id}.build_composition 必须返回 "
            "{'visual': [clip…], 'subtitle': [clip…]}，"
            f"收到 {type(parts).__name__}")
    visual_clips = _composition_clips(parts, "visual", type_id)
    subtitle_clips = _composition_clips(parts, "subtitle", type_id)

    # 时长 = max(画面末点, 旁白时长) + tailPad（与 storyboard 路径同口径：
    # type.json defaults.tailPad 帧 @FPS_DEFAULT）；composition 的 data-duration
    tail_pad = int((type_json.get("defaults") or {}).get(
        "tailPad", TAIL_PAD_FRAMES_DEFAULT))
    visual_end = max(
        [float(c["start"]) + float(c["duration"])
         for c in visual_clips + subtitle_clips] or [0.0])
    duration_s = round(max(audio_s, visual_end) + tail_pad / FPS_DEFAULT, 4)

    # 音频轨：旁白整轨 start=0；BGM 独立轨（下一轨），volume/fade_out 来自
    # resolve_bgm 的解析结果（默认 0.2 / fade_out=True 与 compose 同口径）
    voice_asset = _asset_name("voice", voice_ref)
    narration = {"start": 0.0, "duration": audio_s,
                 "src": f"assets/{voice_asset}", "volume": 1.0}
    audio_clips = [narration]
    bgm_meta = None
    assets = [{"role": "voice", "path": f"assets/{voice_asset}",
               "source": voice_ref}]
    bgm_spec = _resolve_composition_bgm(bgm, owner)
    if bgm_spec is not None:
        bgm_file = Path(bgm_spec["file"])
        bgm_asset = _asset_name("bgm", bgm_file)
        bgm_volume = float(bgm_spec.get("volume", 0.2))
        bgm_fade = bool(bgm_spec.get("fade_out", True))
        audio_clips.append({
            "start": 0.0, "duration": duration_s,
            "src": f"assets/{bgm_asset}", "volume": bgm_volume,
            "fade_out": bgm_fade,
        })
        assets.append({"role": "bgm", "path": f"assets/{bgm_asset}",
                       "source": str(bgm_file)})
        bgm_meta = {
            "ref": (f"asset:{bgm_spec['asset_id']}" if bgm_spec.get("asset_id")
                    else f"path:{bgm_spec.get('path') or bgm_file}"),
            "volume": bgm_volume,
            "fade_out": bgm_fade,
        }

    tracks = [
        {"index": VISUAL_TRACK_INDEX, "kind": "visual", "clips": visual_clips},
        {"index": SUBTITLE_TRACK_INDEX, "kind": "subtitle",
         "clips": subtitle_clips},
        {"index": AUDIO_TRACK_INDEX, "kind": "audio", "clips": audio_clips},
    ]
    if bgm_meta is not None:
        tracks.append({"index": BGM_TRACK_INDEX, "kind": "audio",
                       "clips": audio_clips[1:]})

    composition_html = build_composition_html(
        {"size": size, "duration_s": duration_s, "fps": FPS_DEFAULT,
         "tracks": tracks},
        theme)

    scene_seconds = round(sum(float(c["duration"]) for c in visual_clips), 3)
    meta = {
        "type": type_id,
        "renderer": type_json.get("renderer"),
        "engine": "hyperframes",
        "composition": type_json.get("composition"),
        "plan_slug": plan_slug,
        "size": size,
        "fps": FPS_DEFAULT,
        "duration_s": duration_s,
        "scene_seconds": scene_seconds,
        "tail_pad_frames": tail_pad,
        "voice_mode": voice_mode,
        "voice_path": voice_ref,
        "segments": [
            {"name": s["name"], "text": s["text"],
             "duration_s": s["duration_s"], "sentences": s["sentences"],
             "chars": len(s["text"])}
            for s in segments
        ],
        "billing": {
            "mode": voice_mode,
            "chars": sum(len(s["text"]) for s in raw),
            "tts_segments": billing_tts,
            "scene_seconds": scene_seconds,
            "unit_type": "second",  # render_video usage 行计价口径（frame→秒）
        },
        "bgm": bgm_meta,
        "assets": assets,
    }
    return composition_html, meta


# ─── 补图 confirm 协议（W3.3，公共层；carousel 等并行波次共用） ─────────────

def collect_pending_images(inputs: dict) -> list[dict]:
    """inputs.images 清单里的待补图项（提示词）。

    条目形态（对齐 carousel type.json inputs.images.desc）：
      - {"prompt": str, "size"?: str}      → 待补图（提示词），恒定
      - {"path": str} / 已存在的文件路径    → 就绪，跳过
      - 纯字符串且不是已存在文件            → 仅 inputs.generate 为真时视为
                                             待补 prompt（缺图补图开关）
    返回 [{"index": int, "prompt": str, "size"?: str}, ...]（按清单序）。
    """
    images = inputs.get("images")
    if not isinstance(images, list):
        return []
    from .alignment import _resolve_file
    want_generate = inputs.get("generate") is True or \
        str(inputs.get("generate", "false")).strip().lower() == "true"
    pending: list[dict] = []
    for i, item in enumerate(images):
        if isinstance(item, dict):
            prompt = item.get("prompt")
            if isinstance(prompt, str) and prompt.strip() and not item.get("path"):
                entry = {"index": i, "prompt": prompt.strip()}
                if item.get("size"):
                    entry["size"] = str(item["size"])
                pending.append(entry)
        elif isinstance(item, str) and item.strip():
            if _resolve_file(item).is_file():
                continue
            if want_generate:
                pending.append({"index": i, "prompt": item.strip()})
    return pending


def resolve_pending_images(inputs: dict,
                           owner: Optional[str] = None) -> tuple[dict, list[dict]]:
    """confirm_images=true 分支：逐待补项调 generate_image 补图（清单入账），
    产物路径（downloads 相对）回填 inputs.images。

    返回 (回填后的 inputs, 生成清单)；生成清单由调用方并入账本 metadata。
    无待补项时原样返回（不发起任何生成）。
    """
    pending = collect_pending_images(inputs)
    if not pending:
        return inputs, []
    from ..generate import generate_image
    images = list(inputs.get("images") or [])
    generated: list[dict] = []
    for p in pending:
        res = generate_image(prompt=p["prompt"], size=p.get("size"))
        rel = (res.get("file_paths") or [""])[0]
        if not rel:
            raise RuntimeError(
                f"generate_image produced no file for prompt: {p['prompt'][:60]}")
        images[p["index"]] = rel
        generated.append({"index": p["index"], "prompt": p["prompt"],
                          "asset_id": res.get("id"), "file_path": rel})
    return {**inputs, "images": images}, generated


# 触发 builder 自动发现（须在 register/AbstractBuilder 定义之后）
from .builders import discover_builders as _discover_builders  # noqa: E402
_discover_builders()

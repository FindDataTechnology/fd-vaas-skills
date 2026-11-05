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

type 模式计划键（W1.4）：type+script+inputs+voice_path+bgm 全折入
（typed_plan_slug，同输入重放免费，接既有 scoped slug 纪律）。
"""

import hashlib
import json
from typing import Optional

from ...utils import DOWNLOADS_DIR, VAAS_ROOT, ensure_directory_rel
from .alignment import (FPS_DEFAULT, TAIL_PAD_FRAMES_DEFAULT, Segment,
                        align_tts, align_voice_path, apply_tail_pad,
                        concat_audio, skeleton_segments, split_script)
from .theme import load_theme

# fd-vaas-video-creator 类型注册表（type.json 的单一事实源）
VIDEO_TYPES_DIR = VAAS_ROOT / ".agents" / "skills" / "fd-vaas-video-creator" / "types"


class AbstractBuilder:
    """Typed-scene builder 基类（契约见模块 docstring；子类覆写两个方法）。"""

    type_id: str = ""

    def validate_inputs(self, inputs: dict, segments: list[Segment]) -> None:
        raise NotImplementedError

    def build(self, segments: list[Segment], inputs: dict,
              size: list[int], theme: dict) -> list[dict]:
        raise NotImplementedError


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
    """type.json 三道 gate：注册存在 → renderer=html → builder 已注册。"""
    type_json = load_type_json(type_id)
    if type_json.get("renderer") != "html":
        raise ValueError(
            f"video type '{type_id}' is not an html-renderer type "
            f"(renderer={type_json.get('renderer')!r}) — 本 change 的 type "
            '模式只服务 type.json 声明 "renderer": "html" 的类型')
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
    """script 为文件路径则读文本，否则视为内联口播稿。"""
    from pathlib import Path
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

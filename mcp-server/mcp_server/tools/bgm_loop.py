"""BGM 短于片长时预循环补长（composition 路径的缺失补丁）。

背景：文档承诺「曲短 -stream_loop 循环补长」，但那只在**旧 ffmpeg 混流路径**
（render.mix_bgm_onto_audio / compose）成立。W4 切到 composition 之后，BGM 只是
一条 `<audio data-start data-duration src volume>`，没有 loop 属性——曲比片短时
尾巴是**数字静音**（实测：20s 片 + 15.92s 曲，尾段 17–19.8s mean_volume=-91.0dB，
中段 -22.8dB）。

这里在提交渲染前把曲**预循环**成覆盖片长的文件（ffmpeg -stream_loop，确定性：
同一输入+片长 → 同一文件名，重复调用复用）。渲染器侧无需理解 loop 语义。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

# 判定「够长」的容差：片长 0.15s 内的差距不值得重编码
_TOLERANCE_S = 0.15

# MPEG-1 Layer III 的合法最低码率是 32kbps；反推出的码率低于它，说明
# duration 元数据不可信（见 _probe_seconds 注释里的实测反例）。
_MP3_MIN_KBPS = 32


def _probe_seconds(path: Path) -> Optional[float]:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return _duration_from_frames(path)
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        return _duration_from_frames(path)

    # 元数据自洽性校验：同一首种子曲（511751B / 15.92s），本地 ffmpeg 的
    # format=duration 读 15.92s，而 CI 的静态 ffmpeg 构建读成 205.08s
    # （反推码率 ≈20kbps，44.1kHz 立体声不可能）→ 补长被误判为「曲已够长」
    # 而跳过，成片尾段静音。duration 一高估，BGM 就会悄悄不补长，所以这里
    # 不能只信一个字段：反推码率不合理时改数解码帧。
    try:
        size = path.stat().st_size
    except OSError:
        return dur
    if dur > 0 and size > 0 and (size * 8 / 1000.0 / dur) < _MP3_MIN_KBPS:
        alt = _duration_from_frames(path)
        if alt is not None:
            return alt
    return dur


def _duration_from_frames(path: Path) -> Optional[float]:
    """按解码帧数算时长（mp3 每帧 1152/576 采样），比容器元数据可靠。"""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames,sample_rate",
         "-of", "default=nw=1", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    vals: dict[str, str] = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    try:
        frames = int(vals["nb_read_frames"])
        rate = int(vals["sample_rate"])
    except (KeyError, ValueError):
        return None
    if frames <= 0 or rate <= 0:
        return None
    # MPEG-1（32kHz 及以上）每帧 1152 采样，MPEG-2/2.5 每帧 576
    spf = 1152 if rate >= 32000 else 576
    return frames * spf / rate


def loop_bgm_to(bgm_path: Path, duration_s: float,
                out_dir: Optional[Path] = None) -> tuple[Path, bool]:
    """曲短于片长 → 预循环补到片长；返回 (可用文件, 是否做了补长)。

    - 时长探测失败 / 曲已够长 → 原样返回，不动文件；
    - 需要补长 → 写 ``<stem>_loop_<ms>ms<suffix>``（同名同参幂等），
      重编码为 192k mp3，避免 -c copy 拼接的时间戳问题。
    """
    bgm_path = Path(bgm_path)
    if duration_s <= 0:
        return bgm_path, False
    actual = _probe_seconds(bgm_path)
    if actual is None or actual + _TOLERANCE_S >= duration_s:
        # 诊断留痕：这条静默返回与下面的编码失败，在 CI 上是同一个 False，
        # 只报「assert False is True」时无法区分「探测失败」和「曲已够长」。
        print(
            f"ℹ️ BGM 预循环跳过: probe_seconds={actual} duration_s={duration_s} "
            f"tolerance={_TOLERANCE_S}",
            flush=True,
        )
        return bgm_path, False

    out_dir = Path(out_dir) if out_dir is not None else bgm_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{bgm_path.stem}_loop_{int(round(duration_s * 1000))}ms.mp3"
    if not target.is_file() or (_probe_seconds(target) or 0) + _TOLERANCE_S < duration_s:
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1",
             "-i", str(bgm_path), "-t", f"{duration_s:.3f}",
             "-c:a", "libmp3lame", "-b:a", "192k", str(target)],
            capture_output=True, text=True)
        if r.returncode != 0 or not target.is_file():
            # 补长失败不该让整片失败：退回原文件（尾段静音，行为与修复前一致）。
            # 但**必须留痕**：早先这里静默 return False，CI 上两条用例只报
            # 「assert False is True」，日志里没有任何可归因信息——环境差异
            #（编码器缺失/参数不支持）无从判断。失败原因写 stderr 供 CI 归因。
            print(
                f"⚠️ BGM 预循环失败（退回原文件，尾段会是静音）: ffmpeg rc={r.returncode} "
                f"target_exists={target.is_file()} stderr={(r.stderr or '').strip()[:500]}",
                flush=True,
            )
            return bgm_path, False
    # 硬保险：对外只返回确实存在的文件
    return (target, True) if target.is_file() else (bgm_path, False)

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


def _probe_seconds(path: Path) -> Optional[float]:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


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

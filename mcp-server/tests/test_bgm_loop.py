"""BGM 预循环：曲短于片长时补长（否则 composition 尾巴是数字静音）。

实测背景：20s 片 + 15.92s 曲 → 尾段（17–19.8s）mean_volume=-91.0dB（数字静音），
中段 -22.8dB。composition 的 <audio> 没有 loop 属性，旧 ffmpeg 混流路径的
"-stream_loop 补长" 在 W4 切流后失效。
"""

from pathlib import Path

import pytest

from mcp_server.tools.bgm_loop import loop_bgm_to

SEED = Path(__file__).resolve().parents[1] / "mcp_server" / "templates" / "bgm" / "carefree.mp3"


@pytest.mark.skipif(not SEED.is_file(), reason="种子曲库未随仓提供")
def test_loops_short_track_to_target(tmp_path):
    out, looped = loop_bgm_to(SEED, 20.0, tmp_path)
    assert looped is True
    assert out != SEED and out.is_file()
    assert out.name == "carefree_loop_20000ms.mp3"
    from mcp_server.tools.bgm_loop import _probe_seconds
    assert _probe_seconds(out) >= 19.9


@pytest.mark.skipif(not SEED.is_file(), reason="种子曲库未随仓提供")
def test_leaves_long_track_untouched(tmp_path):
    out, looped = loop_bgm_to(SEED, 5.0, tmp_path)
    assert looped is False
    assert out == SEED


@pytest.mark.skipif(not SEED.is_file(), reason="种子曲库未随仓提供")
def test_idempotent(tmp_path):
    a, _ = loop_bgm_to(SEED, 18.0, tmp_path)
    stamp = a.stat().st_mtime_ns
    b, looped = loop_bgm_to(SEED, 18.0, tmp_path)
    assert b == a and looped is True
    assert b.stat().st_mtime_ns == stamp, "同名同参应复用，不重复编码"


def test_missing_file_passthrough(tmp_path):
    ghost = tmp_path / "nope.mp3"
    out, looped = loop_bgm_to(ghost, 20.0, tmp_path)
    assert out == ghost and looped is False, "探测失败不应让整片失败"

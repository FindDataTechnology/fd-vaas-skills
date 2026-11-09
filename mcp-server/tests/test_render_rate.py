"""编码码率透传（DEBT-RENDER-ENC-01 的入口）。

深色大面积平坦内容按默认 CRF 会压出前帧残影与色带；这里锁住三条通道：
环境变量 → render.py → render_client → 渲染面请求体，以及客户端的形状校验。
"""

import pytest

from mcp_server.tools import render_client

# conftest 的 autouse 夹具会把 render_client.submit_render 整体换成假对象；
# 本文件验的是真函数的校验与请求体，用 real_render 标记绕开打桩（不联网：
# 用例自己拦 _request）。
pytestmark = pytest.mark.real_render


def test_env_rate_kwargs(monkeypatch):
    from mcp_server.tools.render import _render_rate_kwargs

    monkeypatch.delenv("VAAS_RENDER_CRF", raising=False)
    monkeypatch.delenv("VAAS_RENDER_VIDEO_BITRATE", raising=False)
    monkeypatch.delenv("VAAS_RENDER_MAX_BITRATE", raising=False)
    assert _render_rate_kwargs() == {}

    monkeypatch.setenv("VAAS_RENDER_CRF", "12")
    monkeypatch.setenv("VAAS_RENDER_MAX_BITRATE", "12M")
    assert _render_rate_kwargs() == {"crf": 12, "max_bitrate": "12M"}

    monkeypatch.setenv("VAAS_RENDER_CRF", "abc")
    with pytest.raises(ValueError):
        _render_rate_kwargs()


@pytest.mark.parametrize("kwargs", [
    {"crf": 99},
    {"crf": -1},
    {"crf": 12.5},
    {"max_bitrate": "abc"},
    {"video_bitrate": "8MB"},
    {"crf": 12, "video_bitrate": "6M"},   # CLI 同源互斥
])
def test_client_rejects_bad_rate(kwargs):
    with pytest.raises(ValueError):
        render_client.submit_render("<html>x</html>", job_id="j", **kwargs)


def test_rate_reaches_request_body(monkeypatch):
    """渲染面请求体带上码率字段（不真的发请求：拦 _request）。"""
    sent = {}

    def fake_request(url, data=None, method="GET", headers=None, timeout=None):
        sent["url"] = url
        sent["body"] = data
        return b"", {}

    monkeypatch.setattr(render_client, "_request", fake_request)
    render_client.submit_render(
        "<html>x</html>", job_id="j", crf=12, max_bitrate="12M")
    import json

    payload = json.loads(sent["body"].decode("utf-8"))
    assert payload["crf"] == 12
    assert payload["max_bitrate"] == "12M"
    assert "video_bitrate" not in payload

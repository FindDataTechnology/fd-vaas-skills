"""共享测试夹具（W4 起视频渲染走独立渲染面）。

绝大多数单测只关心 composition/契约/账本，不该依赖真实渲染面进程：
`_stub_render_plane` 为 autouse，把 `render_client.submit_render` 换成
确定性假实现。需要真实出片的用例打 `@pytest.mark.real_render`（本文件的
autouse 会跳过打桩），并自行在渲染面/浏览器不可用时 skip。
"""

import pytest


class FakeRenderPlane:
    """记录调用参数，返回确定性的假成片。"""

    def __init__(self):
        self.calls = []
        self.engine = "hyperframes@0.9.26"
        self.fail_with = None

    def __call__(self, html, assets=None, fps=30, quality="looks",
                 format="mp4", job_id="", base_url=None, timeout=None,
                 crf=None, video_bitrate=None, max_bitrate=None):
        self.calls.append({"html": html, "assets": list(assets or []),
                           "fps": fps, "quality": quality,
                           "format": format, "job_id": job_id,
                           "crf": crf, "video_bitrate": video_bitrate,
                           "max_bitrate": max_bitrate})
        if self.fail_with is not None:
            raise self.fail_with
        return (b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64,
                {"x-engine": self.engine, "x-job-id": job_id,
                 "x-render-ms": "1", "x-warnings": "[]"})

    @property
    def last(self):
        assert self.calls, "submit_render 未被调用"
        return self.calls[-1]


@pytest.fixture(autouse=True)
def _stub_render_plane(request, monkeypatch):
    """默认打桩渲染面；`real_render` 标记的用例走真实 HTTP。"""
    if request.node.get_closest_marker("real_render"):
        return None
    from mcp_server.tools import render_client
    fake = FakeRenderPlane()
    monkeypatch.setattr(render_client, "submit_render", fake, raising=True)
    request.node._vaas_fake_plane = fake
    return fake


@pytest.fixture
def fake_render_plane(request):
    """取当前用例的假渲染面（与 autouse 同一个实例）。"""
    fake = getattr(request.node, "_vaas_fake_plane", None)
    assert fake is not None, "该用例被标记为 real_render，无假渲染面"
    return fake


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "real_render: 需要真实渲染面（HTTP）的出片用例")

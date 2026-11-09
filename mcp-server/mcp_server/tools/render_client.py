"""
渲染面 HTTP 客户端（adopt-hyperframes-video-renderer W4 预埋，本波不切流）。

VAAS API 面把 composition HTML + 素材字节提交给独立渲染面（render-plane/，
HyperFrames），取回成片字节：先 `PUT /v1/assets/<sha256>` 入库每个素材
（按 sha256 命名，服务端校验一致），再 `POST /v1/render` 提交作业。

契约（render-plane/README.md）：

  PUT  /v1/assets/<sha256>   原始字节；Content-Type: application/octet-stream
  POST /v1/render            {job_id, fps, quality, format,
                              composition: {html, assets: [{sha256, name, path}]}}
  200                        body 为成片字节流，响应头 X-Engine / X-Job-Id /
                             X-Render-Ms / X-Warnings

配置：`VAAS_RENDER_URL`（默认 http://127.0.0.1:8099）、
`VAAS_RENDER_TIMEOUT_S`（默认 600）。失败抛 RenderPlaneError，消息带
「哪个端点 + 状态码 + error/phase/log_tail」或「连不上 + 该改哪个环境变量」。

注意：本模块**尚未接进 render_video**（W4 才切流；当前 type 模式仍走
compose_storyboard）。
"""

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Optional

__all__ = ["RenderPlaneError", "submit_render", "DEFAULT_BASE_URL",
           "DEFAULT_TIMEOUT_S"]

DEFAULT_BASE_URL = "http://127.0.0.1:8099"
DEFAULT_TIMEOUT_S = 600.0


class RenderPlaneError(RuntimeError):
    """渲染面调用失败。status=None 表示不可达/超时（可重试）。"""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status

    @property
    def retryable(self) -> bool:
        # 不可达/超时（status None）、限流 429、网关类 5xx 可换实例重试；
        # 400（composition 不合规）/413（过大）重试无意义
        return self.status is None or self.status in (429, 500, 502, 503, 504)
    """渲染面调用失败（配置/网络/HTTP 错误统一口径）。"""


def _base_urls(base_url: Optional[str] = None) -> list[str]:
    """渲染面基址列表：base_url > VAAS_RENDER_URLS（逗号分隔多实例）> VAAS_RENDER_URL。"""
    raw = base_url or os.getenv("VAAS_RENDER_URLS") or os.getenv("VAAS_RENDER_URL")
    raw = (raw or DEFAULT_BASE_URL).strip()
    urls = [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]
    for u in urls:
        if not (u.startswith("http://") or u.startswith("https://")):
            raise ValueError(
                f"VAAS_RENDER_URL / base_url 必须是 http(s) URL，收到 {u!r}")
    return urls or [DEFAULT_BASE_URL]


def _base_url(base_url: Optional[str]) -> str:
    url = (base_url or os.getenv("VAAS_RENDER_URL") or DEFAULT_BASE_URL).strip()
    if not url:
        url = DEFAULT_BASE_URL
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError(
            f"VAAS_RENDER_URL / base_url 必须是 http(s) URL，收到 {url!r}")
    return url.rstrip("/")


def _timeout(timeout: Optional[float]) -> float:
    if timeout is not None:
        value = float(timeout)
    else:
        raw = os.getenv("VAAS_RENDER_TIMEOUT_S", "")
        try:
            value = float(raw) if raw else DEFAULT_TIMEOUT_S
        except ValueError as exc:
            raise ValueError(
                f"VAAS_RENDER_TIMEOUT_S 不是数字: {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"render timeout 必须 > 0，收到 {value!r}")
    return value


def _normalize_assets(assets) -> list[tuple[str, bytes]]:
    """素材输入 → [(相对路径, 字节)]。

    支持三种写法（便于 W4 从不同产物面组装）：
      - dict: {"assets/voice.mp3": b"..."}
      - list[dict]: [{"path": "assets/voice.mp3", "bytes": b"..."}]
      - list[(path, bytes)]
    路径必须是作业内相对路径（渲染面拒绝绝对路径与 .. 段）。
    """
    if not assets:
        return []
    if isinstance(assets, dict):
        items = list(assets.items())
    elif isinstance(assets, (list, tuple)):
        items = list(assets)
    else:
        raise ValueError(
            "assets 必须是 dict / list[dict] / list[(path, bytes)]，"
            f"收到 {type(assets).__name__}")

    out: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for i, item in enumerate(items):
        if isinstance(item, dict):
            path = item.get("path") or item.get("name")
            blob = item.get("bytes", item.get("data"))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            path, blob = item
        else:
            raise ValueError(
                f"assets[{i}] 必须是 {{path, bytes}} 或 (path, bytes)，收到 {item!r}")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"assets[{i}].path 必须是非空 string")
        rel = path.strip().replace("\\", "/")
        if rel.startswith("/") or any(seg in ("", ".", "..") for seg in rel.split("/")):
            raise ValueError(
                f"assets[{i}].path 必须是作业内相对路径（无绝对路径/./..），"
                f"收到 {path!r}")
        if rel in seen:
            raise ValueError(f"assets 路径重复: {rel}")
        seen.add(rel)
        if isinstance(blob, (bytes, bytearray)):
            data = bytes(blob)
        else:
            raise ValueError(
                f"assets[{i}].bytes 必须是 bytes，收到 {type(blob).__name__}")
        out.append((rel, data))
    return out


def _error_detail(raw: bytes) -> str:
    """渲染面错误体 → 一行摘要（优先 {error, phase, log_tail}）。"""
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return "(empty body)"
    try:
        payload = json.loads(text)
    except ValueError:
        return text[:500]
    if not isinstance(payload, dict):
        return text[:500]
    parts = [f"{key}={payload[key]}" for key in ("error", "phase")
             if payload.get(key)]
    if payload.get("log_tail"):
        parts.append("log_tail=" + str(payload["log_tail"])[-400:])
    return ", ".join(parts) or text[:500]


def _request(url: str, *, data: bytes, method: str, headers: dict,
             timeout: float) -> tuple[bytes, dict]:
    """单请求封装：成功返回 (body, headers)，失败统一抛 RenderPlaneError。"""
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        detail = _error_detail(exc.read())
        raise RenderPlaneError(
            f"render plane {exc.code} {method} {url}: {detail}",
            status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RenderPlaneError(
            f"render plane unreachable: {url} ({exc.reason}) — "
            "启动渲染面或设置 VAAS_RENDER_URL") from exc
    except (TimeoutError, OSError) as exc:
        raise RenderPlaneError(
            f"render plane {method} {url} failed after {timeout:g}s: {exc}") from exc


def submit_render(html: str, assets=None, fps: int = 30, quality: str = "looks",
                  format: str = "mp4", job_id: str = "",
                  base_url: Optional[str] = None,
                  timeout: Optional[float] = None,
                  crf: Optional[int] = None,
                  video_bitrate: Optional[str] = None,
                  max_bitrate: Optional[str] = None) -> tuple[bytes, dict]:
    """提交 composition 到渲染面，返回 (成片字节, 响应头)。

    参数：
      html    composition 整页 HTML（composition.build_composition_html 产物）
      assets  [(相对路径, bytes)] / {相对路径: bytes} / [{"path","bytes"}]
      fps     渲染帧率（正整数）
      quality 渲染面质量档（draft / looks / delivery / …）
      format  成片格式（mp4 / webm / …）
      job_id  作业键（计划 slug；同一 job_id 的重放语义由渲染面决定）
      base_url 覆盖 VAAS_RENDER_URL（缺省读环境变量）
      timeout  覆盖 VAAS_RENDER_TIMEOUT_S（秒）
      crf      覆盖编码 CRF（0-51，越小越清晰；深色平坦画面按默认 CRF 会压出
               色带与前帧残影，需要时下调）
      video_bitrate 目标码率（如 "6M"），与 crf 互斥（渲染面 CLI 同源约束）
      max_bitrate   峰值码率上限（如 "10M"）

    码率三项只对 mp4/webm 生效（MOV/ProRes 不支持），None 即交给 quality 档。

    实现：素材逐个 PUT /v1/assets/<sha256>（内容寻址，天然幂等），再
    POST /v1/render；响应 body 即视频字节，不落盘（调用方决定落盘/计费）。
    """
    if not isinstance(html, str) or not html.strip():
        raise ValueError("submit_render: html 必须是非空 composition HTML")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("submit_render: job_id 必须是非空 string（计划 slug）")
    if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0:
        raise ValueError(f"submit_render: fps 必须是正整数，收到 {fps!r}")
    if not isinstance(quality, str) or not quality.strip():
        raise ValueError("submit_render: quality 必须是非空 string")
    if not isinstance(format, str) or not format.strip():
        raise ValueError("submit_render: format 必须是非空 string")
    if crf is not None:
        if isinstance(crf, bool) or not isinstance(crf, int) or not 0 <= crf <= 51:
            raise ValueError(f"submit_render: crf 必须是 0-51 整数，收到 {crf!r}")
    if crf is not None and video_bitrate is not None:
        raise ValueError("submit_render: crf 与 video_bitrate 互斥（渲染面 CLI 同源约束）")
    for _label, _val in (("video_bitrate", video_bitrate),
                         ("max_bitrate", max_bitrate)):
        if _val is not None:
            if not isinstance(_val, str) or not re.fullmatch(r"\d+[kKmM]", _val.strip()):
                raise ValueError(
                    f"submit_render: {_label} 须形如 '8M' / '4000k'，收到 {_val!r}")

    bases = _base_urls(base_url) if base_url is None else [_base_url(base_url)]
    tmo = _timeout(timeout)
    prepared = _normalize_assets(assets)
    retries = int(os.getenv("VAAS_RENDER_RETRIES", "2") or 0)
    backoff = float(os.getenv("VAAS_RENDER_RETRY_BACKOFF_S", "0.5") or 0.0)

    # 内容寻址：同一资产的 PUT 天然幂等，重试/换实例无需特殊处理
    digests = [(rel, blob, hashlib.sha256(blob).hexdigest())
               for rel, blob in prepared]
    rate: dict = {}
    if crf is not None:
        rate["crf"] = int(crf)
    if video_bitrate is not None:
        rate["video_bitrate"] = video_bitrate.strip()
    if max_bitrate is not None:
        rate["max_bitrate"] = max_bitrate.strip()

    body = json.dumps({
        "job_id": job_id.strip(),
        "fps": fps,
        "quality": quality.strip(),
        "format": format.strip(),
        **rate,
        "composition": {"html": html,
                        "assets": [{"sha256": d, "name": rel, "path": rel}
                                   for rel, _b, d in digests]},
    }, ensure_ascii=False).encode("utf-8")

    last_exc: Optional[RenderPlaneError] = None
    attempts = retries + 1
    for attempt in range(attempts):
        for base in bases:
            try:
                for rel, blob, digest in digests:
                    _request(f"{base}/v1/assets/{digest}", data=blob,
                             method="PUT",
                             headers={"Content-Type":
                                      "application/octet-stream"},
                             timeout=tmo)
                return _request(
                    f"{base}/v1/render", data=body, method="POST",
                    headers={"Content-Type":
                             "application/json; charset=utf-8"},
                    timeout=tmo)
            except RenderPlaneError as exc:
                last_exc = exc
                if not exc.retryable:
                    raise
                continue  # 换下一个实例
        if attempt + 1 < attempts and backoff > 0:
            time.sleep(backoff * (attempt + 1))
    assert last_exc is not None
    raise RenderPlaneError(
        f"render plane unavailable after {attempts} attempt(s) across "
        f"{len(bases)} instance(s): {last_exc}", status=last_exc.status)

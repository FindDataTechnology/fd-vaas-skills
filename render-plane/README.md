# VAAS 渲染面（Render Plane）

VAAS 的**视频渲染平面**：无状态 HTTP 服务，把 HyperFrames composition 渲染成成片（MP4/WebM/PNG 序列等）。与 API 面（Python，MCP 工具面 + 账本 + 计价）解耦、可多实例、可部署在任意机器。

> 哲学：**API 面负责「说了什么」，渲染面负责「画出来」**。API 面保持轻量（无 Node、无浏览器下载），渲染面是专用重资源平面。

## 契约

| 端点 | 方法 | 说明 |
|---|---|---|
| `/healthz` | GET | 引擎版本 / Node / Chrome 路径 / 容量 / 作业计数 |
| `/v1/version` | GET | 引擎版本（API 面钉版校验） |
| `/v1/assets/<sha256>` | PUT | 原始字节入库（按 sha256 命名，服务端校验一致）；`data:` 内联可跳过 |
| `/v1/render` | POST | 提交作业：composition + 素材引用 → 成片字节流 |

`POST /v1/render` 请求体：

```json
{
  "job_id": "typed-6f2a…",
  "fps": 10,
  "quality": "looks",
  "format": "mp4",
  "composition": {
    "html": "<!doctype html>…",
    "assets": [{"sha256": "…", "name": "img.png", "path": "assets/img.png"}]
  }
}
```

成功响应：`200`，body 为成片字节流；响应头 `X-Engine`、`X-Job-Id`、`X-Render-Ms`、`X-Warnings`（JSON 串）。
失败：`5xx` + `{error, phase, log_tail}`；`429` 队列满；`504` 超时。

## composition 格式（HyperFrames）

```html
<div data-composition-id="main" data-start="0" data-duration="10"
     data-width="1080" data-height="1920" data-fps="10">
  <div class="clip" data-start="0" data-duration="3" data-track-index="0">…</div>
  <audio data-start="0" data-duration="10" data-track-index="2" src="voice.mp3"></audio>
</div>
<script>
  // 非 GSAP 动画用官方自定义运行时钩子（逐帧 seek，纯函数）
  window.__hf = { duration: 10, seek(t) { /* … */ } };
  // 或 GSAP：window.__timelines["main"] = gsap.timeline({paused:true});
</script>
```

**零外链**：composition 中出现 `http(s)://` 资源引用即被拒（400）。前端库（GSAP 等）必须本地 vendor。

## 部署

```bash
# 单机
docker compose up -d --build

# 多机 / 多实例：每台渲染机各跑一份，API 面 VAAS_RENDER_URL 指向 LB 或实例列表
```

API 面接入方式（compose 片段）：

```yaml
services:
  vaas-wanxing:
    environment:
      VAAS_RENDER_URL: "http://vaas-renderer:8099"
    networks: [default, vaas-render-net]

networks:
  vaas-render-net:
    external: true
```

## 隔离模型

- 渲染面容器只接 **internal 网络**（无外网出口）
- 每次作业独立 tmpdir；进程 `HOME` 指向该 tmpdir
- 子进程 env 白名单（`PATH`/`LANG`/`TZ`/`TMPDIR`/`HYPERFRAMES_*`），显式剔除 `VAAS_*`/`OPENBAO_*`/`*TOKEN*`/`*KEY*`/`*SECRET*`
- 并发信号量（默认 1）+ 有界队列（默认 32）+ 硬超时（默认 600s，杀进程组）
- 失败/超时零残留（tmpdir 清理，无部分产物）

## 容量

- 每 worker 一个 Chrome ≈ 256MB；`/dev/shm` ≥ 512m（Chrome 需 ≥256MB）
- 3.8GB 内存机：`VAAS_RENDER_MAX_CONCURRENCY=1`
- 8GB+ 机可设 2-3

## 已知前提

- 引擎钉版 `hyperframes@0.9.26`（package.json + lockfile）；升级须过双跑确定性门禁
- 复用镜像内 chromium/ffmpeg（`HYPERFRAMES_BROWSER_PATH` 等），不下载浏览器
- 遥测/自动安装/更新检查全部关闭（离线）

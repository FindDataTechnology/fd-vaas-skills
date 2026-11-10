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

## 子进程 TMPDIR 与大坑：chromium 单例 socket 的 108 字节上限

**这条是血的教训（DEBT-RENDER-FLAKY-01，2026-11-11）**，改动 `buildChildEnv` 前务必读完。

### 机制

chromium 会在 `TMPDIR` 下建进程单例：

```
$TMPDIR/org.chromium.Chromium.XXXXXX/SingletonSocket
```

这是个 **unix domain socket**，其路径受内核 `sun_path` 上限约束——**108 字节**（含结尾 NUL）。
超了 chromium 不会降级，而是直接：

```
FATAL:chrome/browser/process_singleton_posix.cc:315] Socket path too long: <path>
```

→ chrome `SIGABRT` → puppeteer 报 `Protocol error (Target.setDiscoverTargets): Target closed`
→ 渲染在 `failedStage="Starting frame capture"` 处失败，响应 `exit_code=1 / signal=null`
（**看起来像“引擎自崩”，实际是路径太长；和帧数、分辨率、质量档、GPU、字体全都无关**）。

### 事故经过

早期 `buildChildEnv` 把 `TMPDIR` 指到 `<jobDir>/tmp`，而 `jobDir` 是
`<workdir>/jobs/<safeJobLabel(jobId)>-XXXXXX`，storyboard 的 jobId 是 `compose-<12hex>` 这类长 slug：

```
/tmp/vaas-render/jobs/e2e-bisect--compose-fdfe1c5e0a1d-9F3HaI/tmp/org.chromium.Chromium.<rand>/SingletonSocket
└────────────────────────────── 110 字节 ──────────────────────────────────────────────────────────┘
```

→ 20s 分镜必失败；而手工在 `/tmp/m1` 这类短路径下跑同一份 HTML 却成功。
排查时因为只看到 `log_tail` 里的 crashpad 噪音（真正的 FATAL 在里面），绕了九轮。

### 现行设计（不要退回）

```js
const TMP_ROOT = process.env.VAAS_RENDER_TMP_ROOT || '/tmp/vrp';
// 每个作业一个短且唯一的目录：sha256(homeDir) 前 10 个 hex
env.TMPDIR = path.join(TMP_ROOT, shortTmpLabel(homeDir));
```

- 拼接后长度：`/tmp/vrp/<10hex>` (19) + `/org.chromium.Chromium.XXXXXX/SingletonSocket` (45) = **64 字节**，余量 44
- 引擎退出后 `finally` 里 `rmSync(TMPDIR)`，不随 jobDir 清理路径走（jobDir 的清理分支多，容易漏）

### 运维约束

| 约束 | 说明 |
|---|---|
| **`VAAS_RENDER_TMP_ROOT` 必须短** | 它直接吃掉 socket 路径预算：`len(TMP_ROOT) + 1 + 10 + 45 ≤ 108` ⇒ **`TMP_ROOT` 不得超过 52 字节**。默认 `/tmp/vrp` 只占 8 |
| 不要把它指回 jobDir | jobDir 名字含 plan slug，长度不可控（就是本次事故） |
| macOS 无此限制 | chromium 在 macOS 用 Mach port/lock 文件，不占 `sun_path`；本条只在 linux 生效（自测里按 `process.platform` 分支断言） |
| 症状识别 | 见 `Socket path too long` 或 `exit_code=1 && signal=null` 且 `failedStage="Starting frame capture"`，先量路径长度 |

### 自查一行

```bash
# 在渲染容器内：应 ≤108
python3 -c "print(len('/tmp/vrp/'+'a'*10+'/org.chromium.Chromium.XXXXXX/SingletonSocket'))"
# 或对指定 TMP_ROOT 验算
python3 -c "import sys;r=sys.argv[1];print(len(r)+1+10+45)" /your/tmp/root
```

## 已知前提

- 引擎钉版 `hyperframes@0.9.26`（package.json + lockfile）；升级须过双跑确定性门禁
- 复用镜像内 chromium/ffmpeg（`HYPERFRAMES_BROWSER_PATH` 等），不下载浏览器
- 遥测/自动安装/更新检查全部关闭（离线）

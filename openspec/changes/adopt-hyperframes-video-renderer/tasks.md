# Tasks: adopt-hyperframes-video-renderer

> Phase 0 gate 已于 2026-11-09 实测通过（结论见 design.md「Gate 结论」）：系统浏览器复用、`window.__hf.seek` 适配器钩子、fps/workers/quality/png-sequence、双跑确定性、离线渲染全部成立；已知前提：`/dev/shm` 需 ≥512m、`unshare -n` 需 CAP_SYS_ADMIN、脚手架默认 CDN 需本地 vendor。

## tasks

### W1 渲染面服务（独立，可单测）

- [x] W1.1 渲染面镜像：Node 22 + `hyperframes@0.9.26`（npmmirror 构建、精确钉版、lockfile）+ chromium + ffmpeg + CJK 字体；构建期 `hyperframes doctor` 门禁
- [x] W1.2 `POST /v1/render` 作业 API（无状态）：composition + 素材（multipart/sha256）→ 成片（流式或上传地址）+ 引擎版本 + 耗时 + 告警
- [x] W1.3 幂等作业（`job_id` 去重）+ 并发上限（`-w` 可配）+ 硬超时 + 进程组 kill
- [x] W1.4 按作业沙箱：独立 tmpdir、env 白名单（剔除平台密钥）、无外网（internal 网络优先 / unshare -n 备选）、`--shm-size=512m`、内存限额
- [x] W1.5 健康检查（`/healthz`：引擎版本 + doctor 摘要 + 容量）+ 版本回报
- [x] W1.6 渲染面单测/自测：最小 composition 出片、幂等、超时零残留、密钥 env 不可见、零外链拒绝

### W2 spec + 编译器（VAAS 侧，离线）

> W1 完成记录（2026-11-09，容器实测）：镜像 2.0GB（node22+hyperframes0.9.26+chromium+ffmpeg+fonts）；`healthz` 通（engine/chrome/workers/doctor）；同网络容器访问 OK；**外网隔离实测阻断**（egress 000）；真作业 200 出 mp4（ftypisom）；**双跑 md5 一致**（668203cf…）；零外链 400 并指名资源；mac 自测 44/44（env 不泄漏/超时 504 零残留/队列 429）。构建坑：node slim 需 http 源（无 ca 证书）、bin 在 node_modules/.bin。

- [ ] W2.1 `tools/composition.py`：`CompositionSpec` 模型 + 校验（size/duration/fps/tracks/clips）
- [ ] W2.2 `compile_composition(spec)`：clips → `data-*` composition HTML；品牌令牌注入（theme 单源、kebab 规则）；零外链扫描
- [ ] W2.3 前端库本地 vendor（GSAP/Lottie 等，按需）+ 编译器内联；禁 CDN
- [ ] W2.4 编译器单测：多轨落位/字幕轨/音频轨/品牌变量/零外链/素材引用

### W3 五 builder 改声明式

- [x] W3.1 builder 契约 v2（`build() -> {visual, subtitle}`），删 seek JS；`typed_scenes/__init__` 适配；音频统一注入
- [x] W3.2 news-flash / listicle（卡族与 rank 弹入）
- [x] W3.3 carousel（kenburns + 段淡入 + 段字幕）
- [x] W3.4 data-viz（`window.__hf.seek` 驱动 ECharts + 三图型）
- [x] W3.5 kinetic-quote（逐句入场 + `**词**` 强调）
- [x] W3.6 type.json ×5 `renderer: "hyperframes"`；templates_list runtime 标注同步
- [x] W3.7 结构数对照 / 补图 confirm 协议在契约 v2 下保持

### W4 切流：render_video 委托渲染面

> W3 完成记录（2026-11-09）：五类型 build_composition 全部落地（news-flash/listicle/carousel/kinetic-quote/data-viz），type.json ×5 renderer=hyperframes。**关键修复**：HyperFrames 逐帧驱动靠 `window.__timelines[main].seek(t)`，仅 `window.__hf.seek` 时动画静止（0.9.26 实测：像素 0→71→142→212→255）——`composition._seek_runtime` 现同时注册两者。data-viz 惰性初始化 echarts（脚本早于挂载，顶层 DOM 必 null）。测试 342→464 全绿；编译产物真渲染 4.5s/301.8KB，抽帧 md5 全不同。

- [ ] W4.1 `render_video` 切流：storyboard/type → composition → 提交作业；删 `_render_html_frames`/`_ffmpeg` 视频分支
- [ ] W4.2 计划哈希折入引擎版本；确定性重放（同 job_id 返回同结果）
- [ ] W4.3 作业客户端：`VAAS_RENDER_URL` 契约 + 重试/多实例派发 + 超时 + 明确错误
- [ ] W4.4 诊断入账本（引擎版本/耗时/告警）；失败零残留
- [ ] W4.5 `_scene_guard` 升级为 composition 级校验

### W5 测试重定向

- [ ] W5.1 既有 342 测试中针对 seek 契约/自制帧循环的用例改到 composition 契约
- [ ] W5.2 确定性套件：五类型 voice_path 腿双跑帧级一致（渲染面内）
- [ ] W5.3 隔离套件：外链被拒/越权路径不可达/密钥 env 不可见/超时零残留/幂等
- [ ] W5.4 静态出口回归：render_still / render_document 全绿（引擎无关）

### W6 上产与收口

- [ ] W6.1 渲染面部署（推荐 cheap-6 8c/7.9G，不绑单机）+ `VAAS_RENDER_URL` 接入 API 面；多实例派发冒烟
- [ ] W6.2 生产 E2E：五类型 voice_path 腿（mp4 + 签名下载 + 帧级确定性）+ still/doc 回归
- [ ] W6.3 文档：`fd-vaas-storyboard` SKILL.md 改 composition 格式/适配器/轨模型；deploy README（渲染面 + 钉版 + 隔离）
- [ ] W6.4 ADR-0004 增补（渲染面独立、API 面保持无 Node）
- [ ] W6.5 退役 Remotion app 与 fd-vaas-video-creator 渲染管线（types/ 契约保留）；清 `remotion-app/`
- [ ] W6.6 TTS 腿 E2E 复验 + 计价复核（render_video/second 口径不变）

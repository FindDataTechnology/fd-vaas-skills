# Verification evidence: deliver-hosted-surface（2026-11-06，主会话）

## W0 前置收账
- `add-typed-video-html-renderer`（20/20）已 strict 校验后归档为 `2026-11-06-add-typed-video-html-renderer`；presentation-plane/typed-video-html-renderer/video-types 三 spec 已更新（主 spec 现如实规定「type 模式经 HTML 构建器本地/托管一致；Remotion 族托管指路报错」）。W5.2 的图像腿受阻注记原已在其 tasks 中。

## W1 镜像底座
- canonical `deploy/mcp-server.Dockerfile` 重写：apt 层 ffmpeg + fonts-noto-cjk + chromium；pip 层 +mutagen +playwright（不跑 playwright install，渲染面走 `/usr/bin/chromium` 系统回退——render.py `_launch_kwargs` 原生支持）；根 shim `scripts/gen-root-dockerfile.sh` 重生成，`cmp` IDENTICAL（漂移检查绿）。
- `mcp-server/requirements.txt` 与 `pyproject.toml` 依赖同步（mutagen/playwright）；本机 pip install mutagen 实测可用。
- 镜像体积 +~500MB 警示已写进 canonical 头注与 deploy README 存活节；滚版前节点磁盘核对随 DEBT-IMGROLL-01。

## W2 python 腿词元 TTS 出口层（node 腿同算法回灌）
- `scripts/_ciyuan_tts.py` 全量重写为出口层：`split_text_into_segments`（≤150 字句切+硬切，165/170 墙实测口径）、`split_text_into_tokens`、段级合成（3 次重试退避 1.5/3s + 段间 0.3s 调用间隔）+ ffmpeg concat（0.22s 静音）+ 段级 ffprobe 实测时长锚定 captions；短文本单次路径行为不变；`audio_duration_seconds` 恒实测。
- 桥 `litellm-bridge.py` ciyuan 分支：`enable_subtitle=not no_subtitle`（原硬编码 False 摘除）+ `captions_path` 直传驱动；`generators/tts.py` 透传 `captions_source`/`segments` 进响应与账本 metadata。
- 离线校验：560 字 → 4 段全 ≤150；token 切分与 node 同形；captions 单调+段间 gap 推进；ffprobe 实测 1.5s WAV 命中。py_compile 三文件全过。
- 单测：`TestCiyuanPythonLaneParity` 5 项（test_correctness_c1.py）。

## W3 车道 health
- 新增机读台账 `mcp-server/mcp_server/lane_health.json`（8 车道：voice.ciyuan active；voice/image/video volcengine down(unconfigured)；image/video ciyuan down(upstream_blocked→DEBT-LANE-9-01)；render.local active）+ `lane_health.py`（lane_health/lane_down/annotate，未知车道保守 degraded）。
- 发现面：`registry_list_generators`/`registry_describe_generator` 注入 `lane` 块（registry.json 增补 ciyuan 档条目使两档可对比）；`models_voices` provider 块带 lane。
- 执行闸：`runtime.prepare` 在凭证解析**之前**按 env 车道判 health，down → `lane_down` 分类拒绝（CredentialUnavailable 子类）；本地 stdio 保持历史自由（hosted 或 VAAS_LANE_HEALTH_GATE=1 时启用闸）。
- fail-open 修：`templates.py::_load_video_types` 类型目录缺失从静默 `[]` 改为 `templates_unavailable` 响亮错误。
- 探针：`probe_hosted_surface.py` 新增 check 5（discovery carries lane health）。
- 实证：stdio 全量 tools/call `registry_list_generators` → image/ciyuan health=down 如实暴露；pytest 380 全绿（新增 TestLaneHealthSurface 4 项 + TestTemplatesFailOpen 1 项）。

## 待部署侧（外依赖，不阻塞本地验收）
- W4.1 词元 image/video 上游 acct 40 解封/换号 → 实调销账（DEBT-LANE-9-01）。
- W4.2 volcengine 备档 seedream 权限核对；W4.3 豆包 acct 43 复查。
- W5.1 镜像重建 + 上产 + hosted 全面探针（含五类型 type 模式、长文 voice 分段）——与 C1 W5.2 同批滚版（DEBT-IMGROLL-01）。

## 并发会话注记
- node 链（tts.js whisper 对齐）为并行会话进行中工作，本 change 零触碰；node 面红非本 change 责任。

## 部署补证（2026-11-06 晚，主会话）：DEBT-IMGROLL-01 / DEBT-HEALTH-01 销账

- **通道**：cheap-2 = <DEPLOY_NODE_IP>（tailnet <NODE_TAILNET_IP>:30950），sshpass+口令专线；节点无 rsync → tar-over-ssh 同步 `mcp-server/ scripts/ .agents/skills/fd-vaas-video-creator/types/` 到 `/opt/vaas-src-wave6`（6.4M）。
- **构建选择**：节点 `df` 30G/25G used/5.9G avail；`docker run --rm` 实证现役 `sha-338ed2f` 已含 ffmpeg/ffprobe/chromium + mutagen/playwright/markdown/fastmcp。故采用 **FROM 现役镜像的增量构建**（清树 COPY 防退役文件残留 + pip 复核 `deps-ok`），共享渲染底座层，仅叠加 6.4M 源码——避免全量 FROM 再吃 2.4G。canonical 全量 Dockerfile 仍是 build-pool 通道真源，根 shim `cmp` IDENTICAL。
- **滚版**：`/opt/vaas-deploy/docker-compose.vaas.yml` 改 tag → `sha-wave6-202611061854` + 新增 healthcheck（interval 30s/start_period 20s）；`docker compose -f docker-compose.vaas.yml up -d --no-deps --force-recreate vaas-wanxing`（坑：文件名非默认必须显式 `-f`，否则 "no configuration file provided"）。现网 `docker inspect` = healthy。
- **探针**：`scripts/probe_hosted_surface.py` 新增可选 `VAAS_PROBE_USER`（hosted 身份 `X-Forwarded-User` fail-closed 必带）；实跑 **6/6 PASS**：17 工具面精确、publish 面不可见、publish_video 调用拒、discovery lane health 10 块（5 down 如实暴露）。
- **真实生成 E2E**：541 字长文 `generate_voice` → `segments=4`（每段 ≤150 字）、`captions_source=synthetic`、`duration_ms=112356`（ffprobe 实测）、scoped slug `vaastrial--wave6-voice-e2e`、签名 download_url、`credential_source=pool`。同 slug 重放返回同一 id 且 `assets_stats.total_assets` 恒 1 = 零重复计费。
- **实弹抓出并修的老文案**：ciyuan 档 warnings 原写「request proceeded without captions」与 synthetic 字幕已落盘矛盾 → 改为「does not return official word-level timestamps; captions are synthesized from measured segment durations (captions_source=synthetic)」；二次增量重建+滚版后新 slug 实调验证新文案生效（test_correctness_c1 相关 7 项绿）。
- **自愈**：kill 容器 PID1 → T+5s `running/starting restarts=1` → T+10s `healthy` + 容器内 `/health=200`；`deploy/health-watch.sh` 已装 root crontab `*/5`，阈值分支仿真（unhealthy×2 触发 restart、healthy 清戳）通过。

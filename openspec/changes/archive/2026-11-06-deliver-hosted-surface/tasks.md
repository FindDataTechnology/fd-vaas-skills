# Tasks: deliver-hosted-surface

## tasks

### W0 前置收账

- [x] W0.1 归档 `add-typed-video-html-renderer`（20/20）：已 archive 为 2026-11-06-*；三 spec delta 落主 spec（W5.2 图像腿挂账注记原已在档）

### W1 镜像底座补全

- [x] W1.1 canonical 重写：apt ffmpeg+fonts-noto-cjk+chromium；pip +mutagen+playwright（决策注记：不跑 playwright install，渲染面走系统 /usr/bin/chromium 回退——render.py 原生支持，离线友好）
- [x] W1.2 2026-11-06 节点实测：df 30G/25G used/5.9G avail（81%），现役镜像 2.37GB 已含完整渲染底座；故未再叠加 +500MB 全量重建，改增量构建共享底座层（新层仅 6.4M 源码 + pip 复核），滚版后 `docker images` 与 healthy 均正常，磁盘余量 5.8G
- [x] W1.3 根 shim 经 gen-root-dockerfile.sh 重生成，cmp IDENTICAL（C4 单源机制红利）

### W2 python 腿词元出口层对齐

- [x] W2.1 桥 ciyuan 分支：enable_subtitle 参数化（原硬编码 False 摘除）+ captions_path 直传；`alloy` 兜底删除见下注——litellm-bridge `TTS_VOICE` 默认值仍为 alloy，但 hosted 路径恒有显式 voice（manifest 校验强制），直调桥的裸路径留 C6 清（generate_voice 无 voice 时 manifest default 101001 已强制）
- [x] W2.2 出口层下沉 `_ciyuan_tts.py`（桥与 stdio 共享）：≤150 字段切/3×重试退避/段间 0.3s 调用间隔/ffmpeg concat 0.22s 静音/段级 ffprobe 实测 captions；`captions_source` 回传
- [x] W2.3 合成字幕兜底落地（token 均分+实测缩放，形状同官方）；docstring 虚标修正（audio_duration_seconds 现恒实测返回）；speed 诚实已在 C1 参数诚实层（provider 真值化 + warnings）
- [x] W2.4 单测落地（TestCiyuanPythonLaneParity 5 项：分段边界/token 同形/captions 单调+gap/实测探针；hosted 端到端=mock 桥在 C1 测试类已覆盖 file_path 与重放路径）；node 腿测试文件为并发会话工作区，未触碰

### W3 车道健康可见与标注诚实

- [x] W3.1 `lane_health.json`（8 车道）+ `lane_health.py`；registry_list/describe 与 models_voices 注入 `lane` 块；prepare 层 down→lane_down 拒绝（hosted 启用，本地 opt-in；闸在凭证解析之前）
- [x] W3.2 `_load_video_types` 缺目录改 `templates_unavailable` 响亮错误（TestTemplatesFailOpen）；`runtime` 标注一致性=滚版探针项（hosted 五类型实测随 DEBT-IMGROLL-01）
- [x] W3.3 探针新增 check 5「discovery carries lane health」（health 块计数 + down 计数）；每车道最小实调版待滚版后按 health 逐步启用（down 车道现在调=预期失败，探针如实注 down 数）

### W4 上游车道修复（外依赖）

- [ ] W4.1 词元图像/视频：sub2api 侧 acct 40（openai-next 403 封禁）解封或换可用账号——跨仓操作，完成后实调 generate_image/generate_video_submit 全链为销账证据；期间车道保持 down
- [ ] W4.2 volcengine 备档：图像 key 的 seedream 权限核对、TTS 订阅态确认；备档可用性记入白名单文档
- [ ] W4.3 豆包语音 acct 43（upstream-broken）复查并补听记录（词元线既有挂账，顺路收口或显式续挂）

### W5 验收与收口

- [x] W5.1 2026-11-06 上产 cheap-2（<DEPLOY_NODE_IP> / tailnet <NODE_TAILNET_IP>:30950）：tar-over-ssh 源码树 → 增量镜像 `sha-wave6-202611061854` → compose tag+healthcheck → force-recreate → healthy；probe_hosted_surface.py 6/6 PASS（新增 X-Forwarded-User 租户头支持）；长文 voice E2E 4 段合成字幕全绿；见 evidence/verification-notes.md 部署补证节
- [x] W5.2 全量 pytest 380 绿（新增 10 项）+ test_hosted_surface 17/23 面形不回退；deploy README 存活节已有镜像体积警示（能力矩阵与车道健康文档随滚版探针一并同步——sync-external-ledgers W3 承接 trial 面）
- [x] W5.3 勾 tasks、strict 校验绿；归档随滚版批次（W1.2/W4/W5.1 三项部署侧收口后与本波统一收，车道 down 如实保留=车道缺陷条款允许）

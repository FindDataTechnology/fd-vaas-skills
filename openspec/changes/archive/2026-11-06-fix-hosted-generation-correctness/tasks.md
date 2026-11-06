# Tasks: fix-hosted-generation-correctness

## tasks

### W1 工具面正确性（文本源/白名单/参数诚实）

- [x] W1.1 `generators/tts.py`：`file_path` 读文件内容传入桥 `--text`（读空/失败如实报错）；`text`+`file_path` 同给报 invalid_input；桥 `litellm-bridge.py` tts 子命令 `--input` dest 独立或废弃——负例：路径串不再被合成
- [x] W1.2 产物文件名白名单：tts `format`（mp3/wav）、image `output_format`（png/jpeg）生成前枚举校验；落盘路径 `resolve()+is_relative_to` 双重收敛；负例 `format="mp3/../../x"` 拒绝且零文件外溢
- [x] W1.3 参数诚实：`reference_image` 从 `generate_image` 工具面摘除（或桥实现 `--image` 透传两车道并 E2E 补证，二选一，摘除默认）；volcengine 图像 `n` 支持或 warn；`n>1` 全部产物逐张入账 + 响应 count 对账
- [x] W1.4 单测：W1.1-W1.3 各正反例进 `mcp-server/tests/`；全量 pytest 基线（337 项）不回退

### W2 租户隔离与幂等（owner-scoped 一致性）

- [x] W2.1 `tools/generate.py:video_job_status` 以当前 owner 过滤查库；作业表读取路径全量核对（poll/cancel/expire）；托管双租户对演：B 查 A 的 job_id 得不可见错误（探针留证）
- [x] W2.2 全部生成器 insert 统一 `scoped_asset_slug`（image/video/cover/voiceover 现用 raw slug 的四处）；跨租户同 slug 并发各自成立
- [x] W2.3 幂等重放查找改 scoped 域（tts 及其他带 idem 键路径）；重放命中响应补齐 `download_url`（与成功路径同形状）；重放不再产生第二行用量
- [x] W2.4 单测：双 owner 同 slug、重放命中零重计、重放含下载链接

### W3 计价与挂钟

- [x] W3.1 定价实价落地：`pricing.json`（audio ¥0.3/万字符按 voices_manifest.price_note；image/video 按上游实价）入 deploy 配置，替换 example 全零挂载；托管启动缺表/坏表响亮失败（拒启或计价端点明确未配置错误，择一实现）
- [x] W3.2 视频计费改实测：poll 成功下载后 ffprobe 量长入账与资产元数据；sync 路径同理去掉请求值兜底
- [x] W3.3 记账口径归一：unit_type（second/image/char/doc）与 credential_source 枚举对账（`local` 值并入合法枚举或映射），usage 报表可读
- [x] W3.4 子进程超时全覆盖：`runtime.py` subprocess 默认超时（env 可调）+ 各调用点核查（cover/voiceover/publish）；桥 ciyuan `--status` 改单次读取（阻塞轮询逻辑移出托管调用链）
- [x] W3.5 `generators/video.py` 状态解析：CalledProcessError/JSON 错误/5xx 不置 failed，保持原态按 upstream_transient/timeout 返回；仅供应商明确终态失败入 failed

### W4 面泄露与错误治理

- [x] W4.1 错误分类层：租户可见错误统一 invalid_input/credential_unavailable/lane_down/upstream_transient/upstream_error/timeout + 短消息；上游 body/桥命令行仅入服务端日志；image/tts/video 三处 f-string 错误透传改造
- [x] W4.2 `tools/assets.py` 公共素材返回相对路径；hosted 响应全字段扫描零 `/app` 绝对路径（探针断言）
- [x] W4.3 `hosting.py` 签名 base 仅取显式配置；缺配置时响应省略 download_url + 提示文案；`VAAS_PUBLIC_URL` 必设项写入 deploy README 检查单
- [x] W4.4 GC 静默吞错加计数日志；`startswith` 路径收敛改 `is_relative_to`

### W5 验收与收口

- [x] W5.1 本地 pytest 全绿 + `VAAS_HOSTED=1` 同构跑（scoped slug/重放/错误分类）
- [x] W5.2 2026-11-06 与 deliver-hosted-surface 同批滚产 `sha-wave6-202611061854`：探针 6/6（17 工具面/publish 拒/lane health）、hosted 长文 541 字 E2E（4 段 ≤150 字、captions_source=synthetic、实测 112.356s、owner-scoped slug、签名下载、credential_source=pool）、幂等重放（同 slug 同 id、assets 总数恒 1=零重复计费）、文件源/金额脱敏由 380 项单测覆盖。注：双租户互不可见/n=4 全入账为既有单测+架构保证，未在生产另造第二租户（无真实客户，避免脏数据）
- [x] W5.3 证据与台账：evidence/verification-notes.md 落本 change 目录；deploy README 口径同步（compose 挂载实价表、公网基址必设）；strict 校验绿；归档随 W5.2 滚产补证后执行

# Verification evidence: fix-hosted-generation-correctness (2026-11-06, main agent session)

## 已实证（本地）

1. **全量 pytest**：`cd mcp-server && python3 -m pytest tests -q` → **370 passed**（337 基线不回退 + 28 项新契约回归 + 原有多余项）。
2. **新契约测试** `mcp-server/tests/test_correctness_c1.py`（28 项全绿）：
   - file_path 读内容合成（`--text`=文件正文；路径串绝不入 cmd）；text+file_path 互斥、空文件、不可读各报 invalid_input
   - format 白名单（`mp3/../../../../evil` 拒绝且零落盘）
   - hosted 同租户幂等重放命中（scoped 域查找；bridge 仅调 1 次；usage 仅 1 行；slug 带 `tenant-a--` 前缀）
   - 跨租户同 slug 各自成立（无 UNIQUE 冲突）
   - poll 瞬时故障（503 封禁体/TimeoutExpired/不可解析）→ 作业保持 running + `last_poll_error`；供应商终态 failed 如实落
   - poll 成功 → ffprobe 实测 7.4s 入账（units=7.4、metadata.duration_source=measured、scoped slug 入账）；无产物 → 计 0 秒 + warnings（不再编 5 秒）
   - `video_job_status` 经 `current_owner()` 过滤（原 owner=None 越权洞）
   - `reference_image` 已摘出签名（generator+tool 两处）；图像 0 产物大声失败零入账；count 缺口 warnings；row 落 scoped 域
   - 错误脱敏：lane_down 分类且 `openai-next/id=40/group 9/router detail` 字样不出现在租户可见消息
   - 本地 .env 车道 provider 真值化（volcengine 不误报 speed warn；ciyuan 正确 warn）
   - 签名 base 仅 VAAS_PUBLIC_URL；未配置不挂链接不泄内网 host（test_mcp_server 相应旧断言已按新契约改写：request host 假扮内网、断言不泄露）
   - 定价 fail-loud：缺表拒启（实测 traceback：`pricing configuration missing or unreadable`）；实价表 voice char=3e-05（¥0.3/万字符）
   - GC `is_relative_to`：欺骗性 `downloads_evil` 前缀目录不被误删、行仍收
   - `run_bridge` 挂钟：timeout 参数必设且超时归 `timeout:` 分类
3. **桥层**：`--input` 别名摘除（dest 陷阱根除）；词元 video `--status` 改 `status_once` 单次读（hosted poll 不再子进程阻塞 600s）。
4. **计价表**：`mcp-server/pricing.json` 新增（audio 实价先行）；example compose 挂载改真实表。

## 待部署侧补证（并入批次，不阻塞归档纪律=如实注记）

- W5.2 hosted 实例重建滚产 + 探针复跑（file_path/n=4/双租户/脱敏/计价非零）：随 deliver-hosted-surface 的镜像重建**一次滚版**（避免连滚两次）；台账 DEBT-IMGROLL-01 同批。

## 并发会话注记（当日实况）

- `scripts/ci-local.sh` 的 node 段当前红，根因是**另一会话的进行中改动**：`tests/tts-synthetic-captions.test.mjs` 新增 whisper 对齐用例引用 `require('@remotion/captions')`（ESM 下解析不到），且 `generators/tts.js` 正被其编辑（mtime 06:12/06:13）。本 change 未触碰 node 链；留待该会话自行收敛。本 change 的 node 面证据=改动前后 `tts.js`/测试文件 diff 与本会话无交集（git 可核）。

## 部署补证（2026-11-06 晚）：W5.2 hosted 滚产复跑

镜像 `sha-wave6-202611061854` 与 deliver-hosted-surface 同批滚现网（详见该 change 的「部署补证」节）。
实证：probe 6/6 PASS；长文 voice 541 字 → 4 段合成字幕 + 实测 112.356s；同 slug 幂等重放同 id、assets 总数恒 1；owner-scoped slug 与签名下载在现网生效。
`file_path` 文本源对账 / n=4 全入账 / 双租户互不可见 / 错误体脱敏 / 计价非零由 380 项本地单测与既有架构保证覆盖，未在生产另造第二租户（无真实客户，避免脏数据）。

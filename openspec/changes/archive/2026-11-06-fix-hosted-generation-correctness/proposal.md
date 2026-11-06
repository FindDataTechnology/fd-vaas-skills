# Proposal: fix-hosted-generation-correctness

## Why

2026-11-06 五路只读调研（file:line 实锤）发现 hosted 生成面存在成组的正确性/安全缺陷：`generate_voice(file_path=…)` 把路径字符串当台词合成且零计费（`generators/tts.py:197` + `litellm-bridge.py:394`）、`video_job_status` 不带 owner 查库实现跨租户读他人作业（直接违反 `generation-jobs` 既有「跨租户不可见」条款）、幂等重放查 raw slug 而存 scoped slug 导致重放永不命中重复计费、`format`/`output_format` 未白名单可路径穿越写任意文件、计价表全零且缺文件静默兜底（`/usage/summary` 恒 0）、上游错误体（含网关账号细节）原样吐给租户、托管实例响应泄露服务器绝对路径与内网 host:port、子进程零超时且瞬时轮询故障把已付费作业永久判死。无真实客户是当下唯一安全的修窗口——面越用，洞越贵。

## What Changes

- **修复（对既有 spec 的违约实现）**：作业查询 owner 隔离（generation-jobs 已规定「只有归属租户 MAY 查询」）、幂等重放命中（同租户同 idem 键不重生不重计）、用量金额真实（计价表非零、缺表响亮失败）、公共素材响应不泄露绝对路径。
- **ADDED 工具文本源契约**：`generate_voice.file_path` MUST 读文件内容为台词；`text` 与 `file_path` 同给 MUST 显式报错。
- **ADDED 参数安全与文件名白名单**：产物文件名的扩展名 MUST 白名单（mp3/wav、png/jpeg 等），调用方输入 MUST NOT 逃逸产物目录；托管响应只含相对路径。
- **ADDED 参数诚实与降级披露**：车道不支持的参数（`speed`、`reference_image`、volcengine 图像 `n`）MUST NOT 静默吞掉——要么生效、要么响应携 `warnings` 或显式拒绝；`generate_image(n>1)` 全部产物入账。
- **ADDED 上游错误脱敏分类**：租户可见错误收敛为分类码（invalid_input / credential_unavailable / lane_down / upstream_transient / upstream_error），上游原始 body 仅服务端日志。
- **ADDED 调用挂钟上限**：车道子进程全部带超时；作业状态查询单次读取、秒级返回，MUST NOT 在子进程内阻塞轮询。
- **MODIFIED 作业查询与状态机**（generation-jobs）：瞬时查询故障（超时/5xx）MUST NOT 置 `failed` 终态，保持 running 可续查；成功落账按 ffprobe 实测时长计费（现状硬编码 5 秒/请求值）。
- **MODIFIED 租户归属与隔离**（material-store）：全部生成器（image/video/cover/voiceover）统一 scoped slug 写入域；跨租户同 slug 并发各自成立。
- **MODIFIED 计价用量记录与报表 / 签名下载端点**（unified-mcp-interface）：托管计价表缺失/为空 MUST 响亮失败；签名 URL base MUST 来自显式配置，MUST NOT 回落 request host 泄露内网地址（未配置时产物响应不附下载链接并给出明确提示）。
- 不改工具面形状（17/23 面不动）、不动镜像依赖（归 deliver-hosted-surface）、不动词元桥实现细节（除本面契约所需透传）。

## Capabilities

### New Capabilities

（无——全部落入既有 capability 的 delta。）

### Modified Capabilities

- `unified-mcp-interface`：新增文本源/参数安全/参数诚实/错误脱敏/挂钟上限五条 requirement；修订计价与签名下载两条。
- `generation-jobs`：修订「作业查询与状态机」——owner 隔离落地、瞬时故障不终态、实测计费。
- `material-store`：修订「租户归属与隔离」——scoped slug 全域一致与幂等重放同域命中。

## Impact

- **代码**：`mcp-server/mcp_server/generators/tts.py|image.py|video.py|cover.py`、`tools/generate.py`（owner 传递）、`tools/assets.py`（相对路径）、`hosting.py`（签名 base）、`runtime.py`（子进程超时）、`db/models.py`（重放查找）、`scripts/litellm-bridge.py`（--input dest、status 单次读）、`main.py`（pricing fail-loud）；`mcp-server/tests/` 补回归用例并跑全量 pytest（337 项基线不回退）。
- **配置/部署**：`pricing.json` 实价落地（audio 按 manifest ¥0.3/万字符先行），替代现网挂 `pricing.example.json` 全零表的做法；`VAAS_PUBLIC_URL` 部署侧必设检查入 deploy README。
- **外仓**：sub2api/词元上游不在本 change（归 deliver-hosted-surface 与 lane 修复任务）。
- **验证**：本地 pytest + `VAAS_HOSTED=1` 同构跑 + hosted 探针（跨租户读他人 job_id、重放双跑、穿越负例、n=4 全入账）。

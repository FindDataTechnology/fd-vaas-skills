## 1. 词元车道客户端（bridge 层）

- [ ] 1.1 新增 `scripts/_ciyuan_tts.py`：封装 `POST /v1/audio/speech`（model/voice/input/format），
      返回与 `_volcengine_tts.py` 同形状的结果字典（含 `local_path` / `file_size_bytes` /
      `api_latency_ms`）。验证：用试用组 3 key 实调 `qwen3-tts-flash`+`Cherry`，落盘文件 >10KB
      且能被识别为音频。
- [ ] 1.2 新增 `scripts/_ciyuan_image.py`：封装 `POST /v1/images/generations`，解析
      `data[].b64_json` 解码落盘；响应非 JSON 时抛明确错误（不得从 HTML 猜 URL）。
      验证：实调 `gemini-3-pro-image`，落盘文件能被 `file` 识别为图像；再以 `gpt-image-1`
      调用须报「应答形状不合规」而非产出文件。
- [ ] 1.3 新增 `scripts/_ciyuan_video.py`：封装 `POST /v1/contents/generations/tasks` 创建 +
      `GET` 同路径轮询 + 终态下载 `content.video_url`。
      验证：实调 `doubao-seedance-2-0-fast-260128`，轮询至 `succeeded` 并下载到文件，
      `file` 识别为 `ISO Media, MP4`。
- [ ] 1.4 把实测可用模型白名单与已知缺陷（`gpt-image-*` 返回 HTML、
      `doubao-seedance-1-0-pro` 503）写成三个客户端文件的常量注释，标注实测日期 2026-10-16。

## 2. Bridge 与凭证分档

- [ ] 2.1 `scripts/litellm-bridge.py`：三个 `cmd_*` 各增 `if provider == "ciyuan"` 分支调用
      上一步的客户端；移除 litellm 调用路径。验证：`python3 litellm-bridge.py tts --help`
      等仍可用，且 `--provider` 只接受 volcengine/ciyuan。
- [ ] 2.2 拒绝非受支持的 provider 值：显式报错并列出 `volcengine` 与 `ciyuan`，
      不得静默回落。验证：设 `*_PROVIDER=elevenlabs` 实跑，得到明确拒绝错误且无网络调用。
- [ ] 2.3 `mcp-server/mcp_server/credentials.py`：把 `_OPENAI_ENV` 改为按 provider 取 env 映射，
      新增 ciyuan 档（`CIYUAN_API_KEY` / `CIYUAN_BASE_URL` / 各 kind 的模型与 voice）；
      `subprocess_env()` 按 `provider == "ciyuan"` 走新映射。
      验证：单元级构造一条 `provider="ciyuan"` 记录调 `subprocess_env()`，断言环境含
      `CIYUAN_*` 且不含 `ARK_*`。
- [ ] 2.4 生成器 `tts/image/video.py` 的 `finish(...)` 里硬编码的 `"volcengine"` 改为按
      `ctx["resolved"]["provider"]` 取值。验证：本地跑一次生成，用量行的 provider 字段
      反映真实档位。

## 3. 依赖与默认配置

- [ ] 3.1 从 `requirements.txt`（及 pyproject 若有）移除 `litellm`；确认生成链路只剩 stdlib。
      验证：`pip freeze | grep -i litellm` 为空，且三条车道仍能实调成功。
- [ ] 3.2 `.env.example` 与 README（中/英）的 Provider 配置表更新：受支持档位改为
      volcengine/ciyuan，默认模型改为 `gemini-3-pro-image` /
      `doubao-seedance-2-0-fast-260128` / `qwen3-tts-flash`+`Cherry`，
      并标注「语音一把 key、图像/视频另一把 key」的分组口径。
      验证：文档grep 无 `elevenlabs`/`azure` 等失效 provider 残留。
- [ ] 3.3 `deploy/README.md` 的 OpenBAO 路径说明补 ciyuan 档示例（三条 kind 路径、
      provider 字段、分组口径）。验证：路径示例与 `credentials.py` 实际读取路径一致。

## 4. 端到端验证

- [ ] 4.1 本地三条真请求：用试用两把 key 经 MCP 工具实跑 `generate_voice` /
      `generate_image` / `generate_video_submit`+`video_job_status`，
      确认产物落盘非空、类型正确、工具响应形状不变。
      验证：音频可播、图像 `file` 为 JPEG、视频 `file` 为 MP4，三条均非占位文件。
- [ ] 4.2 负向验证：图像用 `gpt-image-1` 调须明确报错；视频用 `doubao-seedance-1-0-pro`
      调须如实报 503；不得产出空文件。
- [ ] 4.3 托管模式验证：向 OpenBAO 写三条 ciyuan 记录（tts 用组 3 key、
      image/video 用组 9 key），滚版后经 MCP 各调一次成功；回滚验证=改回 volcengine 记录
      后原后端恢复可用。

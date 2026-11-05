# ciyuan-lane-providers Specification

## Purpose
萬星·词元（`router.finddatatech.cloud`，self-fork 的 sub2api）作为 VAAS 语音/图像/视频
生成的后端车道：规定三条车道（TTS / 图像 / 视频）的端点契约、可用模型白名单、产物落盘
口径与失败语义，使 VAAS 的生成调用走自家网关与账本，且不依赖第三方 LLM 桥接库。

## Requirements

### Requirement: 词元车道作为生成后端

VAAS 的语音、图像、视频生成 SHALL 支持以萬星·词元车道 API 为后端，与火山方舟直连并列
为可选的 provider 档位；选择由凭证记录声明，MUST NOT 由代码硬编码。

#### Scenario: 声明 ciyuan 档的凭证走词元车道

- **WHEN** 某次生成调用解析到的凭证记录 provider 为 `ciyuan`
- **THEN** 该调用请求词元车道端点（语音 `/v1/audio/*`、图像 `/v1/images/generations`、
  视频 `/v1/contents/generations/tasks`）
- **AND** 请求携带该凭证的 key 作为 Bearer 鉴权

#### Scenario: 声明 volcengine 档的凭证保持既有行为

- **WHEN** 凭证记录 provider 为 `volcengine`（或缺失）
- **THEN** 调用行为与本 change 之前完全一致

### Requirement: 语音车道（TTS）合成

TTS 生成 SHALL 以 OpenAI 音频协议调用词元 `POST /v1/audio/speech`，并把返回的音频流
按 VAAS 落盘约定写成产物文件；音色与模型由凭证记录提供，默认值 MUST 为实测可服务的组合。
当 provider 未返回逐字时间戳时，TTS 出口层 SHALL 合成字幕（fallback captions），
使 voiceover 管线在任一 provider 下都拿到完整 Caption[]，MUST NOT 因 provider 分叉。

#### Scenario: TTS 合成成功落盘

- **WHEN** 调用者请求一段文本的语音合成且凭证为 ciyuan 档
- **THEN** 系统以凭证声明的 model 与 voice 请求 `/v1/audio/speech`
- **AND** 返回的音频字节写入本次生成的产物路径
- **AND** 响应返回该产物的 slug 与相对路径，形状与既有 TTS 响应一致

#### Scenario: 词元语音车道上游不可用

- **WHEN** 词元语音车道返回车道级错误（如 `lane_upstream_error` /
  `lane_upstream_unavailable`）
- **THEN** 该次生成失败并向上暴露含车道标识的错误信息
- **AND** MUST NOT 把上游 5xx 伪装成成功，MUST NOT 产出空或占位音频文件

#### Scenario: 超上游长度上限时分段合成

- **WHEN** 口播文本超过 provider 单次请求长度上限（腾讯 TTS 实测 ~170 字）
- **THEN** TTS 出口层按句切分为 ≤150 字的段，逐段合成并拼接（段间短静音）
- **AND** captions 按段级实测时长对齐（段间时长计入时间轴）
- **AND** 单段重试有退避上限；任一段最终失败 SHALL 整体失败，MUST NOT 产出残缺音频
- **AND** 段间调用 MUST 有间隔，MUST NOT 因连续失败触发上游熔断扩大故障

#### Scenario: 无官方逐字戳时合成字幕兜底

- **WHEN** provider 返回音频但未返回逐字时间戳（词元档常态）
- **THEN** TTS 出口层以口播文本切分 token（中文按字、标点并入前字），
  生成 Caption[]（text/startMs/endMs/timestampMs），并以 ffprobe 实测音频时长
  对全部 token 时间戳做线性缩放对齐
- **AND** 合成结果随音频一起落盘为 captions 文件，形状与官方逐字戳完全一致
- **AND** 结果元数据标记 `captions_source: synthetic`；官方逐字戳存在时标记 `official`

#### Scenario: 合成字幕过管线门禁

- **WHEN** 使用 synthetic captions 走 voiceover 管线（fix-tts-timings → preflight → 渲染）
- **THEN** preflight 的音画三方对齐校验通过（字幕末帧与音频实测时长偏差 ≤ 容差）
- **AND** fix-tts-timings 对 synthetic captions 幂等无改动（其 token 时长由构造保证均匀）

#### Scenario: manifest 记录字幕来源

- **WHEN** 一次 TTS 任务写入 task.json
- **THEN** tts 段 SHALL 包含 provider、model、voice 与 captions_source
  （official | synthetic），成片口径可审计

### Requirement: 图像车道生成与模型白名单

图像生成 SHALL 以 OpenAI 图像协议调用词元 `POST /v1/images/generations`，并仅使用实测
返回合规 JSON 产物的模型；返回非 JSON（如 HTML）的模型 MUST NOT 作为默认或推荐值。

#### Scenario: 图像生成成功落盘

- **WHEN** 调用者请求文生图且凭证为 ciyuan 档
- **THEN** 系统请求 `/v1/images/generations` 并解析响应的 `data[].b64_json`
- **AND** 解码后的图像字节按 VAAS 命名约定写入产物目录
- **AND** 响应返回产物相对路径列表，形状与既有图像响应一致

#### Scenario: 图像车道返回非 JSON 应答

- **WHEN** 词元图像车道对某模型返回 `Content-Type: text/html` 或不可解析的响应体
- **THEN** 该次生成失败并明确报错（说明该模型应答形状不合规）
- **AND** MUST NOT 从 HTML 中猜测或提取图片 URL 充当产物

#### Scenario: 默认图像模型可服务

- **WHEN** 使用 ciyuan 档凭证且调用者未指定模型
- **THEN** 系统使用默认模型 `gemini-3-pro-image`（2026-10-16 实测返回合规 b64_json）

### Requirement: 视频车道异步任务与轮询

视频生成 SHALL 以词元异步任务协议调用：创建任务取回任务 ID，轮询同一路径至终态，
终态取回视频 URL 并下载落盘；失败终态与上游不可路由 MUST 如实报错。

#### Scenario: 视频任务创建并轮询至成功

- **WHEN** 调用者请求文生视频且凭证为 ciyuan 档
- **THEN** 系统 `POST /v1/contents/generations/tasks` 创建任务并取回任务 ID
- **AND** 轮询 `GET /v1/contents/generations/tasks/<id>` 直至终态
- **AND** 终态为成功时下载 `content.video_url` 的字节写入产物路径
- **AND** 响应返回产物相对路径，形状与既有视频响应一致

#### Scenario: 视频模型不可路由

- **WHEN** 词元对请求的视频模型返回 404（无对应上游端点）或 503（上游不可达）
- **THEN** 该次生成失败并如实上报状态码与错误信息
- **AND** MUST NOT 重试其他模型来掩盖模型不可路由的事实

#### Scenario: 默认视频模型可服务

- **WHEN** 使用 ciyuan 档凭证且调用者未指定模型
- **THEN** 系统使用默认模型 `doubao-seedance-2-0-fast-260128`

#### Scenario: 异步两阶段与重复计费防护

- **WHEN** 托管模式以 submit/poll 两阶段调用视频生成
- **THEN** 提交阶段只创建任务并返回任务 ID，轮询阶段负责落盘
- **AND** 客户端超时后重试的是状态查询，MUST NOT 重复提交已付费的创建请求

### Requirement: 词元分组口径与分路凭证

系统 SHALL 承认词元「一把密钥只绑一个分组、图像/视频与语音分属不同分组」的约束，
并按生成类型（kind）分路解析凭证；MUST NOT 假设单一 key 可服务全部车道。

#### Scenario: 语音与图像使用各自分组的凭证

- **WHEN** 同一次部署内分别发起语音合成与图像生成
- **THEN** 两者可分别解析到不同分组的词元 key
- **AND** 各自调用成功，不因分组差异而互相失败

#### Scenario: 缺失某路凭证时仅该路失败

- **WHEN** 某一 kind（如 image）未配置 ciyuan 凭证而其他 kind 已配置
- **THEN** 该 kind 的生成调用失败并指出缺失的凭证路径
- **AND** 其他 kind 的生成不受影响

### Requirement: 移除第三方 LLM 桥接依赖

生成后端 MUST NOT 依赖通用 LLM 桥接库（litellm）：多 Provider 能力由 volcengine 直连
与 ciyuan 车道两条自有路径提供，词元本身即是网关。

#### Scenario: 生成代码无桥接库依赖

- **WHEN** 检查生成链路的依赖声明
- **THEN** 其中不含 litellm 及其传递依赖要求
- **AND** 词元车道调用仅使用标准库 HTTP 能力

#### Scenario: 第三方 provider 值被明确拒绝

- **WHEN** 凭证或环境声明了一个既非 volcengine 也非 ciyuan 的 provider 值
- **THEN** 系统拒绝该次生成并提示仅支持 `volcengine` 与 `ciyuan`
- **AND** MUST NOT 静默回落到任一可用后端

### Requirement: 词元侧车道缺陷的记录与规避

对已实测确认的词元侧车道缺陷（应答形状不合规、模型不可路由），系统 SHALL 以默认模型
白名单与显式错误规避之，并在文档中如实标注；MUST NOT 假装这些车道正常可用。

#### Scenario: 已知缺陷模型不作为默认

- **WHEN** 配置或文档声明 ciyuan 档的默认模型
- **THEN** 默认模型取自实测可服务的白名单
- **AND** 已知返回 HTML 或不可路由的模型被明确标注为不可用

#### Scenario: 语音车道上游未配置时如实报错

- **WHEN** 调用 ASR 转写且词元语音车道无可用的上游账号
- **THEN** 系统如实上报车道不可用（含车道与引擎标识），不伪装成输入错误

### Requirement: TTS 输出确定性落盘

TTS 合成产物 SHALL 支持调用方指定输出目录直写；未指定时才回退到既有桌面时间戳目录约定。

#### Scenario: 指定输出目录

- **WHEN** 调用方（如 task-render 的 tts 步骤）向 TTS 包装层传入输出目录
- **THEN** 音频与 captions 文件 SHALL 直写该目录，落盘路径在调用结果中如实返回
- **AND** 调用方 MUST NOT 依赖「扫描桌面最新时间戳目录」来定位本次产物

#### Scenario: 未指定输出目录的兼容行为

- **WHEN** 调用方未传输出目录
- **THEN** 行为与现状一致（三级 fallback 目录 + 时间戳子目录）

### Requirement: TTS 错误按真实原因分类

TTS 合成失败 SHALL 向上暴露 provider 返回的真实错误类别与可行动提示。

#### Scenario: Ark 订阅失效可行动报错

- **WHEN** 火山方舟分块响应中返回 JSON 错误块（如 code=InvalidSubscription）
- **THEN** 错误信息 SHALL 包含该 code 与原文要点，并附可行动提示
  （续订方舟，或切换 `TTS_PROVIDER=ciyuan`）
- **AND** MUST NOT 将其报为音频解码失败（DECODE_FAILED）

#### Scenario: 词元车道错误保持车道标识

- **WHEN** 词元 audio 车道返回非音频响应或车道错误
- **THEN** 错误信息保持车道标识与上游原文要点（既有语义不变）

### Requirement: 词元语音模型与音色白名单

词元语音车道的默认 model 与 voice MUST 为实测可服务的组合，白名单随实调更新。

#### Scenario: 腾讯 TTS 默认组合

- **WHEN** 凭证为 ciyuan 档且未显式指定 TTS model/voice
- **THEN** 默认组合为 `tencent-tts` + 音色 `101001`（2026-11-06 实调可用）
- **AND** qwen3-tts-flash（voice Cherry）保留为白名单备选
- **AND** audio 车道按 protocol 路由、模型名不进 `/v1/models` 目录的实测事实
  记录于白名单文档，防止以目录探测代替实调

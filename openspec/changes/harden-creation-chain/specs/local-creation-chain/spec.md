# local-creation-chain Specification

## Purpose

本地 node+Remotion 创作管线（new-task/task-render/TTS 出口层/渲染组件）的行为契约：时长与帧数推导以实测为准、请求参数端到端不丢失、字幕兜底跨 provider 同形、渲染产物跨平台一致，且数学区有回归测试可拦。

## ADDED Requirements

### Requirement: 帧数与时长以实测音频为准

口播/类型视频管线的总帧数 SHALL 由 TTS 产物的实测音频时长（ffprobe）推导，MUST NOT 以字幕末帧 endMs 为源（官方逐字戳常带尾部静音，字幕推算会触发 preflight drift 超差）；字幕末帧推算仅作合成字幕（tailPad=0）路径的等价推导。task.json 的 `audioDurationSec` MUST 记录实测音频时长，MUST NOT 记录字幕口径值；字段名与语义一致。

#### Scenario: 官方戳带尾静音仍过门

- **WHEN** 官方逐字戳末帧比音频实测短 1 秒（尾静音）且管线渲染口播视频
- **THEN** 帧数按实测音频推导，preflight 音画对齐校验通过
- **AND** 字幕不越过音频末帧的校验同步成立

#### Scenario: 合成字幕路径等价

- **WHEN** 词元腿 synthetic captions（构造上字幕末帧≈实测时长）渲染
- **THEN** 推导结果与官方路径同源（均实测），tailPad=0 行为不变

### Requirement: 请求参数端到端不丢失

管线 SHALL 将调用方显式传入的 `--voice`/`--speed` 等参数贯通到 TTS 出口层并生效（车道不支持时按参数诚实条款降级并记录），MUST NOT 因内部键遮蔽、defaults 透传泄漏或 args 构造遗漏而静默丢失；task.json SHALL 同时记录请求值与实际生效值（如 `voice`/`voice_requested`），渲染 props 中 MUST NOT 混入非渲染用途的 defaults 残留键。

#### Scenario: --voice 直达产物

- **WHEN** 用户以 `--voice 101013` 执行 new-task 并渲染
- **THEN** TTS 以 101013 合成，task.json 记录请求与生效音色一致
- **AND** 不出现「CLI 传了、产物是默认音色」的静默回落

#### Scenario: speed 进入合成层

- **WHEN** 用户设置 `defaults.speed` 或 CLI 传入速率
- **THEN** 该参数进入 TTS 调用（不支持车道则 warnings 记录并按默认速率）
- **AND** 该键不泄漏进渲染 props

### Requirement: 字幕兜底跨 provider 同形

任一 provider 的合成腿（词元桥接与火山直连）MUST NOT 假设官方逐字戳必然存在：provider 返回音频而无逐字戳时，出口层 SHALL 合成字幕兜底（形状与官方一致并落盘，标 `captions_source: synthetic`）；成功返回 SHALL 携带 `provider` 与 `captions_source` 元数据入 task.json，MUST NOT 以 null/缺省再默认冒充 official。

#### Scenario: 直连腿无逐字戳不再断链

- **WHEN** 火山直连响应 `sentences` 为空
- **THEN** 管线仍产出完整 captions 文件并标 synthetic，task-render 不因缺字幕硬失败
- **AND** 有官方戳时标 official，task.json 口径可审计

#### Scenario: 元数据如实入册

- **WHEN** 任一腿完成一次合成
- **THEN** task.json 的 tts 段含 provider/model/voice/captions_source 四元组
- **AND** direct 腿不再留 null

### Requirement: 渲染产物跨平台一致

渲染组件 MUST NOT 依赖宿主机系统字体栈产出中文（字体 SHALL 显式打包/注册并全组件统一口径），使 macOS/Windows 渲染产物字形一致；字幕垂直位置等观感参数 SHALL 从管线（task/type 声明或 CLI）可达，而非只能手工 extra-props。Remotion 链与 HTML 链的同类型能力差异（如 BGM 支持）SHALL 在类型/技能文档如实标注。

#### Scenario: Windows 出片无豆腐块

- **WHEN** 同一任务在 Windows 节点渲染含中文口播的字幕
- **THEN** 字体与 macOS 渲染一致（打包字体生效，不回落 PingFang 猜测）

#### Scenario: 观感参数走管线

- **WHEN** 用户选择竖屏字幕居中/贴底
- **THEN** 该参数经 new-task/task-render 传入渲染组件
- **AND** 不需要调用方触碰内部 JSON

### Requirement: 创作链回归测试

管线数学区 SHALL 有 `node --test` 覆盖：帧数/时长推导、preflight 三规则、字幕合成与缩放、类型注册表校验、参数贯通——用固定桩数据（不依赖浏览器/网络），并入统一测试闸；既有 TTS helper 测试不回退。

#### Scenario: 推导回归可拦截

- **WHEN** 有人把帧数推导改回字幕口径
- **THEN** 测试闸变红并指明受影响规则
- **AND** 无需真实渲染一次即可暴露

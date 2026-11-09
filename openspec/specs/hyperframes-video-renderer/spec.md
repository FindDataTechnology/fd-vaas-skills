# hyperframes-video-renderer Specification

## Purpose
VAAS 视频出口的引擎契约：视频不再由 API 面自己渲染，而是委托给**独立、无状态、可多实例**的渲染面（HyperFrames，钉版本）。VAAS 负责把内容编译成 composition、把作业提交出去、把成片接入账本；渲染面只做一件事：把 composition 变成 MP4。

## Requirements

### Requirement: 渲染面独立于 API 面

视频渲染 SHALL 由独立的渲染服务承担，API 面 MUST NOT 自行逐帧渲染视频、MUST NOT 依赖 Node 或视频引擎运行时。API 面与渲染面之间 SHALL 以显式 HTTP 契约通信（基址由 `VAAS_RENDER_URL` 一类环境变量配置、可重指），MUST NOT 进程内耦合。渲染面 SHALL 无状态（不持有资产账本、不落业务数据），可多实例部署。

#### Scenario: API 镜像保持轻量

- **WHEN** 检查 API 面镜像与运行时依赖
- **THEN** 不含 Node 与视频引擎，也不含其浏览器下载
- **AND** 视频能力仍可经渲染面完整可用

#### Scenario: 渲染面可重指与多实例

- **WHEN** 运维将 `VAAS_RENDER_URL` 指向另一台渲染面实例或负载均衡地址
- **THEN** 视频渲染照常工作，无需改动 API 代码或重建镜像
- **AND** 多实例并存时作业按可用实例派发

### Requirement: 渲染作业契约

VAAS SHALL 以作业形式提交渲染：作业含 composition（含画幅、时长、轨道与内联/暂存素材）、期望格式（默认 mp4）、帧率与质量档；渲染面 SHALL 返回成片产物（字节流或可拉取地址）。作业 SHALL 带幂等标识，重复提交同标识 MUST NOT 重复产出不同结果。渲染面 MUST NOT 联网拉取依赖或浏览器；引擎版本 SHALL 钉死并在作业响应中回报。

#### Scenario: 提交作业取回成片

- **WHEN** VAAS 向渲染面提交一个 composition 作业
- **THEN** 渲染面返回 MP4 成片与引擎版本
- **AND** 同幂等标识的重复提交返回一致结果

#### Scenario: 离线可渲

- **WHEN** 渲染面无外网
- **THEN** 渲染成功（引擎与浏览器复用镜像内既有二进制）
- **AND** 不发起任何依赖下载

### Requirement: Composition 生成契约（VAAS 侧）

VAAS SHALL 以中性 composition spec 生成 HyperFrames composition：至少含画幅、总时长与多轨 clips；轨 SHALL 至少覆盖视觉、字幕、音频三类。每个 clip SHALL 声明起始时刻与时长并落在明确的轨上；动画 SHALL 经引擎适配器驱动（CSS/WAAPI/GSAP/自定义 `window.__hf.seek`），MUST NOT 依赖逐页自写的帧循环。品牌令牌（品牌色板与字体栈）SHALL 由同一主题源注入，MUST NOT 与静态出口产生第二套品牌口径。前端动画库（GSAP/Lottie 等）MUST 本地 vendor，MUST NOT 引用公共 CDN。

#### Scenario: 多轨 composition 正确落位

- **WHEN** VAAS 编译一段含视觉、字幕、旁白三轨的 composition
- **THEN** 各轨 clip 在成片中的起始时刻与时长与 spec 一致
- **AND** 字幕以品牌字体栈出形、视觉配色取品牌色板

#### Scenario: 自定义运行时可用

- **WHEN** 某个视觉 clip 使用 `window.__hf.seek` 自定义运行时（如声明式图表）
- **THEN** 引擎逐帧调用该 seek，动画随时间推进
- **AND** 同 spec 双跑逐帧一致

#### Scenario: 零外链编译

- **WHEN** composition 或其依赖引用 http(s) 资源
- **THEN** 编译期拒绝并指明资源
- **AND** 不提交作业

### Requirement: 渲染确定性与版本门禁

同 composition 同参数双跑 MUST 产出一致结果（帧级哈希一致为目标口径；容器字节一致在合流器不写时间戳时可达，已实测可达）。引擎版本变更 MUST 经双跑门禁后才可上产。composition 内容生成 MUST NOT 引入随机源（随机标识、当前时间、本地化格式等）。

#### Scenario: 双跑一致

- **WHEN** 以同一 composition 与参数连续渲染两次
- **THEN** 两次产物帧级哈希一致
- **AND** 资产元数据标记确定性结果与引擎版本

#### Scenario: 引擎升级门禁

- **WHEN** 渲染面引擎版本变更
- **THEN** 上产前以固定样例跑双跑门禁
- **AND** 不一致即阻断上产

### Requirement: 按作业租户隔离

渲染面 MUST 以作业为单位隔离：每次渲染使用独立临时目录，网络仅保留必要回环（无外网），环境变量为白名单（MUST NOT 携带平台密钥/bearer/密钥库 token），并设硬超时与内存/shm 限额。任一隔离条件不满足 MUST 失败且零部分产物。租户提交的 composition MUST 在任何情况下都不得触达宿主敏感路径。

#### Scenario: 外链与越权被断

- **WHEN** 租户 composition 尝试访问外网或宿主敏感路径
- **THEN** 该作业失败并指明违规面
- **AND** 不产生部分产物、不影响其他作业

#### Scenario: 密钥不可见

- **WHEN** 检查任一渲染作业的进程环境
- **THEN** 不含令牌、密钥库 token、平台 bearer 等敏感变量

### Requirement: 音频多轨合流

旁白与 BGM SHALL 作为 composition 的音频轨参与合流，MUST NOT 依赖成片后的二次混流。BGM 长于视频时 SHALL 在视频时长处收尾；多段旁白 SHALL 按段起始时刻落在音频轨上。

#### Scenario: 旁白与 BGM 同片合流

- **WHEN** 作业含旁白音频与 bgm 参数
- **THEN** 成片音轨包含按时刻落位的旁白与 BGM
- **AND** BGM 在视频时长处收尾

### Requirement: 故障、重试与回滚

渲染作业失败或超时 MUST NOT 产生部分产物或半写账本行；VAAS SHALL 以明确错误上报并可按策略重试（不同实例）。渲染面整体不可用时 MUST 返回明确错误并建议回滚路径（镜像/渲染面 tag 级）。渲染 SHALL 捕获引擎诊断（版本、耗时、告警）并入资产元数据。

#### Scenario: 失败零残留

- **WHEN** 作业中途失败或超时
- **THEN** 不残留产物与账本行
- **AND** 返回明确错误且可重试

#### Scenario: 诊断入账本

- **WHEN** 作业成功
- **THEN** 资产元数据含引擎版本与渲染耗时
- **AND** 引擎告警可检索

### Requirement: 静态出口边界

`render_still` 与 `render_document` SHALL 继续由静态出口（chromium 截图/打印）在 API 面产出，MUST NOT 经渲染面；两者与视频出口 SHALL 共享同一品牌令牌与字体栈。渲染面的引入 MUST NOT 改变静态出口的接口或产物语义。

#### Scenario: 静帧与视频共用品牌

- **WHEN** 同一品牌主题下分别产出单帧图表与 composition 视频
- **THEN** 字体栈与品牌色板一致
- **AND** 静态出口接口与产物语义不变

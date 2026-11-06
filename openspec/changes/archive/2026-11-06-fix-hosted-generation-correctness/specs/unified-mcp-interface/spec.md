# Unified MCP Interface (delta)

## ADDED Requirements

### Requirement: 生成工具文本源契约

生成类工具接受文本源时 SHALL 语义明确：`generate_voice` 的 `file_path` MUST 读取该文件的内容作为台词文本；`text` 与 `file_path` 同时提供 MUST 显式报错（invalid_input），MUST NOT 任选其一静默处理；`file_path` 指向空文件或读取失败 MUST 如实报错，MUST NOT 以路径字符串本身作为台词继续合成。

#### Scenario: file_path 读内容合成

- **WHEN** 租户仅以 `file_path` 提交一段口播稿
- **THEN** 合成产物以该文件的文本内容为台词
- **AND** 计费字符数等于文件实际文本长度

#### Scenario: 双文本源被拒

- **WHEN** 调用同时携带 `text` 与 `file_path`
- **THEN** 返回 invalid_input 明确错误
- **AND** 不产生任何产物或计费

### Requirement: 参数安全与文件名白名单

调用方可影响产物文件名的参数（`format`/`output_format` 等）MUST 经枚举白名单校验（音频 mp3/wav，图像 png/jpeg 等），非白名单值 MUST 在生成前被拒绝；任何产物落盘路径 MUST 收敛于 downloads 产物目录内，调用方输入 MUST NOT 使写入逃逸该目录。托管实例的工具响应与账本记录 MUST 只含相对路径，MUST NOT 出现服务器文件系统绝对路径。

#### Scenario: 恶意扩展名被拒

- **WHEN** 调用方以 `format="mp3/../../x"` 发起语音生成
- **THEN** 请求在合成前被拒绝（invalid_input）
- **AND** 产物目录外无任何文件被创建

#### Scenario: 资产响应零绝对路径

- **WHEN** 租户经托管实例读取自己名下的资产详情
- **THEN** file_path 与相关字段均为 downloads 相对路径
- **AND** 响应不含 /app、/root 等服务器路径布局信息

### Requirement: 参数诚实与降级披露

车道不支持的请求参数 MUST NOT 静默吞掉：`speed` 在 provider 不支持时响应 SHALL 携 `warnings` 说明按默认速率合成；`reference_image` 等未实现的输入参数 SHALL 从工具面移除或显式拒绝（不支持即报错），MUST NOT 收下参数假装处理；`generate_image(n>1)` MUST 实际产出 n 张（provider 不支持 n 时 SHALL warning 或报错），且全部产物逐张写入资产账本。

#### Scenario: 不支持变速时明说

- **WHEN** 租户在不支持变速的车道上以 `speed=1.5` 合成语音
- **THEN** 产物正常返回但响应 warnings 说明该车道不支持变速
- **AND** 账本记录请求值与实际生效值

#### Scenario: 多张图全部入账

- **WHEN** 租户以 `n=4` 生成图像且车道支持
- **THEN** 4 张产物文件与 4 条（或含变体计数的）资产记录一致
- **AND** 无任何一张文件游离于账本之外

### Requirement: 上游错误脱敏分类

面向调用方的错误 MUST 收敛为分类与短消息（invalid_input / credential_unavailable / lane_down / upstream_transient / upstream_error / timeout），上游原始响应体、网关内部细节与子进程命令行 MUST NOT 出现在工具返回中；完整错误上下文 SHALL 仅记录于服务端日志供运维对账。

#### Scenario: 503 原文不外泄

- **WHEN** 词元网关对图像请求返回含账号状态的 503 body
- **THEN** 租户收到的错误为分类码 + 人类可读短消息（如 lane_down）
- **AND** 响应中不出现上游 body、账号标识或桥命令行

### Requirement: 调用挂钟上限

工具调用 MUST 有挂钟上限：车道子进程 SHALL 配置超时（env 可调、有默认值），超时按 timeout 分类返回；异步作业的状态查询 SHALL 为单次上游读取并秒级返回，MUST NOT 在任何环节于子进程内阻塞轮询至分钟级。客户端重试状态查询 MUST NOT 触发重复提交付费创建。

#### Scenario: 状态查询快速返回

- **WHEN** 租户反复轮询一个仍在生成的视频作业
- **THEN** 每次 `video_job_status` 在上游单次读取后返回（秒级）
- **AND** 作业保持 running 状态

#### Scenario: 上游挂起不拖死调用

- **WHEN** 车道上游长时间无响应
- **THEN** 调用在配置的超时上限处返回 timeout 分类错误
- **AND** 服务端子进程被回收，无孤儿进程残留

## MODIFIED Requirements

### Requirement: 计价用量记录与报表

托管实例 SHALL 为每次生成调用记录用量（归属租户、工具、供应商、模型、数量、单位、凭证来源）； SHALL 提供只读计价汇总端点（按租户×工具聚合，单价来自可配置定价表），端点 MUST 要求服务凭证。定价表初值不属于代码契约，MUST 可在部署侧调整而无需改代码。托管模式下定价表缺失、为空或不可读 MUST 在启动或计价时响亮失败（拒绝以全零静默折算），并输出可行动的修复提示；计费数量 MUST 来自产物实测（音频实测字符/时长、视频以 ffprobe 实测成片时长），MUST NOT 采用上游自报或硬编码值；记账单位 SHALL 归一（second/image/char/doc 口径一致），凭证来源枚举 MUST 与实际解析通道一致。

#### Scenario: 用量可查可折价

- **WHEN** 管理员以服务凭证查询计价汇总
- **THEN** 返回按租户与工具聚合的用量与折算金额
- **AND** 金额随定价表调整而变化，无需重新部署代码

#### Scenario: 用量与凭证来源对账

- **WHEN** 某租户的一批调用分别走了线池凭证与服务默认凭证
- **THEN** 汇总能按凭证来源拆分该租户用量
- **AND** 与逐条用量记录合计一致

#### Scenario: 定价表缺失响亮失败

- **WHEN** 托管实例启动时定价表文件不存在或解析失败
- **THEN** 实例明确报错（或计价端点返回未配置错误）而非默默全零折算
- **AND** 错误信息指出所缺文件与配置项

#### Scenario: 视频按实测时长计费

- **WHEN** 一个请求 8 秒的异步视频作业实际产出 7.4 秒成片
- **THEN** 用量记录的数量为实测 7.4 秒
- **AND** 资产元数据携带同一实测时长

### Requirement: 签名下载端点

托管实例 SHALL 提供产物下载端点：URL 由 HMAC 签名绑定资产标识、归属租户与过期时间（默认 24 小时，可配）；过期或签名不符 MUST 返回错误；跨租户持有他人签名链接 MUST 被拒绝。生成类工具的响应 SHALL 直接包含有效下载地址；签名 base URL MUST 来自显式部署配置，MUST NOT 在配置缺失时回落到请求 Host 头（避免内网 host:port 进入租户响应）——配置缺失时响应 SHALL 省略下载地址并给出可行动提示。签名密钥 SHALL 存放于密钥库服务默认路径。

#### Scenario: 生成响应即含可下载链接

- **WHEN** 租户完成一次图片生成
- **THEN** 响应中的下载地址在有效期内可直接取回该图片
- **AND** 内容与生成的文件一致

#### Scenario: 过期与跨租户链接失效

- **WHEN** 使用过期签名或把他人的签名链接换用自己身份访问
- **THEN** 均被拒绝且不泄露产物内容

#### Scenario: 未配置公网基址不泄内网地址

- **WHEN** 托管实例未配置公网基址时完成一次生成
- **THEN** 响应不附内网地址下载链接，并提示需配置公网基址后可用
- **AND** 资产仍可经列表/再次签发取得

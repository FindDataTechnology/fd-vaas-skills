# generation-jobs (delta)

## MODIFIED Requirements

### Requirement: 作业查询与状态机

系统 SHALL 提供作业查询工具，按作业标识返回状态（排队/运行中/成功/失败/过期）；成功时返回产物资产标识与下载地址，失败时返回供应商错误摘要（经错误脱敏分类，不含上游原始体）。只有作业归属租户 MAY 查询该作业：托管模式下查询 MUST 以当前请求身份为 owner 过滤，非归属租户查询他人作业 SHALL 得到不可见错误而非任何作业详情。瞬时查询故障（上游超时、5xx、解析失败）MUST NOT 使作业进入 `failed` 终态——作业 SHALL 保持原状态可续查；`failed` 仅由供应商明确终态失败置入。作业成功完成时 SHALL 以 ffprobe 实测成片时长入账计费。作业 SHALL 在 TTL（默认 24 小时）后置为过期且不可再查；已完成作业的产物不受作业过期影响，随资产保留期独立管理。

#### Scenario: 轮询至成功

- **WHEN** 租户轮询一个已完成的作业
- **THEN** 返回成功状态、产物资产标识与下载地址
- **AND** 产物已入内容库并归属该租户
- **AND** 计费数量为实测时长

#### Scenario: 跨租户不可见

- **WHEN** 租户 B 查询租户 A 的作业标识
- **THEN** 得到不可见错误而非作业详情
- **AND** 不泄露该作业的 slug、状态或产物信息

#### Scenario: 瞬时故障不终态

- **WHEN** 轮询时上游查询超时或返回 5xx
- **THEN** 作业保持 running/queued 原状态，错误按 upstream_transient/timeout 分类返回
- **AND** 后续轮询成功仍可取得产物入账

#### Scenario: 过期作业

- **WHEN** 作业超过 TTL 后被查询
- **THEN** 返回过期状态或不可见
- **AND** 其已完成的产物仍可按资产保留期正常下载

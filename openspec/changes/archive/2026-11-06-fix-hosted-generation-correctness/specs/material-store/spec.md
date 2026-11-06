# Material Store (delta)

## MODIFIED Requirements

### Requirement: 租户归属与隔离

托管模式下，系统 SHALL 为每条资产记录归属租户（`owner`），并在内容库读写时按 owner 过滤：租户 MUST 只能列出、读取与检索自己生成的资产。全部生成器写入资产账本时 MUST 使用统一的 owner-scoped slug 域（同一调用方 slug 在不同租户下各自独立成立、互不冲突）；幂等重放查找 MUST 与写入同一 slug 域——同租户同幂等键的重放 SHALL 命中已有产物直接返回，MUST NOT 重复生成或重复计费。存量资产与本地（非托管）模式产生的资产 SHALL 归属服务内部所有者，本地模式行为 MUST 保持不变。平台提供的公共品牌素材（公共 assets 查询、logo、合成模板）MUST NOT 按 owner 过滤。托管模式下携带不到租户身份的变更请求 MUST 被拒绝（fail-closed）。

#### Scenario: 租户只见自己的资产

- **WHEN** 租户 A（owner=a）与租户 B（owner=b）各生成过图片，租户 A 列出自己的内容库
- **THEN** 结果只含 owner=a 的资产
- **AND** 租户 A 按 id 读取租户 B 的资产时得到不可见错误

#### Scenario: 跨租户同 slug 各自成立

- **WHEN** 租户 A 与租户 B 先后以同一 `slug="demo"` 生成语音
- **THEN** 两次生成各自成功、各归其主
- **AND** 不出现唯一键冲突或互相覆盖

#### Scenario: 幂等重放同域命中

- **WHEN** 同一租户以同一幂等键重复提交同内容的生成请求
- **THEN** 第二次调用命中已有产物（含有效下载地址）
- **AND** 不产生新资产、不新增用量记录

#### Scenario: 存量资产归服务所有

- **WHEN** 迁移在含存量资产的库上执行
- **THEN** 全部存量行 owner 置为服务内部所有者
- **AND** 本地 stdio 模式的工具行为与迁移前一致

#### Scenario: 公共素材不受隔离约束

- **WHEN** 任意租户查询公共品牌素材
- **THEN** 返回完整的平台公共素材列表
- **AND** 不因 owner 过滤而缺项

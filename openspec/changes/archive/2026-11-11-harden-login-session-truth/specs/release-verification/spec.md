# release-verification Specification

## Purpose

发布验证契约：变更测试闸、镜像构建单源、托管实例存活自证、外依赖债务台账。本 change 只把登录态验真新鲜度接入既有测试闸，其余条款不变。

## ADDED Requirements

### Requirement: 登录态验真纳入一致性闸

既有的 `registry 一致性` 步骤 MUST 同时校验登录态验真的存在性与新鲜度，而不只校验平台数量一致：
registry 的 `cookieCheck` 与运行态 `.login_state.json` 不得分裂，任一平台出现「运行态有验真记录而
registry 无快照」或「快照超过 14 天」，该步骤 MUST 以非零退出使变更闸整体变红。

该闸 MUST NOT 把「文件存在」或「文件未超龄」当作登录态有效的替代证据；MUST NOT 因
`lastVerified`（选择器戳）新鲜而放行 `cookieCheck` 缺失的平台。

阈值与降级路径 SHALL 写在代码内可检索处：若生产环境出现误报，可把该检查降级为提示级
（不计入错误）而保留 registry 字段不动，降级 MUST 在 commit message 与债务台账中留痕。

#### Scenario: 缺快照即阻断

- **WHEN** 运行态已有某平台验真记录而 registry 该平台 `cookieCheck` 为 `null`
- **THEN** `bash scripts/ci-local.sh` 的 `registry 一致性` 一项失败并非零退出
- **AND** 失败信息点名平台并给出「回填后重跑」的处置指引

#### Scenario: 陈旧即阻断

- **WHEN** 某平台 `cookieCheck.checkedAt` 距今天数超过 14
- **THEN** 同一闸门失败并报出实际天数与阈值
- **AND** 其余平台的新鲜记录不受牵连（只报违规项）

#### Scenario: 回填后转绿

- **WHEN** 按运行态记录回填 `cookieCheck` 并重跑
- **THEN** 该步骤转绿，其余四项检查结论不变

# Material Store (delta)

## ADDED Requirements

### Requirement: BGM 素材类型

资产树 SHALL 支持 `type=bgm` 素材：每条记录含音频文件、时长、授权来源字段。BGM 素材 SHALL 可被视频渲染与旁白混流按资产 id 引用，租户隔离规则与其他素材一致。系统 SHALL 随镜像内置一份授权清晰的种子 BGM 曲库。

#### Scenario: 内置曲库可查询
- **WHEN** 调用方以 type=bgm 查询资产列表
- **THEN** 返回内置种子曲库（含时长与授权来源字段）
- **AND** 每条可直接被视频渲染引用

#### Scenario: BGM 按租户隔离
- **WHEN** 租户 A 引用租户 B 名下的 bgm 资产
- **THEN** 引用被拒绝并提示资产不存在
- **AND** 内置曲库对所有租户可见

# 待审补丁（未并入 main、未发布）

这里的 `.patch` 是**待裁决**的改动草稿，配套的代码在独立分支上，`main` 不含这些改动。
用 `git apply --check <patch>` 可验证能否干净应用。

| 补丁 | 分支 | 关联债务 | 状态 |
|---|---|---|---|
| `DEBT-RENDER-FLAKY-01-killgroup-log.patch` | `probe/killgroup-log`（`9bf078d`） | `DEBT-RENDER-FLAKY-01` | 待审：只加 pid/pgid/信号三态观测日志，不改清理语义 |

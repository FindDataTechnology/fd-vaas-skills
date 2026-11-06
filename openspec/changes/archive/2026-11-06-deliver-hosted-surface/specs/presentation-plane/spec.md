# presentation-plane (delta)

## MODIFIED Requirements

### Requirement: 渲染底座统一

系统 SHALL 以单一渲染底座产出全部确定性视觉产物：无头浏览器 + 内置 CJK 字体 + 品牌主题令牌（theme.ts）。三类出口（单帧、帧序列、分页文档）MUST 共享同一底座、同一字体栈与同一品牌主题，MUST NOT 为单一模态引入第二套渲染口径。视频与单帧的接口方言 SHALL 为 seek 契约（`window.__DURATION__`/`window.__SIZE__`、`window.seek(t)`、`data-stage` 标记）。托管实例镜像 SHALL 自带渲染底座的完整运行依赖（无头浏览器、CJK 字体、逐帧捕获与音视频合流工具、音频时长测量）：被工具面与模板目录标注为 hosted 可用的能力，MUST 在托管实例部署态可直接执行；底座缺失或目录未打包时 MUST 显式报错，MUST NOT 以空清单或占位假绿静默降级。

#### Scenario: 同主题跨出口一致

- **WHEN** 同一品牌主题下分别渲染单帧图表与一段视频
- **THEN** 两者的字体、品牌色板、尺寸语义一致
- **AND** 视频场景可内联复用为单帧产物的场景 HTML（seek 契约互拷）

#### Scenario: 托管实例开箱可渲

- **WHEN** 租户在重建后的托管实例上调用 render_still、render_document 或 type 模式渲染
- **THEN** 产物正常生成并落资产账本
- **AND** 中文文本以 CJK 字体正确出形（无豆腐块）

#### Scenario: 标注与真实能力一致

- **WHEN** 模板目录将某类型标注 runtime 为 hosted 而实例底座不可用
- **THEN** 调用返回明确错误指出底座缺失
- **AND** 系统不返回空清单或静默跳过的假成功

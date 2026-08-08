# 视频类型注册表：声明式类型 + 数据驱动场景

## Summary

把「视频类型」从 SKILL.md 里两条硬编码流程升级为**声明式注册项**：每个类型一个 `type.json`（输入要求、pipeline 步骤、composition、默认参数、适用平台），配套一个数据驱动的 Remotion 模板。新增类型 = 加一个注册条目 + 一个模板，不再改动核心脚本。同时确立「场景边界必须由 captions 时间戳计算、禁止硬编码帧数」的模板标准。

## Motivation

**当前问题：**

1. **类型概念是隐式的**：`task.json` 有个 `type` 字段（voiceover/screen-recording），但类型没有注册表、没有 schema、没有列表命令——加类型要改 SKILL.md 散文 + 改脚本分支。
2. **硬编码场景反复踩坑**：`IntroduceXxx`/`VAASTutorial` 等模板把场景帧数写死，短音频算出负 `durationInFrames` 直接渲染失败，长音频则画面与口播脱节（VAASTutorial 9140f 事故）。字幕文本还硬编码在 `SubtitleBar.tsx`，换文案 = 改源码。
3. **加类型的心智成本高**：不知道要动哪些文件、按什么顺序，每个新类型都重新发明一次场景对齐。
4. **`generation-registry` spec 已走半步**：`mcp-server/registry.json` 的 video 组已有 seedance/voiceover 两条，但只描述「生成器」，不描述「成片类型」的输入与 pipeline。

**目标：**
- 类型可发现：`node scripts/types/list.mjs` 列出全部类型 + 输入要求 + 状态
- 类型可注册：新类型不动核心脚本，只加文件
- 模板有标准：场景边界一律由 captions 时间戳驱动（scene-align），硬编码帧数模式对新类型禁用
- 与 MCP 注册表对齐：类型条目字段可映射进 `registry.json` 的 video 组

## Requirements

### 核心功能

1. **类型注册表**
   - 位置：`.agents/skills/fd-vaas-video-creator/types/<type-id>/type.json`
   - schema：`id / name / description / version / status(experimental|stable) / inputs / pipeline / composition / defaults / platforms`
   - `inputs` 声明每项输入的必填性、类型、说明（script、items、images、orientation……）
   - `pipeline` 声明步骤序列（如 `["tts","fix-tts-timings","scene-align","preflight","render"]`）

2. **调度与发现**
   - `new-task.mjs --type <id>`：按 type.json 校验输入、初始化 task.json（写入 `type`）
   - `task-render.mjs`：按 task.json 的 `type` 查注册表，依 `pipeline` 字段执行步骤（未知类型报清晰错误并列出可用类型）
   - `scripts/types/list.mjs`：人类可读的类型清单（id、名称、状态、必填输入、适用平台）
   - 无 `--type` 时默认 `voiceover`，行为与现状完全一致（向后兼容）

3. **scene-align 场景映射标准**
   - 新工具 `scripts/scene-align.mjs`：输入修正后 captions.json + 可选的分段标记，输出 `[{from, durationInFrames, text, role}]` 场景数组
   - 分段规则：句间静音 gap ≥ 300ms 或脚本中的显式标记（如 `## 场景`）为边界；短于 1.5s 的段与相邻段合并；首尾留白可配
   - 新类型模板 MUST 从 scene-align 输出派生 `<Sequence from durationInFrames>`，MUST NOT 使用 `durationInFrames - N` 之类的硬编码算术
   - 旧硬编码模板（IntroduceOrg 等）保留可用、标记 legacy，不强制迁移

4. **模板与类型同驻**
   - 每个类型的 Remotion composition 放 `remotion-app/src/types/<TypeName>.tsx`（依赖 opensource-readiness 把 src 签入公开仓库）
   - 类型目录可带 `README.md`（用法示例）与示例输入（`example/`）

5. **与 MCP 注册表对齐**
   - type.json 字段设计兼容 `mcp-server/registry.json`：类型可作为 video 组的新条目注册（`driver` 指向 task-render）
   - 本变更只保证字段可映射，MCP 侧接线另起变更

### 非目标（Non-goals）

- 不迁移旧硬编码模板（标记 legacy 即可）
- 不改发布链路（publish 对类型无感，只认 mp4）
- 不做类型的 UI 选择器（Claude 读 list.mjs 输出即可）
- 不在本变更内新增任何具体类型（那是 add-video-types-batch-1）
- 不改 TTS/fix-tts-timings/preflight 现有脚本的行为

## Technical Approach

- **注册即文件系统**：类型 = `types/<id>/` 目录，发现 = 扫目录读 type.json，无需数据库
- **pipeline 解释器**：task-render.mjs 把现有步骤（tts→fix→preflight→render）抽成命名步骤函数，按 type.json 的 pipeline 数组顺序调用；`scene-align` 作为可选步骤插入
- **scene-align 算法**：
  ```
  captions[] → 按 (gap≥300ms | 显式标记) 切段
             → 合并 <1.5s 的短段（并入前段）
             → 每段: from = round(firstWord.startMs/1000*fps)
                    durationInFrames = round((lastWord.endMs-firstWord.startMs)/1000*fps) + pad
             → 段间可插 transition 帧（类型 defaults 配置）
  ```
- **模板契约**：composition 通过 props 接收 `scenes`（scene-align 输出）+ 类型自有 props（如 listicle 的 `items`）；总帧数 = scenes 末段 end + 尾留白，与音频时长由 preflight 校验

## Success Criteria

1. `list.mjs` 至少列出 `voiceover`、`screen-recording` 两个内置类型（它们也要补 type.json，作为注册表的 dogfood）
2. 新增一个类型的全部工作 = 新建 `types/<id>/type.json` + `src/types/<X>.tsx`，不改 new-task/task-render 源码
3. 用一个短音频（比模板设计时长短）渲染任一新类型：不出现负 durationInFrames，preflight 通过，画面切换与口播段落对齐
4. 旧工作流回归：不带 `--type` 的口播命令行为与变更前一致

## Risks & Mitigations

| 风险 | 影响 | 缓解 |
|------|------|------|
| pipeline 解释器重排现有步骤引入回归 | 口播主线坏掉 | voiceover 类型 dogfood + 不带 --type 的回归测试；步骤函数纯抽取不改逻辑 |
| scene-align 分段不符合内容语义 | 画面切换时机怪 | 支持脚本内显式标记覆盖自动分段；模板渲染前打印分段预览供确认 |
| 类型 schema 设计不足，batch-1 实施时又要改 | 返工 | batch-1 与本变更连续实施，schema 以 batch-1 五个类型的真实输入反推验证 |
| 与 mcp-server registry 字段漂移 | 两处真相 | 本变更定字段时对照 registry.json；接线变更时做单向同步（type.json → registry.json） |

## Open Questions

1. screen-recording 类型没有 captions，scene-align 对其不适用——它的 pipeline 是 `["record","postprocess"]` 形态，pipeline 解释器要支持「非渲染类」步骤占位吗？（倾向：支持，步骤函数可来自类型目录的可选 `steps.mjs`）
2. 类型级封面策略（每类型默认封面版式）放 defaults 还是 fd-cover-image 的职责？（倾向：defaults 里只放封面模板名引用）

## Dependencies

- **依赖 `opensource-readiness`**：模板源码要随 remotion-app/src 签入公开仓库，类型注册表才对公开用户有意义
- 现有脚本：new-task.mjs、task-render.mjs、preflight.mjs、fix-tts-timings.mjs

## Timeline Estimate

- type.json schema + 注册/发现/list：2 小时
- pipeline 解释器抽取 + 回归：2-3 小时
- scene-align.mjs + 分段预览：2 小时
- voiceover/screen-recording 补 type.json dogfood：1 小时
- **总计：7-8 小时**

# Tasks

## Phase 1: 类型 schema 与注册发现

### 1.1 type.json schema
- [x] 定义 schema：`id, name, description, version, status, inputs{}, pipeline[], composition, defaults{}, platforms[]`
- [x] `inputs` 每项：`{required, type(file|json|text|enum), desc, default?}`
- [x] 写 schema 校验函数（无新依赖，手写断言即可），非法 type.json 报具体字段错误

### 1.2 注册与发现
- [x] 新建 `.agents/skills/fd-vaas-video-creator/types/` 目录
- [x] `scripts/types/registry.mjs`：扫 `types/*/type.json`，缓存，提供 `get(id)` / `list()` / `validate()`
- [x] `scripts/types/list.mjs`：打印类型清单（id/名称/状态/必填输入/适用平台/简介）

## Phase 2: pipeline 解释器

### 2.1 步骤抽取（纯重构，不改行为）
- [x] task-render.mjs 现有流程抽成命名步骤：`tts` → `fix-tts-timings` → `preflight` → `render`
- [x] 每步签名统一 `(ctx) => ctx`，ctx 携带 taskDir/task.json/props
- [x] 回归：不带 `--type` 跑一次完整口播渲染，产物与变更前一致

### 2.2 按类型调度
- [x] `new-task.mjs --type <id>`：校验类型存在 + 必填输入齐全，task.json 写入 `type`
- [x] `task-render.mjs`：读 task.json.type → registry.get → 按 pipeline 顺序执行
- [x] 未知类型错误信息列出可用类型清单
- [x] 类型可提供 `types/<id>/steps.mjs` 覆盖/插入自定义步骤（供 screen-recording 等非渲染类型用）

## Phase 3: scene-align 场景映射

- [ ] 新建 `scripts/scene-align.mjs`：
  - [ ] 输入：修正后 captions.json + 可选脚本文件（读显式分段标记）+ fps/pad 参数
  - [ ] 自动分段：句间 gap ≥ 300ms 为边界
  - [ ] 合并 < 1.5s 短段（并入前段）
  - [ ] 输出 `[{from, durationInFrames, text, role}]`（role 预留 hook/body/cta）
- [ ] `--preview` 模式：打印分段表（序号/起止秒/时长/文本前 20 字）供渲染前确认
- [ ] 写进 SKILL.md 模板标准：新类型 MUST 用 scene-align 派生 Sequence，MUST NOT 硬编码帧数算术

## Phase 4: 内置类型 dogfood

- [ ] `types/voiceover/type.json`：映射现有口播流程（pipeline: tts→fix-tts-timings→preflight→render；composition: VoiceoverVideo）
- [ ] `types/screen-recording/type.json`：pipeline 用自定义 steps.mjs 封装录屏流程
- [ ] `list.mjs` 正确列出两者；`--type voiceover` 渲染与默认路径产物一致

## Phase 5: 文档与对齐

- [ ] SKILL.md 重写「视频类型判断」节：指向 list.mjs + 类型目录，删除散文式双类型描述
- [ ] SKILL.md「组合视频模板」节：IntroduceXxx 标记 legacy，说明新类型标准
- [ ] 对照 `mcp-server/registry.json` 检查 type.json 字段可映射（name/provider/model/driver），记录映射表到 design.md
- [ ] AGENTS.md 补一句：新视频类型 = types/ 目录 + src/types/ 模板

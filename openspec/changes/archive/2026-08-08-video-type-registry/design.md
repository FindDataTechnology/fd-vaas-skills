# Design: 视频类型注册表

## 关键决策

### 1. 注册表 = 文件系统目录，不是数据库

```
.agents/skills/fd-vaas-video-creator/
└── types/
    ├── voiceover/
    │   └── type.json
    ├── screen-recording/
    │   ├── type.json
    │   └── steps.mjs          # 可选：自定义 pipeline 步骤
    └── listicle/              # （batch-1 新增示例）
        ├── type.json
        ├── README.md
        └── example/
            ├── script.txt
            └── items.json
```

**理由**：类型需要随技能一起 git 跟踪、一起分发；文件系统天然满足「加类型 = 加文件」。`vaas.db` 存的是产物（assets），类型定义是代码不是数据。

### 2. type.json schema（v1）

```json
{
  "id": "listicle",
  "name": "榜单合集视频",
  "description": "Top-N 榜单口播：开场钩子 + N 个条目卡 + CTA",
  "version": 1,
  "status": "experimental",
  "inputs": {
    "script":  { "required": true,  "type": "file", "desc": "口播稿（支持 ## 场景 显式分段标记）" },
    "items":   { "required": true,  "type": "json", "desc": "榜单条目 [{rank,title,desc,image?}]" },
    "orientation": { "required": false, "type": "enum", "enum": ["1080x1920","1920x1080"], "default": "1080x1920" }
  },
  "pipeline": ["tts", "fix-tts-timings", "scene-align", "preflight", "render"],
  "composition": "ListicleVideo",
  "defaults": { "voice": "auto", "subtitleStyle": "tiktok-green", "transitionFrames": 8 },
  "platforms": ["douyin", "xiaohongshu", "bilibili", "weixin", "kuaishou", "youtube"]
}
```

与 `mcp-server/registry.json` 的映射（本变更只保证可对齐，不接线）：

| type.json | registry.json video 条目 |
|---|---|
| id | name |
| "local"（固定） | provider |
| composition | model |
| "task-render"（固定） | driver |

**对照检查（2026-08-08 实测）**：`mcp-server/registry.json` 现有 voiceover 条目为
`{name:"voiceover", provider:"local", model:"remotion", driver:"create_voiceover"}`。映射规则可对齐：
name=type.id ✓、provider 固定 "local" ✓；model 登记 composition（"VoiceoverVideo"）比 "remotion" 更精确、
driver 新类型统一 "task-render"。既有 voiceover 条目的 model/driver **保持不动**（mcp_server 已在用，
改动会破坏既有调用），新类型按上表登记。

### 3. scene-align 算法

```
输入: captions-fixed.json（逐字 startMs/endMs）+ 可选 script.txt + fps + pad
1. 显式标记优先: script.txt 中 `## ` 开头的行 = 强制场景边界（按首字匹配定位 startMs）
2. 自动分段: 相邻 caption gap ≥ 300ms → 切
3. 短段合并: 段时长 < 1.5s → 并入前段（避免画面闪烁）
4. 帧换算: from = round(first.startMs/1000*fps)
          dur  = round((last.endMs - first.startMs)/1000*fps) + pad
5. 输出: [{from, durationInFrames, text, role}]
   - role 推断: 首段=hook, 末段（含 CTA 关键词时）=cta, 其余=body
6. 渲染契约: 总帧数 = 末段 from+dur + tailPad；preflight 校验 总帧数/fps ≥ 音频时长 且 drift < 0.5s
```

**为什么 300ms**：seed-tts 句间停顿实测多在 250-600ms，300ms 能切开句子又不被逗号停顿（<200ms）误切。该值进 defaults 可调。

**为什么禁止硬编码**：`durationInFrames - N` 在音频短于 N 帧时算负值直接崩（VAASTutorial 事故）；且音频变长时画面不同步。scene-align 让帧数永远从真实音频推导。

### 4. pipeline 解释器：命名步骤 + ctx 传递

```js
const BUILTIN_STEPS = { 'tts': stepTts, 'fix-tts-timings': stepFix,
  'scene-align': stepSceneAlign, 'preflight': stepPreflight, 'render': stepRender };
// 类型可用 steps.mjs 覆盖或插入:
// pipeline: ["record", "postprocess"] → 全部来自 types/screen-recording/steps.mjs
```

- 步骤签名 `(ctx) => ctx`；ctx = `{taskDir, task, props, log}`
- 未知步骤名 → 报错并列出该类型可用的步骤来源
- **行为兼容**：无 `type` 的 task.json 视为 voiceover，pipeline 与现状逐步一致

### 5. 旧模板处置：legacy 标记，不迁移

IntroduceOrg/IntroduceGov/IntroduceReport/VAASTutorial 等继续渲染（历史视频可重渲），SKILL.md 标记「legacy：硬编码场景，新视频勿用」。迁移价值低（一次性大片），重写成本高。

### 6. composition 位置：`remotion-app/src/types/`

与现有平铺场景文件区分：`src/types/ListicleVideo.tsx` 等是「类型模板」（数据驱动、随类型注册），`src/scenes*.tsx` 是 legacy 一次性场景。Root.tsx 注册时按目录分组注释。

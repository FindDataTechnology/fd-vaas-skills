---
name: fd-vaas-storyboard
description: >
  VAAS 展示层创作手册(纯知识,无脚本):render_video 双模式选型 + seek 契约分镜撰写 + 配音/BGM 链。
  覆盖:(1) storyboard 模式四种场景 kind(html_intro/html_outro/html_full/kenburns)的字段、
  HyperFrames composition 契约（data-start/duration/track-index + window.__timelines 逐帧 seek）、无外链/data: URI 纪律、
  kenburns 图片输入;(2) storyboard vs type(carousel|listicle|data-viz|kinetic-quote|news-flash)
  选型决策;(3) render_still(kind="chart") 图表静帧作为视频视觉输入的数据→视频桥;
  (4) 视频内图表动画走 type=data-viz、静态图走 render_still 的分工;(5) generate_voice /
  voiceover_assemble 配音链与 bgm 混流。
  触发场景:用户要做视频 / 出片 / 写分镜 / storyboard、问"用什么视频形态"、要把数据做成视频、
  要自制开场片尾画面、要给视频配配音 / 加 BGM,或问 render_video / render_still 怎么传参。
compatibility: VAAS MCP 工具面(render_video / render_still / generate_voice / voiceover_assemble / models_voices / templates_list / templates_get);chromium+ffmpeg 渲染(本地与托管同一 HTML 场景底座);ECharts 品牌主题(echarts-theme,源自 remotion-app theme.ts)。
---

# FD VAAS Storyboard——展示层创作手册

做一支视频 = 三道决策:**形态选型**(storyboard 还是 type)→ **分镜撰写**(场景怎么写)→ **声音**(配音 + BGM)。本 skill 是这三步的知识手册,不含可执行脚本——所有产出都通过 VAAS MCP 工具面。

## 1. 形态选型:render_video 双模式

`render_video` 有两个互斥模式,**同时传 storyboard 和 type 是明确错误**:

| 你要什么 | 模式 | 调用形态 |
|---|---|---|
| 组合控制 / 自定义视觉 / 精确到帧的分镜(自制片头片尾、图表静帧串片、逐帧可复现) | **storyboard** | `render_video(storyboard={size, scenes:[...]}, voice_path=?, fps=?, bgm=?, slug=?, format=?)` |
| 成品结构化视频(TTS / 字幕 / 场景对齐 / 渲染全自动,只要给稿和素材) | **type** | `render_video(type=<五类之一>, script=口播稿, inputs={...}, slug=?)` |

模式语义:

- **storyboard = 确定性渲染**:场景序列编译为 HyperFrames composition 后交**渲染面**(独立服务)渲染,同一 storyboard → 同一字节流。slug 缺省按 storyboard 内容哈希派生,重复提交同一 storyboard 会幂等重放既有资产(不重渲、不重计费)。
- **type = 类型管线(HTML 场景构建器)**:五类型均由场景构建器直接产出 composition 片段,再走与 storyboard 同一渲染面——**本地与托管实例同一行为**(API 面不依赖 node,渲染全在渲染面)。`script` 可传内联文本或文件路径;`inputs` 的每个键变成管线参数(契约见 `templates_get(domain="video", id=<type>)`)。`templates_list(domain="video")` 每项带 `runtime` 标注:`hosted` = 该类型托管实例可用(五类型皆如此);`local_stdio_only` = 未移植类型仅本地 stdio 实例支持,托管上调用会指路报错。
- type 模式的配音与 BGM:`voice_path` 给定时**跳过 TTS**,按实测音频总时长×各段字符数加权分摊段时长;不给则管线内逐段 TTS(音色 `inputs.voice`,默认 auto)。`bgm={asset_id|path, volume?, fade_out?}` 与 storyboard 同语义,合成后混流。
- **补图 confirm 协议**:inputs 含提示词待补图(`{"prompt":...}`,或 `generate=true` 下的纯字符串)且未确认时,零产物返回 `pending_images` 清单;确认后重试传 `inputs.confirm_images=true`,先 generate_image 补图入账、再渲染。也可把对应条目直接换成已就绪的图片路径。
- slug 缺省按计划哈希派生(type+script+inputs+voice_path+bgm 全折入),同输入命中既有资产即幂等重放(跳过补图/TTS/渲染,不重渲、不重复计费)。
- 画幅:storyboard `size` 默认 `[1080,1920]` 竖屏;type 的 `orientation` 输入选 `1080x1920` 或 `1920x1080`。B 站 / YouTube 用横屏。
- 缺文件会在渲染前一次性报全(kenburns images / voice_path / bgm path 逐条列出),不会渲到一半才炸。

### type 五类型各适合什么内容

| type | 形态 | inputs 必填 | 适合内容 |
|---|---|---|---|
| `carousel` | 图文轮播:一图对一段,Ken Burns + 交叉淡入 | `script` + `images`(路径字符串 / `{"path":...}` 就绪图 / `{"prompt":...}` 待补图,走 confirm 协议,见上节) | 有图片素材的叙事、种草、教程 |
| `listicle` | 倒数排名卡片:hook → 条目卡×N → CTA | `script` + `items={title, items:[{title, text?, image?}], source?}` | Top N 榜单、盘点、测评合集 |
| `data-viz` | 图表动画讲解:hook → 图表卡×N → CTA | `script` + `data={title, charts:[...], source?}` | 数据解读、财报速览、行业数字 |
| `kinetic-quote` | 金句文字动画:逐句弹入、逐字高亮,无图 | `script`(`**关键词**` 显式标记放大词) | 观点、情绪、语录、金句合集 |
| `news-flash` | 固定结构卡片:标题卡 → 要点卡×N → CTA | `script` + `meta={headline, points:[...], source?}` | 快讯、要闻速报、公告 |

**分段纪律**(listicle / data-viz / news-flash 共用):script 用 `## 段名` 分段 = 1 hook + N 条目/图表/要点段 + 1 cta;条目 / 图表 / 要点的**数量必须与段数一致**,渲染前有校验步。carousel 不标 `##` 则按停顿自动分段。

还是拿不准 → 对照各类型 `type.json` 的 description / platforms(`templates_list(domain="video")`),都不匹配再问用户,别硬套。

## 2. storyboard 分镜撰写(编译为 composition)

storyboard 结构:

```json
{
  "size": [1080, 1920],
  "scenes": [
    {"kind": "html_intro", "duration_s": 4, "title": "标题", "sub": "副标题"},
    {"kind": "kenburns",   "duration_s": 8, "images": ["/abs/chart1.png"], "caption": "解读句", "motion": "zoom_in"},
    {"kind": "html_full",  "duration_s": 3, "html": "<!DOCTYPE html>…"},
    {"kind": "html_outro", "duration_s": 3, "title": "关注看更多", "sub": ""}
  ]
}
```

### 四种场景 kind 的字段

| kind | 必填 | 可选 | 说明 |
|---|---|---|---|
| `html_intro` / `html_outro` | `duration_s` | `title`, `sub`, `css` | 片头 / 片尾字卡。内置版式:深蓝渐变底(可 `css` 覆盖),标题随进度淡入上移,副标题延迟 25% 淡入 |
| `html_full` | `duration_s` + `html`(整页内联 HTML) | — | 完全自定义的一屏,必须遵守 seek 契约 |
| `kenburns` | `duration_s` + `images`(非空文件路径数组) | `caption`, `motion`(`pan_down` 默认 / `zoom_in` / `pan_right`) | 图片缓推缓拉;多图**均分**场景时长逐张切换,caption 前 1/4 段淡入 |

### 渲染契约(W4 起：编译为 HyperFrames composition)

**W4 起 storyboard 场景会被编译成 HyperFrames composition**（渲染在独立渲染面完成），因此只写「场景内容」，不要自己搭整页运行时：

1. **`html_intro` / `html_outro`**：只给 `title` / `sub`（可选 `css`），编译器生成入场阶跃动效与版式。
2. **`kenburns`**：给 `images`（本地路径或 downloads 相对路径）+ `duration_s`（可选 `motion`、`caption`）；图片由服务端内联为 `data:` URI，推拉动效由编译器生成。
3. **`html_full`**：给一段内联 HTML，作为该 clip 的内容原样注入——**视为静态**。需要动效时用 CSS animation（HyperFrames 会逐帧 seek 驱动），不要写自写帧循环 / `rAF` / `transition`。
4. **无外链纪律（硬性）**：拷贝会被编译期扫描，出现 `http(s)://` / `file://` 资源即拒绝，报错点名场景与资源；位图必须 `data:` URI 内联，`<link>` / `fetch` / 外链字体一律禁止。
5. **确定性**：画面状态必须是时间（引擎 seek）的纯函数——不依赖随机数、时钟、网络。

最小 `html_full` 片段（CSS animation 版，可逐帧 seek）：

```html
<style>
  .msg{position:absolute;inset:40% 8%;color:#fff;font:700 64px/1.4 sans-serif;
       text-align:center;animation:in 1.2s linear both}
  @keyframes in{from{opacity:0;transform:translateY(24px)}
                to{opacity:1;transform:translateY(0)}}
</style>
<div class="msg">你好，VAAS</div>
```

type 模式的五个构建器已经产出 composition 片段，不需要手写上述任何内容——直接用 `templates_get(domain="video", id=<type>)` 看输入契约。

### 时长与音频纪律(硬性)

- 场景 `duration_s` 总和 = 计划视频时长。带配音时 ffmpeg `-shortest` 会裁到短边,**音频必须 ≥ 计划视频时长**——正确顺序:先配音拿实测 `duration_ms`,再倒排各场景时长,别拍脑袋估。
- `fps` 默认 30;`format` 默认 mp4。
- 渲染产物目录里会保留 `storyboard.json`(分镜即真相源),PNG 帧丢弃。

## 3. chart 输入模式:数据 → 视频的桥

`render_still(kind="chart")` 把数据变成图片,再喂给 storyboard 场景当视觉输入:

```json
// 第一步:数据 → 图表静帧
render_still(kind="chart", spec={
  "echarts_option": {                       // 原生 echarts option,必填
    "xAxis": {"type": "category", "data": ["Q1","Q2","Q3","Q4"]},
    "yAxis": {"type": "value"},
    "series": [{"type": "bar", "data": [120, 200, 150, 260]}]
  },
  "size": {"width": 1080, "height": 1920},  // 和视频画幅对齐!
  "format": "png"                           // 默认 png;svg 也可
})
// → {"file_path": "chart/<slug>/<slug>.png", "width": 1080, "height": 1920, ...}
```

要点:

- `file_path` 相对 `downloads/`,**绝对路径 = `<VAAS_ROOT>/downloads/<file_path>`**——喂给 kenburns `images` 时用绝对路径。
- **品牌主题自动注入**(echarts-theme 注册,源自 remotion-app theme.ts):option 里显式指定的颜色优先,未指定的槽位取品牌色板——所以通常**不用**自己配色。
- 静帧强制 `animation:false`(确定性);`size` 默认 1280x720 横版,**竖屏视频记得传 `{width:1080,height:1920}`**,否则图在竖屏画幅里留黑边。
- slug 缺省按 spec 规范化哈希派生,同一 spec 幂等重放。

**桥接成片**:每张图一个 kenburns 场景(`caption` 写解读句、`motion` 挑缓动),片头 `html_intro` + 片尾 `html_outro` 一包——就是一支可复现的数据短片:

```json
{"size": [1080, 1920], "scenes": [
  {"kind": "html_intro", "duration_s": 3, "title": "三季度营收拆解", "sub": "数据说话"},
  {"kind": "kenburns", "duration_s": 6, "images": ["<VAAS_ROOT>/downloads/chart/a/a.png"], "caption": "营收连续四季加速", "motion": "zoom_in"},
  {"kind": "kenburns", "duration_s": 6, "images": ["<VAAS_ROOT>/downloads/chart/b/b.png"], "caption": "毛利率企稳回升", "motion": "pan_right"},
  {"kind": "html_outro", "duration_s": 3, "title": "关注看更多数据解读", "sub": ""}
]}
```

## 4. 图表动画 vs 静态图:分工

| 需求 | 走哪条 | 原因 |
|---|---|---|
| 图表要**跟随口播节奏动**(讲到哪长到哪) | `render_video(type="data-viz", script, inputs.data=...)` | 图表进度动画占每段帧数 40%:柱状生长 / 折线描画 / 饼图展开,与字幕时间戳对齐 |
| 只要一张能看的图(配图文、封面、kenburns 素材) | `render_still(kind="chart", spec=...)` | 一次调用出图,品牌主题自带,可复用可入库 |

data-viz 的图表规格(`inputs.data`):

```json
{
  "title": "标题",
  "charts": [
    {"type": "bar",  "title"?: "...", "labels": [...], "values": [...], "unit"? : "..."},
    {"type": "line", "series"?: [{"name","values"}], "labels": [...]},
    {"type": "pie",  "labels": [...], "values": [...]}
  ],
  "source"?: "数据来源标注"
}
```

纪律:`charts` 数量 == 口播稿的图表段数(`## 段名` 分段,1 hook + N 图表段 + 1 cta),渲染前校验不过不出片。**视频内动画一律走 data-viz 的 charts spec,不要试图在 storyboard 的 html_full 里手写 echarts 动画**(逐帧 seek 契约与 echarts 动画模型相性差,且绕开了品牌主题)。

## 5. 配音链

音色 / 模型先查真值表:`models_voices()`(能力、状态、计费、是否支持逐字字幕)。

```
                    ┌─ 单段:generate_voice(text, voice?, speed?) ──→ {file_path, duration_ms}
成稿(brainstorm 定稿)┤
                    └─ 长稿:voiceover_assemble(segments=[{text, window_s?}], voice?)
                            → 按段 TTS 拼接;超窗段返回压缩建议(suggestion),不硬变速率
                              → {file_path, duration_ms, segments:[{over_window, suggestion}]}
                                        │
                                        ▼
              render_video(storyboard=..., voice_path="<VAAS_ROOT>/downloads/<file_path>")
              (type 模式也可接外部配音:voice_path 给定时跳过 TTS、按字符数加权分摊段时长;
               缺省则管线内 TTS,音色用 inputs.voice,默认 auto)
```

- `generate_voice` 返回的 `file_path` 相对 `downloads/`;`render_video` 的 `voice_path` 要**绝对路径**。
- `voiceover_assemble` 的 `window_s` 是每段目标时长;超窗不截断不加速,给出的是**改稿建议**——回去改文案再重跑,重放幂等(同计划 + idempotency_key 不重复计费)。
- storyboard 场景时长按实测 `duration_ms` 倒排(见第 2 节纪律)。

### BGM

`bgm={asset_id | path, volume?, fade_out?}`——`asset_id`(资产账本 type=bgm 资产,含平台种子曲库)与 `path`(宿主音频文件)**二选一**;`volume` 默认 0.2(范围 (0,1]),`fade_out` 默认 true(片尾 3s 淡出)。

| 挂在哪 | 行为 |
|---|---|
| `render_video(storyboard=..., bgm=...)` | 视频合成后混流;曲短 `-stream_loop` 循环补长,曲长在片长处收尾;有配音时 amix 不压干声 |
| `voiceover_assemble(..., bgm=...)` | 混进干声成片;干声自动备份,**换 BGM 重跑从干声出发不叠混**;同计划不同 BGM 不串重放键 |
| `render_video(type=..., bgm=...)` | 与 storyboard 同语义:视频合成后混流,循环补长 / 片长收尾、volume / fade_out 一致 |

## 6. 最小全链示例(自定义分镜 + 配音 + BGM)

```text
1. generate_voice(text="…口播稿全文…")            # → file_path: audio/x.mp3, duration_ms: 14000
2. 按实测 14s 排场景(总时长 ≥ 14s):
   render_video(
     storyboard={
       "size": [1080, 1920],
       "scenes": [
         {"kind": "html_intro", "duration_s": 3, "title": "季度数据速览", "sub": "30 秒看懂"},
         {"kind": "kenburns", "duration_s": 8, "images": ["<VAAS_ROOT>/downloads/chart/q3/q3.png"],
          "caption": "营收同比 +34%", "motion": "zoom_in"},
         {"kind": "html_outro", "duration_s": 3, "title": "关注看更多", "sub": ""}
       ]
     },
     voice_path="<VAAS_ROOT>/downloads/audio/x.mp3",
     bgm={"asset_id": "<种子曲库 asset_id>", "volume": 0.15}
   )
3. 产物落资产账本,type=video,返回 {id, slug, file_path, duration_ms}。
```

结构化成品不需要这套手工分镜 → 直接 `render_video(type=..., script=..., inputs=...)`(第 1 节)。

## 参考

- `references/seek-contract.md` —— 四种 kind 的场景模板片段（W4 起 html_full 片段为静态注入；html_intro/outro/kenburns 由编译器生成动效）
- `fd-vaas-video-creator` skill —— type 模式的执行体;类型注册表在 `.agents/skills/fd-vaas-video-creator/types/<id>/type.json`
- `fd-vaas-brainstorm` skill —— 上游内容策划(选题矩阵 → 口播稿 / 图文草稿)

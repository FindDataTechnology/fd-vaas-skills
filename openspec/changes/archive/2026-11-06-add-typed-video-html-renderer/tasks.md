# Tasks: add-typed-video-html-renderer

## tasks

### W1 分段对齐与构建器基建

- [x] W1.1 `tools/typed_scenes.py` 骨架：builder 注册表（type id → builder）、inputs 契约校验（读 type.json，结构数对照前置报错列全）、`## 段名` 分段
- [x] W1.2 对齐层：逐段 TTS（复用 generators/tts，凭证链同 generate_voice）取真实段时长；`voice_path` 输入走 ffprobe 总时长按段字符数加权分摊；句级字幕切分（段内按句、时长按字符数比例）
- [x] W1.3 品牌 CSS wrapper 接入 builder 场景（theme.ts 单源变量 + 字幕底部条样式，与 SubtitleBrand 语义对齐）
- [x] W1.4 type 模式计划哈希折入 type/script/inputs/voice/bgm（确定性重放键，接既有 scoped slug）

### W2 五类型 builder

- [x] W2.1 card 族：news-flash（标题卡→要点卡×N→CTA+来源署名位）+ listicle（钩子卡→倒数条目卡 rank 弹入→CTA）
- [x] W2.2 carousel（分段 kenburns + 段字幕；images 路径或提示词，提示词走补图 pending→confirm 协议）
- [x] W2.3 data-viz（ECharts seek 驱动：bar 生长/line 描画/pie 角度扫描，animation 由 theme 注入 false，echarts.min.js 内联）
- [x] W2.4 kinetic-quote（逐句入场阶跃 + `**词**` 关键词放大变色，零图片依赖；句级对齐口径）
- [x] W2.5 type.json ×5 加 `renderer: "html"`；templates_list(domain=video) runtime 标注翻转为 hosted 可用

### W3 type 模式重接

- [x] W3.1 `render_video` type 分支：subprocess(node) → typed_scenes 管线；W7.6 hosted carve-out 摘除（本地/托管同行为）
- [x] W3.2 type 模式 bgm 参数接入（复用 storyboard 的 normalize/resolve/mix 链）
- [x] W3.3 补图 confirm 协议：首次调用返回 pending 清单 + confirm 参数二次调用进入渲染

### W4 质量门

- [x] W4.1 builder 单测：每类型场景 HTML 断言（结构节点/品牌变量/seek 契约字段/零外链）；结构数不匹配对照报错
- [x] W4.2 对齐单测：mock TTS 段时长驱动边界；voice_path 比例分摊；句级字幕切分
- [x] W4.3 确定性回归：voice_path 腿每类型真渲染双跑一致（沿用 test_determinism 口径）；本地 vs VAAS_HOSTED=1 同构
- [x] W4.4 既有 213 测试全绿不回退（render.py 接口未破坏）

### W5 部署与收口

- [x] W5.1 镜像重建（无新系统依赖）+ 上产 + 托管探针：五类型 voice_path 腿生产 E2E（成片+签名下载+md5 口径）
- [x] W5.2 TTS 腿 E2E（11-05 词元自铸 key 后补跑：generate_voice qwen3-tts-flash+voice 101001 全链 PASS 出 MP3+签名下载；image/video 腿凭证链已通但上游 openai-next 账号被 403 封→503，非本 change/key 问题，见 deploy/README 复核）
- [x] W5.3 文档：fd-vaas-storyboard SKILL.md 类型段更新（hosted 可用、voice_path/bgm、confirm 协议）；README render_video 段同步
- [x] W5.4 pricing 复核（type 模式记账仍 render_video+render，无新条目即勾）+ 外账记录（trial 文档如提及类型则同步）

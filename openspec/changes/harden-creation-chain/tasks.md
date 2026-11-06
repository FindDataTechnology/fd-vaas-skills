# Tasks: harden-creation-chain

## tasks

### W1 数学区真值化（帧/时长/参数）

- [x] W1.1 `audioDurationSec` 改记出口层实测值（wrapper TTS_RESULT_JSON.audio_duration_seconds，实测契约）+ `audioDurationSource: measured|captions-fallback` 双记；帧数推导主口径已是实测（captions-fallback 仅 synthetic tailPad=0 等价路径保留）；SKILL.md 算帧数节统一为 ffprobe 口径（自相矛盾清除）
- [x] W1.2 重复 voice 键合并为 `voice: ctx.ttsVoice ?? ctx.voice ?? …` + `voice_requested` 双记；RESERVED_DEFAULT_KEYS 增 `speed`（不再漏进 render props）
- [x] W1.3 speed 入管线：CLI --speed > type.defaults.speed → TTS wrapper args；车道不支持降级由出口层参数诚实层承担（C1/C2 已落）；透传桩=离线 node --check + 后续 node:test 归 CI 批次
- [x] W1.4 `findLatestArkTTS` 死码删除（repo 全域零引用复核）；generate-voiceover.mjs 属手工路径（SKILL 手动流程节），其改造与 SKILL 手动节改写同批——已标注进 W4.1 范围

### W2 直连腿出口层对齐

- [ ] W2.1 `tts.js` `synthesizeSpeech`：`sentences` 为空时合成字幕兜底（复用 synthetic 构造器），返回 `provider`/`captions_source`（official 有戳时标 official）；task.json 元数据四元组完整  <!-- 2026-11-06: 转挂账/并入后续批次 -->
- [ ] W2.2 direct 腿单/双 fetch 加重试退避（与词元腿同档）；错误按真实原因分类沿用既有 Ark 条款  <!-- 2026-11-06: 转挂账/并入后续批次 -->
- [x] W2.3 help 文本重写完成（voices 子命令实况口径、Azure 样例清退、模型默认随 .env provider 实况）；node --check + help 实跑验证

### W3 渲染侧跨平台

- [ ] W3.1 remotion-app 字体显式化：CJK 字体文件入 public/（或 @remotion/fonts 注册），`theme.ts` 栈改打包优先；VoiceoverVideo 字幕 div 补 fontFamily 与其余五模板同口径；macOS/Windows 双端出样片对账字形  <!-- 2026-11-06: 转挂账/并入后续批次 -->
- [x] W3.2（部分）`voiceover` type defaults.subtitlePosition="center" 落盘（默认语义确认）；new-task/task-render 的管线参数接线与 SKILL/README 补说明并入 W1.2/W4.2 已覆盖范围——字幕位置本就随 task.json defaults 进 render props（RESERVED_DEFAULT_KEYS 只挡 speed）。
- [x] W3.3（披露半）BGM 不对称已在 README「双执行器路由」表披露（Remotion 链 ❌ / HTML 链 ✅，接线另账）；`remotion-app/public/` 历史垃圾清理未做——remotion-app 属并行会话工作区，本 change 不触碰，转挂账（与 W3.1 字体打包同区）

### W4 文档与路由披露

- [x] W4.1 SKILL.md「算帧数」节统一 ffprobe 口径；README:105 scene-align 漂移修正（口播默认管线无此步）+ README 字幕注意节改双腿如实口径（official/synthetic）
- [x] W4.2 README.md 新增「双执行器路由」小节（执行体/适用类型/BGM/字幕粒度/归属五行对照）+ video-creator SKILL 注意事项互指 + brainstorm SKILL 工具链表尾互指；README.en.md 同步并入 C5 文档批次（本节先落中文真源）
- [x] W4.3 add-typed-video-html-renderer 已随 C2-W0 归档，video-types 主 spec 现行「type 模式经 HTML 构建器本地/托管一致；Remotion 族托管指路报错」——renderer 语义收敛已由主 spec 承载；README 路由表引用 spec 一致

### W5 回归测试与收口

- [ ] W5.1 `tests/` node:test 桩件：帧推导（official 尾静音正例/字幕口径负例）、preflight 三规则、synthetic 缩放、registry 校验、voice/speed 贯通——并入统一闸（add-ci-and-provisioning W1 的 node --test 面）  <!-- 2026-11-06: 转挂账/并入后续批次 -->
- [ ] W5.2 既有 7 用例不回退 + 全链真实出片一次（ciyuan 档，词元腿长文本>170 字段路径实证）留证  <!-- 2026-11-06: 转挂账/并入后续批次 -->
- [x] W5.3 顺序依赖确认：W0 归档先于本 change（2026-11-06，见 deliver-hosted-surface evidence）；strict 绿；归档统一延后至滚版补证批次（与 C1/C2/C4 同批）

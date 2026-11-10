#!/usr/bin/env node
/**
 * generate-cover.mjs — 已退役（2026-11-09）
 *
 * 原实现用 `npx remotion still` 渲染封面，但 Remotion 已从本仓退役
 * （`remotion-app/` 已删除，出片链切到 HyperFrames + chromium 单帧）。
 * 于是这个脚本的每条路径都是死的：cwd 不存在，启动即失败；更糟的是用户会
 * 以为「有命令可跑」，试半天才发现本仓根本没有 Remotion 项目。
 *
 * 保留文件而不直接删除：SKILL.md、历史文档、用户自己的脚本可能按路径调用它；
 * 静默消失会变成 `No such file`，比「明确说已退役」更难查。
 *
 * 现行做法：托管 MCP 工具 `generate_cover`（chromium 单帧，与视频卡片共用
 * `_stage.BASE_BG` 品牌底座）。参数语义见同目录上一级 SKILL.md。
 *
 * 台账：docs/debt-ledger.md DEBT-REMOTION-RESIDUE-01
 */

console.error(`
❌ generate-cover.mjs 已退役：本仓的 Remotion 项目（remotion-app/）已删除。

   原因：2026-11-09 起出片链切到 HyperFrames，封面/静帧改为 chromium 单帧渲染，
   \`npx remotion still\` 在这个仓里没有任何 composition 可渲染。

   改用托管 MCP 工具 generate_cover：
     {
       "title": "寻数科技",
       "subtitle": "探索更开放更公平的 AI 未来",
       "tags": "开源 · 数据 · AI",     // 字符串，不要传数组
       "width": 1920, "height": 1080
     }
   参数语义（尺寸/朝向/模板/Logo）见：
     .agents/skills/fd-cover-image/SKILL.md

   确实需要在本机跑 Remotion 项目，那是另一件事——请新建独立工程，
   不要把 remotion-app/ 恢复到本仓（退役决定见 docs/debt-ledger.md）。
`);

// 传任何参数也一律退出：这个入口没有可用路径，不该出现「成功」的样子
process.exit(2);

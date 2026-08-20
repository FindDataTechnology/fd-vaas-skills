---
name: ppt-master
description: >
  AI-driven presentation workflow: generate editable PPTX decks/slides, reconstruct page
  visuals, create reusable Brand/Style/Layout/Deck workspaces, fill native PPTX templates,
  and enhance finished PPTX files. Use when the user asks to create/generate/reconstruct/
  beautify/redesign/template/fill/enhance a PPT, PPTX, slide deck, or courseware, add
  narration or animation to one, or mentions "ppt-master" / "做PPT" / "生成PPT" /
  "制作演示文稿". Heavy skill — fetch on first use (`bash scripts/fetch-ppt-master.sh`).
---

# PPT Master

> **⚠️ 薄壳技能：完整实现需按需下载。**
> ppt-master 是一个重资产技能（约 1.2 万文件 / ~120 MB）。为了让 VAAS 仓库对首次用户保持
> 轻量，仓库只签入了本 stub，完整技能树（脚本 / 模板 / 参考素材 / 路由工作流）按需从上游拉取。

## 首次使用：拉取上游

```bash
bash scripts/fetch-ppt-master.sh
```

拉取后，**完整、权威的技能契约在 `.agents/skills/ppt-master/upstream/SKILL.md`** —— 驱动前先读它。
`upstream/` 已 gitignore，不会被提交回 VAAS；重新下载：`rm -rf .agents/skills/ppt-master/upstream && bash scripts/fetch-ppt-master.sh`。

## 能力概览

把源文档（PDF / DOCX / URL / Markdown）变成高质量 SVG 幻灯片，再导出 `.pptx`。

核心流水线：

```
源文档 → 创建项目 → [模板] → 策略师生成结构化方案 → [图像生成] → 执行器实时预览 → 质检 → 后处理 → 导出
```

- **策略师（Strategist）**：把源文档拆成结构化的逐页方案（含设计规范 `design_spec.md` / `spec_lock.md`）。
- **执行器（Executor）**：按方案逐页手写 SVG（`svg_output/`），支持实时预览。
- **质检（QC）**：逐页校验视觉一致性、字体/颜色合规、版式闭合。
- **导出**：`svg_output/` → `.pptx`（DrawingML / 原生对象映射）。

> SVG 是页面设计语言：每页可见内容（文字 / 图 / 形状 / 图表）都须落在该页 SVG 或其引用中。
> 模板 / `design_spec.md` 只是创作输入，不能在导出时凭空补内容。

## 前置条件

- 若用到生图步骤：`pip install -r .agents/skills/ppt-master/upstream/requirements.txt`，并按 `upstream/.env.example` 配置密钥。
- 需要 Claude Code 主体 agent 端到端完成 SVG 生成（**禁止**用子 agent 批量生成 SVG，**禁止**用脚本批量产出 SVG）。

## 与 VAAS 主线的关系

ppt-master 产出的 `.pptx` **不能直接当视频上传**。`cap`（屏幕录制）、`fd-vaas-video-creator`、或 ppt-master 自身的导出/渲染步骤，是把幻灯片变成可发布视频的桥。

---

> 上游仓库：https://github.com/hugohe3/ppt-master · 技能子树路径：`skills/ppt-master/`

---
name: fd-cover-image
description: >
  生成专业品牌封面图（横版/竖版），对齐项目设计系统，支持自定义标题、副标题、标签、Logo。
  适用于视频封面、社交媒体封面、海报、宣传图等场景。
  当用户说"做个封面"、"生成封面图"、"视频封面"、"封面设计"、"做张海报"、"生成宣传图"、
  "横版封面"、"竖版封面"、"小红书封面"、"抖音封面"、"B站封面"、"给视频加封面"时，
  **优先走托管工具 generate_cover（chromium 单帧）**，不要直接用 AI 生图。
  只有当用户明确要求 AI 画图、需要创意插画/照片风格、排版做不出来的效果时，
  才退回到 seedream 等 AI 生图工具。
compatibility: 托管 MCP 工具 generate_cover（chromium 单帧，无本地依赖）；本文的设计规范同样适用于手写 HTML/CSS 封面
---

# FD 封面生成器 (fd-cover-image)

> ⚠️ **本地 Remotion CLI 已退役（2026-11-09）**：`remotion-app/` 已删除，
> `scripts/generate-cover.mjs` 现在只会**明确报错并退出**（不再假装能出图）。
> 出封面请走托管 `generate_cover`（chromium 单帧，与视频卡片同一套品牌底座）。
> 本文保留的是**设计规范**（配色/排版/尺寸/模板语义），对托管路径和手写 HTML 封面同样适用。
> 退役台账：`docs/debt-ledger.md` DEBT-REMOTION-RESIDUE-01。

## 为什么用渲染而不是 AI 生图

| 维度 | Remotion 封面 | AI 生图（seedream 等） |
|---|---|---|
| **文字准确性** | ✅ 像素级精确，不会乱码/错字 | ❌ 中文字经常乱码、错字、变形 |
| **排版控制** | ✅ 精确到像素，对齐一致 | ❌ 随机，每次都不一样 |
| **品牌一致性** | ✅ 直接复用项目主题色、字体、Logo | ❌ 风格不可控，很难对齐品牌 |
| **生成速度** | ✅ 1~3 秒出图 | ⚠️ 5~15 秒 |
| **创意/插画** | ❌ 做不了复杂插画、真实照片 | ✅ 擅长创意视觉 |

**原则**：
- 文字为主的封面 → **必须**用本 skill（Remotion）
- 需要创意插画、照片风格、复杂视觉 → 才用 AI 生图

---

## 快速使用

### 生成封面（托管工具，推荐）

托管 MCP 工具 `generate_cover`（chromium 单帧渲染，与视频卡片共用 `_stage.BASE_BG` 品牌底座）：

```jsonc
// 工具名：generate_cover
{
  "title": "寻数科技",
  "subtitle": "探索更开放更公平的 AI 未来",
  "tags": "开源 · 数据 · AI",        // 注意：字符串，不要传数组
  "kind": "cover",                   // 或 still_graphic
  "width": 1920, "height": 1080
}
```

计量口径：**1 张封面 = 1 render**（`units=1, unit_type="render"`）。

### 老 CLI（已退役，仅保留报错说明）

```bash
# 这条命令现在只会报错退出——remotion-app/ 已删除，没有 Remotion 项目可跑
node $VAAS/.agents/skills/fd-cover-image/scripts/generate-cover.mjs --title "..." --output out.jpg
```

### 参数语义（设计规范，托管路径同名对应）

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--title` | ✅ | — | 主标题（大号白色粗体） |
| `--subtitle` | ❌ | — | 副标题（中号绿色） |
| `--tags` | ❌ | — | 底部标签（小号灰色） |
| `--orientation` | ❌ | `horizontal` | `horizontal`(横版) / `vertical`(竖版) / `square`(方版) |
| `--size` | ❌ | 横版 1920x1080 | 自定义尺寸，格式 `WxH`，如 `1080x1440` |
| `--template` | ❌ | `brand` | 模板：`brand`(品牌简约) / `title-only`(仅标题) / `gradient`(渐变大字) |
| `--logo` | ❌ | `downloads/common/icon.png` | Logo 路径，传 `none` 则不加 Logo |
| `--output` | ✅ | — | 输出文件路径 |
| `--format` | ❌ | 自动（按后缀） | `jpeg` / `png` |

### 预设尺寸速查

| 用途 | 尺寸 | orientation |
|---|---|---|
| 抖音横封面 | 1920×1080 | horizontal |
| 抖音竖封面（3:4） | 1080×1440 | vertical |
| 小红书封面（3:4） | 1080×1440 | vertical |
| B站封面（16:9） | 1920×1080 | horizontal |
| 视频号封面 | 1080×1260 | vertical |
| YouTube 缩略图 | 1280×720 | horizontal |

---

## 内置模板

### `brand`（品牌简约，默认）

左上角 Logo + 品牌名，中央大标题 + 绿色分割线 + 副标题，底部标签，深色渐变背景 + 淡绿光晕。

适用于：品牌宣传片封面、公司介绍视频封面、官方账号内容。

### `title-only`（极简大字）

纯深色背景，居中超大号标题，无副标题无标签，底部小 Logo。

适用于：观点类视频、金句封面、纯文字封面。

### `gradient`（渐变大字）

大标题渐变填充（绿→青），适合冲击力强的封面，底部小字副标题。

适用于：热点话题、教程类、吸引眼球的封面。

---

## 进阶：自定义版式（已退役路径，仅供理解历史实现）

> 本节描述的是**已删除**的 `remotion-app/`（`CoverBrand.tsx` / `Composition.tsx` / `npx remotion still`）。
> 现在加新版式的正确做法：在 `mcp-server/mcp_server/tools/typed_scenes/builders/` 里写 chromium 版式，
> 复用 `_stage.BASE_BG` 与家具（FURNITURE_HTML），走托管渲染；不要试图恢复 Remotion 项目。

```bash
# 历史命令（remotion-app 已删，跑不了）
# cd $VAAS/remotion-app && npx remotion still <CompositionId> --output out.jpg
```

---

## 工作流约定

1. **接到封面需求 → 先用托管 `generate_cover`**（除非用户明确说要 AI 画图）
2. 选择合适的模板和尺寸，生成封面图
3. 在浏览器里打开给用户确认（`open <path>` 或 ego-browser 打开 file://）
4. 用户满意后，用于上传发布 / 嵌入视频 / 导出

---

## 与其他工具的关系

- **fd-vaas-video-creator**：视频渲染完成后，如果用户要加封面，调用 `generate_cover` 生成，再嵌入到视频里（`embed-poster.mjs`）或用于平台上传。
- **fd-vaas-publish-videos**：分发前自动调用 `generate_cover` 生成各平台对应尺寸的封面，用户确认后再上传。
- **fd-vaas-video-creator 内置 seedream**：需要插画、照片、复杂创意视觉时才用；用前向用户说明为什么不用渲染方案。

---

## 参考

- `mcp-server/mcp_server/tools/typed_scenes/` —— 托管渲染版式（chromium，现行）
- `mcp-server/mcp_server/tools/typed_scenes/builders/_stage.py` —— 品牌底座（`BASE_BG`）与共用家具
- `scripts/generate-cover.mjs` —— **已退役**，只保留报错说明
- `downloads/common/icon.png` —— 公司 Logo（默认）

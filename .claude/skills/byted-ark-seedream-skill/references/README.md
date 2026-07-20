# Seedream 参考

本目录存放图像生成 Skill 的参考数据。

## seedream-model-matrix.json

维护所有 Seedream 图像模型的能力矩阵。Wrapper 据此进行智能模型路由：
当用户传入参考图、联网搜索、PNG 输出、批量生成等参数时，Wrapper 自动推断能力需求并匹配最佳模型。

### 字段说明

| 字段 | 说明 |
|------|------|
| `capabilities` | 基础能力：`text2image`（文生图）、`image2image`（图生图/图像参考） |
| `supported_sizes` | 支持的尺寸：`2K`/`3K`/`4K`/`WxH`（自定义像素如 `2048x2048`） |
| `supports_reference_image` | 是否支持参考图（图生图） |
| `supports_multi_reference_image` | 是否支持多张参考图 |
| `supports_web_search` | 是否支持联网搜索（实时信息增强） |
| `supports_png_output` | 是否支持 PNG 输出（否则仅 JPEG） |
| `supports_sequential` | 是否支持批量顺序生成 |
| `supports_optimize_prompt` | 是否支持提示词优化 |
| `supports_streaming` | 是否支持流式输出 |
| `supports_seed` | 是否支持随机种子 |
| `max_images_per_request` | 单次请求最大生成图片数 |
| `speed` / `quality` | 速度与画质评级 |

### 模型命名约定

- **Agent Plan（`/api/plan/v3`）使用带点的友好名**：`doubao-seedream-5.0-lite`、`doubao-seedream-5.0` 等。
  本 Skill 默认走 Agent Plan，故矩阵键名采用带点格式。
- 标准 API（`/api/v3`）使用带日期的 ID：`doubao-seedream-5-0-lite-260128` 等。
  两者是同一模型在不同入口的寻址方式。

### 新增模型

如需新增模型，只需在此 JSON 中追加条目，Wrapper 会自动纳入路由，无需改代码。

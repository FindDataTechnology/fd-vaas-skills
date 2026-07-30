# 小红书选择器表

验证日期：2026-07-27。登录页（`/login`）实机确认；发布页选择器来自 `uploader/xiaohongshu_uploader/main.py`，标 `[源码]`。

## 登录态判断

| 信号 | 特征 | 状态 |
| --- | --- | --- |
| 未登录 | URL 含 `/login` | [已验证] |
| 登录框 | `div[class*='login-box']` 可见 | [源码] |

## 登录页

| 用途 | 选择器 | 状态 |
| --- | --- | --- |
| 登录框 | `div[class*='login-box']` | [源码] |
| 切到扫码 | `img.css-wemwzq` | [源码] |
| 二维码区 | `.login-box-container`「APP扫一扫登录」旁 img | [源码] |

## 上传

| 用途 | 选择器 | 状态 | 说明 |
| --- | --- | --- | --- |
| 视频文件 input | `div[class^='upload-content'] input.upload-input` | [源码] | |
| 图片文件 input | `input[type="file"][accept*="image"]` | [源码] | 兜底同上 |
| 上传完成标记 | 预览区 `.preview-new` 含「上传成功/分辨率/重新上传/编辑封面/已上传/已选择/100%」 | [源码] | 或标题框出现 |

## 表单

| 用途 | 选择器 | 状态 | 说明 |
| --- | --- | --- | --- |
| 标题 | `input[placeholder*="填写标题"]` | [源码] | 最多 20 字 |
| 正文 | `p[data-placeholder*="输入正文描述"]` | [源码] | click 后清空再 typeText |
| 话题候选容器 | `#creator-editor-topic-container` | [源码] | typeText('#'+tag) 后等它出现 |
| 话题候选首项 | `#creator-editor-topic-container .item` | [源码] | 等不到就退格清掉 |
| 发布按钮 | `xpath=//button[normalize-space(text())="发布"]` | [源码] | 定时用「定时发布」 |

## 封面（可选）

| 用途 | 选择器 | 状态 |
| --- | --- | --- |
| 入口 | `xpath=//div[contains(@class,"cover-plugin-title")][normalize-space(text())="设置封面"]` | [源码] |
| 打开弹窗 | 入口 `ancestor::div[contains(@class,"cover-plugin-preview")]` 下 `div.cover > div.default` | [源码] |
| 弹窗 | `div.d-modal.cover-modal` | [源码] |
| 文件 input | `div.d-modal.cover-modal input[type="file"][accept*="image"]` | [源码] |
| 确定 | `xpath=//div[contains(@class,"cover-modal")]//button[contains(@class,"mojito-button")][normalize-space(text())="确定"]` | [源码] |

## 原创声明 & 定时发布（可选）

| 用途 | 选择器 | 状态 |
| --- | --- | --- |
| 原创声明 | `div.original-declaration input[type="checkbox"]` 或文本「原创声明」 | [源码] |
| 定时开关 | `xpath=//div[contains(@class,"custom-switch-card")][normalize-space(.//text())="定时发布"]//div[contains(@class,"d-switch")]` | [源码] |
| 时间 input | `.d-datepicker-input-filter input.d-text` | [源码] |

---
name: fd-vaas-pull-from-cloud
description: 从 VAAS 托管生成实例拉取租户名下的产物到本机发布目录。三种输入任选其一：谦面调用键（连网关按 owner 过滤）、签名下载 URL（生成响应里带的）、或直接给 asset id + 实例地址。产物自动落 downloads/ 标准目录并生成发布技能可直接消费的 task 目录（article.md + meta.json 骨架）。无凭据时输出获取指引。**本技能只拉内容，不碰任何登录态**（发布登录走 fd-vaas-login，在本机完成）。
compatibility: Python 3.8+（零第三方依赖）；产物在某个 VAAS 托管实例上（默认 https://mcp.finddatatech.cloud/vaas-wanxing）。
---

# FD VAAS 云端拉取器

云端生成 → 本机发布的第一步。托管实例（cheap-2）上的生成产物按租户（owner）隔离存放，
本技能把**你名下的**产物拉到本机 `downloads/` 里，落成发布技能（fd-vaas-publish-docs /
fd-vaas-publish-videos）直接可用的目录结构。

## 三种拉取方式

```bash
# 方式 A：谦面调用键（推荐）——自动按 owner 过滤，可浏览整个内容库
python3 scripts/pull_from_cloud.py --call-key "$FACET_CALL_KEY" --list
python3 scripts/pull-from-cloud.py --call-key "$FACET_CALL_KEY" --asset <asset-id>

# 方式 B：签名下载 URL（生成响应里直接给的 download_url）
python3 scripts/pull_from_cloud.py --url "http://.../download/<asset-id>?owner=...&exp=...&signature=..."

# 方式 C：直连实例（自部署/内网场景）
python3 scripts/pull_from_cloud.py --base https://mcp.finddatatech.cloud/vaas-wanxing \
    --call-key "$KEY" --asset <asset-id>
```

`--list` 列出 owner 名下的资产（id/slug/类型/时间）；`--asset` 拉单个产物并落盘；
`--all` 拉列表里全部未拉取过的产物。

## 落盘规则（与发布技能契约对齐）

| 资产类型 | 落盘位置 | 产物文件 |
|---|---|---|
| article/copy | `downloads/fd-docs/<slug>/` | `article.md` + `meta.json`（title/tags/summary 骨架） |
| video | `downloads/fd-videos/<slug>/` | `<slug>.mp4` |
| image/cover | `downloads/fd-images/<slug>/` | `<slug>.<ext>` |
| audio | `downloads/fd-audio/<slug>/` | `<slug>.mp3` |

图文类落成 `article.md + meta.json` 后即可直接 `node publish.mjs --slug <name> --plan`
走 fd-vaas-publish-docs 的标准流程（dry-run 预览 → 确认 → 发布）。

## 安全边界（读本技能前请知悉）

- **登录态零接触**：本技能只经手内容文件。平台登录态由 fd-vaas-login 在你本机扫码产生，
  存你本机专用 profile，任何技能（含本技能）都没有上传它的通道。
- **凭据最小化**：调用键只用于向谦面网关证明「你是你」，平台侧只能看到与你 owner 匹配的
  产物元数据；签名 URL 自带过期（默认 24h），本身就是凭证，不需要再配别的。

## 无凭据时

不传任何凭据运行会打印获取指引（怎么拿调用键、怎么重新生成签名 URL），不会抛堆栈。

# VAAS Goal / 目标

> The why of this project. For the how, see `README.md`.

## EN

**VAAS — Variable Asset Authoring & Syndication.**

The goal is to take a single content demand and turn it into a **variable-type resource** — a
slide deck, a document, a screen recording, an AI-generated image/video, or a voiceover video —
then **publish it automatically to multiple social-media accounts**, ideally producing a
*different* variant per platform.

We are an **orchestration layer**, not an application: creation skills produce asset files, a
distribution engine ships them. There is no monolithic app — just skills wired to a CLI, and a
`fd-vaas-*` mainline that chains a demand all the way to a published post:

```
demand  ->  brainstorm  ->  voiceover video (.mp4 + .srt)  ->  multi-platform publish
```

**Why this exists:** lower the cost of going from an idea to a published, platform-appropriate
asset, so one person can run many accounts without hand-rolling each platform's quirks.

---

## 中文

**VAAS —— 可变资源创作与分发（Variable Asset Authoring & Syndication）。**

目标是：接收一个内容需求，把它变成**可变类型的资源**——幻灯片、文档、屏幕录制、AI 生图/生视频、或口播视频，然后**自动发布到多个社交媒体账号**，理想情况下为每个平台产出*不同*的变体。

我们是一个**编排层**，不是一个应用：创作技能负责产出素材文件，分发引擎负责把素材发出去。这里没有庞大的应用代码——只有把技能接到一个 CLI 上的胶水，以及一条 `fd-vaas-*` 主线，把需求一路串到一条已发布的帖子：

```
需求  ->  选题策划  ->  口播视频 (.mp4 + .srt)  ->  多平台发布
```

**为什么存在：** 降低从「一个想法」到「一条平台适配的已发布内容」的成本，让一个人不用为每个平台的坑手写参数，也能同时运营多个账号。

# 发布流程说明(已重构)

本文件已精简为指针。发布相关的两个 skill 的权威文档在各自 SKILL.md:

- **图文分发** → `.agents/skills/fd-vaas-publish-docs/SKILL.md`
- **视频分发** → `.agents/skills/fd-vaas-publish-videos/SKILL.md`

## 共享库(unify-publish-lib)

两个发布 skill 的公共实现收敛到 `.agents/skills/_shared/publish/`:

| 文件 | 说明 |
|---|---|
| `browser_utils.py` | patchright sync API 封装(Browser / login_or_wait / paste_text / confirm_gate / publish_and_verify)。图文+视频共用的**单一实现**,各平台脚本经 `_publish_path.py` 解析后 `from browser_utils import ...` |
| `publish-common.mjs` | 两个 `publish.mjs` 共用的纯函数(loadEnv / truncate / stripMd / mdToPlain / summarize / ensureSeconds / limitTags)。无副作用,`node --test publish-common.test.mjs` 直接可跑 |
| `platform-registry.json` | 平台**路由 + 选择器验证状态**的单一可机读源(图文+视频共用)。改状态用 `probe.py <platform> [--mark-broken]` 回写,别手改 |

## 历史说明

本文件曾记录一版「发布流程优化」:handOffTaskSpace 轮询登录、文本匹配元素定位、
douyin/bilibili/youtube 的 ego-browser 独立上传脚本等。这些已随架构演进被取代:

- 视频上传改为「vendor social-auto-upload + `sau_adapter.py` 薄适配层」,统一 py 运行时(patchright),旧的 ego-browser `.mjs` 运行时已删除;
- 图文分发改为「上游 Note 复用(`note_adapter.py`)+ 自有逻辑(ego-browser heredoc 或 patchright)」双运行时。

细节以两个 SKILL.md 为准,本文件不再重复。

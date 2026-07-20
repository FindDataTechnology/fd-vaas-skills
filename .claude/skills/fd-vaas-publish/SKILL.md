---
name: fd-vaas-publish
description: 把 fd-vaas-video-creator 出的口播视频一键发到多个社交平台。**只做编排 —— 平台差异化偏好、账号、标签、定时 —— 上传本身完全委托给 social-auto-upload(`sau` CLI)**,不重造轮子。触发场景:用户说"把这支视频发到抖音/小红书/B站/视频号/YouTube"、"多平台一起发"、"给 finddata-intro 发出去"、"上传到 XXX"、"分发这条视频"、"push to socials"、"posting the video",或者刚做完一支 fd-videos/<slug>/ 里的视频、要走下一步分发时。**必须**用本 skill 的 publish.mjs,不要直接手写 sau 参数 —— 因为标签/描述/tid/短标题这些平台差异每次手抄都会漏,该 skill 从 .env 读一次配一次,后面每条视频复用。也不要用本 skill 做上传本身的登录/cookie 管理/浏览器自动化,那些去调 social-auto-upload/skills/*-upload/ SKILL。
compatibility: Node.js 18+;social-auto-upload 已 `uv pip install -e .` 且 `sau` 在 PATH;各平台 cookie 已经 `sau <platform> login` 过一次;fd-vaas-video-creator 已跑完(存在 downloads/fd-videos/<slug>/task.json + <slug>.mp4)。
---

# FD VAAS 视频分发器

一支视频 = 一次发布指令 → **多个平台 各自的偏好参数 各自的 sau 调用**。本 skill 存在的唯一价值是**把平台差异化配置外化**到 .env,再让 CLI 一行组装出对每个平台正确的 `sau upload-video`,而不是每支视频靠人肉抄 tag/tid/短标题。

## 核心边界

- **上传逻辑 = social-auto-upload**。cookie、登录、浏览器自动化、防风控 —— 100% 交给 `sau` 和 `social-auto-upload/skills/{douyin,kuaishou,xiaohongshu,bilibili}-upload/`。碰到"cookie 过期怎么办"、"要不要 headed"、"平台风控了" 之类的问题,读 social-auto-upload 的文档,别在本 skill 里加。
- **视频产出 = fd-vaas-video-creator**。本 skill 只读 `downloads/fd-videos/<slug>/task.json` 里的成片,不生成视频。要改视频、加封面、换字幕 —— 回 fd-vaas-video-creator。
- **本 skill 只做**:读 .env 合并偏好 → 按平台差异组装 sau 参数 → 逐平台 shell out → 把发布结果回写到 task.json 的 `distribution[]`。

## 输入

从对话里能提取就别问。

| 项 | 必填 | 说明 |
|---|---|---|
| `slug` | ✅ | task 目录名,如 `finddata-intro`。视频路径从 task.json 读。 |
| `title` | ✅ | 视频标题(每个平台通用) |
| `desc` | 用户可选 | 抖音/B站/视频号/快手/YouTube 用的正文 |
| `note` | 用户可选 | 小红书用的笔记正文(叫 `note` 不叫 `desc`);未给则退到 `desc` |
| 目标平台 | ❌ | CLI `--platforms`,不给用 .env 的 `PLATFORMS` |
| 标签 | ❌ | CLI `--tags`,不给用 .env 的 `TAGS` 或平台专属 `XXX_TAGS` |
| 定时 | ❌ | CLI `--schedule "YYYY-MM-DD HH:MM"`,不给立即发 |

标题、正文用户没给 → **问用户**,不要瞎编。发出去挂在自家账号上,内容质量不能猜。

## 首次配置(每人配一次)

配置在**项目根 `.env`**(和 TTS/seedream 共享一个),不在 skill 目录里。首次用:

```bash
cd /Users/chengsishi/VAAS
[ -f .env ] || cp .env.example .env
$EDITOR .env   # 改 PLATFORMS 和 XXX_ACCOUNT
```

关键项:
- `PLATFORMS`:逗号分隔,默认发到哪些平台。CLI `--platforms` 会覆盖。
- `<PLATFORM>_ACCOUNT`:必须和 `social-auto-upload/cookies/<platform>_uploader/` 里的 account_name 对上,否则 sau 找不到 cookie。
- `BILIBILI_TID`:B站必须传分区 id;不填 B站会失败。常见:36=科技·软件应用,124=科普,208=财经商业。
- `SCHEDULE`:全局默认定时,一般留空(立即发)。
- `HEADLESS`:抖音/视频号首次登录改 `false`,QR 才能扫;登进后可以改回 `true`。

**分层覆盖**:每支视频想微调偏好(比如这支想加特殊 tag),在该 task 目录里放一份 `downloads/fd-videos/<slug>/.publish.env`,同样格式,**只写要覆盖的项**。优先级:`--flag CLI > <task>/.publish.env > <VAAS>/.env > 内置默认`。

## 用法

```bash
SKILL=/Users/chengsishi/VAAS/.claude/skills/fd-vaas-publish/scripts

# 最简:发到 .env 里配的默认平台,标题必给
node $SKILL/publish.mjs --slug finddata-intro --title "让公开信息真正可被计算"

# 平台差异化正文
node $SKILL/publish.mjs --slug finddata-intro \
  --title "让公开信息真正可被计算" \
  --desc "..." \
  --note "..." \
  --platforms douyin,xiaohongshu,bilibili \
  --tags "开源,AI,数据,MCP" \
  --schedule "2026-07-20 21:30"

# 别真发,先看一眼命令(强烈推荐第一次跑先加这个)
node $SKILL/publish.mjs --slug finddata-intro --title "..." --dry-run
```

发完之后 `downloads/fd-videos/<slug>/task.json` 的 `distribution[]` 会自增一条,`history.md` 也会记账。查:`node .claude/skills/fd-vaas-video-creator/scripts/task-info.mjs --slug <slug>`。

## 平台差异化默认(为什么值得外化)

每个平台的 CLI 参数不一样,不是加个 `--platform` 就能通用。举例:

| 平台 | 正文字段 | 特殊必填 | 常踩的坑 |
|---|---|---|---|
| 抖音 | `--desc` | — | tag 别写 `#`,tag 数 ≤ 10 |
| 小红书 | `--note` | — | 标题短、笔记体、tag 放末尾 |
| B站 | `--desc` | `--tid <int>` | 忘了 tid 直接失败;desc 是必填(sau 层做的) |
| 视频号 | `--desc` | — | 短标题字段 `--short-title` ≤ 6 字;缩略图三种 aspect ratio |
| 快手 | `--desc` | — | 和抖音差不多,但账号 cookie 隔离 |
| YouTube | `--desc` | — | `--visibility public/unlisted/private`;需要 `YT_PROXY`;抽 GAPI 而非 API,登录靠浏览器 |

所以本 skill 从 `.env` 读 `BILIBILI_TID` `TENCENT_SHORT_TITLE` `YOUTUBE_VISIBILITY` `XIAOHONGSHU_TAGS` 之类**每个平台各一份**,然后组装 `sau` 时挑对应的参数塞进去。用户改 `.env` 一次,后面每支视频都对齐;不改就用你自己项目对齐的默认。

## 故障排查

- **`sau: command not found`**:去 `social-auto-upload/` 跑 `uv pip install -e .`,或者改用 `python sau_cli.py …` 直接调(把 .env 里 `SAU_PROJECT_DIR` 指对)。
- **`Cookie expired / login required`**:`cd social-auto-upload && sau <platform> login --account <name>` 重扫。这是 sau 的事,不是本 skill 的锅。
- **B站 `--tid` 必填报错**:在 `.env` 或 `.publish.env` 加 `BILIBILI_TID=xx`。
- **抖音首次登录 QR 不显示**:`.env` 里 `HEADLESS=false`,再跑一次 login。
- **小红书正文空**:检查是不是只传了 `--desc` 没传 `--note`,本 skill 会自动 fallback `desc→note`,但你想要笔记专属正文就用 `--note`。
- **想只 dry-run 看命令**:加 `--dry-run`,不真发。

## 参考

- `/Users/chengsishi/VAAS/.env.example` —— 项目根统一配置样板(含各字段说明)
- `references/platform-quirks.md` —— 各平台的坑详解(什么内容规格能过审、什么 tag 会拦、字数限制、首次登录路数)
- `scripts/publish.mjs` —— 主入口
- 上传本体:`social-auto-upload/CLAUDE.md` + `sau <platform> --help`

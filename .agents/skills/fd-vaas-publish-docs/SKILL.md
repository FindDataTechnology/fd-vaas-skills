---
name: fd-vaas-publish-docs
description: 把一篇文章/图文一键分发到主流图文平台(知乎、微信公众号、小红书、雪球、东方财富号、同花顺财经号、今日头条、百家号、微博)。**只做编排 -- 平台差异化文案/字数/标签/封面 + 内容适配 + 发布记录**。两条浏览器运行时:**默认 ego-browser**(由 references/<platform>.md heredoc 驱动,复用 Chrome 登录态);**`--runtime patchright`**(scripts/platforms/<p>.py,stealth Playwright,独立 profile,跨平台 macOS/Windows)。触发场景:用户说"把这篇文章发到知乎/公众号/雪球/东财/同花顺/小红书"、"多平台发图文"、"分发这篇文章"、"把这篇图文发出去"、"publish the article/doc"、"post this article to...",或者刚写好一篇 `downloads/fd-docs/<slug>/` 里的文章、要走下一步分发时。**发布前必须让用户确认**(发出去撤不回来);各平台浏览器选择器多为页面结构推断、未在登录态下实机验证,**首次发布前必须用 `references/probe.md` 或 `scripts/platforms/probe.py` 核对选择器再驱动**。不要用本 skill 做文档写作本身。
compatibility: Node.js 18+;ego-browser 已装(`which ego-browser`);目标平台在 ego-browser 继承的 Chrome 登录态里已登录(没登录走 references 里各平台的 handoff 扫码);文档已写好(`downloads/fd-docs/<slug>/article.md` + `meta.json`,或 CLI 直传 `--title --body`)。
---

# FD VAAS 文档分发器

一篇文章 = 一次发布指令 -> **多个平台 各自的字数/标签/封面偏好 各自的 ego-browser heredoc**。本 skill 存在的唯一价值是**把平台差异化配置外化**到 `.env` + **按平台适配内容**(标题截断、正文限长、标签限数、摘要生成)+ **记录发布结果**,而不是每篇文章靠人肉抄每个平台的编辑器路数。

## 发布路由

本 skill 不调用任何外部 CLI(sau / playwright_upload.py 都不用)。每个平台的浏览器自动化 heredoc 直接写在 `references/<platform>.md` 里,你(Claude)读出来用 `ego-browser nodejs` 跑。

| 平台 | references | 编辑器入口 | 登录态 | 选择器验证 |
|---|---|---|---|---|
| 知乎 zhihu | `references/zhihu.md` | `https://zhuanlan.zhihu.com/write` | ego-browser 继承 | ⚠️ 未实机验证,首次 probe |
| 微信公众号 weixin | `references/weixin.md` | `https://mp.weixin.qq.com/` → 新建图文 | ego-browser 继承(扫码) | ⚠️ 未实机验证,首次 probe |
| 小红书 xiaohongshu | `references/xiaohongshu.md` | `https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image` | ego-browser 继承 | ✅ 部分实机确认(复用 xiaohongshu-upload) |
| 雪球 xueqiu | `references/xueqiu.md` | `https://xueqiu.com/zhuanlan/publish` | ego-browser 继承 | ⚠️ 未实机验证,首次 probe |
| 东方财富号 eastmoney | `references/eastmoney.md` | `https://mp.eastmoney.com/collect/pc_article/index.html#/` | ego-browser 继承 | ⚠️ 未实机验证,首次 probe |
| 同花顺财经号 tonghuashun | `references/tonghuashun.md` | `https://media.10jqka.com.cn/`(媒体开放平台) | ego-browser 继承 | ⚠️ 未实机验证,首次 probe |
| 今日头条 toutiao | `references/toutiao.md` | `https://mp.toutiao.com/profile_v4/graphic/publish` | ego-browser 继承 | ⚠️ 未实机验证,首次 probe |
| 百家号 baijiahao | `references/baijiahao.md` | `https://baijiahao.baidu.com/builder/rc/edit` | ego-browser 继承 | ⚠️ 未实机验证,首次 probe |
| 微博 weibo | `references/weibo.md` | `https://weibo.com/newblog`(长文) | ego-browser 继承 | ⚠️ 未实机验证,首次 probe |

## 核心边界

- **浏览器自动化 = ego-browser**(本 skill 内)。登录、扫码、填表、上传封面、点发布 -- 100% 走 `references/<platform>.md` 里的 heredoc。碰到"选择器失效"、"页面改版"、"风控验证码" -- 先跑 `references/probe.md` 重新 snapshot 定位,再改 heredoc 里的选择器;别在本 skill 之外另造。
- **文档产出 = 用户 / fd-docs task dir**。本 skill 只读 `downloads/fd-docs/<slug>/article.md` 里的正文 + `meta.json` 里的标题/标签/封面,不写文章。要改文章回去改 `article.md`。
- **本 skill 只做**:读 .env 合并偏好 -> publish.mjs 按平台适配内容(写 `.adapted/<platform>/`) -> 你按 references 逐平台跑 heredoc -> 跑完用 publish.mjs `--record` 回写 `meta.json` 的 `distribution[]`。

## ⚠️ 硬性发布前流程(必须遵守)

**发文章不是拿到正文就点发布**,必须按以下顺序走完,用户确认后才能发:

```
文章已写完(article.md + meta.json)
    ↓
1. 拟定各平台文案(标题 + 正文 + 标签 + 摘要)
    ↓ publish.mjs --plan 出适配后内容;标题/摘要用户没给就问,别瞎编
2. 准备封面图
    - 公众号:必填,900×500(或 2.35:1)
    - 小红书:必填至少 1 张(图文笔记不能纯文字),竖图 3:4 最佳
    - 知乎/雪球/东财/同花顺:推荐,横图 16:9
    ↓ 用 fd-cover-image(Remotion)生成,不要 AI 生图(文字会乱码)
3. 输出「发布确认清单」给用户
    - 各平台适配后标题、正文(字数)、标签、封面
    - 各平台发布时间(立即 / 定时 / 存草稿)
    ↓ 用户明确说「确认发布」
4. 逐个平台跑 heredoc 发布(串行,别并发同账号)
    ↓ 每发完一个 publish.mjs --record 回写
5. 发布完成汇总
```

**违反此流程直接发出去 = 事故**。文案封面没确认就发,发出去撤不回来。

## 输入

从对话里能提取就别问。

| 项 | 必填 | 说明 |
|---|---|---|
| `slug` | ✅(或直传 title+body) | task 目录名,如 `finddata-open-data`。正文从 `downloads/fd-docs/<slug>/article.md` 读,元数据从 `meta.json` 读。 |
| `title` | ✅ | 文章标题(各平台通用,publish.mjs 按平台字数自动截) |
| `body` | ✅ | 正文,Markdown。从 `article.md` 读或 `--body` 直传 |
| `tags` | ❌ | CLI `--tags`,不给用 .env `DOC_TAGS` 或平台专属 `XXX_DOC_TAGS` |
| `cover` | ❌ | 封面图绝对路径。不给用 `meta.json` 的 `cover` |
| `summary` | ❌ | 摘要(公众号必填);不给 publish.mjs 从正文前 N 字生成 |
| 目标平台 | ❌ | CLI `--platforms`,不给用 .env `PLATFORMS_DOCS` |
| 定时 | ❌ | CLI `--schedule "YYYY-MM-DD HH:MM"`,不给立即发(公众号默认存草稿) |

标题、正文用户没给 -> **问用户**,不要瞎编。发出去挂在自家账号上,内容质量不能猜。

`downloads/fd-docs/<slug>/` 结构:

```
downloads/fd-docs/<slug>/
  article.md        # 正文 Markdown
  meta.json         # { "title", "tags": [...], "cover", "summary", "platforms": [...] }
  cover.jpg         # 可选,meta.json 的 cover 也可指向别处
  .publish.env      # 可选,只写要覆盖 .env 的项
```

## 首次配置(每人配一次)

配置在**项目根 `.env`**(和 TTS/seedream/fd-vaas-publish 共享一个),不在 skill 目录里。首次用:

```bash
export VAAS=<VAAS 仓库根目录,如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代
cd $VAAS
[ -f .env ] || cp .env.example .env
$EDITOR .env   # 改 PLATFORMS_DOCS 和各平台 XXX_DOC_TAGS
```

关键项:
- `PLATFORMS_DOCS`:逗号分隔,默认发到哪些图文平台。CLI `--platforms` 覆盖。可选:`zhihu,weixin,xiaohongshu,xueqiu,eastmoney,tonghuashun,toutiao,baijiahao,weibo`
- **登录**:ego-browser 直接继承用户 Chrome 的登录态,**没有 cookie 文件、没有 account**。每个平台登一次(在自己的 Chrome 里登进对应创作者后台),后续 ego-browser 复用。没登录时 references 里各平台的 heredoc 会检测到登录页 -> `handOffTaskSpace` 交还给你扫码。
- `DOC_SCHEDULE`:全局默认定时,一般留空(立即发)。
- `DOC_HEADLESS`:`true`(默认)无头;首次登录或调试改 `false`。

**分层覆盖**:每篇文章想微调偏好(比如这篇想加特殊 tag),在该 task 目录放 `downloads/fd-docs/<slug>/.publish.env`,同格式,**只写要覆盖的项**。优先级:`--flag CLI > <task>/.publish.env > <VAAS>/.env > 内置默认`。

## 用法

### 第一步:出适配后的发布计划(必跑)

```bash
SKILL=$VAAS/.agents/skills/fd-vaas-publish-docs/scripts

# 读 task dir,出每个平台适配后的标题/正文/标签/封面 + 要 export 的环境变量
node $SKILL/publish.mjs --slug finddata-open-data --plan

# 直传内容(不走 task dir)
node $SKILL/publish.mjs --title "让公开信息真正可被计算" \
  --body "$(cat article.md)" --tags "开源,AI,数据" \
  --platforms zhihu,weixin,xiaohongshu --plan

# 别真发,先看一眼每个平台适配后是什么(强烈推荐第一次先加 --dry-run)
node $SKILL/publish.mjs --slug finddata-open-data --dry-run
```

publish.mjs `--plan` 会:
1. 读 `article.md` + `meta.json` + `.env` + `.publish.env`,合并偏好
2. 按平台适配:标题截断(知乎 100 / 公众号 64 / 小红书 20 / 雪球 50 / 东财 30 / 同花顺 30 字)、正文限长、标签限数、摘要生成
3. 把适配后的内容写到 `downloads/fd-docs/<slug>/.adapted/<platform>/{title.txt,body.md,tags.txt,cover.txt}`
4. 打印每个平台的发布计划 + 一段 `export DOC_TITLE=... DOC_BODY=... DOC_TAGS=... DOC_COVER=...`(给第二步 heredoc 用)

`--dry-run` 只打印计划、不写 `.adapted/`、不真发。

### 第二步:逐平台跑 heredoc 发布

对每个目标平台:先 `references/probe.md` 核选择器(首次必做),再读 `references/<platform>.md`,把第一步打印的 `export` 行跑一遍,然后跑该平台的 heredoc。heredoc 里正文/标题/标签/封面全从环境变量 `DOC_TITLE` `DOC_BODY` `DOC_TAGS` `DOC_COVER` 读,不在 heredoc 里硬编码(避免长正文转义炸):

```bash
# 例:发知乎(完整 heredoc 见 references/zhihu.md)
export DOC_TITLE="$(cat .adapted/zhihu/title.txt)" \
       DOC_BODY="$(cat .adapted/zhihu/body.md)" \
       DOC_TAGS="$(cat .adapted/zhihu/tags.txt)" \
       DOC_COVER="$(cat .adapted/zhihu/cover.txt)"
ego-browser nodejs <<'EOF'
const TITLE = process.env.DOC_TITLE
const BODY  = process.env.DOC_BODY
const TAGS  = (process.env.DOC_TAGS || '').split(',').map(s=>s.trim()).filter(Boolean)
const COVER = process.env.DOC_COVER || ''
// … 见 references/zhihu.md:open 编辑器 -> 填标题 -> 粘贴正文 -> 上传封面 -> 话题 -> 发布
EOF
```

**发布前让用户确认**适配后内容;**一个平台一个 task space**(命名 `docs-publish-<slug>-<platform>`),串行别并发同账号。

### 第三步:记录发布结果

每发完一个平台确认成功后,回写一条:

```bash
node $SKILL/publish.mjs --slug finddata-open-data --record --platforms zhihu,weixin --title "..."
```

会 append 到 `meta.json` 的 `distribution[]` + `history.md`。

## patchright 运行时(`--runtime patchright`)

默认 `--runtime ego`:本 skill 只 plan/record,浏览器自动化由你按 `references/<platform>.md` 的 heredoc 用 ego-browser 手跑(复用 Chrome 登录态)。

`--runtime patchright`:plan 写 `.adapted/<p>/` 后,`publish.mjs` 逐平台 `spawnSync('python3', ['platforms/<p>.py', ...])`,用 **patchright(stealth Playwright)** 自动开浏览器、登录、填表、传封面、点发布。跨平台(macOS/Windows 都行),是 ego-browser 没有 Windows 版时的替代链路,也可在本机 macOS 直接跑。

```bash
# 单平台发布(推荐先单平台打通)
node $SKILL/publish.mjs --slug <name> --runtime patchright --platforms zhihu

# 多平台串行(同账号别并发)
node $SKILL/publish.mjs --slug <name> --runtime patchright --platforms zhihu,weixin,xiaohongshu

# 调试:--headless=false(默认就 headed,首次登录要看);--auto-publish 跳过确认门(慎用)
```

**文件**:
- `scripts/platforms/lib/browser_utils.py` -- patchright sync API 封装(Browser 持久 context、login_or_wait 轮询登录、paste_text 剪贴板灌正文、confirm_gate 发布前确认门、publish_and_verify)
- `scripts/platforms/<platform>.py` × 9 -- 每平台发文流程,CLI 统一:`--title --body-file --tags --cover --summary --dry-run --auto-publish --headless --markdown --confirm-file --preview`
- `scripts/platforms/probe.py` -- 选择器核对(打开编辑器 dump 可交互元素 + file input + iframe),8 个未验证平台首次必跑
- `scripts/platforms/requirements.txt` -- `patchright`

**登录态**:patchright 用**独立持久 profile** `VAAS/.profiles/<platform>/`,**不复用 Chrome 登录态**(和 ego-browser 的关键差异)。每平台首次发布要在 patchright 浏览器窗口里扫码/登录一次,profile 存下来后续复用。`login_or_wait` 轮询 URL 检测登录完成(无 stdin 依赖)。

**发布确认门(非交互)**:`.py` 默认半自动 -- 填完一切 + 截图存 `.adapted/<p>/preview.png` + 等 sentinel 文件 `/tmp/vaas-doc-<platform>.go` 出现才点发布。Claude 在后台跑脚本,看到「等待确认」后问你,你说「确认发布」-> Claude `touch /tmp/vaas-doc-<p>.go` 放行。`--auto-publish` 跳过此门(仅你明确要求时加,对应「违反流程直接发=事故」)。

**正文灌入**:`paste_text` 优先剪贴板粘贴(瞬时、保留换行;知乎专栏还能渲染 markdown -> `--markdown` 走 `body.md`,其余平台走 `body.txt` = mdToPlain 去符号但**保留代码块**),失败回退 `execCommand('insertText')` -> 逐行 `typeText`。

**选择器验证状态**(见各 `references/<platform>.md` 底部):
- ✅ 已验证:zhihu、xiaohongshu、toutiao、baijiahao、weibo(2026-07-29/30)、eastmoney(部分,需财经号)
- ⚠️ 待 probe:weixin、xueqiu、tonghuashun -- 首次发布前**必须**跑 `probe.py <platform>` 核对选择器再改 `.py`

**安装**:
```bash
pip install -r scripts/platforms/requirements.txt
patchright install chromium   # macOS 走 https_proxy=http://127.0.0.1:7892(见 memory)
```

## 平台差异化默认(为什么值得外化)

每个平台编辑器参数不一样,不是加个 `--platform` 就能通用。publish.mjs 按平台挑对应限制:

| 平台 | 正文形态 | 标题字数 | 正文上限 | 标签 | 封面 | 特殊坑 |
|---|---|---|---|---|---|---|
| 知乎 | 专栏长文(富文本,可粘 markdown) | ~100 | ~50000 | 话题 5 个 | 可选,横 16:9 | 标题别超 100;正文支持 markdown 粘贴渲染 |
| 公众号 | 图文(富文本 ueditor) | 64 | 20000 | 无标签,用合集 | **必填** 900×500 | **摘要必填**;默认存草稿不群发;原创声明可选 |
| 小红书 | 图文笔记(纯文字不行) | **20** | 1000 | 话题 **≤10** | **必填** ≥1 张,竖 3:4 | 笔记体短段;话题放末尾;复用 xiaohongshu-upload 选择器 |
| 雪球 | 长文(富文本) | ~50 | 无硬限 | 股票 `$代码` + 话题 | 可选 | 长文入口在个人页「写长文」;可关联股票 |
| 东方财富号 | 文章(富文本) | ~30 | 无硬限 | 标签 | 可选 | 走 oa.eastmoney.com 创作者后台;需财经号资质 |
| 同花顺财经号 | 文章(富文本) | ~30 | 无硬限 | 标签 | 可选 | 走 media.10jqka.com.cn 媒体开放平台;需财经号资质 |
| 今日头条 | 文章(富文本) | ~30 | 无硬限 | 话题 | 可选 | 走 mp.toutiao.com 头条号;标题控制在 30 字内 |
| 百家号 | 文章(富文本) | ~40 | 无硬限 | 关键词 | **必填** | 走 baijiahao.baidu.com;封面必填;需选分类 |
| 微博 | 长文(头条文章) | ~140 | 10000 | `#话题#` | 可选 | 分长文/newblog 和短微博;标签以 #话题# 形式放正文 |

所以本 skill 从 `.env` 读 `ZHIHU_DOC_TAGS` `WEIXIN_DOC_TAGS` `XIAOHONGSHU_DOC_TAGS` `XUEQIU_DOC_TAGS` `EASTMONEY_DOC_TAGS` `TONGHUASHUN_DOC_TAGS` 之类**每个平台各一份**(用 `_DOC_TAGS` 后缀,和视频 skill `fd-vaas-publish` 的 `*_TAGS` 区分,共用一个 `.env` 不撞车),适配时挑对应限制塞。用户改 `.env` 一次,后面每篇文章都对齐。

## 故障排查

- **选择器点不动 / 填不进去**:平台前端改版了。先跑 `references/probe.md` 的 `snapshotText()` 重新 dump 编辑器结构,定位新选择器,改 `references/<platform>.md` 里的 heredoc。别死依赖固定 class。
- **跳到登录页**:ego-browser 继承的登录态没登录或过期。跑该平台 references 里的「登录 handoff」heredoc,`handOffTaskSpace` 交还用户扫码,扫完 `takeOverTaskSpace` 收回。
- **公众号发布按钮灰**:摘要没填、封面没传、或正文空。检查 `.adapted/weixin/` 里 cover 和 summary。
- **小红书发不出**:图文笔记**必须至少 1 张图**;话题超 10 个会卡;标题超 20 字截断。
- **东方财富号 / 同花顺进不了后台**:这俩需要先申请财经号/媒体号资质,没开通的话后台没有发文入口。先去对应平台开通。
- **正文太长被平台截**:publish.mjs 已按各平台上限截,但雪球/东财/同花顺无硬上限,超长可能审核慢。
- **想只看计划不真发**:加 `--dry-run`。

## 参考

- `$VAAS/.env.example` -- 项目根统一配置样板(含 `fd-vaas-publish-docs` 段)
- `references/platform-quirks.md` -- 各图文平台内容规格坑(字数/图片/标签/原创/排版/风控)
- `references/probe.md` -- 选择器核对流程(snapshotText dump + 定位),首次发布前必跑
- `references/{zhihu,weixin,xiaohongshu,xueqiu,eastmoney,tonghuashun}.md` -- 各平台登录 + 发文 heredoc 骨架
- `scripts/publish.mjs` -- 主入口(`--plan` 出适配内容 / `--dry-run` / `--record` 回写)
- **fd-cover-image skill** -- 封面生成(Remotion 方案,优先用)
- **xiaohongshu-upload skill** -- 小红书图文选择器来源(`.claude/skills/xiaohongshu-upload/references/`)

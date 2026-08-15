---
name: fd-vaas-publish-videos
description: >
  把 fd-vaas-video-creator 出的口播视频一键发到多个社交平台。**编排 + 上传一体化**：
  平台差异化偏好、标签、定时由 publish.mjs 编排；上传逻辑走「vendor + 薄适配层」——
  把 social-auto-upload 上游整个 vendor 进 scripts/upstream/，薄适配层 sau_adapter.py 把
  CLI 翻译成上游 <Platform>Video(...).main() 调用。统一 py 运行时（patchright）。
  支持抖音/小红书/B站/快手/视频号/YouTube 六平台。触发场景：用户说"把这支视频发到
  抖音/小红书/B站/视频号/YouTube/快手"、"多平台一起发"、"分发这条视频"、"push to socials"、
  "posting the video"，或者刚做完一支 fd-videos/<slug>/ 里的视频、要走下一步分发时。
  **必须**用本 skill 的 publish.mjs，不要直接手写各平台参数。
compatibility: py 运行时=Python 3.10+ + patchright(`pip install patchright` + `patchright install chromium`)，
  各平台 cookie 已登录(cookies/<platform>_uploader/account.json)；fd-vaas-video-creator 已跑完
  (存在 downloads/fd-videos/<slug>/task.json + <slug>.mp4)。
---

# FD VAAS 视频分发器

一支视频 = 一次发布指令 -> **多个平台 各自的偏好参数**。本 skill 把平台差异化配置外化到 `.env`，
`publish.mjs` 一行组装出对每个平台正确的上传命令。上传逻辑走「vendor + 薄适配层」：
social-auto-upload 上游整个 vendor 进 `scripts/upstream/`，薄适配层 `sau_adapter.py` 把 CLI 翻译成
上游 `<Platform>Video(...).main()` 调用。bilibili 上游用 biliup 二进制而非 Playwright，走本地 `bilibili.py`。

## 架构：vendor + 薄适配层

```
publish.mjs (编排: 封面/标签/定时/路由)
    │
    ├── sau_adapter.py → vendored upstream (social-auto-upload, patchright)
    │     xiaohongshu / douyin / kuaishou / weixin / youtube → upstream Playwright
    │     登录态: cookies/<platform>_uploader/account.json (storage_state)
    │
    └── bilibili.py（上游用 biliup 二进制，非 Playwright，独立实现）
```

**为什么 vendor 上游**：我们手写的 `.py` 退出 0 但实际没发布成功——漏 `set_thumbnail` 封面步骤、
无原创声明、无 success-page 校验。上游是久经实战的实现，vendor 后小红书实发验证通过
（上游 `wait_for_url("**/publish/success?**")` 命中 success 页才报「视频发布成功」）。
vendor 让我们免费获得上游的 bugfix，`sync-upstream.sh` 一键同步。

## 支持平台

> 平台**路由**(sau_adapter→upstream / bilibili.py 自有)+ **选择器验证状态**的单一可机读源是
> `.agents/skills/_shared/publish/platform-registry.json`(图文+视频共用)。下表从它渲染。

| 平台 | 上传路径 | 核心技术挑战 |
|---|---|---|
| 抖音 (douyin) | sau_adapter → upstream | 标准 DOM，无特殊框架 |
| 小红书 (xiaohongshu) | sau_adapter → upstream ✓已实发 | 标题 ≤ 20 字；话题 ≤ 10 |
| B站 (bilibili) | bilibili.py（上游用 biliup） | **micro-app shadow DOM** |
| 快手 (kuaishou) | sau_adapter → upstream | **React Joyride 遮罩** + 视口外按钮；话题 ≤ **4** |
| 视频号 (weixin) | sau_adapter → upstream | **Wujie shadow DOM** |
| YouTube | sau_adapter → upstream（需代理） | **Polymer dialog** 4 步流程；"Not made for kids" 必答 |

> py 运行时上传逻辑在 `scripts/upstream/uploader/<platform>_uploader/main.py`，是上游 canonical 代码，不要手改。
> 平台核心挑战（shadow DOM 结构、字数限制等运行时无关的事实）见 `references/<platform>.md`。

## ⚠️ 硬性发布前流程（必须遵守）

**发布视频不是拿到视频就点上传**，必须按以下顺序走完前置准备，用户确认后才能发：

```
视频已渲染完成
    ↓
1. 拟定发布文案（标题 + 描述/笔记 + 各平台标签）
    ↓ 用 .env 预设 + 本次内容生成差异化文案
2. 生成各平台封面（**publish.mjs 自动生成**，无需手动跑）
    - 抖音：横封面 1920×1080 + 竖封面 1080×1440
    - 小红书：竖封面 1080×1440
    - B站：横封面 1920×1080
    - YouTube：横封面 1280×720
    - 视频号：1080×1260
    ↓ 用 Remotion BrandCover 模板生成，公司风格统一，无 AI 文字乱码
    ↓ 先预览确认可跑 `--cover-only` 单生成封面；加 `--no-cover` 跳过
3. 输出「发布确认清单」给用户
    - 各平台标题、描述、标签
    - 各平台封面预览图
    - 发布时间（立即 / 定时）
    ↓ 用户确认（必须明确说「确认发布」）
4. 逐个平台上传发布
    ↓ 每发完一个回写 task.json distribution[]
5. 发布完成汇总
    ↓
6. 清理（见下「发布后清理」）
```

**违反此流程直接发出去 = 事故**。封面文案都没确认就发，发出去撤不回来。

## 用法

### 一键多平台发布（推荐）

```bash
export VAAS=<VAAS 仓库根目录,如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代
SKILL=$VAAS/.agents/skills/fd-vaas-publish-videos/scripts

# 最简：发到 .env 里配的默认平台
node $SKILL/publish.mjs --slug finddata-brand-2026 --title "寻数科技｜探索更开放更公平的AI未来"

# 指定平台 + 标签 + 描述
node $SKILL/publish.mjs --slug finddata-brand-2026 \
  --title "寻数科技｜探索更开放更公平的AI未来" \
  --desc "让数据驱动决策" \
  --platforms douyin,xiaohongshu,bilibili,kuaishou,weixin,youtube \
  --tags "科技,开源,AI,数据,程序员"

# 定时发布（除 youtube 外都支持；bilibili.py 不支持定时）
node $SKILL/publish.mjs --slug finddata-brand-2026 \
  --title "..." --schedule "2026-07-20 21:30"

# 别真发，先看一眼每个平台会跑的命令
node $SKILL/publish.mjs --slug finddata-brand-2026 --title "..." --dry-run
```

### 单平台调试（直接调适配层）

```bash
ADAPTER=$VAAS/.agents/skills/fd-vaas-publish-videos/scripts/platforms/sau_adapter.py

# 发一条（走 vendored upstream）
python3 $ADAPTER --platform xiaohongshu --file video.mp4 --title "标题≤20字"

# 登录（扫码）
python3 $ADAPTER --platform douyin --login

# 检查 cookie 是否有效
python3 $ADAPTER --platform xiaohongshu --login-check

# 从旧 .profiles/ 迁移登录态到 cookies/（一次性）
python3 $ADAPTER --platform weixin --migrate-profile
```

### publish.mjs 参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `--slug` | ✅ | task 目录名，如 `finddata-brand-2026`。视频路径从 task.json 读。 |
| `--title` | ✅ | 视频标题（每个平台通用） |
| `--desc` | ❌ | 抖音/B站/视频号/快手/YouTube 用的正文 |
| `--note` | ❌ | 小红书用的笔记正文；未给则退到 `desc` |
| `--platforms` | ❌ | 逗号分隔平台列表，不给用 .env 的 `PLATFORMS` |
| `--tags` | ❌ | 逗号分隔标签，不给用 .env 的 `TAGS` 或平台专属 `XXX_TAGS` |
| `--schedule` | ❌ | `YYYY-MM-DD HH:MM`，不给立即发 |
| `--dry-run` | ❌ | 只打印命令不执行 |
| `--no-cover` | ❌ | 跳过封面生成与上传，用平台默认封面 |
| `--cover-only` | ❌ | 只跑封面生成（4 张 + 回写 task.json），不执行发布（给预览确认用） |

> `--runtime` 仍接受 `py`/`auto`（=py，默认）；旧脚本里写 `--runtime py` 不用改。传 `mjs` 会报错退出。

## 平台差异化参数路由

publish.mjs 按平台差异组装不同的 CLI 参数：

| 平台 | 封面参数 | 标签字段 | 特殊参数 | 标签上限 |
|---|---|---|---|---|
| 抖音 | `--cover-horizontal` + `--cover-vertical`（**自动传两张**） | `--tags` | `--schedule` | 10 |
| 小红书 | `--cover` | `--tags` | 标题 ≤ 20 字 | 10 |
| B站 | `--cover` | `--tags` | `--tid` (分区) | - |
| 快手 | `--cover` | `--tags` | - | **4**（不是5！） |
| 视频号 | `--cover` | (描述内 #话题) | 无单独标题字段 | - |
| YouTube | `--thumbnail` | `--tags` | `--visibility` | - |

## 登录态管理

vendored upstream 用 patchright 的 `storage_state=` 加载登录态，存为 cookie JSON 文件：

```
scripts/upstream/cookies/<platform>_uploader/account.json    # xiaohongshu/douyin/kuaishou/weixin/youtube
scripts/upstream/cookies/kuaishou_creator.json                # kuaishou 单独命名
```

这些是**运行态登录态，gitignored，永不提交**。首次登录或失效后重新登录：

```bash
ADAPTER=$VAAS/.agents/skills/fd-vaas-publish-videos/scripts/platforms/sau_adapter.py

# 1. 扫码登录（弹 headed 浏览器，切扫码 tab，等用户扫）
python3 $ADAPTER --platform xiaohongshu --login

# 2. 检查 cookie 是否还有效（不弹浏览器则有效）
python3 $ADAPTER --platform xiaohongshu --login-check

# 3. 从旧 .profiles/<platform>/ 迁移到 cookies/（已有持久 profile 时一次性迁移）
python3 $ADAPTER --platform weixin --migrate-profile
```

登录流程（硬性 3 步，上游实现）：
1. **自动切到扫码登录** — 登录页找「扫码登录」按钮/tab 自动点击
2. **明确提示用户** — 告诉用户切到弹出的 patchright 窗口扫码
3. **自动轮询检测** — 每 3 秒检查登录状态，检测到成功自动继续，超时 120 秒提醒

cookie 过期了重跑 `--login` 即可。

## 同步上游：sync-upstream.sh

`scripts/sync-upstream.sh` 是「快速和开源项目同步」机制：

```bash
cd $VAAS/.agents/skills/fd-vaas-publish-videos/scripts

./sync-upstream.sh              # 同步到上游最新 main
./sync-upstream.sh <sha>        # 同步到指定 commit
./sync-upstream.sh --check      # 只看 diff + SHA 对比，不写文件
./sync-upstream.sh --remote <url>  # 用 fork（默认 dreammis/social-auto-upload）
```

机制：clone 上游 → `rsync -a --delete` uploader/+utils/ → `scripts/upstream/`（`--delete` 让 vendor
与上游完全一致）→ 记录 SHA 到 `.upstream-version`。`conf.py` 是本地覆盖（headed/proxy 等），
sync 不覆盖已有 conf.py，只在首次缺失时 bootstrap。

规则：
- `scripts/upstream/uploader|utils` 里的文件是 canonical 上游代码，**不要手改**——手改会被下次 sync 冲掉
- 本地适配全在 `sau_adapter.py` / `conf.py` / `--migrate-profile` 里
- `cookies/` 与 `logs/` 是运行态，gitignored，不会被 rsync 覆盖

## 发布后清理

py 运行时走 patchright，**没有 ego 任务窗口要关**。上游脚本跑完 `wait_for_url("**/publish/success?**")`
命中 success 页后自行结束，浏览器窗口由 patchright 生命周期管理，脚本退出即关。
- 自动发布平台（xiaohongshu/kuaishou/weixin/youtube）：脚本跑完即结束，无需兜底
- douyin：上游也是自动发布

## 首次配置

```bash
cd $VAAS
[ -f .env ] || cp .env.example .env
$EDITOR .env   # 改 PLATFORMS 和各平台 XXX_TAGS

# py 运行时依赖（一次性）
pip install patchright
patchright install chromium

# 各平台扫码登录（headed 浏览器）
SKILL=$VAAS/.agents/skills/fd-vaas-publish-videos/scripts
python3 $SKILL/platforms/sau_adapter.py --platform xiaohongshu --login
python3 $SKILL/platforms/sau_adapter.py --platform douyin --login
# ... 其余平台同理；youtube 需代理：export VAAS_YT_PROXY=http://127.0.0.1:7892
```

关键 .env 项：
- `PLATFORMS`：逗号分隔，默认发到哪些平台
- `TAGS`：全局默认标签；`DOUYIN_TAGS` / `BILIBILI_TAGS` 等平台专属覆盖
- `SCHEDULE`：全局默认定时，一般留空（立即发）

**分层覆盖**：每支视频想微调，在该 task 目录放 `downloads/fd-videos/<slug>/.publish.env`。
优先级：`--flag CLI > <task>/.publish.env > <VAAS>/.env > 内置默认`。

## 各平台核心挑战

> 以下平台事实（shadow DOM 结构、字数限制等）运行时无关，调试 vendored upstream 时可参考。
> 实际上传逻辑见 `scripts/upstream/uploader/<platform>_uploader/main.py`（canonical，不要手改）。

### 抖音 (douyin) — 标准 DOM，最简单
- 无特殊框架，标准 `document.querySelector`
- 描述输入框是 `contenteditable`
- 封面：横版 + 竖版
- 详见 `references/douyin.md`

### 快手 (kuaishou) — React Joyride + 视口外按钮
- **React Joyride 遮罩**：首次出现全屏遮罩拦截点击，必须先移除 `[class*="react-joyride"]`
- **发布按钮在视口外**：需 `scrollIntoView({ block: 'center' })`
- **话题标签 ≤ 4 个**（不是5！）
- 详见 `references/kuaishou.md`

### B站 (bilibili) — micro-app shadow DOM
- **micro-app 微前端**：所有内容在 `micro-app[name=video-up].shadowRoot` 内
- 需选择分区（`--tid`），否则无法发布
- 走 `bilibili.py`（上游用 biliup 二进制，不在适配层）
- 详见 `references/bilibili.md`

### 小红书 (xiaohongshu) — 标题字数限制
- **标题 ≤ 20 字**（硬限制）；**话题 ≤ 10 个**
- 发布验证：URL 含 `/publish/success?`（上游 `wait_for_url` 命中才报成功）
- 详见 `references/xiaohongshu.md`

### 视频号 (weixin) — Wujie shadow DOM，最复杂
- **Wujie 微前端**：所有内容在 `wujie-app.shadowRoot` 内
- 详见 `references/weixin.md`

### YouTube — Polymer Web Components
- **Polymer dialog**：`tp-yt-paper-dialog` 需强制 `opened=true`
- **4 步对话框**：Details -> Video elements -> Checks -> Visibility
- **"Not made for kids" 必答**
- 需代理：`export VAAS_YT_PROXY=http://127.0.0.1:7892`
- 详见 `references/youtube.md`

## 故障排查

| 问题 | 解决方案 |
|---|---|
| 某平台上传失败 | 读 `scripts/upstream/uploader/<platform>_uploader/main.py` 看上游逻辑；先 `--login-check` 确认 cookie 有效 |
| cookie 失效 | `python3 sau_adapter.py --platform <p> --login` 重新扫码 |
| 从旧 .profiles 迁移 | `python3 sau_adapter.py --platform <p> --migrate-profile` |
| 想同步上游最新代码 | `./sync-upstream.sh`（或 `--check` 只看 diff） |
| bilibili 上传 | 走 `bilibili.py`，上游用 biliup 二进制不在适配层 |
| youtube 需代理 | `export VAAS_YT_PROXY=http://127.0.0.1:7892` |
| shadow DOM 找不到元素 | B站 `micro-app[name=video-up].shadowRoot`，视频号 `wujie-app.shadowRoot` |
| 快手话题报错 | 话题 ≤ 4 个，超过需刷新 |
| YouTube Next 按钮灰色 | 必选 "Not made for kids" + 等 Checks 步骤完成 |
| 想只看命令不真发 | 加 `--dry-run` |
| Windows: `command not found: python` | .env 设 `PYTHON=py` 或 `PYTHON=python3` |
| Windows: patchright 报找不到 chromium | 跑 `patchright install chromium` |

## 参考

- `scripts/publish.mjs` — 主入口（编排 + 路由到各平台脚本）
- `scripts/platforms/sau_adapter.py` — 薄适配层（CLI→上游 `<Platform>Video.main()`；`--login`/`--login-check`/`--migrate-profile`）
- `scripts/sync-upstream.sh` — 上游同步机制（clone+rsync--delete+记 SHA；`--check`/`--remote`/`<sha>`）
- `scripts/upstream/` — vendored social-auto-upload（uploader/+utils/+conf.py+conf.example.py）
  - `uploader/<platform>_uploader/main.py` — 各平台上传 canonical 代码（**不要手改**）
  - `utils/` — stealth.min.js 等共享工具
  - `conf.py` — VAAS 本地 conf 覆盖（headed/proxy；sync 不覆盖）
  - `cookies/<platform>_uploader/account.json` — 运行态登录态（gitignored）
- `scripts/platforms/bilibili.py` — bilibili 上传（上游用 biliup 二进制，独立实现）
- `.agents/skills/_shared/publish/browser_utils.py` — bilibili.py 用的 patchright 共享工具（图文/视频共用单一实现）
- `.agents/skills/_shared/publish/platform-registry.json` — 平台路由 + 选择器验证状态单一可机读源（图文/视频共用）
- `references/<platform>.md` — 各平台核心挑战档案（shadow DOM 结构、字数限制等运行时无关事实）
- **fd-cover-image skill** — 封面生成（Remotion 方案，优先用）
- **fd-vaas-video-creator skill** — 视频产出（本 skill 只读成片，不生成视频）

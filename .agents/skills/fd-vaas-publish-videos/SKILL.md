---
name: fd-vaas-publish-videos
description: >
  把 fd-vaas-video-creator 出的口播视频一键发到多个社交平台。**编排 + 上传一体化**：
  平台差异化偏好、标签、定时由 publish.mjs 编排；上传逻辑走「vendor + 薄适配层」——
  把 social-auto-upload 上游整个 vendor 进 scripts/upstream/，薄适配层 sau_adapter.py 把
  CLI 翻译成上游 <Platform>Video(...).main() 调用。支持抖音/小红书/B站/快手/视频号/YouTube 六平台。
  两种运行时：`--runtime py`（推荐，走 vendored upstream + patchright，已验证小红书实发）；
  `--runtime mjs`（legacy，ego-browser，Phase 3 淘汰）。bilibili 上游走 biliup
  二进制而非 Playwright，py 运行时仍走本地 bilibili.py。触发场景：用户说"把这支视频发到
  抖音/小红书/B站/视频号/YouTube/快手"、"多平台一起发"、"分发这条视频"、"push to socials"、
  "posting the video"，或者刚做完一支 fd-videos/<slug>/ 里的视频、要走下一步分发时。
  **必须**用本 skill 的 publish.mjs，不要直接手写各平台参数。
compatibility: 推荐 py 运行时=Python 3.10+ + patchright(`pip install patchright` + `patchright install chromium`)，
  各平台 cookie 已登录(cookies/<platform>_uploader/account.json)；fd-vaas-video-creator 已跑完
  (存在 downloads/fd-videos/<slug>/task.json + <slug>.mp4)。macOS 也可用 legacy mjs 运行时
  (Node.js 18+ + ego-browser)。**默认 auto = py**（vendored upstream）；`--runtime mjs` 是 legacy
  逃生口（ego-browser，Phase 3 删除）；`--runtime py` 显式走 vendored upstream。
---

# FD VAAS 视频分发器

一支视频 = 一次发布指令 -> **多个平台 各自的偏好参数**。本 skill 把平台差异化配置外化到 `.env`，
`publish.mjs` 一行组装出对每个平台正确的上传命令。上传逻辑走「vendor + 薄适配层」：
social-auto-upload 上游整个 vendor 进 `scripts/upstream/`，薄适配层 `sau_adapter.py` 把 CLI 翻译成
上游 `<Platform>Video(...).main()` 调用。bilibili 上游用 biliup 二进制而非 Playwright，仍走本地 `bilibili.py`。

## 架构：vendor + 薄适配层

```
publish.mjs (编排: 封面/标签/定时/路由)
    │
    ├── --runtime py（推荐）→ sau_adapter.py → vendored upstream
    │     ├── xiaohongshu/douyin/kuaishou/weixin/youtube → upstream Playwright (patchright)
    │     │     登录态: cookies/<platform>_uploader/account.json (storage_state)
    │     └── bilibili → bilibili.py（上游用 biliup 二进制，不在适配层）
    │
    └── --runtime mjs（legacy 逃生口）→ <platform>.mjs (ego-browser，Phase 3 删除)
          登录态: ego-browser 继承用户 Chrome
```

**为什么 vendor 上游**：我们手写的 `.py` 退出 0 但实际没发布成功——漏 `set_thumbnail` 封面步骤、
无原创声明、无 success-page 校验。上游是久经实战的实现，vendor 后小红书实发验证通过
（上游 `wait_for_url("**/publish/success?**")` 命中 success 页才报「视频发布成功」）。
vendor 让我们免费获得上游的 bugfix，sync-upstream.sh 一键同步。

## 支持平台

| 平台 | py 运行时（推荐） | mjs 运行时（legacy） | 核心技术挑战 |
|---|---|---|---|
| 抖音 (douyin) | sau_adapter → upstream | douyin.mjs (ego-browser) | 标准 DOM，无特殊框架 |
| 小红书 (xiaohongshu) | sau_adapter → upstream ✓已实发 | xiaohongshu.mjs | 标题 ≤ 20 字；话题 ≤ 10 |
| B站 (bilibili) | bilibili.py（上游用 biliup） | bilibili.mjs | **micro-app shadow DOM** |
| 快手 (kuaishou) | sau_adapter → upstream | kuaishou.mjs | **React Joyride 遮罩** + 视口外按钮 |
| 视频号 (weixin) | sau_adapter → upstream | weixin.mjs | **Wujie shadow DOM** + DataTransfer 上传 |
| YouTube | sau_adapter → upstream（需代理） | youtube.mjs | **Polymer dialog** 4 步流程 |

> mjs 运行时各平台完整技术档案（选择器表、ego-browser heredoc 代码、常见问题）见 `references/<platform>.md`。
> py 运行时上传逻辑在 `scripts/upstream/uploader/<platform>_uploader/`，是上游 canonical 代码，不要手改。

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

# 最简：发到 .env 里配的默认平台（默认 auto=py，走 vendored upstream，无需显式 --runtime）
node $SKILL/publish.mjs --slug finddata-brand-2026 --title "寻数科技｜探索更开放更公平的AI未来"

# 指定平台 + 标签 + 描述
node $SKILL/publish.mjs --slug finddata-brand-2026 \
  --title "寻数科技｜探索更开放更公平的AI未来" \
  --desc "让数据驱动决策" \
  --platforms douyin,xiaohongshu,bilibili,kuaishou,weixin,youtube \
  --tags "科技,开源,AI,数据,程序员" \
  --runtime py

# 定时发布（py 运行时：除 youtube 外都支持；mjs 运行时：仅 douyin/kuaishou）
node $SKILL/publish.mjs --slug finddata-brand-2026 \
  --title "..." --schedule "2026-07-20 21:30" --runtime py

# 别真发，先看一眼每个平台会跑的命令
node $SKILL/publish.mjs --slug finddata-brand-2026 --title "..." --dry-run --runtime py
```

### 单平台调试（py 运行时，直接调适配层）

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
| `--runtime` | ❌ | `auto`（默认=**py**，vendored upstream）/ `py`（显式）/ `mjs`（legacy 逃生口，ego-browser，Phase 3 删） |
| `--schedule` | ❌ | `YYYY-MM-DD HH:MM`，不给立即发 |
| `--dry-run` | ❌ | 只打印命令不执行 |
| `--no-cover` | ❌ | 跳过封面生成与上传，用平台默认封面 |
| `--cover-only` | ❌ | 只跑封面生成（4 张 + 回写 task.json），不执行发布（给预览确认用） |

## 平台差异化参数路由

publish.mjs 按平台差异组装不同的 CLI 参数（py/mjs 运行时路由一致）：

| 平台 | 封面参数 | 标签字段 | 特殊参数 | 标签上限 |
|---|---|---|---|---|
| 抖音 | `--cover-horizontal` + `--cover-vertical`（**自动传两张**） | `--tags` | `--schedule` | 10 |
| 小红书 | `--cover` | `--tags` | 标题 ≤ 20 字 | 10 |
| B站 | `--cover` | `--tags` | `--tid` (分区) | - |
| 快手 | `--cover` | `--tags` | - | **4**（不是5！） |
| 视频号 | `--cover` | (描述内 #话题) | 无单独标题字段 | - |
| YouTube | `--thumbnail` | `--tags` | `--visibility` | - |

## 登录态管理

### py 运行时（推荐）：cookie storage_state 文件

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

cookie 过期了重跑 `--login` 即可。`.profiles/` 是旧 `.py` 脚本的持久 profile，py 运行时不再用它
（除 `--migrate-profile` 一次性迁移）。

### mjs 运行时（legacy）：ego-browser 继承 Chrome

ego-browser 继承用户 Chrome 登录态，无 cookie 文件。过期在 ego-browser 中重新登录即可。

## 同步上游：sync-upstream.sh

`scripts/sync-upstream.sh` 是用户要的「快速和开源项目同步」机制：

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

### py 运行时（patchright，无 ego 任务窗口）

py 运行时走 patchright，**没有 ego 任务窗口要关**。上游脚本跑完 `wait_for_url("**/publish/success?**")`
命中 success 页后自行结束，浏览器窗口由 patchright 生命周期管理，脚本退出即关。
- 自动发布平台（xiaohongshu/kuaishou/weixin/youtube）：脚本跑完即结束，无需兜底
- douyin：上游也是自动发布（与 mjs 运行时不同，mjs 的 douyin 需手动点发布）

### mjs 运行时（ego-browser，legacy）

mjs 运行时用 ego-browser，发布完**必须关闭 ego 任务窗口**，别留给用户自己关：
- 自动发布平台（bilibili/kuaishou/xiaohongshu/youtube/weixin）：脚本末尾自调 `completeTaskSpace(id, { keep: false })`，但中途报错会跳过，仍要跑兜底清理
- 手动发布平台（douyin）：脚本 `handOffTaskSpace` 后退出，**等用户回复「发布完成」后**再跑兜底清理

```bash
ego-browser nodejs <<'EOF'
const spaces = await listTaskSpaces();
let closed = 0;
for (const s of spaces) {
  const name = s.name || s.title || '';
  const id = s.id ?? s.taskId;
  if (id == null || !/publish/i.test(name)) continue;
  try {
    const r = await completeTaskSpace(id, { keep: false });
    cliLog('closed ' + name + ': ' + (r && r.done));
    closed++;
  } catch (e) { cliLog('skip ' + name + ': ' + e.message); }
}
cliLog('🧹 清理完成，关闭 ' + closed + ' 个任务窗口');
EOF
```

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

## 各平台技术要点（mjs 运行时 / legacy）

> 以下针对 mjs 运行时（ego-browser）。py 运行时上传逻辑由 vendored upstream 实现，
> 见 `scripts/upstream/uploader/<platform>_uploader/main.py`，是上游 canonical 代码。

### 抖音 (douyin) — 标准 DOM，最简单
- 无特殊框架，标准 `document.querySelector`
- 描述输入框是 `contenteditable`，用 `execCommand('insertText')` 填写
- 封面：横版 `.cover-Jg3T4p[0]` + 竖版 `.cover-Jg3T4p[1]`，点击后点「上传封面」
- 发布按钮：`button` 含「发布」文本 + `primary` class
- 详见 `references/douyin.md`

### 快手 (kuaishou) — React Joyride + 视口外按钮
- **React Joyride 遮罩**：首次出现全屏遮罩拦截点击，必须先移除 `[class*="react-joyride"]`
- **发布按钮在视口外**：`._button-primary_3a3lq_60`，必须 `scrollIntoView({ block: 'center' })`
- **话题标签 ≤ 4 个**（不是5！）
- 详见 `references/kuaishou.md`

### B站 (bilibili) — micro-app shadow DOM
- **micro-app 微前端**：所有内容在 `micro-app[name=video-up].shadowRoot` 内
- 需选择分区（`--tid`），否则无法发布
- py 运行时走 `bilibili.py`（上游用 biliup 二进制，不在适配层）
- 详见 `references/bilibili.md`

### 小红书 (xiaohongshu) — 标题字数限制
- **标题 ≤ 20 字**（硬限制）；**话题 ≤ 10 个**
- 发布验证：URL 含 `/publish/success?`（py 运行时上游 `wait_for_url` 命中才报成功）
- 详见 `references/xiaohongshu.md`

### 视频号 (weixin) — Wujie shadow DOM，最复杂
- **Wujie 微前端**：所有内容在 `wujie-app.shadowRoot` 内
- **文件上传必须用 HTTP 服务器 + DataTransfer API**（mjs 运行时）
- 详见 `references/weixin.md`

### YouTube — Polymer Web Components
- **Polymer dialog**：`tp-yt-paper-dialog` 需强制 `opened=true`
- **4 步对话框**：Details -> Video elements -> Checks -> Visibility
- **"Not made for kids" 必答**
- py 运行时需代理：`export VAAS_YT_PROXY=http://127.0.0.1:7892`
- 详见 `references/youtube.md`

## 故障排查

| 问题 | 解决方案 |
|---|---|
| py 运行时某平台上传失败 | 读 `scripts/upstream/uploader/<platform>_uploader/main.py` 看上游逻辑；先 `--login-check` 确认 cookie 有效 |
| cookie 失效 | `python3 sau_adapter.py --platform <p> --login` 重新扫码 |
| 从旧 .profiles 迁移 | `python3 sau_adapter.py --platform <p> --migrate-profile` |
| 想同步上游最新代码 | `./sync-upstream.sh`（或 `--check` 只看 diff） |
| bilibili py 运行时 | 走 `bilibili.py`，上游用 biliup 二进制不在适配层 |
| youtube 需代理 | `export VAAS_YT_PROXY=http://127.0.0.1:7892` |
| mjs 运行时登录态失效 | ego-browser 继承 Chrome 登录态，在 ego-browser 中重新登录 |
| shadow DOM 找不到元素 | B站 `micro-app[name=video-up].shadowRoot`，视频号 `wujie-app.shadowRoot` |
| 视频号文件传不上去 | mjs 运行时必须 HTTP+DataTransfer 方案；py 运行时上游已处理 |
| 快手话题报错 | 话题 ≤ 4 个，超过需刷新 |
| YouTube Next 按钮灰色 | 必选 "Not made for kids" + 等 Checks 步骤完成 |
| 想只看命令不真发 | 加 `--dry-run` |
| Windows: `command not found: python` | .env 设 `PYTHON=py` 或 `PYTHON=python3` |
| Windows: patchright 报找不到 chromium | 跑 `patchright install chromium` |

## 参考

- `scripts/publish.mjs` — 主入口（编排 + 路由到各平台脚本 + `--runtime` 派发）
- `scripts/platforms/sau_adapter.py` — 薄适配层（CLI→上游 `<Platform>Video.main()`；`--login`/`--login-check`/`--migrate-profile`）
- `scripts/sync-upstream.sh` — 上游同步机制（clone+rsync--delete+记 SHA；`--check`/`--remote`/`<sha>`）
- `scripts/upstream/` — vendored social-auto-upload（uploader/+utils/+conf.py+conf.example.py）
  - `uploader/<platform>_uploader/main.py` — 各平台上传 canonical 代码（**不要手改**）
  - `utils/` — stealth.min.js 等共享工具
  - `conf.py` — VAAS 本地 conf 覆盖（headed/proxy；sync 不覆盖）
  - `cookies/<platform>_uploader/account.json` — 运行态登录态（gitignored）
- `scripts/platforms/<platform>.py` — bilibili.py（py 运行时；其余平台走 sau_adapter）
- `scripts/platforms/<platform>.mjs` — legacy ego-browser 脚本（Phase 3 删除）
- `scripts/platforms/lib/browser_utils.py` — 旧 .py 共享工具（仅 bilibili.py 仍用）
- `scripts/lib/browser-utils.mjs` — legacy 共享浏览器工具函数
- `references/<platform>.md` — 各平台完整技术档案（选择器表、heredoc 代码、常见问题）
- **fd-cover-image skill** — 封面生成（Remotion 方案，优先用）
- **fd-vaas-video-creator skill** — 视频产出（本 skill 只读成片，不生成视频）

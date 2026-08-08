# Tasks

## Phase 1: 源码签入（含隐私审计）

### 1.1 .gitignore 收敛
- [x] 移除 `remotion-app/` 整目录忽略，改为精确忽略：
  - `remotion-app/node_modules/`、`remotion-app/out/`、`remotion-app/.remotion/`
  - `remotion-app/public/voiceover-*`、`remotion-app/public/captions-*`、`remotion-app/public/*.mp3`
- [x] 新增忽略：`*.bak`、`.env.bak`
- [x] 确认 `vaas.db`、`data/`、`downloads/`、`demand*.md`、`.profiles/` 仍被忽略

### 1.2 隐私审计（签入前硬性门槛）
- [x] grep 待签入文件：密钥模式（`sk-`、`appid`、`secret`、`token=`）、内部 IP/域名、个人路径（`/Users/<user>`）
- [x] 人工过一遍 `remotion-app/src/scenes*.tsx`、`LogoAnimation.tsx`、`theme.ts`：确认无未公开产品名/内部代号
- [x] `mcp-server/` 同样审计；确认 `registry.json` 的 `${VAR}` 占位不含真实 key
- [x] 发现敏感信息：脱敏后再签入，并在 tasks 里记录脱敏点
  - 脱敏记录（2026-08-08）：
    - 8 个脚本去除硬编码个人绝对路径（`/Users/<user>/VAAS`）：改为 `VAAS_ROOT` 环境变量 ?? 脚本位置上四级推导（两个 publish.mjs、video-creator 5 个脚本、fd-cover-image/generate-cover.mjs、fd-vaas-dashboard-sharing/share.sh、remotion-app/scripts/compute-timings.py 改 argv 传参）
    - 13 个 markdown 文档（README×2、fd-* SKILL.md/references）统一替换为 `$VAAS` 占位，并在首次使用前补 `export VAAS=<仓库根>` 说明
    - 未发现密钥/内部 IP/账号 ID 泄漏；scene 品牌词仅 FindDataTech/FindData（已公开品牌）

### 1.3 签入
- [x] `git add remotion-app/src remotion-app/package.json remotion-app/tsconfig.json`（及 remotion 配置文件）
- [x] `git add remotion-app/public/` 中渲染必需的品牌资产（logo 等），逐个确认
- [x] `git add openspec/ mcp-server/`（排除 `__pycache__`、本地 db）
- [x] 提交信息说明「公开渲染源码 + 已归档 spec 成果」

## Phase 2: install.sh 升级

### 2.1 依赖检查
- [x] 检查 Node 18+、git、ffmpeg/ffprobe（缺失给 brew/apt 安装命令）
- [x] 按平台检查：macOS → ego-browser、cap、officecli；Windows 提示 patchright + uv
- [x] 每项缺失只警告不中断，汇总到最后报告

### 2.2 项目初始化
- [x] `npm install --prefix remotion-app`（失败时给出手动命令）
- [x] 检查 `VoiceoverVideo` composition 已注册；未注册则执行/提示 `references/setup.md` 步骤
- [x] `.env` 不存在时从 `.env.example` 复制并高亮提示填 Ark key

### 2.3 技能链接（跨平台）
- [x] 枚举 `.agents/skills/` 中需要暴露的技能清单（与现有 `.claude/skills` 子集一致）
- [x] macOS/Linux：创建/修复软链接；Windows（Git Bash 检测到 `MINGW`/`MSYS` 或无软链权限）：复制目录
- [x] 幂等：已存在且指向正确则跳过

### 2.4 收尾
- [x] 调用 `node scripts/doctor.mjs`，把报告作为安装结果输出
- [x] 打印「下一步：填 .env → 看 README 快速路径」

## Phase 3: doctor.mjs

- [x] 新建 `scripts/doctor.mjs`，检查项为数据驱动数组 `{name, check(), level, fix}`
- [x] 检查：Node/ffmpeg/python 版本；ego-browser/cap/officecli which；`.env` 关键变量存在性（`VOL_*`/Ark key，不打印值）；`remotion-app/node_modules` 存在；`VoiceoverVideo` 注册；`.claude/skills` 链接完整
- [x] 输出 ✅/⚠️/❌ 三级 + 修复命令；有 ❌ 退出码非 0
- [x] README「坑与排错」节引用 doctor 作为第一排查手段

## Phase 4: README 快速路径与状态透明

- [x] README.md 顶部（一键安装之后）新增「5 分钟第一支视频」：install → 填 key → new-task + task-render 两条命令 → 产物路径
- [x] 平台支持矩阵加「验证状态」列：✅ 实机验证 / ⚠️ 推断未验证（图文 9 平台标 ⚠️ + 指向 probe.md；patchright Windows 链路标 ⚠️）
- [x] README.en.md 同步上述两处改动
- [x] AGENTS.md 补一句：改技能改 `.agents/skills/`（真相源），`.claude/skills` 由 install.sh 生成

## Phase 5: 验证

- [x] 干净目录模拟新用户：`git clone` 公开仓库 → install.sh → doctor → 快速路径渲染（可用本机另开目录）
- [x] 确认 `git status` 干净、无敏感文件被跟踪
- [x] 推送到 GitHub 后以「匿名视角」过一遍 README 快速路径

# Design: 开源可用性

## 关键决策

### 1. remotion-app/src 全量签入，而非精选子集

**选择**：`src/` 全部签入（含 scenesVAAS/scenesGov/scenesOrg 等品牌场景），签入前审计脱敏。

**理由**：
- 品牌场景本就是公开发布视频的视觉内容，公开无新增暴露面
- 精选子集会产生「本地能渲、公开仓库缺组件」的漂移，正是本次要消灭的问题
- 真正私密的是素材（`downloads/common/`、logo 源文件），它们继续 gitignore

**替代方案（否掉）**：只签入 VoiceoverVideo + setup.md 重建其余——保留了两套真相，新用户仍可能卡在场景组件缺失。

### 2. 技能分发：真相源唯一，链接/复制由安装脚本生成

```
.agents/skills/          ← 唯一真相源（git 跟踪）
.claude/skills/<name>    ← 由 install.sh 生成：
                            macOS/Linux = 软链接（现状）
                            Windows     = 目录复制（git 软链不可靠）
```

- `.claude/skills/` 是否继续签入？**保持签入**（macOS 用户 clone 即可用，无需跑 install）；Windows 用户跑 install.sh 时检测断链/缺失并复制修复
- 漂移风险用文档约束：AGENTS.md 明确「只改 .agents/skills」

### 3. doctor 数据驱动、退出码语义化

```js
const CHECKS = [
  { name: 'ffmpeg', level: 'required', run: () => which('ffmpeg'),
    fix: 'brew install ffmpeg' },
  { name: 'Ark API key', level: 'required', run: () => envSet(/^VOL_|ARK/),
    fix: '编辑 .env，见 .env.example 注释' },
  { name: 'ego-browser', level: 'optional', run: () => which('ego-browser'),
    fix: 'macOS 分发需要；见 README 前置条件' },
  // ...
]
```

- `required` 缺失 → ❌ → 退出码 1（install.sh 据此提示，未来 CI 可直接用）
- `optional` 缺失 → ⚠️ → 说明影响哪些功能（如「无 ego-browser 则 macOS 无法发布」）
- 不打印任何密钥值，只报存在性

### 4. install.sh 保持 bash 单文件，Windows 靠 doctor.mjs 兜底

Windows 无原生 bash；与其维护 install.ps1 双份逻辑，不如：
- install.sh 服务 macOS/Linux（主用户群）
- Windows 文档路径：clone → `npm install --prefix remotion-app` → `node scripts/doctor.mjs`（Node 脚本天然跨平台，技能复制逻辑也在 doctor/Node 层实现，install.sh 只是调它）

即：**复制/检查逻辑写一次（Node），bash 只是壳**。

### 5. 平台验证状态用静态标记，不做自动检测

README 矩阵加一列「验证状态」手工维护。自动检测登录态/选择器存活是 probe.md 流程的职责，不属于安装体验。标记规则：
- ✅ = 在真实登录态下完整发布成功过
- ⚠️ = 选择器推断/未经实机发布，首次用前先跑 probe.md

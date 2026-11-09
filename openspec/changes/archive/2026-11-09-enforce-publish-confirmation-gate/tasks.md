# Tasks: enforce-publish-confirmation-gate

## tasks

### W1 确认闸代码化（全自动化路径）

- [x] W1.1 `_shared/publish/browser_utils.confirm_gate` 抽为通用闸（去平台耦合），非 TTY EOFError 路径改 fail-closed（缺确认即失败并提示补齐方法，无超时自动发布）
- [x] W1.2 `fd-vaas-publish-videos/scripts/publish.mjs`：spawn 上传器前接入确认闸（哨兵/`--confirm` 参数），未确认零上传；旁路 `--auto-publish` 显式参数存在且回执标注
- [x] W1.3 `note_adapter.py`（上游图文三平台 xiaohongshu/douyin/kuaishou 路径）同形态过闸
- [x] W1.4 闸负例测试：三链路（视频/上游图文/自有图文）无确认→零子进程 spawn、`node --test`/pytest 各一正反例

### W2 发布结果真实性

- [x] W2.1 `bilibili.py`：点击发布后验证落地（管理页/回跳 URL 探针），未验证 exit≠0；不写 distribution 成功行；`--tid` 死参数处理（应用或删除，与 SKILL 分区说明对齐）
- [x] W2.2 `fd-vaas-publish-docs/scripts/publish.mjs`：聚合子进程状态决定退出码（仿 videos 侧聚合形态），部分失败非零 + 逐平台列明
- [x] W2.3 台账对账：负例注入（mock 失败子进程）验证 distribution 零假成功行

### W3 平台登记一致性

- [x] W3.1 `platform-registry.json` 补全：weibo/baijiahao 视频路由、alipay/hupu 全条目（与 `sau_adapter.py` REGISTRY 10 平台对平）
- [x] W3.2 `check-registry-consistency.py` 扩面覆盖 platform-registry.json（registry↔adapter↔publish.mjs 三方对账，差集非零退出）；跑绿为证据
- [x] W3.3 两个 SKILL.md 平台表改由 registry 渲染（videos SKILL.md:9,46-53 六平台旧口径清除）；README 平台矩阵同步 10+11
- [x] W3.4 `.env` 默认 `PLATFORMS_DOCS` 剔除 broken（xueqiu/tonghuashun），重验回归机制记录在 registry 条目

### W4 登录检查与定时矩阵

- [x] W4.1 `sau_adapter.py --login-check`：缺 cookie_auth → `unknown`（非 exit 0「有效」）；login-manager 消费 unknown 态提示人工复核
- [x] W4.2 `bilibili_login.py` 会话探针（仿 `docs_login.py` 探测形态）替代目录存在检查
- [x] W4.3 定时能力入 registry（每平台 schedule 字段），videos publish.mjs 按声明分流（不再对 no_strategy 平台批内中断）；SKILL 107 行口径修正

### W5 Windows 可移植

- [x] W5.1 哨兵/临时产物路径改系统临时目录等价（`tempfile.gettempdir()` + env 覆盖），zhihu.py 等回退路径同步
- [x] W5.2 Python 启动器平台感知统一：login-manager 六处 `python3` 字面量 + 两个 publish.mjs 的 db-writer/history spawn 口径
- [ ] W5.3 Windows 语义验证：本地可验部分已由 tests/publish-gate.test.mjs 覆盖（tempdir 语义/哨兵消费）；真机（<WIN_NODE_IP>）复验=外依赖挂账 DEBT-WIN-01（扫码登录→带闸发布 dry-run→真实发布一次）

### W6 运维批次与收口

- [ ] W6.1 cookies/登录态过旧重登重验一批（4 平台 cookie mtime 近 30 天门限；`.docs_state.json` 已过期）——真实发布前运维前置（人工扫码，挂 DEBT-RELOGIN-01）
- [x] W6.2 `conf.py` DEBUG_MODE 复核关断；`upstream/uploader/xhs_uploader/accounts.ini` 加 gitignore 洞；sync-upstream `--check` 说明补进 README（README:173 断链归 add-ci-and-provisioning 一并修）
- [x] W6.3 全量 node:test + pytest 绿（370 pytest + 14 publish-gate + 12 publish-common）；strict 校验绿；归档待 W5.3/W6.1 运维批次后与本波统一收

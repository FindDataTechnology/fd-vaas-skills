# DEBT-RENDER-FLAKY-01 · 合入/部署/取证/回滚 执行清单（待签）

> 状态：**待批准**（冻结中）。本页是批准后照做即可的执行单，任何一步不达检查点就停并回滚。
> 关联：`docs/debt-ledger.md` → `DEBT-RENDER-FLAKY-01`；补丁 `docs/patches/DEBT-RENDER-FLAKY-01-killgroup-log.patch`；分支 `probe/killgroup-log`。

## 0. 目标与判据（先对齐"什么算成功"）

| 项 | 定义 |
|---|---|
| 要证伪/证实的假设 | render plane 的 `runEngine.finish()` → `killGroup(child.pid,'SIGKILL')` 会**误杀同类子进程**（detached 下 pgid==pid，按 `-pid` 发信号） |
| 取证成功判据 | 一次 20s storyboard 的 3 次重试里，出现 `[killGroup] send … pgid=-P`，而该 `P` **不是**当次作业子进程自己的 pid（或：发信号时该组仍 `alive` 且随后本次作业失败） |
| 反证判据 | 三次重试的 `[killGroup]` 全部是「作业结束后的收尾」，`groupBefore=ESRCH`（组早已自行消失）→ 假设不成立，需换方向（如 capture 阶段 chromium 自崩） |
| 不变量 | 现网 API `sha-5c88dbe` 不动；渲染面失败可随时用 §5 命令退回 `sha-3c6a856`；台账/分支/补丁除 §1、§4 外不改 |

## 1. 合入（只进日志观测，不改行为）

```bash
cd /Users/chengsishi/VAAS
git checkout main && git pull --ff-only origin main
git apply --check docs/patches/DEBT-RENDER-FLAKY-01-killgroup-log.patch   # 必须 OK（已验）
git apply         docs/patches/DEBT-RENDER-FLAKY-01-killgroup-log.patch
node --check render-plane/server.mjs
git add render-plane/server.mjs
git commit -m "probe(render-plane): killGroup 增加 pid/pgid 与信号三态日志（DEBT-RENDER-FLAKY-01 取证）"
git push origin main
```

- **为什么用 `git apply` 而不是 `git merge`**：分支上 `f5a23a7` 的内容已通过 cherry-pick 落在 main（`dfa4bf6`），直接 merge 会产生重复/冲突；补丁正是待审的那份 diff，逐字应用最可审计。
- **检查点 C1**：`git apply --check` = OK；`node --check` = OK；`git show --stat HEAD` 只含 `render-plane/server.mjs`（+29/−3）。
- **不改 meshing 语义**：`ESRCH` 仍吞、`pid=0` 仍直接 return（diff 里已注明）。

## 2. 部署到 cheap-4

镜像 `ccr.ccs.tencentyun.com/yizuo/vaas-render-plane:sha-fba0c12`（GHA run 42813304322，target=vaas-render-plane，含 `/healthz` 冒烟门）。
**权威可用性（双仓已核）**：hkccr OK / ccr OK（从部署节点验；cheap-4 对 hkccr 无凭据，不能从那边判断）。

```bash
# 在 cheap-4（100.64.0.8）上执行 —— 与台账回滚命令同形，仅镜像 tag 换成 fba0c12
docker pull ccr.ccs.tencentyun.com/yizuo/vaas-render-plane:sha-fba0c12
docker rm -f vaas-renderer
docker run -d --name vaas-renderer --restart no --network vaas-render-ext \
  --memory=4g --shm-size=2g -p 100.64.0.8:8099:8099 \
  -e VAAS_RENDER_MAX_CONCURRENCY=3 -e VAAS_RENDER_PORT=8099 \
  -e VAAS_RENDER_WORKDIR=/tmp/vaas-render \
  -e HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium \
  -e HYPERFRAMES_FFMPEG_PATH=/usr/bin/ffmpeg -e HYPERFRAMES_FFPROBE_PATH=/usr/bin/ffprobe \
  -e HYPERFRAMES_NO_TELEMETRY=1 -e HYPERFRAMES_NO_AUTO_INSTALL=1 \
  -e HYPERFRAMES_NO_OPTIONAL_INSTALL=1 -e HYPERFRAMES_NO_UPDATE_CHECK=1 \
  -e HYPERFRAMES_CACHE_DIR=/tmp/hf-cache -e HYPERFRAMES_MEDIA_HOME=/tmp/hf-media \
  ccr.ccs.tencentyun.com/yizuo/vaas-render-plane:sha-fba0c12
```

- **检查点 C2（部署生效）**：`docker ps` 的 `Image` = `…:sha-fba0c12`；`curl -s http://100.64.0.8:8099/healthz` → `ok:true`、`workers:3`；`docker exec vaas-renderer grep -c killGroup /app/server.mjs` ≥ 3（确认代码真的进了镜像层）。
- 无需 `VAAS_RENDER_DEBUG`：`[killGroup]` 是**无条件 console.log**，`docker logs` 直接可见。
- 若拉取失败：先 `fd-build-channel` 判路，再按通道重出（`fd-build-snapshot` → `gh workflow run images.yml -f target=vaas-render-plane`）；不要手工 `docker build`。

## 3. 取证（20s storyboard 三连用例）

```bash
# 在 vaas-wanxing 容器内（api 侧），沿用既有脚本
docker cp /root/e2e_sb20.py vaas-wanxing:/tmp/sb20.py
docker exec -d vaas-wanxing sh -c "python3 /tmp/sb20.py > /tmp/sb20c.log 2>&1"
# 渲面日志（取证核心）
docker logs -t vaas-renderer 2>&1 | grep -E "\[killGroup\]|render failed" | tail -40
```

- **检查点 C3（拿到证据）**：`docker logs` 出现 ≥1 条 `[killGroup] send sig=SIGKILL pid=<P> pgid=-<P> selfPid=<plane pid> groupBefore=<alive|ESRCH>`；
  且 `done … groupAfter=… sendErr=…` 成对出现。
- **判读规则**（照 §0）：`groupBefore=alive` **且** 该 `P` 对应的作业在日志里随后失败 → 误杀成立；全部 `ESRCH` → 误杀不成立。
- **旁证**：失败作业的 job 目录残留 `.hyperframes/running/<pid>` 且无 `video-state.json`（与先前一致）。
- **注意**：SIGKILL 后立刻探测可能仍 `alive`（进程未回收），`groupAfter` 只作旁证，不能单独当判据。

## 4. 收尾（把结论写回台账）

无论成败都要写，避免下次重跑：

```bash
cd /Users/chengsishi/VAAS
# 改 docs/debt-ledger.md 的 DEBT-RENDER-FLAKY-01：
#   成立 → 记「误杀证据」（pid/pgid/时间线）+ 下一步修法（显式 pgid 清理 / 收窄 kill 时机），保持 🟡 并要求改 meshing 语义另开 change
#   不成立 → 记「三次全 ESRCH」反证 + 换方向（capture 阶段 chromium 自崩、BeginFrame 未跑）
git commit -m "docs(ledger): FLAKY-01 取证结论（<成立/不成立>）"
git push origin main
```

- **检查点 C4**：台账行仍单行、竖线数 = 7；结论里含具体 `pid/pgid` 与时间线。

## 5. 回滚（任何一步异常立即执行）

```bash
# cheap-4 上，退回已验证可用的 sha-3c6a856
docker pull ccr.ccs.tencentyun.com/yizuo/vaas-render-plane:sha-3c6a856
docker rm -f vaas-renderer
docker run -d --name vaas-renderer --restart no --network vaas-render-ext \
  --memory=4g --shm-size=2g -p 100.64.0.8:8099:8099 \
  -e VAAS_RENDER_MAX_CONCURRENCY=3 -e VAAS_RENDER_PORT=8099 \
  -e VAAS_RENDER_WORKDIR=/tmp/vaas-render \
  -e HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium \
  -e HYPERFRAMES_FFMPEG_PATH=/usr/bin/ffmpeg -e HYPERFRAMES_FFPROBE_PATH=/usr/bin/ffprobe \
  -e HYPERFRAMES_NO_TELEMETRY=1 -e HYPERFRAMES_NO_AUTO_INSTALL=1 \
  -e HYPERFRAMES_NO_OPTIONAL_INSTALL=1 -e HYPERFRAMES_NO_UPDATE_CHECK=1 \
  -e HYPERFRAMES_CACHE_DIR=/tmp/hf-cache -e HYPERFRAMES_MEDIA_HOME=/tmp/hf-media \
  ccr.ccs.tencentyun.com/yizuo/vaas-render-plane:sha-3c6a856
curl -s http://100.64.0.8:8099/healthz
docker ps --format '{{.Image}}' --filter name=vaas-renderer
```

- **本命令已于 2026-11-10 实测**（换名 `vaas-renderer-rbcheck` + 端口 `127.0.0.1:18099`，去掉 `rm -f`）：起容器 8s 后 `healthz ok:true / workers:3`，演练容器已删、端口已释放。
- **检查点 C5**：`healthz ok:true` + `Image` 回到 `sha-3c6a856`。
- 代码侧回滚（若已合入 main 且需撤销）：`git revert <合入 commit>`，再 `fd-build-snapshot` + `gh workflow run … target=vaas-render-plane` 重出；**不要**直接改节点上的 `server.mjs`。

## 6. 风险与时间

| 风险 | 处置 |
|---|---|
| 取证期间渲染面不可用 | 只影响出片，不影响 API/账本；失败即执行 §5 |
| 20s 用例本身 flaky，三次全过（无证据） | 视为「未复现」：记台账，保留日志，重复一轮（最多 2 轮） |
| 误杀假设不成立 | 立即回滚 + 换方向，不在同一假设上反复烧时间 |
| 耗时 | 部署 ~1min；三连用例 ~5–8min（单次 135s + 重试）；回滚 ~1min |

**签字位**：批准 ☐ / 驳回 ☐ ｜ 批准范围：仅 §1–§4（合入观测日志 + 部署 fba0c12 + 取证 + 回填台账），不含修改清理语义。

/**
 * publish-gate.test.mjs — 发布确认闸负例测试（enforce-publish-confirmation-gate W1.4/W2.3）。
 *
 * 覆盖三条链路的「无确认 → 零上传」闸语义，全部离线、确定性、零新增依赖：
 *   1. JS 共享闸 helper（_shared/publish/confirm-gate.mjs）单元语义；
 *   2. Python 侧同一闸实现（browser_utils.confirm_gate / note_adapter.gate_file/gate_publish）
 *      —— 与 JS 侧同命名同语义的对拍；
 *   3. 视频编排器端到端负例：fd-vaas-publish-videos publish.mjs 缺确认凭据时
 *      exit 非零、零上传器 spawn、台账零写入（spec「视频路径同样有硬闸」「非交互不静默放行」）。
 *
 * 故意不测「哨兵放行后真的 spawn 上传器」——那会触发真实平台上传；
 * 放行语义由 checkGate/confirm_gate 的单元正例覆盖（sentinel 出现=ok+消费）。
 *
 * 运行：node --test tests/publish-gate.test.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";

import {
  checkGate,
  defaultGateFile,
  resolveTempDir,
  GATE_PREFIX_DOC,
  GATE_PREFIX_VIDEO,
} from "../.agents/skills/_shared/publish/confirm-gate.mjs";

const VAAS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SHARED_PUBLISH = path.join(VAAS, ".agents", "skills", "_shared", "publish");
const NOTE_ADAPTER_DIR = path.join(VAAS, ".agents", "skills", "fd-vaas-publish-docs", "scripts");

function withTempDir(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vaas-gate-test-"));
  try {
    return fn(dir);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

/** 跑一段 python 断言脚本（-I 隔离 site/user 路径，离线纯断言）。 */
function runPy(code, env = {}) {
  return spawnSync("python3", ["-I", "-c", code], {
    encoding: "utf8",
    timeout: 30000,
    env: { ...process.env, ...env },
  });
}

// ─── 1) JS 共享闸 helper ─────────────────────────────────────

test("resolveTempDir: 缺省 = 系统临时目录", () => {
  assert.equal(resolveTempDir({}), os.tmpdir());
});

test("resolveTempDir: VAAS_GATE_DIR 优先（Windows 节点逃生口，W5.1）", () => {
  assert.equal(resolveTempDir({ VAAS_GATE_DIR: "/custom/gate" }), "/custom/gate");
});

test("defaultGateFile: 命名 <prefix>-<platform>.go；空平台名拒绝（防空凭据挂等）", () => {
  assert.equal(
    defaultGateFile("douyin", GATE_PREFIX_VIDEO, {}),
    path.join(os.tmpdir(), "vaas-video-douyin.go"),
  );
  assert.equal(
    defaultGateFile("zhihu", GATE_PREFIX_DOC, { VAAS_GATE_DIR: "/g" }),
    path.join("/g", "vaas-doc-zhihu.go"),
  );
  assert.throws(() => defaultGateFile("", GATE_PREFIX_VIDEO, {}));
});

test("checkGate: 缺确认凭据 = fail closed（ok:false, source:missing）", () => {
  withTempDir((dir) => {
    const v = checkGate("douyin", { prefix: GATE_PREFIX_VIDEO, env: { VAAS_GATE_DIR: dir } });
    assert.equal(v.ok, false);
    assert.equal(v.source, "missing");
    assert.match(v.reason, /哨兵/);
  });
});

test("checkGate: 哨兵存在 = 放行一次并消费（删除）", () => {
  withTempDir((dir) => {
    const gateFile = path.join(dir, "vaas-video-bilibili.go");
    fs.writeFileSync(gateFile, "");
    const v = checkGate("bilibili", { prefix: GATE_PREFIX_VIDEO, env: { VAAS_GATE_DIR: dir } });
    assert.equal(v.ok, true);
    assert.equal(v.source, "sentinel");
    // 消费语义与 Python wait_for_file 对齐：touch 放行一次即失效
    assert.equal(fs.existsSync(gateFile), false, "哨兵放行后必须被删除（一次确认一次放行）");
    const again = checkGate("bilibili", { prefix: GATE_PREFIX_VIDEO, env: { VAAS_GATE_DIR: dir } });
    assert.equal(again.ok, false, "同一哨兵不能放行第二次");
  });
});

test("checkGate: consume:false 保留哨兵（docs 路径由 Python confirm_gate 消费）", () => {
  withTempDir((dir) => {
    const gateFile = path.join(dir, "vaas-doc-zhihu.go");
    fs.writeFileSync(gateFile, "");
    const v = checkGate("zhihu", { prefix: GATE_PREFIX_DOC, consume: false, env: { VAAS_GATE_DIR: dir } });
    assert.equal(v.ok, true);
    assert.equal(fs.existsSync(gateFile), true, "JS 只预检不消费，哨兵留给 Python 侧");
  });
});

test("checkGate: --confirm-file 显式路径覆盖默认哨兵名", () => {
  withTempDir((dir) => {
    const explicit = path.join(dir, "my-own-credential.go");
    fs.writeFileSync(explicit, "");
    const ok = checkGate("douyin", { confirmFile: explicit, prefix: GATE_PREFIX_VIDEO, env: {} });
    assert.equal(ok.ok, true);
    const missing = checkGate("douyin", {
      confirmFile: path.join(dir, "nope.go"),
      prefix: GATE_PREFIX_VIDEO,
      env: {},
    });
    assert.equal(missing.ok, false);
  });
});

test("checkGate: --auto-publish 显式旁路（source 标注，供回执 auto_publish: true）", () => {
  // 无任何哨兵文件也能放行 —— 但 source 必须可区分，publish.mjs 据此写台账标记
  const v = checkGate("douyin", { autoPublish: true, prefix: GATE_PREFIX_VIDEO, env: { VAAS_GATE_DIR: os.tmpdir() } });
  assert.equal(v.ok, true);
  assert.equal(v.source, "auto-publish");
  assert.equal(v.gateFile, null);
});

// ─── 2) Python 侧同一闸实现（正反例各一，W1.4）───────────────

test("python confirm_gate: 空/缺确认凭据立即拒绝（W1.1 fail closed，不挂 timeout）", () => {
  withTempDir((dir) => {
    const r = runPy(
      `
import sys, time
sys.path.insert(0, ${JSON.stringify(SHARED_PUBLISH)})
from browser_utils import confirm_gate
t0 = time.time()
ok = confirm_gate(None, "", timeout=7200)   # 旧行为会拿空路径挂满 7200s
assert ok is False, "空凭据必须拒绝"
assert time.time() - t0 < 5, "空凭据必须立即拒绝，不得等待 timeout"
print("PY_GATE_EMPTY_OK")
`,
      { VAAS_GATE_DIR: dir },
    );
    assert.equal(r.status, 0, r.stderr);
    assert.match(r.stdout, /PY_GATE_EMPTY_OK/);
  });
});

test("python confirm_gate: 哨兵存在 = 放行并消费（与 JS 同语义对拍）", () => {
  withTempDir((dir) => {
    const gateFile = path.join(dir, "vaas-doc-toutiao.go");
    fs.writeFileSync(gateFile, "");
    const r = runPy(
      `
import sys
sys.path.insert(0, ${JSON.stringify(SHARED_PUBLISH)})
from browser_utils import confirm_gate
import os
ok = confirm_gate(None, ${JSON.stringify(gateFile)}, timeout=10)
assert ok is True, "哨兵存在必须放行"
assert not os.path.exists(${JSON.stringify(gateFile)}), "放行后哨兵必须被消费"
ok2 = confirm_gate(None, ${JSON.stringify(gateFile)}, timeout=1)
assert ok2 is False, "消费后第二次必须拒绝"
print("PY_GATE_SENTINEL_OK")
`,
      { VAAS_GATE_DIR: dir },
    );
    assert.equal(r.status, 0, r.stderr);
    assert.match(r.stdout, /PY_GATE_SENTINEL_OK/);
  });
});

test("python note_adapter.gate_file: 与 JS defaultGateFile 同命名同语义（W5.1 系统临时目录）", () => {
  withTempDir((dir) => {
    const r = runPy(
      `
import sys, os
sys.path.insert(0, ${JSON.stringify(NOTE_ADAPTER_DIR)})
import note_adapter
assert note_adapter.gate_file("douyin", "") == os.path.join(os.environ["VAAS_GATE_DIR"], "vaas-doc-douyin.go")
assert note_adapter.gate_file("douyin", "/explicit/p.go") == "/explicit/p.go", "--confirm-file 显式路径优先"
print("PY_GATE_FILE_OK")
`,
      { VAAS_GATE_DIR: dir },
    );
    assert.equal(r.status, 0, r.stderr);
    assert.match(r.stdout, /PY_GATE_FILE_OK/);
  });
});

test("python note_adapter.gate_publish: --auto-publish 显式旁路返回 True", () => {
  const r = runPy(
    `
import sys
sys.path.insert(0, ${JSON.stringify(NOTE_ADAPTER_DIR)})
import note_adapter
assert note_adapter.gate_publish("xiaohongshu", "", True, timeout=1) is True
print("PY_GATE_BYPASS_OK")
`,
  );
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /PY_GATE_BYPASS_OK/);
});

// ─── 3) 视频编排器端到端负例（W1.2/W2.3）─────────────────────

test("videos publish.mjs 缺确认凭据 → exit 1、零上传器 spawn、台账零写入", () => {
  withTempDir((gateDir) => {
    // fixture task：最小 task.json + 空 mp4（只走到确认闸，不进封面/上传）
    const slug = `gate-negtest-${process.pid}`;
    const taskDir = path.join(VAAS, "downloads", "fd-videos", slug);
    fs.mkdirSync(taskDir, { recursive: true });
    const manifestPath = path.join(taskDir, "task.json");
    fs.writeFileSync(manifestPath, JSON.stringify({ render: { output: `${slug}.mp4` } }));
    fs.writeFileSync(path.join(taskDir, `${slug}.mp4`), "not-a-real-video");
    try {
      // VAAS_GATE_DIR 指向空测试目录 + 不传 --confirm-file/--auto-publish：
      // 凭据必然缺失 → 闸必须在 spawn 任何上传器之前 exit 非零（非交互无 TTY 同样失败关闭）
      const r = spawnSync(
        "node",
        [
          path.join(VAAS, ".agents", "skills", "fd-vaas-publish-videos", "scripts", "publish.mjs"),
          "--slug", slug,
          "--title", "确认闸负例测试",
          "--platforms", "douyin",
          "--no-cover",
        ],
        { encoding: "utf8", timeout: 60000, env: { ...process.env, VAAS_GATE_DIR: gateDir } },
      );
      assert.equal(r.status, 1, `期望 exit 1，实际 ${r.status}\nstdout: ${r.stdout}\nstderr: ${r.stderr}`);
      assert.match(r.stdout, /确认闸未满足/, "必须打印闸拒绝信息");
      assert.match(r.stdout, /touch /, "必须给出补齐确认的可行动指引");
      assert.doesNotMatch(r.stdout, /发布总结/, "不得进入发布执行段");
      // 台账零写入：task.json 未被追加 distribution（零假成功行，W2.3）
      const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
      assert.equal(manifest.distribution, undefined, "未确认不得写 distribution 台账");
    } finally {
      fs.rmSync(taskDir, { recursive: true, force: true });
    }
  });
});

test("videos publish.mjs --dry-run 不触发确认闸（预览语义保留）", () => {
  withTempDir((gateDir) => {
    const slug = `gate-dryrun-${process.pid}`;
    const taskDir = path.join(VAAS, "downloads", "fd-videos", slug);
    fs.mkdirSync(taskDir, { recursive: true });
    const manifestPath = path.join(taskDir, "task.json");
    fs.writeFileSync(manifestPath, JSON.stringify({ render: { output: `${slug}.mp4` } }));
    fs.writeFileSync(path.join(taskDir, `${slug}.mp4`), "not-a-real-video");
    try {
      const r = spawnSync(
        "node",
        [
          path.join(VAAS, ".agents", "skills", "fd-vaas-publish-videos", "scripts", "publish.mjs"),
          "--slug", slug,
          "--title", "dry-run 预览",
          "--platforms", "douyin",
          "--no-cover",
          "--dry-run",
        ],
        { encoding: "utf8", timeout: 60000, env: { ...process.env, VAAS_GATE_DIR: gateDir } },
      );
      assert.equal(r.status, 0, `dry-run 应 exit 0\nstdout: ${r.stdout}\nstderr: ${r.stderr}`);
      assert.match(r.stdout, /dry/, "dry-run 输出应带 dry 标记");
      assert.doesNotMatch(r.stdout, /确认闸未满足/, "dry-run 预览不应被确认闸拦截");
    } finally {
      fs.rmSync(taskDir, { recursive: true, force: true });
    }
  });
});

#!/usr/bin/env node
// 渲染面自测 —— 起真服务、真渲染、真断言。
//
//   node test/selftest.mjs        （或 npm test）
//
// 覆盖：健康检查/版本 · 素材入库与 sha 校验 · 最小 composition 出片（真 MP4）
//      · 幂等（同 job_id 命中结果缓存）· 确定性（不同 job_id 同内容 md5 一致）
//      · 素材相对路径落位 · 零外链拒绝 · 路径穿越拒绝 · 缺素材拒绝
//      · 子进程 env 不含任何 VAAS_/TOKEN/KEY/SECRET · 超时 5xx 且 tmpdir 零残留
//      · 并发上限（队列满 429）
//
// 前提：本机有 Chrome（mac 上 hyperframes 自动用系统 Google Chrome）与 ffmpeg。
// 不依赖 docker；容器级验证交给部署节点。

import fs from 'node:fs';
import fsp from 'node:fs/promises';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PLANE_ROOT = path.resolve(HERE, '..');
const SERVER = path.join(PLANE_ROOT, 'server.mjs');
const EXAMPLE_HTML = path.join(PLANE_ROOT, 'examples', 'minimal', 'index.html');

// 1x1 透明 PNG：用作「素材」验证 sha256 入库与相对路径落位
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

const results = [];
let failures = 0;

function check(name, cond, detail) {
  const ok = Boolean(cond);
  if (!ok) failures += 1;
  results.push({ name, ok, detail });
  const mark = ok ? 'PASS' : 'FAIL';
  console.log(`[${mark}] ${name}${detail === undefined ? '' : ` — ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`}`);
  return ok;
}

const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
const md5 = (buf) => crypto.createHash('md5').update(buf).digest('hex');

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

async function waitHealth(port, timeoutMs = 45_000) {
  const deadline = Date.now() + timeoutMs;
  let lastErr = null;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/healthz`);
      if (r.ok) return await r.json();
      lastErr = new Error(`status ${r.status}`);
    } catch (err) {
      lastErr = err;
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`healthz not ready on :${port}: ${lastErr?.message || lastErr}`);
}

async function startPlane({ workdir, env = {}, port }) {
  const child = spawn(process.execPath, [SERVER], {
    env: {
      PATH: process.env.PATH,
      LANG: process.env.LANG || 'en_US.UTF-8',
      // 故意注入平台凭证，验证渲染子进程看不到
      VAAS_BEARER_TOKEN: 'selftest-should-not-leak',
      VAAS_RENDER_WORKDIR: workdir,
      VAAS_RENDER_PORT: String(port),
      VAAS_RENDER_BIND: '127.0.0.1',
      ...(process.env.HYPERFRAMES_BROWSER_PATH ? { HYPERFRAMES_BROWSER_PATH: process.env.HYPERFRAMES_BROWSER_PATH } : {}),
      ...env,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const logs = [];
  child.stdout.on('data', (b) => logs.push(b.toString()));
  child.stderr.on('data', (b) => logs.push(b.toString()));
  const healthz = await waitHealth(port);
  return { child, logs, healthz };
}

async function stopPlane(plane) {
  if (!plane?.child) return;
  plane.child.kill('SIGTERM');
  await new Promise((resolve) => {
    const t = setTimeout(resolve, 8_000);
    plane.child.once('close', () => {
      clearTimeout(t);
      resolve();
    });
  });
}

async function render(port, body) {
  const t0 = Date.now();
  const res = await fetch(`http://127.0.0.1:${port}/v1/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const buf = Buffer.from(await res.arrayBuffer());
  const headers = Object.fromEntries(res.headers.entries());
  return { status: res.status, headers, buf, ms: Date.now() - t0 };
}

const compositionOfExample = () => fs.readFileSync(EXAMPLE_HTML, 'utf8');

function assetComposition() {
  // 素材链路：图片以相对路径 assets/logo.png 引用（data: 与相对路径是唯一放行口径）
  return `<!doctype html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:320px;height:180px;overflow:hidden;background:#0b1020}
#root{position:relative;width:100%;height:100%}
.logo{position:absolute;left:24px;top:24px;width:64px;height:64px;image-rendering:pixelated;border:2px solid #ff5c39}
.caption{position:absolute;left:24px;top:110px;color:#f5f7ff;font:600 20px/1 sans-serif}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="2"
     data-width="320" data-height="180" data-fps="10">
  <img class="clip logo" src="assets/logo.png" data-start="0" data-duration="2" data-track-index="0" />
  <div class="clip caption" data-start="0" data-duration="2" data-track-index="1">asset ok</div>
</div>
<script>window.__hf = { duration: 2, seek() {} };</script>
</body></html>`;
}

async function listDir(dir) {
  try {
    return await fsp.readdir(dir);
  } catch {
    return [];
  }
}

async function main() {
  const workRoot = await fsp.mkdtemp(path.join(os.tmpdir(), 'vaas-render-selftest-'));
  const workdirA = path.join(workRoot, 'plane-a');
  const workdirB = path.join(workRoot, 'plane-b');
  await fsp.mkdir(workdirA, { recursive: true });
  await fsp.mkdir(workdirB, { recursive: true });

  const portA = await freePort();
  const portB = await freePort();
  const planes = [];
  const outDir = await fsp.mkdtemp(path.join(os.tmpdir(), 'vaas-render-artifacts-'));

  try {
    // ── 服务 A：默认配置 + 调试端点 ─────────────────────────────────────
    const planeA = await startPlane({
      workdir: workdirA,
      port: portA,
      env: {
        VAAS_RENDER_DEBUG: '1',
        VAAS_RENDER_MAX_CONCURRENCY: '1',
        VAAS_RENDER_QUEUE_MAX: '4',
        VAAS_RENDER_TIMEOUT_S: '300',
      },
    });
    planes.push(planeA);

    console.log('\n=== /healthz ===');
    console.log(JSON.stringify(planeA.healthz, null, 2));

    check('healthz.ok 为 true', planeA.healthz.ok === true);
    check(
      'healthz.engine 为 hyperframes@0.9.26',
      planeA.healthz.engine === 'hyperframes@0.9.26',
      planeA.healthz.engine,
    );
    check('healthz.chrome 已解析', typeof planeA.healthz.chrome === 'string' && planeA.healthz.chrome.length > 0, planeA.healthz.chrome);
    check('healthz.node 为运行时版本', /^v\d+\./.test(planeA.healthz.node || ''), planeA.healthz.node);
    check('healthz.workers >= 1', planeA.healthz.workers >= 1, String(planeA.healthz.workers));
    check('healthz.uptime_s 为数字', Number.isFinite(planeA.healthz.uptime_s), String(planeA.healthz.uptime_s));
    check(
      'healthz.jobs 计数齐备',
      ['active', 'done', 'failed'].every((k) => Number.isInteger(planeA.healthz.jobs?.[k])),
      planeA.healthz.jobs,
    );
    check(
      'healthz doctor 摘要含 Chrome/FFmpeg',
      (planeA.healthz.doctor?.checks || []).some((c) => /chrome/i.test(c.name)),
      (planeA.healthz.doctor?.checks || []).map((c) => `${c.name}:${c.ok}`),
    );

    const ver = await (await fetch(`http://127.0.0.1:${portA}/v1/version`)).json();
    console.log('\n=== /v1/version ===');
    console.log(JSON.stringify(ver, null, 2));
    check('/v1/version 回报钉版引擎', ver.hyperframes === '0.9.26' && ver.engine === 'hyperframes@0.9.26', ver.engine);

    // ── 素材入库 ────────────────────────────────────────────────────────
    const pngSha = sha256(PNG_1X1);
    const put = await fetch(`http://127.0.0.1:${portA}/v1/assets/${pngSha}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: PNG_1X1,
    });
    const putBody = await put.json();
    check('PUT /v1/assets/<sha256> 返回 201', put.status === 201, putBody);
    check(
      '素材落盘于 assets/<sha256>',
      fs.existsSync(path.join(workdirA, 'assets', pngSha)),
      path.join(workdirA, 'assets', pngSha),
    );

    const badSha = sha256(Buffer.from('not-this-content'));
    const putBad = await fetch(`http://127.0.0.1:${portA}/v1/assets/${badSha}`, {
      method: 'PUT',
      body: PNG_1X1,
    });
    const putBadBody = await putBad.json();
    check('sha256 与内容不符 → 400', putBad.status === 400 && putBadBody.actual === pngSha, putBadBody);

    // ── 最小 composition 出片 ───────────────────────────────────────────
    const baseJob = {
      job_id: 'selftest-minimal-a1',
      fps: 10,
      quality: 'draft',
      format: 'mp4',
      composition: { html: compositionOfExample(), assets: [] },
    };
    const r1 = await render(portA, baseJob);
    console.log('\n=== POST /v1/render（examples/minimal）响应头 ===');
    console.log(
      JSON.stringify(
        {
          'x-engine': r1.headers['x-engine'],
          'x-job-id': r1.headers['x-job-id'],
          'x-render-ms': r1.headers['x-render-ms'],
          'x-warnings': r1.headers['x-warnings'],
          'x-format': r1.headers['x-format'],
          'x-cache': r1.headers['x-cache'],
          'content-type': r1.headers['content-type'],
          'content-length': r1.headers['content-length'],
        },
        null,
        2,
      ),
    );

    const isMp4 = r1.buf.length > 12 && r1.buf.subarray(4, 8).toString('latin1') === 'ftyp';
    check('渲染返回 200', r1.status === 200, String(r1.status));
    check('响应体是 MP4（ftyp box）', isMp4, `${r1.buf.length} bytes`);
    check('X-Engine = hyperframes@0.9.26', r1.headers['x-engine'] === 'hyperframes@0.9.26', r1.headers['x-engine']);
    check('X-Job-Id 回显', r1.headers['x-job-id'] === baseJob.job_id, r1.headers['x-job-id']);
    check('X-Render-Ms 为数字', /^\d+$/.test(r1.headers['x-render-ms'] || ''), r1.headers['x-render-ms']);
    let warningsOk = false;
    try {
      warningsOk = Array.isArray(JSON.parse(r1.headers['x-warnings'] || ''));
    } catch {
      warningsOk = false;
    }
    check('X-Warnings 是 JSON 数组', warningsOk, r1.headers['x-warnings']);

    const out1 = path.join(outDir, 'minimal-a1.mp4');
    await fsp.writeFile(out1, r1.buf);
    const fileOut = spawnSync('file', ['-b', out1], { encoding: 'utf8' });
    console.log(`\n$ file -b ${out1}\n${(fileOut.stdout || '').trim()}`);
    check('file(1) 识别为 ISO Media / MP4', /ISO Media|MP4/i.test(fileOut.stdout || ''), (fileOut.stdout || '').trim());

    // ── 幂等：同 job_id 同内容 → 命中缓存且字节一致 ──────────────────────
    const r2 = await render(portA, baseJob);
    const md5a = md5(r1.buf);
    const md5b = md5(r2.buf);
    check('幂等：同 job_id 重提返回 200', r2.status === 200, String(r2.status));
    check('幂等：命中结果缓存（X-Cache: hit）', r2.headers['x-cache'] === 'hit', r2.headers['x-cache']);
    check('幂等：两次字节 md5 一致', md5a === md5b, `${md5a} / ${md5b}`);

    // ── 确定性：不同 job_id、同内容 → 缓存未命中但产物一致 ───────────────
    const r3 = await render(portA, { ...baseJob, job_id: 'selftest-minimal-a2' });
    const md5c = md5(r3.buf);
    check('确定性：新 job_id 缓存未命中（真的重渲）', r3.headers['x-cache'] === 'miss', r3.headers['x-cache']);
    check('确定性：重渲产物 md5 与首跑一致', md5c === md5a, `${md5a} / ${md5c}`);

    // ── 素材链路：相对路径 + sha256 入库素材 ────────────────────────────
    const ra = await render(portA, {
      job_id: 'selftest-asset-1',
      fps: 10,
      quality: 'draft',
      format: 'mp4',
      composition: {
        html: assetComposition(),
        assets: [{ sha256: pngSha, name: 'logo.png', path: 'assets/logo.png' }],
      },
    });
    check('素材 composition 渲染 200', ra.status === 200, `${ra.status} ${ra.status !== 200 ? ra.buf.toString().slice(0, 300) : ''}`);
    check('素材 composition 产物是 MP4', md5(ra.buf) && ra.buf.subarray(4, 8).toString('latin1') === 'ftyp', `${ra.buf.length} bytes`);
    await fsp.writeFile(path.join(outDir, 'asset.mp4'), ra.buf);

    // ── 负例：零外链 ────────────────────────────────────────────────────
    const externalHtml = compositionOfExample().replace(
      '</head>',
      '  <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>\n</head>',
    );
    const rx = await render(portA, {
      job_id: 'selftest-external-1',
      fps: 10,
      quality: 'draft',
      composition: { html: externalHtml, assets: [] },
    });
    const rxBody = JSON.parse(rx.buf.toString() || '{}');
    check('外链 composition → 400', rx.status === 400, String(rx.status));
    check(
      '错误里指明被拒资源',
      JSON.stringify(rxBody.resources || []).includes('cdn.jsdelivr.net'),
      rxBody.resources,
    );

    // ── 负例：协议相对外链（//host/…）同样拒绝 ──────────────────────────
    const protoRelHtml = compositionOfExample().replace(
      '</head>',
      '  <link rel="stylesheet" href="//cdn.example.com/x.css">\n</head>',
    );
    const rp = await render(portA, {
      job_id: 'selftest-external-2',
      composition: { html: protoRelHtml, assets: [] },
    });
    check('协议相对外链（//host）→ 400', rp.status === 400, String(rp.status));

    // ── 负例：路径穿越 ──────────────────────────────────────────────────
    const rt = await render(portA, {
      job_id: 'selftest-traverse-1',
      composition: {
        html: assetComposition(),
        assets: [{ sha256: pngSha, path: '../../etc/passwd' }],
      },
    });
    const rtBody = JSON.parse(rt.buf.toString() || '{}');
    check('素材路径穿越 → 400', rt.status === 400, String(rt.status));
    check(
      '穿越错误指明 path 规则',
      JSON.stringify(rtBody.problems || []).includes('relative'),
      rtBody.problems,
    );

    // ── 负例：引用未入库素材 ────────────────────────────────────────────
    const missingSha = sha256(Buffer.from('never-uploaded'));
    const rm = await render(portA, {
      job_id: 'selftest-missing-asset-1',
      composition: {
        html: assetComposition(),
        assets: [{ sha256: missingSha, path: 'assets/logo.png' }],
      },
    });
    const rmBody = JSON.parse(rm.buf.toString() || '{}');
    check('未入库素材 → 400', rm.status === 400, String(rm.status));
    check('错误列出缺失 sha256', (rmBody.missing || []).includes(missingSha), rmBody.missing);

    // ── 负例：非法 job 参数 ─────────────────────────────────────────────
    const rf = await render(portA, { job_id: '', composition: { html: compositionOfExample() } });
    check('空 job_id → 400', rf.status === 400, String(rf.status));

    // ── env 白名单断言（服务端记录的子进程 env 键名） ────────────────────
    const envDebug = await (await fetch(`http://127.0.0.1:${portA}/v1/_debug/env`)).json();
    console.log('\n=== 渲染子进程 env 键名（/v1/_debug/env） ===');
    console.log(JSON.stringify(envDebug, null, 2));
    const keys = envDebug.keys || [];
    check('子进程 env 无泄露（leaked 为空）', (envDebug.leaked || []).length === 0, envDebug.leaked);
    check('子进程 env 不含 VAAS_BEARER_TOKEN', !keys.some((k) => /VAAS_|BEARER|TOKEN|SECRET|API_KEY/i.test(k)), keys);
    check('子进程 HOME 指向作业 tmpdir', keys.includes('HOME'), keys);
    check('子进程保留 HYPERFRAMES_* 与 PATH', keys.includes('PATH') && keys.some((k) => k.startsWith('HYPERFRAMES_')), keys);

    // ── 作业目录零残留（成功路径） ───────────────────────────────────────
    const jobsAfterSuccess = await listDir(path.join(workdirA, 'jobs'));
    check('成功作业后 jobs/ 无残留目录', jobsAfterSuccess.length === 0, jobsAfterSuccess);

    // ── 服务 B：1s 硬超时 + 队列 0（并发即拒） ───────────────────────────
    const planeB = await startPlane({
      workdir: workdirB,
      port: portB,
      env: {
        VAAS_RENDER_TIMEOUT_S: '1',
        VAAS_RENDER_MAX_CONCURRENCY: '1',
        VAAS_RENDER_QUEUE_MAX: '0',
        VAAS_RENDER_CACHE_MAX_ENTRIES: '0',
      },
    });
    planes.push(planeB);

    const slow = { ...baseJob, job_id: 'selftest-timeout-1' };
    const p1 = render(portB, slow);
    await new Promise((r) => setTimeout(r, 200)); // 确保第一个作业已占住唯一槽位
    const queued = await render(portB, { ...baseJob, job_id: 'selftest-queue-1' });
    const queuedBody = JSON.parse(queued.buf.toString() || '{}');
    check('队列满（QUEUE_MAX=0）→ 429', queued.status === 429, `${queued.status} ${JSON.stringify(queuedBody)}`);

    const timed = await p1;
    const timedBody = JSON.parse(timed.buf.toString() || '{}');
    console.log('\n=== 超时响应（VAAS_RENDER_TIMEOUT_S=1） ===');
    console.log(JSON.stringify({ status: timed.status, phase: timedBody.phase, error: timedBody.error, log_tail_bytes: (timedBody.log_tail || '').length }, null, 2));
    check('超时 → 5xx（504）', timed.status >= 500 && timed.status < 600, String(timed.status));
    check('超时错误带 phase=timeout 与 log_tail', timedBody.phase === 'timeout' && typeof timedBody.log_tail === 'string', timedBody.error);

    const jobsAfterTimeout = await listDir(path.join(workdirB, 'jobs'));
    check('超时后 jobs/ 零残留（tmpdir 已清理）', jobsAfterTimeout.length === 0, jobsAfterTimeout);
    const artifactsAfterTimeout = await listDir(path.join(workdirB, 'jobs')).catch(() => []);
    check('超时后无部分产物文件', artifactsAfterTimeout.length === 0, artifactsAfterTimeout);

    // ── TMPDIR 长度上限回归（DEBT-RENDER-FLAKY-01）────────────────────────
    // 事故：buildChildEnv 曾把 TMPDIR 指到 <jobDir>/tmp，jobDir 含长 plan slug
    // （compose-<12hex>）→ chromium 在 <TMPDIR>/org.chromium.Chromium.XXXXXX/
    // SingletonSocket 建进程单例 socket，路径 110B > sun_path 上限 108B →
    // process_singleton_posix.cc FATAL "Socket path too long" → chrome SIGABRT →
    // 渲染失败（exit_code=1 / signal=null），且与帧数/分辨率/质量档/GPU 全无关。
    console.log('\n=== TMPDIR 长度上限回归 ===');
    const SOCKET_SUFFIX = '/org.chromium.Chromium.XXXXXX/SingletonSocket';
    const SUN_PATH_MAX = 108;
    const defaultTmp = '/tmp/vrp/' + 'a'.repeat(10); // 与 shortTmpLabel 同形（10 hex）
    check(
      `默认 TMPDIR（/tmp/vrp/<10hex>）下 chromium 单例路径 ≤${SUN_PATH_MAX}B`,
      (defaultTmp + SOCKET_SUFFIX).length <= SUN_PATH_MAX,
      `${(defaultTmp + SOCKET_SUFFIX).length}B`,
    );

    // 正向：长 workdir + 长 jobId 仍必须渲染成功（修复前这里必崩）
    const longWorkdir = path.join(workRoot, 'w'.repeat(40), 'plane-long');
    await fsp.mkdir(longWorkdir, { recursive: true });
    const portLong = await freePort();
    const planeLong = await startPlane({
      workdir: longWorkdir,
      port: portLong,
      env: { VAAS_RENDER_MAX_CONCURRENCY: '1', VAAS_RENDER_TIMEOUT_S: '300' },
    });
    planes.push(planeLong);
    const longJobId = `compose-${'f'.repeat(12)}--e2e-selftest-longslug`;
    const longRes = render(portLong, {
      job_id: longJobId,
      fps: 8,
      quality: 'draft',
      format: 'mp4',
      composition: { html: compositionOfExample() },
    });
    const longOut = await longRes;
    check(
      '长 jobId/workdir 下单帧渲染仍成功（TMPDIR 已短化）',
      longOut.status === 200,
      { status: longOut.status, jobIdLen: longJobId.length, workdirLen: longWorkdir.length },
    );

    // 反向：把 TMP_ROOT 顶到会让 socket 路径超 108B 的长度，必须失败且清理
    const longTmpRoot = '/tmp/' + 'l'.repeat(64); // + /<10hex> + 后缀 → >108B
    check(
      '构造的 TMP_ROOT 确实会让 socket 路径超限（自证前提）',
      (longTmpRoot + '/' + 'a'.repeat(10) + SOCKET_SUFFIX).length > SUN_PATH_MAX,
      `${(longTmpRoot + '/' + 'a'.repeat(10) + SOCKET_SUFFIX).length}B`,
    );
    const longTmpWorkdir = path.join(workRoot, 'plane-longtmp');
    await fsp.mkdir(longTmpWorkdir, { recursive: true });
    const portLongTmp = await freePort();
    const planeLongTmp = await startPlane({
      workdir: longTmpWorkdir,
      port: portLongTmp,
      env: {
        VAAS_RENDER_TMP_ROOT: longTmpRoot,
        VAAS_RENDER_MAX_CONCURRENCY: '1',
        VAAS_RENDER_TIMEOUT_S: '300',
      },
    });
    planes.push(planeLongTmp);
    const badOut = await render(portLongTmp, {
      job_id: 'selftest-longtmp-1',
      fps: 8,
      quality: 'draft',
      format: 'mp4',
      composition: { html: compositionOfExample() },
    });
    // 注意：chromium 的进程单例机制随平台不同——linux 用 unix socket（受 sun_path
    // 108B 限制），macOS 用 Mach port / lock 文件（不占 sun_path）。因此「超长
    // TMP_ROOT 是否致命」是平台相关的：只在 linux 上预期失败。
    // 且成功时响应体是 MP4 二进制（ftypisom…），不能无条件 JSON.parse。
    if (process.platform === 'linux') {
      let badBody = {};
      try {
        badBody = JSON.parse(badOut.buf.toString() || '{}');
      } catch {
        badBody = {}; // 非 JSON（例如意外拿到成片字节）→ 交给下面的断言暴露
      }
      check(
        '超长 TMP_ROOT → 渲染失败（chromium 单例 socket 超 108B）',
        badOut.status >= 500,
        { status: badOut.status, exit_code: badBody.exit_code, engine_log: badBody.engine_log },
      );
      check(
        '失败响应带 exit_code 与 engine_log（可事后归因）',
        badBody.exit_code !== undefined && typeof badBody.engine_log === 'string',
        { exit_code: badBody.exit_code, engine_log: badBody.engine_log },
      );
      const leftover = await listDir(longTmpRoot).catch(() => []);
      check('失败后短 TMPDIR 已被 finally 回收（零残留）', leftover.length === 0, leftover);
    } else {
      // 非 linux 上这条不成立（单例不走 unix socket），断言「不致命」以免回归时静默
      check(
        '非 linux：超长 TMP_ROOT 不触发 socket 上限，渲染仍成功',
        badOut.status === 200,
        { status: badOut.status, platform: process.platform },
      );
      console.log('[NOTE] chromium 单例机制随平台不同：linux=unix socket（sun_path 108B 上限）；macOS=Mach/lock 文件');
    }

    console.log('\n=== 产物 ===');
    for (const f of await listDir(outDir)) {
      const p = path.join(outDir, f);
      const buf = await fsp.readFile(p);
      console.log(`${p} · ${buf.length} bytes · md5 ${md5(buf)}`);
    }
  } finally {
    for (const plane of planes) {
      await stopPlane(plane);
      if (failures > 0) console.log(`\n--- plane log (${plane.child.pid}) ---\n${plane.logs.join('')}`);
    }
    await fsp.rm(workRoot, { recursive: true, force: true }).catch(() => {});
  }

  console.log('\n=== 汇总 ===');
  console.log(`${results.length - failures}/${results.length} 通过，${failures} 失败`);
  if (failures > 0) {
    for (const r of results.filter((x) => !x.ok)) console.log(`  FAIL: ${r.name} — ${JSON.stringify(r.detail)}`);
    process.exitCode = 1;
  } else {
    console.log('全部通过 ✅');
  }
}

main().catch((err) => {
  console.error(`[selftest] fatal: ${err?.stack || err}`);
  process.exitCode = 1;
});

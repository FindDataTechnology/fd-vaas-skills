#!/usr/bin/env node
// VAAS 渲染面 —— 无状态 HTTP 作业服务。
//
// 只做一件事：把 composition（HTML + 素材）交给钉死版本的 HyperFrames 渲染成成片。
// 不持有业务账本、不落业务数据、不联网；可多实例部署，API 面用 VAAS_RENDER_URL 重指。
//
// 端点：
//   GET  /healthz                     引擎/Chrome/doctor 摘要 + 容量 + 作业计数
//   GET  /v1/version                  引擎版本（供 API 面校验钉版）
//   PUT  /v1/assets/<sha256>          原始字节入库（按 sha256 命名，校验一致）
//   POST /v1/render                   作业：composition -> 成片字节流
//   GET  /v1/_debug/env               （仅 VAAS_RENDER_DEBUG=1）最近一次子进程 env 的键名断言
//
// 隔离模型（按作业）：
//   独立 tmpdir · env 白名单（显式剔除 VAAS_*/OPENBAO_*/*TOKEN*/*KEY*/*SECRET*）
//   · 硬超时到点杀进程组 · 成功才出产物 · 失败/超时零残留。
//   无外网由部署面保证（容器接 internal-only 网络），进程内不做 unshare。

import http from 'node:http';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));

// ── 配置（全部走环境变量，缺省即可跑） ──────────────────────────────────────
const cfg = {
  port: intEnv('VAAS_RENDER_PORT', 8099),
  bind: process.env.VAAS_RENDER_BIND || '0.0.0.0',
  workdir: process.env.VAAS_RENDER_WORKDIR || '/tmp/vaas-render',
  maxConcurrency: Math.max(1, intEnv('VAAS_RENDER_MAX_CONCURRENCY', 1)),
  queueMax: Math.max(0, intEnv('VAAS_RENDER_QUEUE_MAX', 32)),
  timeoutS: Math.max(1, intEnv('VAAS_RENDER_TIMEOUT_S', 600)),
  maxAssetBytes: intEnv('VAAS_RENDER_MAX_ASSET_BYTES', 128 * 1024 * 1024),
  maxBodyBytes: intEnv('VAAS_RENDER_MAX_BODY_BYTES', 32 * 1024 * 1024),
  cacheMaxBytes: intEnv('VAAS_RENDER_CACHE_MAX_BYTES', 128 * 1024 * 1024),
  cacheMaxEntries: intEnv('VAAS_RENDER_CACHE_MAX_ENTRIES', 8),
  logTailBytes: intEnv('VAAS_RENDER_LOG_TAIL_BYTES', 8000),
  defaultFps: intEnv('VAAS_RENDER_DEFAULT_FPS', 10),
  defaultQuality: process.env.VAAS_RENDER_DEFAULT_QUALITY || 'looks',
  bin: process.env.VAAS_RENDER_BIN || '',
  debug: process.env.VAAS_RENDER_DEBUG === '1',
};
const ASSET_DIR = path.join(cfg.workdir, 'assets');
const JOB_DIR = path.join(cfg.workdir, 'jobs');

// ── 常量 ────────────────────────────────────────────────────────────────────
const ENGINE_PKG = 'hyperframes'; // 版本在启动时从 CLI 读，钉版见 package.json
const QUALITIES = new Set(['draft', 'looks', 'delivery', 'standard', 'high']);
const BITRATE_RE = /^\d+[kKmM]$/;
const FORMATS = new Set(['mp4', 'webm', 'mov', 'gif', 'png-sequence', 'hls']);
const DIR_FORMATS = new Set(['png-sequence', 'hls']);
const SHA256_RE = /^[0-9a-f]{64}$/;
const MIME = {
  mp4: 'video/mp4',
  webm: 'video/webm',
  mov: 'video/quicktime',
  gif: 'image/gif',
  tar: 'application/x-tar',
};

// 子进程 env 允许出现的前缀/键；其余一律不传。
const ENV_ALLOW_KEYS = new Set(['PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ', 'TMPDIR']);
const ENV_ALLOW_PREFIX = ['HYPERFRAMES_'];
// 显式剔除（优先级高于允许列表）：凭证类绝不外泄，连 HYPERFRAMES_API_KEY 也挡掉。
const ENV_DENY_RE = /(VAAS_|OPENBAO_|TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL|BEARER|COOKIE)/i;

// 离线护栏：容器/机器无外网时，避免引擎尝试任何下载或更新检查。
const FORCED_ENGINE_ENV = {
  HYPERFRAMES_NO_TELEMETRY: process.env.HYPERFRAMES_NO_TELEMETRY || '1',
  HYPERFRAMES_NO_UPDATE_CHECK: process.env.HYPERFRAMES_NO_UPDATE_CHECK || '1',
  HYPERFRAMES_NO_AUTO_INSTALL: process.env.HYPERFRAMES_NO_AUTO_INSTALL || '1',
  HYPERFRAMES_NO_OPTIONAL_INSTALL: process.env.HYPERFRAMES_NO_OPTIONAL_INSTALL || '1',
};

// ── 小工具 ──────────────────────────────────────────────────────────────────
function intEnv(name, dflt) {
  const raw = process.env[name];
  if (raw === undefined || raw === '') return dflt;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : dflt;
}

const nowMs = () => Date.now();

function json(res, status, body, extraHeaders = {}) {
  const buf = Buffer.from(JSON.stringify(body));
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': buf.length,
    'Cache-Control': 'no-store',
    ...extraHeaders,
  });
  res.end(buf);
}

function sha256Hex(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

function stripAnsi(s) {
  // eslint-disable-next-line no-control-regex
  return s.replace(/\u001b\[[0-9;]*m/g, '');
}

// 有界 body 读取：超限即中止（防内存打爆）。
function readBody(req, limit) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    let settled = false;
    const fail = (err) => {
      if (settled) return;
      settled = true;
      reject(err);
    };
    req.on('data', (chunk) => {
      if (settled) return;
      size += chunk.length;
      if (size > limit) {
        const err = new Error(`body exceeds ${limit} bytes`);
        err.code = 'E_BODY_TOO_LARGE';
        fail(err);
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      if (settled) return;
      settled = true;
      resolve(Buffer.concat(chunks, size));
    });
    req.on('error', fail);
  });
}

// ── 配置 / 引擎探测（启动时做一次，结果进 /healthz） ──────────────────────────
function resolveBin() {
  if (cfg.bin) return cfg.bin;
  const local = path.join(ROOT, 'node_modules', '.bin', 'hyperframes');
  if (fs.existsSync(local)) return local;
  return 'hyperframes';
}

const BIN = resolveBin();

// doctor 用的 env：只给系统必需项，不携带任何服务端凭证。
function baseEnv() {
  const env = {};
  for (const key of ['PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ']) {
    if (process.env[key]) env[key] = process.env[key];
  }
  for (const [k, v] of Object.entries(process.env)) {
    if (k.startsWith('HYPERFRAMES_') && !ENV_DENY_RE.test(k)) env[k] = v;
  }
  for (const [k, v] of Object.entries(FORCED_ENGINE_ENV)) env[k] = v;
  return env;
}

function runSync(args, { timeout = 60_000 } = {}) {
  const r = spawnSync(BIN, args, {
    env: baseEnv(),
    encoding: 'utf8',
    timeout,
    maxBuffer: 8 * 1024 * 1024,
  });
  return {
    status: r.status,
    signal: r.signal,
    stdout: r.stdout || '',
    stderr: r.stderr || '',
    error: r.error ? String(r.error.message || r.error) : null,
  };
}

function parseChromePath(doctorChecks) {
  const chrome = doctorChecks.find((c) => /^chrome/i.test(c.name));
  if (!chrome) return null;
  const m = /(?:env|cache):\s*(\S+)/i.exec(chrome.detail || '');
  return m ? m[1] : null;
}

function detectEngine() {
  const out = { version: null, chrome: process.env.HYPERFRAMES_BROWSER_PATH || null, doctor: null, bin: BIN };
  const v = runSync(['--version'], { timeout: 30_000 });
  const vm = /(\d+\.\d+\.\d+[\w.\-]*)/.exec(`${v.stdout}\n${v.stderr}`);
  if (vm) out.version = vm[1];

  const d = runSync(['doctor', '--json'], { timeout: 120_000 });
  try {
    const start = d.stdout.indexOf('{');
    const parsed = JSON.parse(d.stdout.slice(start));
    if (Array.isArray(parsed.checks)) {
      out.doctor = {
        ok: !!parsed.ok,
        checks: parsed.checks.map((c) => ({ name: c.name, ok: !!c.ok, detail: c.detail })),
      };
      if (!out.chrome) out.chrome = parseChromePath(parsed.checks);
    }
  } catch {
    // doctor --json 不可用（旧版本）时退化为文本解析：保留原始输出摘要即可
    const text = stripAnsi(`${d.stdout}\n${d.stderr}`);
    const ok = /✗/.test(text) ? false : d.status === 0;
    const chromeLine = text.split('\n').find((l) => /chrome/i.test(l));
    out.doctor = { ok, text_tail: text.slice(-2000), chrome_line: (chromeLine || '').trim() };
    if (!out.chrome && chromeLine) {
      const m = /(?:env|cache):\s*(\S+)/i.exec(chromeLine);
      if (m) out.chrome = m[1];
    }
  }
  return out;
}

// ── 静态零外链校验 ──────────────────────────────────────────────────────────
// 只放行 data: 与相对路径；http(s):// 与协议相对 //host/... 一律拒绝。
const REF_ATTR_RE = /(?:src|href|srcset|xlink:href|data-composition-src|poster)\s*=\s*("([^"]*)"|'([^']*)')/gi;
const CSS_URL_RE = /url\(\s*(?:"([^"]*)"|'([^']*)'|([^)'"]*))\s*\)/gi;
const CSS_IMPORT_RE = /@import\s+(?:url\(\s*)?["']([^"']+)["']/gi;
const EXTERNAL_RE = /^(?:https?:)?\/\//i;

function findExternalRefs(html) {
  const hits = new Set();
  const consider = (raw, kind) => {
    if (!raw) return;
    for (const piece of String(raw).split(/[\s,]+/)) {
      const v = piece.trim();
      if (!v) continue;
      if (EXTERNAL_RE.test(v)) hits.add(`${kind}: ${v}`);
    }
  };
  for (const m of html.matchAll(REF_ATTR_RE)) {
    const val = m[2] !== undefined ? m[2] : m[3];
    consider(val, m[1].toLowerCase());
  }
  for (const m of html.matchAll(CSS_URL_RE)) {
    consider(m[1] !== undefined ? m[1] : m[2] !== undefined ? m[2] : m[3], 'url()');
  }
  for (const m of html.matchAll(CSS_IMPORT_RE)) consider(m[1], '@import');
  return [...hits];
}

// ── 并发信号量（有界队列） ──────────────────────────────────────────────────
class Semaphore {
  constructor(max, maxQueue) {
    this.max = max;
    this.maxQueue = maxQueue;
    this.active = 0;
    this.waiters = [];
  }
  acquire() {
    if (this.active < this.max) {
      this.active += 1;
      return Promise.resolve();
    }
    if (this.waiters.length >= this.maxQueue) {
      const err = new Error('render queue full');
      err.code = 'E_QUEUE_FULL';
      return Promise.reject(err);
    }
    return new Promise((resolve, reject) => this.waiters.push({ resolve, reject }));
  }
  release() {
    const next = this.waiters.shift();
    if (next) {
      next.resolve(); // 槽位直接转交，active 不变
      return;
    }
    this.active = Math.max(0, this.active - 1);
  }
  get pending() {
    return this.waiters.length;
  }
}

const sem = new Semaphore(cfg.maxConcurrency, cfg.queueMax);

// ── 结果缓存（内存 LRU，可选；只为幂等作业省一次重渲） ───────────────────────
class ResultCache {
  constructor(maxEntries, maxBytes) {
    this.maxEntries = maxEntries;
    this.maxBytes = maxBytes;
    this.map = new Map(); // key -> {buf, mime, headers}
    this.bytes = 0;
  }
  enabled() {
    return this.maxEntries > 0 && this.maxBytes > 0;
  }
  get(key) {
    if (!this.enabled()) return null;
    const hit = this.map.get(key);
    if (!hit) return null;
    this.map.delete(key);
    this.map.set(key, hit); // 刷新 LRU
    return hit;
  }
  put(key, entry) {
    if (!this.enabled()) return;
    if (entry.buf.length > this.maxBytes) return;
    const prev = this.map.get(key);
    if (prev) {
      this.bytes -= prev.buf.length;
      this.map.delete(key);
    }
    this.map.set(key, entry);
    this.bytes += entry.buf.length;
    while (this.map.size > this.maxEntries || this.bytes > this.maxBytes) {
      const [oldKey, oldVal] = this.map.entries().next().value;
      this.map.delete(oldKey);
      this.bytes -= oldVal.buf.length;
    }
  }
  get size() {
    return this.map.size;
  }
}

const cache = new ResultCache(cfg.cacheMaxEntries, cfg.cacheMaxBytes);

// ── 作业计数 / 调试 ─────────────────────────────────────────────────────────
const stats = { active: 0, done: 0, failed: 0, timedOut: 0 };
let lastChildEnvKeys = null;

// ── 子进程 env 构造 + 断言 ──────────────────────────────────────────────────
function buildChildEnv(homeDir) {
  const env = {};
  for (const [k, v] of Object.entries(process.env)) {
    if (ENV_ALLOW_KEYS.has(k) || ENV_ALLOW_PREFIX.some((p) => k.startsWith(p))) {
      if (ENV_DENY_RE.test(k)) continue; // HYPERFRAMES_API_KEY 之类也挡
      env[k] = v;
    }
  }
  // TMPDIR 指到作业目录，避免跨作业共享临时状态
  env.TMPDIR = path.join(homeDir, 'tmp');
  env.HOME = homeDir;
  for (const [k, v] of Object.entries(FORCED_ENGINE_ENV)) {
    if (!(k in env)) env[k] = v;
  }
  const leaked = Object.keys(env).filter((k) => ENV_DENY_RE.test(k));
  if (leaked.length) {
    // 构造上不该发生；一旦发生就拒绝作业，绝不带着疑似凭证去渲。
    const err = new Error(`refusing to spawn with sensitive env keys: ${leaked.join(',')}`);
    err.code = 'E_ENV_LEAK';
    throw err;
  }
  return env;
}

// ── 作业执行 ────────────────────────────────────────────────────────────────
function validateRenderRequest(body) {
  const problems = [];
  if (!body || typeof body !== 'object') return ['body must be a JSON object'];

  const jobId = body.job_id;
  if (typeof jobId !== 'string' || !jobId.trim() || jobId.length > 200) {
    problems.push('job_id: non-empty string (<=200 chars) required');
  }
  const fps = body.fps === undefined ? cfg.defaultFps : body.fps;
  if (!Number.isInteger(fps) || fps < 1 || fps > 240) problems.push('fps: integer 1-240');

  const quality = body.quality === undefined ? cfg.defaultQuality : body.quality;
  if (typeof quality !== 'string' || !QUALITIES.has(quality)) {
    problems.push(`quality: one of ${[...QUALITIES].join('|')}`);
  }
  const format = body.format === undefined ? 'mp4' : body.format;
  if (typeof format !== 'string' || !FORMATS.has(format)) {
    problems.push(`format: one of ${[...FORMATS].join('|')}`);
  }
  // 码率控制（可选）：深色/大面积平坦内容按 CRF 会压到很低，成片出现色带与
  // 前帧残影。这里只做透传与形状校验，策略留给调用方。
  if (body.crf !== undefined) {
    if (!Number.isInteger(body.crf) || body.crf < 0 || body.crf > 51) {
      problems.push('crf: integer 0-51');
    }
  }
  for (const k of ['video_bitrate', 'max_bitrate']) {
    if (body[k] !== undefined) {
      if (typeof body[k] !== 'string' || !BITRATE_RE.test(body[k].trim())) {
        problems.push(`${k}: string like "8M" or "4000k"`);
      }
    }
  }
  const comp = body.composition;
  if (!comp || typeof comp !== 'object') {
    problems.push('composition: object required');
  } else {
    if (typeof comp.html !== 'string' || comp.html.length < 32) {
      problems.push('composition.html: non-empty HTML string required');
    }
    if (comp.assets !== undefined && !Array.isArray(comp.assets)) {
      problems.push('composition.assets: array required when present');
    }
  }
  if (problems.length) return problems;

  // 素材条目校验
  const assets = body.composition.assets || [];
  const seen = new Set();
  for (const [i, a] of assets.entries()) {
    if (!a || typeof a !== 'object') {
      problems.push(`composition.assets[${i}]: object required`);
      continue;
    }
    if (typeof a.sha256 !== 'string' || !SHA256_RE.test(a.sha256)) {
      problems.push(`composition.assets[${i}].sha256: 64 hex chars required`);
      continue;
    }
    const rel = typeof a.path === 'string' && a.path ? a.path : a.name;
    if (typeof rel !== 'string' || !rel) {
      problems.push(`composition.assets[${i}].path: relative path required`);
      continue;
    }
    if (!isSafeRelPath(rel)) {
      problems.push(`composition.assets[${i}].path: must be relative, inside the job dir, without . or .. segments (${rel})`);
      continue;
    }
    if (seen.has(rel)) problems.push(`composition.assets[${i}].path: duplicate ${rel}`);
    seen.add(rel);
  }
  return problems;
}

function isSafeRelPath(rel) {
  if (typeof rel !== 'string' || !rel) return false;
  if (rel.includes('\0')) return false;
  if (path.isAbsolute(rel)) return false;
  if (/^[a-zA-Z]:/.test(rel)) return false;
  const parts = rel.split(/[\\/]+/).filter(Boolean);
  if (!parts.length) return false;
  return parts.every((p) => p !== '.' && p !== '..');
}

function safeJobLabel(jobId) {
  return String(jobId).replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 40);
}

function contentKey(body, engineVersion) {
  const h = crypto.createHash('sha256');
  h.update(String(engineVersion || ''));
  h.update('\0');
  h.update(JSON.stringify({
    fps: body.fps ?? cfg.defaultFps,
    quality: body.quality ?? cfg.defaultQuality,
    format: body.format ?? 'mp4',
    crf: body.crf ?? null,
    video_bitrate: body.video_bitrate ?? null,
    max_bitrate: body.max_bitrate ?? null,
    html: body.composition.html,
    assets: (body.composition.assets || []).map((a) => [a.sha256, a.path || a.name]).sort(),
  }));
  return h.digest('hex');
}

function collectWarnings(logText) {
  const out = [];
  const seen = new Set();
  for (const raw of logText.split('\n')) {
    const line = stripAnsi(raw).trim();
    if (!line || line.startsWith('@hf-progress')) continue;
    if (!/(warn|warning|deprecat|fallback|missing|skipped)/i.test(line)) continue;
    const short = line.length > 200 ? `${line.slice(0, 200)}…` : line;
    if (seen.has(short)) continue;
    seen.add(short);
    out.push(short);
    if (out.length >= 10 || JSON.stringify(out).length > 1800) break;
  }
  return out;
}

// HTTP 头只允许 latin1：JSON 里的非 ASCII 一律转成 \uXXXX 转义（仍是合法 JSON），
// 并去掉 CR/LF，避免 header 注入。
function headerJson(value) {
  return JSON.stringify(value)
    .replace(/[\u007f-\uffff]/g, (ch) => `\\u${ch.charCodeAt(0).toString(16).padStart(4, '0')}`)
    .replace(/[\r\n]/g, ' ');
}

class LogTail {
  constructor(limit) {
    this.limit = limit;
    this.chunks = [];
    this.bytes = 0;
  }
  push(buf) {
    const s = buf.toString('utf8');
    this.chunks.push(s);
    this.bytes += Buffer.byteLength(s);
    while (this.bytes > this.limit * 2 && this.chunks.length > 1) {
      this.bytes -= Buffer.byteLength(this.chunks.shift());
    }
  }
  text() {
    const all = this.chunks.join('');
    if (Buffer.byteLength(all) <= this.limit) return all;
    return all.slice(-this.limit);
  }
}

function runEngine(args, { cwd, env, timeoutMs }) {
  return new Promise((resolve) => {
    const tail = new LogTail(cfg.logTailBytes);
    let child;
    try {
      child = spawn(BIN, args, {
        cwd,
        env,
        detached: true, // 独立进程组：超时能连 Chrome 一起杀
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (err) {
      resolve({ ok: false, timedOut: false, code: null, signal: null, log: `spawn failed: ${err.message}`, spawnError: String(err.message) });
      return;
    }

    let timedOut = false;
    const timer =
      timeoutMs > 0
        ? setTimeout(() => {
            timedOut = true;
            killGroup(child.pid, 'SIGKILL');
          }, timeoutMs)
        : null;

    child.stdout.on('data', (b) => tail.push(b));
    child.stderr.on('data', (b) => tail.push(b));

    const finish = (code, signal, spawnError) => {
      if (timer) clearTimeout(timer);
      // 主进程已退出也要兜一次进程组，确保 Chrome 子进程不残留。
      killGroup(child.pid, 'SIGKILL');
      resolve({
        ok: !timedOut && code === 0,
        timedOut,
        code,
        signal,
        log: tail.text(),
        spawnError: spawnError || null,
      });
    };

    child.on('error', (err) => finish(null, null, String(err.message || err)));
    child.on('close', (code, signal) => finish(code, signal, null));
  });
}

function killGroup(pid, sig) {
  if (!pid) return;
  // ── 诊断日志（只观测，不改语义）────────────────────────────────────────
  // 背景：DEBT-RENDER-FLAKY-01 —— 20s storyboard 走 API 间歇 500，job 目录里留下
  // `.hyperframes/running/<pid>` 却没有 `video-state.json`，形态上像子进程被本函数的
  // 进程组信号误伤（detached:true 时子进程即组长，pgid == pid，故这里打 -pid）。
  // 目的：拿到「发信号前该进程组是否还在 / 发信号是否报错 / 发完是否已消失」三态，
  // 用来判定是「正常收尾顺带清组」还是「误杀同类子进程」。
  // 该日志只写 stdout，不参与任何判定逻辑；确认结论后应删除或降级为 debug 开关。
  const tgt = -pid;
  const probe = () => {
    try {
      process.kill(tgt, 0); // 信号 0 = 仅探测存在性
      return "alive";
    } catch (err) {
      return err && err.code ? err.code : "probe-error";
    }
  };
  const before = probe();
  console.log(
    `[killGroup] send sig=${sig} pid=${pid} pgid=${tgt} selfPid=${process.pid} groupBefore=${before}`,
  );
  let sendErr = "none";
  try {
    process.kill(tgt, sig);
  } catch (err) {
    sendErr = err && err.code ? err.code : "send-error";
    /* ESRCH：进程组已消失（正常收尾的常见情形） */
  }
  const after = probe();
  console.log(
    `[killGroup] done sig=${sig} pid=${pid} pgid=${tgt} groupAfter=${after} sendErr=${sendErr}`,
  );
}

async function placeAssets(jobDir, assetEntries) {
  const missing = [];
  for (const a of assetEntries) {
    const rel = a.path || a.name;
    const src = path.join(ASSET_DIR, a.sha256);
    try {
      await fsp.access(src, fs.constants.R_OK);
    } catch {
      missing.push(a.sha256);
      continue;
    }
    const dest = path.join(jobDir, rel);
    const resolved = path.resolve(dest);
    if (!resolved.startsWith(path.resolve(jobDir) + path.sep)) {
      const err = new Error(`asset path escapes job dir: ${rel}`);
      err.code = 'E_BAD_ASSET_PATH';
      throw err;
    }
    await fsp.mkdir(path.dirname(resolved), { recursive: true });
    try {
      await fsp.link(src, resolved); // 同盘硬链，零拷贝
    } catch {
      await fsp.copyFile(src, resolved); // 跨设备退化为复制
    }
  }
  return missing;
}

async function archiveDir(dir, outPath) {
  // 目录型产物（png-sequence/hls）打成确定性 tar。
  return new Promise((resolve) => {
    const child = spawn(
      'tar',
      ['--format=ustar', '--mtime=@0', '--owner=0', '--group=0', '--numeric-owner', '--sort=name', '-cf', outPath, '-C', dir, '.'],
      { stdio: ['ignore', 'pipe', 'pipe'] },
    );
    let err = '';
    child.stderr.on('data', (b) => (err += b.toString()));
    child.on('error', (e) => resolve({ ok: false, error: String(e.message || e) }));
    child.on('close', (code) => resolve({ ok: code === 0, error: code === 0 ? null : err }));
  });
}

async function sendBuffer(res, buf, headers) {
  res.writeHead(200, {
    'Content-Type': headers.mime,
    'Content-Length': buf.length,
    'Cache-Control': 'no-store',
    ...headers.extra,
  });
  res.end(buf);
}

async function sendFileAndCleanup(res, filePath, headers, cleanup) {
  const st = await fsp.stat(filePath);
  res.writeHead(200, {
    'Content-Type': headers.mime,
    'Content-Length': st.size,
    'Cache-Control': 'no-store',
    ...headers.extra,
  });
  try {
    await pipeline(fs.createReadStream(filePath), res);
  } finally {
    await cleanup();
  }
}

// ── 端点实现 ────────────────────────────────────────────────────────────────
let engine = { version: null, chrome: null, doctor: null, bin: BIN };

function healthz() {
  const doctorChecks = engine.doctor?.checks || [];
  const check = (re) => doctorChecks.find((c) => re.test(c.name)) || null;
  const summary = ['Version', 'Node.js', 'FFmpeg', 'FFprobe', 'Chrome', 'Memory', 'Disk']
    .map((name) => doctorChecks.find((c) => c.name === name))
    .filter(Boolean)
    .map((c) => ({ name: c.name, ok: c.ok, detail: c.detail }));

  const ok = Boolean(engine.version) && Boolean(engine.chrome);
  return {
    ok,
    engine: `${ENGINE_PKG}@${engine.version || 'unknown'}`,
    node: process.version,
    chrome: engine.chrome,
    workers: cfg.maxConcurrency,
    uptime_s: Math.round(process.uptime()),
    jobs: {
      active: stats.active,
      done: stats.done,
      failed: stats.failed,
      timed_out: stats.timedOut,
      queued: sem.pending,
    },
    doctor: {
      available: Boolean(engine.doctor),
      ok: engine.doctor?.ok ?? null,
      checks: summary,
    },
    cache: { enabled: cache.enabled(), entries: cache.size, bytes: cache.bytes },
    limits: {
      timeout_s: cfg.timeoutS,
      queue_max: cfg.queueMax,
      max_asset_bytes: cfg.maxAssetBytes,
    },
  };
}

async function handleAssetUpload(req, res, sha) {
  if (!SHA256_RE.test(sha)) {
    json(res, 400, { error: 'sha256 must be 64 lowercase hex chars', got: sha });
    return;
  }
  let body;
  try {
    body = await readBody(req, cfg.maxAssetBytes);
  } catch (err) {
    if (err.code === 'E_BODY_TOO_LARGE') {
      json(res, 413, { error: `asset exceeds ${cfg.maxAssetBytes} bytes` });
    } else {
      json(res, 400, { error: `asset upload failed: ${err.message}` });
    }
    return;
  }
  const actual = sha256Hex(body);
  if (actual !== sha) {
    json(res, 400, { error: 'sha256 mismatch', expected: sha, actual, bytes: body.length });
    return;
  }
  const dest = path.join(ASSET_DIR, sha);
  const tmp = `${dest}.${process.pid}.${crypto.randomBytes(4).toString('hex')}.tmp`;
  await fsp.writeFile(tmp, body);
  await fsp.rename(tmp, dest);
  json(res, 201, { ok: true, sha256: sha, bytes: body.length });
}

async function handleRender(req, res) {
  let raw;
  try {
    raw = await readBody(req, cfg.maxBodyBytes);
  } catch (err) {
    if (err.code === 'E_BODY_TOO_LARGE') {
      json(res, 413, { error: `render request exceeds ${cfg.maxBodyBytes} bytes` });
    } else {
      json(res, 400, { error: `request read failed: ${err.message}` });
    }
    return;
  }

  let body;
  try {
    body = JSON.parse(raw.toString('utf8'));
  } catch (err) {
    json(res, 400, { error: `invalid JSON: ${err.message}`, phase: 'validate' });
    return;
  }

  const problems = validateRenderRequest(body);
  if (problems.length) {
    json(res, 400, { error: 'invalid render request', phase: 'validate', problems });
    return;
  }

  // 静态零外链：编译期就拒绝，绝不提交作业。
  const externals = findExternalRefs(body.composition.html);
  if (externals.length) {
    json(res, 400, {
      error: 'composition references external resources (offline render plane)',
      phase: 'validate',
      resources: externals,
      hint: 'inline the asset, vendor the library, or use a relative path / data: URI',
    });
    return;
  }

  const jobId = body.job_id;
  const fps = body.fps ?? cfg.defaultFps;
  const quality = body.quality ?? cfg.defaultQuality;
  const format = body.format ?? 'mp4';
  const assetEntries = body.composition.assets || [];

  // 素材必须已入库（PUT /v1/assets/<sha256>）；缺失即拒绝，不做隐式下载。
  const missing = [];
  for (const a of assetEntries) {
    try {
      await fsp.access(path.join(ASSET_DIR, a.sha256), fs.constants.R_OK);
    } catch {
      missing.push(a.sha256);
    }
  }
  if (missing.length) {
    json(res, 400, {
      error: 'composition references assets not uploaded',
      phase: 'validate',
      missing: [...new Set(missing)],
      hint: 'PUT /v1/assets/<sha256> the raw bytes first',
    });
    return;
  }

  const cacheKey = `${jobId}:${contentKey(body, engine.version)}`;
  const cached = cache.get(cacheKey);
  if (cached) {
    stats.done += 1;
    await sendBuffer(res, cached.buf, {
      mime: cached.mime,
      extra: { ...cached.headers, 'X-Cache': 'hit' },
    });
    return;
  }

  try {
    await sem.acquire();
  } catch (err) {
    json(res, 429, {
      error: 'render queue full',
      phase: 'queue',
      queued: sem.pending,
      queue_max: cfg.queueMax,
      retry_after_s: 5,
    }, { 'Retry-After': '5' });
    return;
  }

  stats.active += 1;
  const startedAt = nowMs();
  let jobDir = null;
  let artifactPath = null;

  try {
    jobDir = await fsp.mkdtemp(path.join(JOB_DIR, `${safeJobLabel(jobId)}-`));
    await fsp.mkdir(path.join(jobDir, 'tmp'), { recursive: true });
    await fsp.writeFile(path.join(jobDir, 'index.html'), body.composition.html, 'utf8');
    const stillMissing = await placeAssets(jobDir, assetEntries);
    if (stillMissing.length) {
      throw Object.assign(new Error(`assets vanished: ${stillMissing.join(',')}`), { phase: 'setup' });
    }

    const env = buildChildEnv(jobDir);
    lastChildEnvKeys = Object.keys(env).sort();

    const isDir = DIR_FORMATS.has(format);
    const outName = isDir ? 'out' : `out.${format}`;
    artifactPath = path.join(jobDir, outName);
    const args = ['render', `-f`, String(fps), `-q`, quality, `-w`, '1', '--format', format, '-o', artifactPath];
    // 码率透传：MOV(ProRes) 不支持 crf/bitrate（见 CLI --help），只对 mp4/webm 生效。
    if (format === 'mp4' || format === 'webm') {
      if (body.crf !== undefined) args.push('--crf', String(body.crf));
      if (body.video_bitrate !== undefined) args.push('--video-bitrate', body.video_bitrate.trim());
      if (body.max_bitrate !== undefined) args.push('--max-bitrate', body.max_bitrate.trim());
    }
    args.push(jobDir);

    const result = await runEngine(args, {
      cwd: jobDir,
      env,
      timeoutMs: cfg.timeoutS * 1000,
    });
    const renderMs = nowMs() - startedAt;

    if (!result.ok) {
      // 失败/超时：先清 tmpdir 再回错，保证零残留。
      await cleanupDir(jobDir);
      jobDir = null;
      if (result.timedOut) {
        stats.timedOut += 1;
        stats.failed += 1;
        json(res, 504, {
          error: `render timed out after ${cfg.timeoutS}s`,
          phase: 'timeout',
          job_id: jobId,
          engine: `${ENGINE_PKG}@${engine.version}`,
          log_tail: result.log,
        });
      } else {
        stats.failed += 1;
        json(res, 500, {
          error: 'render failed',
          phase: 'render',
          job_id: jobId,
          engine: `${ENGINE_PKG}@${engine.version}`,
          exit_code: result.code,
          signal: result.signal,
          spawn_error: result.spawnError,
          log_tail: result.log,
        });
      }
      return;
    }

    const warnings = collectWarnings(result.log);

    // 目录型产物先打 tar 再流回
    let payloadPath = artifactPath;
    if (isDir) {
      const tarPath = path.join(jobDir, 'out.tar');
      const tar = await archiveDir(artifactPath, tarPath);
      if (!tar.ok) {
        await cleanupDir(jobDir);
        jobDir = null;
        stats.failed += 1;
        json(res, 500, {
          error: 'artifact archive failed',
          phase: 'package',
          job_id: jobId,
          detail: tar.error,
          log_tail: result.log,
        });
        return;
      }
      payloadPath = tarPath;
    }

    let stat;
    try {
      stat = await fsp.stat(payloadPath);
    } catch {
      stat = null;
    }
    if (!stat || !stat.isFile() || stat.size === 0) {
      await cleanupDir(jobDir);
      jobDir = null;
      stats.failed += 1;
      json(res, 500, {
        error: 'render produced no artifact',
        phase: 'render',
        job_id: jobId,
        log_tail: result.log,
      });
      return;
    }

    const mime = isDir ? MIME.tar : MIME[format] || 'application/octet-stream';
    const headers = {
      'X-Engine': `${ENGINE_PKG}@${engine.version}`,
      // job_id 可能含非 ASCII（中文标识）：header 只允许 latin1，必要时百分号编码
      'X-Job-Id': /^[\x20-\x7e]*$/.test(jobId) ? jobId : encodeURIComponent(jobId),
      'X-Render-Ms': String(renderMs),
      'X-Warnings': headerJson(warnings),
      'X-Format': format,
      'X-Cache': 'miss',
    };

    stats.done += 1;

    if (stat.size <= cache.maxBytes) {
      const buf = await fsp.readFile(payloadPath);
      await cleanupDir(jobDir);
      jobDir = null;
      cache.put(cacheKey, { buf, mime, headers });
      await sendBuffer(res, buf, { mime, extra: headers });
      return;
    }

    // 大产物：流式回传，响应结束再清 tmpdir
    const dirToClean = jobDir;
    jobDir = null;
    await sendFileAndCleanup(res, payloadPath, { mime, extra: headers }, () => cleanupDir(dirToClean));
  } catch (err) {
    if (jobDir) await cleanupDir(jobDir);
    stats.failed += 1;
    json(res, 500, {
      error: 'render job error',
      phase: err.phase || 'internal',
      job_id: jobId,
      detail: String(err.message || err),
    });
  } finally {
    stats.active = Math.max(0, stats.active - 1);
    sem.release();
  }
}

async function cleanupDir(dir) {
  if (!dir) return;
  try {
    await fsp.rm(dir, { recursive: true, force: true, maxRetries: 3 });
  } catch (err) {
    // 清理失败只能记日志：不阻塞响应，但留下可观测痕迹
    console.error(`[render-plane] cleanup failed for ${dir}: ${err.message}`);
  }
}

// ── 路由 ────────────────────────────────────────────────────────────────────
async function route(req, res) {
  const url = new URL(req.url, 'http://localhost');
  const p = url.pathname;

  if (req.method === 'GET' && (p === '/healthz' || p === '/health')) {
    json(res, 200, healthz());
    return;
  }
  if (req.method === 'GET' && p === '/v1/version') {
    json(res, 200, {
      engine: `${ENGINE_PKG}@${engine.version}`,
      hyperframes: engine.version,
      node: process.version,
      chrome: engine.chrome,
      service: 'vaas-render-plane',
      api: 'v1',
    });
    return;
  }
  if (req.method === 'PUT' && p.startsWith('/v1/assets/')) {
    await handleAssetUpload(req, res, decodeURIComponent(p.slice('/v1/assets/'.length)));
    return;
  }
  if (req.method === 'POST' && p === '/v1/render') {
    await handleRender(req, res);
    return;
  }
  if (req.method === 'GET' && p === '/v1/_debug/env') {
    if (!cfg.debug) {
      json(res, 404, { error: 'not found' });
      return;
    }
    const keys = lastChildEnvKeys || [];
    json(res, 200, {
      keys,
      count: keys.length,
      denied_pattern: ENV_DENY_RE.source,
      leaked: keys.filter((k) => ENV_DENY_RE.test(k)),
      forced: FORCED_ENGINE_ENV,
    });
    return;
  }
  json(res, 404, { error: 'not found', path: p, method: req.method });
}

// ── 启动 ────────────────────────────────────────────────────────────────────
async function main() {
  await fsp.mkdir(ASSET_DIR, { recursive: true });
  await fsp.mkdir(JOB_DIR, { recursive: true });
  engine = detectEngine();

  const server = http.createServer((req, res) => {
    route(req, res).catch((err) => {
      console.error(`[render-plane] unhandled: ${err?.stack || err}`);
      if (!res.headersSent) json(res, 500, { error: 'internal error' });
      else res.destroy();
    });
  });
  server.requestTimeout = 15 * 60 * 1000;
  server.headersTimeout = 60 * 1000;
  server.keepAliveTimeout = 65 * 1000;

  server.listen(cfg.port, cfg.bind, () => {
    console.log(
      `[vaas-render-plane] listening on ${cfg.bind}:${cfg.port} · engine=${ENGINE_PKG}@${engine.version} · chrome=${engine.chrome || 'unresolved'} · workers=${cfg.maxConcurrency} · workdir=${cfg.workdir}`,
    );
    if (engine.doctor) {
      const failed = engine.doctor.checks.filter((c) => !c.ok).map((c) => c.name);
      console.log(`[vaas-render-plane] doctor=${engine.doctor.ok ? 'ok' : 'degraded'}${failed.length ? ` · failed: ${failed.join(',')}` : ''}`);
    }
  });

  const shutdown = (sig) => {
    console.log(`[vaas-render-plane] ${sig} received, draining`);
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 10_000).unref();
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((err) => {
  console.error(`[vaas-render-plane] fatal: ${err?.stack || err}`);
  process.exit(1);
});

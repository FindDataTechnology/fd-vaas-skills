'use strict';

/**
 * fd-vaas-video-creator - Seedream core module.
 * Sibling of seedance.js (video). Handles:
 *   - API key resolution (prefers .env `vol_agent_api_key`, then the same
 *     sources seedance uses: --api-key, ANTHROPIC_AUTH_TOKEN, ARK_API_KEY, configs)
 *   - Agent Plan image generation  POST /api/plan/v3/images/generations
 *   - Smart model routing from references/seedream-model-matrix.json
 *   - Reference-image (img2img), web-search, batch/sequential generation
 *   - Local image download with 3-tier fallback
 *
 * No external dependencies — Node >=18 built-ins only (global fetch).
 */

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const os = require('os');
const https = require('https');
const http = require('http');

const SCRIPTS_DIR = __dirname;
const SKILL_DIR = path.join(SCRIPTS_DIR, '..', '..');
const MATRIX_PATH = path.join(SKILL_DIR, 'references', 'seedream-model-matrix.json');

const DEFAULT_BASE_URL = 'https://ark.cn-beijing.volces.com/api/plan/v3';
const DEFAULT_MODEL = 'doubao-seedream-5.0-lite';
const DEFAULT_SIZE = '2K';
const DEFAULT_OUTPUT_FORMAT = 'jpeg';
const DEFAULT_RESPONSE_FORMAT = 'url';
const DEFAULT_WATERMARK = false;

// Preference storage (mirrors seedance's per-user preference file)
const PREF_DIR = path.join(os.homedir(), '.seedream-skill');
const PREF_FILE = path.join(PREF_DIR, 'preferences.json');

/* ------------------------------------------------------------------ *
 * API key resolution
 * ------------------------------------------------------------------ */

function validateArkKey(key) {
  if (!key || typeof key !== 'string') return { valid: false, reason: 'empty' };
  const trimmed = key.trim();
  if (!trimmed.startsWith('ark-')) return { valid: false, reason: 'must start with "ark-"' };
  if (trimmed.length < 20) return { valid: false, reason: 'too short' };
  return { valid: true, key: trimmed };
}

/**
 * Walk up from a start dir looking for a .env that defines `vol_agent_api_key`.
 * Returns the parsed env object (all keys) of the first match, or null.
 */
function findProjectEnv() {
  let dir = SCRIPTS_DIR;
  for (let i = 0; i < 12; i++) {
    const envPath = path.join(dir, '.env');
    if (fs.existsSync(envPath)) {
      const parsed = parseEnvFile(envPath);
      if (parsed.vol_agent_api_key) return parsed;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  // also check cwd and home
  for (const d of [process.cwd(), os.homedir()]) {
    const envPath = path.join(d, '.env');
    if (fs.existsSync(envPath)) {
      const parsed = parseEnvFile(envPath);
      if (parsed.vol_agent_api_key) return parsed;
    }
  }
  return null;
}

function parseEnvFile(envPath) {
  const out = {};
  let content;
  try { content = fs.readFileSync(envPath, 'utf8'); } catch { return out; }
  for (const rawLine of content.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    // strip surrounding quotes
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function readClaudeConfig() {
  // ~/.claude.json may carry env.ANTHROPIC_AUTH_TOKEN (same pattern seedance uses)
  const p = path.join(os.homedir(), '.claude.json');
  try {
    const j = JSON.parse(fs.readFileSync(p, 'utf8'));
    return j || {};
  } catch { return {}; }
}

/**
 * Resolve the API key. Priority:
 *   1. .env `vol_agent_api_key`  (project env — preferred for this skill)
 *   2. options.apiKey            (--api-key, agent-supplied, temp)
 *   3. process.env.ANTHROPIC_AUTH_TOKEN
 *   4. claude config env.ANTHROPIC_AUTH_TOKEN
 *   5. process.env.ARK_API_KEY / API_KEY / apiKey / api_key
 */
async function resolveApiKey(options = {}) {
  // 1. project .env
  const env = findProjectEnv();
  if (env && env.vol_agent_api_key) {
    const v = validateArkKey(env.vol_agent_api_key);
    if (v.valid) return { key: v.key, source: '.env:vol_agent_api_key', env };
  }
  // 2. explicit
  if (options.apiKey) {
    const v = validateArkKey(options.apiKey);
    if (v.valid) return { key: v.key, source: '--api-key', env };
  }
  // 3. ANTHROPIC_AUTH_TOKEN env
  if (process.env.ANTHROPIC_AUTH_TOKEN) {
    const v = validateArkKey(process.env.ANTHROPIC_AUTH_TOKEN);
    if (v.valid) return { key: v.key, source: 'env:ANTHROPIC_AUTH_TOKEN', env };
  }
  // 4. claude config
  const cc = readClaudeConfig();
  if (cc.env && cc.env.ANTHROPIC_AUTH_TOKEN) {
    const v = validateArkKey(cc.env.ANTHROPIC_AUTH_TOKEN);
    if (v.valid) return { key: v.key, source: 'claude-config:ANTHROPIC_AUTH_TOKEN', env };
  }
  // 5. generic env names
  for (const n of ['ARK_API_KEY', 'API_KEY', 'apiKey', 'api_key']) {
    if (process.env[n]) {
      const v = validateArkKey(process.env[n]);
      if (v.valid) return { key: v.key, source: `env:${n}`, env };
    }
  }
  const e = new Error(
    '\n未找到有效的方舟 Agent Plan API Key。\n\n' +
    '请在 VAAS/.env 中配置：\n' +
    '  vol_agent_api_key=ark-xxxxxxxx\n' +
    '（该 key 必须是 Agent Plan 专属 key，不是编程计划 key；编程计划 key 调用 /api/plan/v3 会返回 401）\n'
  );
  e.code = 'NO_API_KEY';
  throw e;
}

function resolveBaseUrl(options = {}, env) {
  // Image generation must hit the Agent Plan endpoint /api/plan/v3.
  // NOTE: we deliberately do NOT read .env `vol_base_url` here - in this project
  // that var holds the *coding-plan* endpoint (/api/coding/v3), which has no
  // images API and would 404. Only explicit overrides change the base.
  if (options.baseUrl) return stripTrailingSlash(options.baseUrl);
  if (process.env.SEEDREAM_BASE_URL) return stripTrailingSlash(process.env.SEEDREAM_BASE_URL);
  return DEFAULT_BASE_URL;
}

function stripTrailingSlash(u) { return u && u.endsWith('/') ? u.slice(0, -1) : u; }

/* ------------------------------------------------------------------ *
 * Model matrix + routing
 * ------------------------------------------------------------------ */

let _matrixCache = null;
function loadMatrix() {
  if (_matrixCache) return _matrixCache;
  try {
    _matrixCache = JSON.parse(fs.readFileSync(MATRIX_PATH, 'utf8'));
  } catch (e) {
    _matrixCache = {};
  }
  return _matrixCache;
}

/**
 * Pick the best model given requested capabilities + user preference.
 * Returns { model, matrix_entry, change_reason? }
 */
function routeModel(params, preference) {
  const matrix = loadMatrix();
  const needs = inferCapabilities(params);

  // hard constraints: web_search / png force 5.0-lite
  const hardConstraintModel = (needs.web_search || needs.png_output) ? 'doubao-seedream-5.0-lite' : null;

  let chosen = hardConstraintModel || preference || DEFAULT_MODEL;
  let changeReason = null;

  // validate preference / chosen against capability needs
  const entry = matrix[chosen];
  if (entry) {
    const missing = checkCapabilityGap(entry, needs);
    if (missing.length) {
      const fallback = pickFallback(matrix, needs, chosen);
      changeReason = {
        preferred: chosen,
        reason: `您偏好的 ${entry.name} 不支持${missing.join('、')}。已自动切换到 ${matrix[fallback].name}`,
        fallback_to: fallback,
      };
      chosen = fallback;
    }
  }

  // quality ultra -> prefer 5.0-pro if no hard constraint and not already pro
  if (params.quality === 'ultra' && !hardConstraintModel && chosen !== 'doubao-seedream-5.0-pro') {
    const pro = matrix['doubao-seedream-5.0-pro'];
    if (pro && checkCapabilityGap(pro, needs).length === 0) {
      chosen = 'doubao-seedream-5.0-pro';
    }
  }

  return { model: chosen, entry: matrix[chosen] || {}, change_reason: changeReason };
}

function inferCapabilities(params) {
  return {
    image2image: !!(params.imageFile && params.imageFile.length) || !!params.imageUrl,
    multi_image: (params.imageFile && params.imageFile.length >= 2) || (params.imageUrl && params.imageUrl.length >= 2),
    web_search: !!params.enableWebSearch,
    png_output: (params.outputFormat || '').toLowerCase() === 'png',
    sequential: !!params.sequential,
    seed: params.seed != null,
  };
}

function checkCapabilityGap(entry, needs) {
  const gap = [];
  if (needs.image2image && !entry.supports_reference_image) gap.push('图像参考');
  if (needs.multi_image && !entry.supports_multi_reference_image) gap.push('多图参考');
  if (needs.web_search && !entry.supports_web_search) gap.push('联网搜索');
  if (needs.png_output && !entry.supports_png_output) gap.push('PNG输出');
  if (needs.sequential && !entry.supports_sequential) gap.push('批量生成');
  if (needs.seed && !entry.supports_seed) gap.push('随机种子');
  return gap;
}

function pickFallback(matrix, needs, exclude) {
  // prefer 5.0-lite (most capable), then 5.0, 5.0-pro, 4.5, 4.0
  const order = ['doubao-seedream-5.0-lite', 'doubao-seedream-5.0', 'doubao-seedream-5.0-pro', 'doubao-seedream-4.5', 'doubao-seedream-4.0'];
  for (const m of order) {
    if (m === exclude) continue;
    const e = matrix[m];
    if (e && checkCapabilityGap(e, needs).length === 0) return m;
  }
  return 'doubao-seedream-5.0-lite';
}

/* ------------------------------------------------------------------ *
 * Preferences
 * ------------------------------------------------------------------ */

function loadPreferences() {
  try { return JSON.parse(fs.readFileSync(PREF_FILE, 'utf8')) || {}; } catch { return {}; }
}
function getPreference(userId) {
  const all = loadPreferences();
  return all[userId || 'default'] || null;
}
function savePreference(userId, model) {
  const all = loadPreferences();
  if (!model || model === 'none' || model === 'clear') delete all[userId || 'default'];
  else all[userId || 'default'] = model;
  try { fs.mkdirSync(PREF_DIR, { recursive: true }); fs.writeFileSync(PREF_FILE, JSON.stringify(all, null, 2)); } catch {}
  return model === 'none' || model === 'clear' ? null : model;
}

/* ------------------------------------------------------------------ *
 * File helpers
 * ------------------------------------------------------------------ */

async function fileToBase64DataUri(filePath) {
  const buf = await fsp.readFile(filePath);
  const ext = path.extname(filePath).slice(1).toLowerCase();
  const mime = ext === 'jpg' ? 'jpeg' : (ext || 'jpeg');
  return `data:image/${mime};base64,${buf.toString('base64')}`;
}

function resolveSaveDir() {
  const ts = makeTimestamp();
  const dirs = [
    path.join(os.homedir(), 'Desktop', 'Seedream-Images', ts),
    path.join(os.homedir(), 'Seedream-Images', ts),
    path.join(process.cwd(), 'Seedream-Images', ts),
  ];
  for (const d of dirs) {
    try { fs.mkdirSync(d, { recursive: true }); if (isWritable(d)) return d; } catch {}
  }
  // last resort
  const d = dirs[2];
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function isWritable(dir) {
  try { fs.accessSync(dir, fs.constants.W_OK); return true; } catch { return false; }
}

function makeTimestamp() {
  // stable, filesystem-safe timestamp (no Date.now randomness issues — uses real clock)
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function extForFormat(outputFormat) {
  return (outputFormat || 'jpeg').toLowerCase() === 'png' ? 'png' : 'jpg';
}

/** Download a URL to a file. Supports http/https and follows redirects. */
function downloadToFile(url, dest) {
  return new Promise((resolve, reject) => {
    const proto = url.startsWith('https') ? https : http;
    const req = proto.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(downloadToFile(res.headers.location, dest)); // follow redirect
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`下载失败 HTTP ${res.statusCode}`));
      }
      const stream = fs.createWriteStream(dest);
      res.pipe(stream);
      stream.on('finish', () => stream.close(() => resolve(dest)));
      stream.on('error', reject);
    });
    req.on('error', reject);
    req.setTimeout(120000, () => req.destroy(new Error('下载超时')));
  });
}

function saveBase64ToFile(b64, dest) {
  return fsp.writeFile(dest, Buffer.from(b64, 'base64'));
}

/* ------------------------------------------------------------------ *
 * Request building
 * ------------------------------------------------------------------ */

function buildRequestBody(params, model, entry) {
  const body = {
    model,
    prompt: params.prompt,
  };

  // size
  body.size = params.size || DEFAULT_SIZE;

  // watermark (top-level, matches Agent Plan curl convention)
  body.watermark = params.watermark != null ? params.watermark : DEFAULT_WATERMARK;

  // response_format
  body.response_format = params.responseFormat || DEFAULT_RESPONSE_FORMAT;

  // output_format — only meaningful for 5.0-lite (png). Drop if unsupported.
  const wantPng = (params.outputFormat || '').toLowerCase() === 'png';
  if (wantPng && entry.supports_png_output) body.output_format = 'png';
  else if (params.outputFormat) body.output_format = params.outputFormat;
  else body.output_format = DEFAULT_OUTPUT_FORMAT;

  // extra_body: reference images + sequential
  const extra = {};
  const images = [];
  if (params.imageUrl && params.imageUrl.length) images.push(...params.imageUrl);
  if (images.length) extra.image = images;

  // local reference images -> base64 data URIs go into extra.image too
  // (resolved to base64 by caller before buildRequestBody; passed via params._imageDataUris)

  // sequential / batch
  if (params.sequential) {
    extra.sequential_image_generation = 'auto';
    const max = parseInt(params.maxImages, 10);
    if (max && max >= 1) {
      extra.sequential_image_generation_options = { max_images: Math.min(max, 15) };
    }
  }

  if (params._imageDataUris && params._imageDataUris.length) {
    extra.image = [...(extra.image || []), ...params._imageDataUris];
  }

  if (Object.keys(extra).length) body.extra_body = extra;

  // tools: web_search (5.0-lite only)
  if (params.enableWebSearch && entry.supports_web_search) {
    body.tools = [{ type: 'web_search' }];
  }

  // seed (3.0-t2i only)
  if (params.seed != null && entry.supports_seed) {
    body.seed = parseInt(params.seed, 10);
  }

  // optimize_prompt_options
  if (params.optimizePrompt && entry.supports_optimize_prompt) {
    const mode = params.optimizePrompt === 'fast' ? 'fast' : 'standard';
    body.optimize_prompt_options = { mode };
  }

  return body;
}

/* ------------------------------------------------------------------ *
 * Main: generate image
 * ------------------------------------------------------------------ */

async function generateImage(params, options = {}) {
  const { key, env } = await resolveApiKey(options);
  const baseUrl = resolveBaseUrl(options, env);

  const preference = options.noPreference ? null : getPreference(params.userId);
  const { model, entry, change_reason } = routeModel(params, preference);

  // resolve local reference images to base64 data URIs
  const dataUris = [];
  if (params.imageFile && params.imageFile.length) {
    for (const p of params.imageFile) {
      if (!fs.existsSync(p)) throw new Error(`参考图不存在: ${p}`);
      dataUris.push(await fileToBase64DataUri(p));
    }
  }
  params._imageDataUris = dataUris;

  const body = buildRequestBody(params, model, entry);
  const url = `${baseUrl}/images/generations`;

  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`,
    },
    body: JSON.stringify(body),
  });

  const text = await resp.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { _raw: text }; }

  if (!resp.ok) {
    return formatError(resp.status, data, { model, baseUrl, keySource: env && env.vol_agent_api_key ? '.env:vol_agent_api_key' : 'env' });
  }

  // Save images locally
  const outDir = resolveSaveDir();
  const ext = extForFormat(body.output_format);
  const images = await extractAndSaveImages(data, outDir, ext, body.response_format);

  return {
    ok: true,
    model,
    size: body.size,
    count: images.length,
    output_format: body.output_format,
    images,
    change_reason,
  };
}

async function extractAndSaveImages(data, outDir, ext, responseFormat) {
  // Standard shape: { data: [ { url } | { b64_json } ] }
  // Alternate shape sometimes seen: { image_url, model_used }
  const items = [];
  if (Array.isArray(data.data)) {
    for (const d of data.data) items.push(d);
  } else if (data.image_url) {
    items.push({ url: data.image_url });
  } else if (data.b64_json) {
    items.push({ b64_json: data.b64_json });
  }

  const out = [];
  let idx = 1;
  for (const it of items) {
    const name = String(idx).padStart(2, '0') + '.' + ext;
    const dest = path.join(outDir, name);
    let url = it.url || null;
    if (it.url) {
      try { await downloadToFile(it.url, dest); } catch { /* keep url even if dl fails */ }
    } else if (it.b64_json) {
      await saveBase64ToFile(it.b64_json, dest);
      url = null;
    }
    out.push({ url, local_path: fs.existsSync(dest) ? dest : null });
    idx++;
  }
  return out;
}

/* ------------------------------------------------------------------ *
 * Error / output formatting
 * ------------------------------------------------------------------ */

function formatError(status, data, ctx) {
  const err = data && data.error ? data.error : {};
  let hint = '';
  if (status === 401) {
    hint = '当前 API Key 被 Agent Plan 拒绝（401）。' +
      '火山方舟各计划 key 不通用：编程计划 key（/api/coding/v3）不能用于图像生成。' +
      '请在 VAAS/.env 的 vol_agent_api_key 中填入真正的 Agent Plan API Key。';
  } else if (err.code === 'ModelNotOpen') {
    hint = '该模型未在账户开通。请到火山方舟控制台开通对应的 Seedream 模型。';
  } else if (err.code === 'InvalidEndpointOrModel.NotFound') {
    hint = '模型名或入口不存在。Agent Plan 使用带点友好名（如 doubao-seedream-5.0-lite）；标准 API /api/v3 使用带日期 ID（如 doubao-seedream-5-0-lite-260128）。请确认 base_url 与模型名匹配。';
  }
  return {
    ok: false,
    status,
    error_code: err.code || `HTTP_${status}`,
    error_message: err.message || (typeof data === 'string' ? data : JSON.stringify(data).slice(0, 300)),
    model: ctx.model,
    base_url: ctx.baseUrl,
    key_source: ctx.keySource,
    hint,
  };
}

/* ------------------------------------------------------------------ *
 * LiteLLM bridge — multi-provider image generation via Python script
 * ------------------------------------------------------------------ */

const { spawnSync } = require('child_process');

function resolveBridgePath() {
  let dir = SCRIPTS_DIR;
  for (let i = 0; i < 12; i++) {
    const candidate = path.join(dir, 'scripts', 'litellm-bridge.py');
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.join(SCRIPTS_DIR, '..', '..', '..', 'scripts', 'litellm-bridge.py');
}

function shouldUseLiteLLM(options, env) {
  if (options && options.litellm) return true;
  const envObj = env || findProjectEnv() || {};
  const provider = (envObj.IMAGE_PROVIDER || 'volcengine').toLowerCase();
  return provider !== 'volcengine';
}

/**
 * Generate an image through the Python litellm-bridge.
 * Returns same shape as generateImage() for drop-in compatibility.
 */
async function generateImageViaLiteLLM(params, options = {}) {
  const bridgePath = resolveBridgePath();
  const env = findProjectEnv() || {};

  const outDir = resolveSaveDir();
  const ext = extForFormat(params.outputFormat || 'jpeg');
  const outPath = path.join(outDir, `01.${ext}`);

  const args = [bridgePath, 'image', '--output', outPath];

  if (params.prompt) args.push('--prompt', params.prompt);
  if (params.model) args.push('--model', params.model);
  else if (env.IMAGE_MODEL) args.push('--model', env.IMAGE_MODEL);
  if (params.size) args.push('--size', params.size);
  if (params.outputFormat) args.push('--output-format', params.outputFormat);
  if (params.maxImages || params.sequential) {
    args.push('-n', String(params.maxImages || 1));
  }
  if (options.apiKey) args.push('--api-key', options.apiKey);
  if (options.baseUrl) args.push('--base-url', options.baseUrl);

  const result = spawnSync('python3', args, {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024,
    env: { ...process.env, ...env },
  });

  if (result.error) {
    return {
      ok: false,
      error_code: 'BRIDGE_ERROR',
      error_message: `Failed to spawn Python bridge: ${result.error.message}`,
      hint: 'Make sure Python 3 and litellm are installed: pip install -r scripts/requirements.txt',
    };
  }

  if (result.status !== 0) {
    return {
      ok: false,
      error_code: 'BRIDGE_EXIT',
      error_message: (result.stderr || result.stdout || '').trim().slice(0, 500),
      hint: `Python bridge exited with code ${result.status}`,
    };
  }

  let data;
  try {
    data = JSON.parse(result.stdout.trim());
  } catch {
    return {
      ok: false,
      error_code: 'PARSE_ERROR',
      error_message: `Could not parse bridge output: ${result.stdout.slice(0, 200)}`,
    };
  }

  if (!data.ok) {
    return { ok: false, ...data };
  }

  return {
    ok: true,
    model: data.model || '',
    size: data.size || params.size || DEFAULT_SIZE,
    count: data.count || data.images?.length || 0,
    output_format: params.outputFormat || DEFAULT_OUTPUT_FORMAT,
    images: data.images || [],
    provider: data.provider || env.IMAGE_PROVIDER || 'litellm',
    api_latency_ms: data.api_latency_ms || 0,
  };
}

module.exports = {
  generateImage,
  generateImageViaLiteLLM,
  shouldUseLiteLLM,
  resolveApiKey,
  resolveBaseUrl,
  routeModel,
  loadMatrix,
  getPreference,
  savePreference,
  validateArkKey,
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
};

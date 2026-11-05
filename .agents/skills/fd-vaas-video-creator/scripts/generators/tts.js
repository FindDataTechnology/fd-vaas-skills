'use strict';

/**
 * fd-vaas-video-creator - TTS core module.
 * Handles:
 *   - API key resolution (same multi-source priority as seedream/seedance)
 *   - Agent Plan TTS: POST /api/v3/audio/speech (OpenAI-compatible)
 *   - Model + voice auto-selection with smart routing
 *   - Local audio file auto-save with 3-tier fallback
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

// Base URL: TTS uses openspeech.bytedance.com endpoint (Agent Plan)
// Documentation: HTTP POST - https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional
const DEFAULT_BASE_URL = 'https://openspeech.bytedance.com/api/v3/plan/tts';
const DEFAULT_MODEL = 'seed-tts-2.0'; // doubao-seed-tts-2.0 (豆包语音合成模型2.0)
const DEFAULT_VOICE = 'zh_female_gaolengyujie_uranus_bigtts'; // 高冷御姐，默认
const DEFAULT_RESPONSE_FORMAT = 'mp3';
const DEFAULT_SPEED = 1.0;

/* ------------------------------------------------------------------ *
 * API key resolution — identical logic to seedream.js
 * ------------------------------------------------------------------ */

function validateArkKey(key) {
  if (!key || typeof key !== 'string') return { valid: false, reason: 'empty' };
  const trimmed = key.trim();
  if (!trimmed.startsWith('ark-')) return { valid: false, reason: 'must start with "ark-"' };
  if (trimmed.length < 20) return { valid: false, reason: 'too short' };
  return { valid: true, key: trimmed };
}

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
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function readClaudeConfig() {
  const p = path.join(os.homedir(), '.claude.json');
  try {
    const j = JSON.parse(fs.readFileSync(p, 'utf8'));
    return j || {};
  } catch { return {}; }
}

async function resolveApiKey(options = {}) {
  const env = findProjectEnv();
  if (env && env.vol_agent_api_key) {
    const v = validateArkKey(env.vol_agent_api_key);
    if (v.valid) return { key: v.key, source: '.env:vol_agent_api_key', env };
  }
  if (options.apiKey) {
    const v = validateArkKey(options.apiKey);
    if (v.valid) return { key: v.key, source: '--api-key', env };
  }
  if (process.env.ANTHROPIC_AUTH_TOKEN) {
    const v = validateArkKey(process.env.ANTHROPIC_AUTH_TOKEN);
    if (v.valid) return { key: v.key, source: 'env:ANTHROPIC_AUTH_TOKEN', env };
  }
  const cc = readClaudeConfig();
  if (cc.env && cc.env.ANTHROPIC_AUTH_TOKEN) {
    const v = validateArkKey(cc.env.ANTHROPIC_AUTH_TOKEN);
    if (v.valid) return { key: v.key, source: 'claude-config:ANTHROPIC_AUTH_TOKEN', env };
  }
  for (const n of ['ARK_API_KEY', 'API_KEY', 'apiKey', 'api_key']) {
    if (process.env[n]) {
      const v = validateArkKey(process.env[n]);
      if (v.valid) return { key: v.key, source: `env:${n}`, env };
    }
  }
  const e = new Error(
    '\n未找到有效的方舟 API Key。\n\n' +
    '请在 VAAS/.env 中配置：\n' +
    '  vol_agent_api_key=ark-xxxxxxxx\n' +
    '（支持 TTS 的 API Key — 如遇 401，请确认该模型已在控制台开通）\n'
  );
  e.code = 'NO_API_KEY';
  throw e;
}

function resolveBaseUrl(options = {}, env) {
  if (options.baseUrl) return stripTrailingSlash(options.baseUrl);
  if (process.env.ARK_TTS_BASE_URL) return stripTrailingSlash(process.env.ARK_TTS_BASE_URL);
  return DEFAULT_BASE_URL;
}

function stripTrailingSlash(u) { return u && u.endsWith('/') ? u.slice(0, -1) : u; }

/* ------------------------------------------------------------------ *
 * File helpers
 * ------------------------------------------------------------------ */

function resolveSaveDir(options = {}) {
  // 确定性输出目录（add-tts-caption-fallback）：调用方（如 task-render stepTts）
  // 传 --output-dir 时直写该目录，消除桌面扫描竞态；未指定保持既有三级 fallback。
  if (options.outputDir) {
    const d = path.isAbsolute(options.outputDir)
      ? options.outputDir
      : path.join(process.cwd(), options.outputDir);
    fs.mkdirSync(d, { recursive: true });
    return d;
  }
  const ts = makeTimestamp();
  const dirs = [
    path.join(os.homedir(), 'Desktop', 'Ark-TTS', ts),
    path.join(os.homedir(), 'Ark-TTS', ts),
    path.join(process.cwd(), 'Ark-TTS', ts),
  ];
  for (const d of dirs) {
    try { fs.mkdirSync(d, { recursive: true }); if (isWritable(d)) return d; } catch {}
  }
  const d = dirs[2];
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function isWritable(dir) {
  try { fs.accessSync(dir, fs.constants.W_OK); return true; } catch { return false; }
}

function makeTimestamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function extForFormat(responseFormat) {
  const fmt = (responseFormat || 'mp3').toLowerCase();
  const map = { mp3: 'mp3', opus: 'opus', aac: 'aac', flac: 'flac', wav: 'wav', pcm: 'pcm' };
  return map[fmt] || fmt;
}

/* ------------------------------------------------------------------ *
 * Voice list + routing
 * ------------------------------------------------------------------ */

// 豆包语音合成模型2.0 (doubao-seed-tts-2.0) 支持的音色
// 音色 ID 格式: {lang}_{gender}_{name}_{constellation}_bigtts
// 文档确认的音色 + 常见可用音色（无效时 API 会返回具体错误）
const VOICE_MATRIX = {
  // --- 中文女声 ---
  'zh_female_gaolengyujie_uranus_bigtts': { name: '高冷御姐', gender: 'female', desc: '✅默认推荐，高冷优雅女声，通用场景', sample_rate: 24000 },
  'zh_female_vv_uranus_bigtts': { name: 'VV', gender: 'female', desc: 'VV 女声，温柔自然', sample_rate: 24000 },
  'zh_female_wanwanxiaohe_moon_bigtts': { name: '湾湾小何', gender: 'female', desc: '台湾腔女声', sample_rate: 24000 },
  'zh_female_qingxinnvsheng_mars_bigtts': { name: '清新女声', gender: 'female', desc: '清新自然女声', sample_rate: 24000 },
  'zh_female_wenrouxiaoya_mars_bigtts': { name: '温柔小雅', gender: 'female', desc: '温柔亲切女声', sample_rate: 24000 },
  'zh_female_tianmeiyueyue_mars_bigtts': { name: '甜美悦悦', gender: 'female', desc: '甜美可爱女声', sample_rate: 24000 },

  // --- 中文男声 ---
  'zh_male_wennuanyangguang_mars_bigtts': { name: '温暖阳光', gender: 'male', desc: '温暖阳光男声，通用场景', sample_rate: 24000 },
  'zh_male_shaoxia_mars_bigtts': { name: '少年', gender: 'male', desc: '少年音男声', sample_rate: 24000 },
  'zh_male_M392_conversation_wvae_bigtts': { name: 'M392', gender: 'male', desc: '对话型男声', sample_rate: 24000 },
};

const MODEL_VOICE_MAP = {
  'seed-tts-2.0': Object.keys(VOICE_MATRIX),
};

function inferBestVoice(input, model) {
  // doubao seed-tts 默认用高冷御姐（通用且自然）
  const voices = MODEL_VOICE_MAP[model] || MODEL_VOICE_MAP[DEFAULT_MODEL];
  return voices[0] || DEFAULT_VOICE;
}

function formatVoiceList(model) {
  const voices = MODEL_VOICE_MAP[model] || MODEL_VOICE_MAP[DEFAULT_MODEL];
  return voices.map(v => {
    const info = VOICE_MATRIX[v] || { name: v, desc: '' };
    return `  • ${v} (${info.name}): ${info.desc}`;
  }).join('\n');
}

/* ------------------------------------------------------------------ *
 * Request building — Volcengine Ark TTS API (豆包语音合成模型2.0)
 * ------------------------------------------------------------------ */

function buildRequestBody(params, model) {
  const text = params.input || params.text || '';
  const speaker = params.voice || inferBestVoice(text, model);
  const speed = params.speed != null ? parseFloat(params.speed) : DEFAULT_SPEED;
  const format = (params.responseFormat || params.response_format || DEFAULT_RESPONSE_FORMAT).toLowerCase();
  // 逐字时间戳（TTS 2.0 用 enable_subtitle，字幕以 sentence.words[] 分块返回）
  const enableSubtitle = params.enableSubtitle !== false;

  // 豆包 seed-tts-2.0 请求体格式（文档确认：req_params 结构）
  const body = {
    req_params: {
      speaker: speaker,
      text: text,
      audio_params: {
        format: format === 'wav' ? 'wav' : format === 'pcm' ? 'pcm' : 'mp3',
        sample_rate: 24000,
        enable_subtitle: enableSubtitle,
      },
    },
  };

  // 韵律参数（speed/volume/pitch ratio）
  if (speed !== 1.0) {
    body.req_params.audio_params.speed_ratio = Math.max(0.2, Math.min(3.0, speed));
  }
  if (params.volume != null) {
    body.req_params.audio_params.volume_ratio = Math.max(0.1, Math.min(3.0, parseFloat(params.volume)));
  }
  if (params.pitch != null) {
    body.req_params.audio_params.pitch_ratio = Math.max(0.1, Math.min(3.0, parseFloat(params.pitch)));
  }

  // 情感参数（seed-tts-2.0 接受，配合文本表达效果更佳）
  if (params.emotion) {
    body.req_params.emotion = params.emotion;
  }

  return body;
}

/* ------------------------------------------------------------------ *
 * Main: synthesize speech
 * ------------------------------------------------------------------ */

async function synthesizeSpeech(params, options = {}) {
  const { key, env } = await resolveApiKey(options);
  const baseUrl = resolveBaseUrl(options, env);
  const model = params.model || DEFAULT_MODEL;

  if (!params.input && !params.text) {
    return {
      ok: false,
      error_code: 'MISSING_INPUT',
      error_message: '请提供要合成的文本内容（--input 或 --text 参数）',
      hint: '支持音色列表:\n' + formatVoiceList(model),
    };
  }

  const body = buildRequestBody(params, model);
  const url = `${baseUrl}/unidirectional`;

  const startTime = Date.now();
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Api-Key': key,                          // 文档确认的认证头
      'X-Api-Resource-Id': 'seed-tts-2.0',       // 文档确认：豆包语音合成模型2.0
      'X-Control-Require-Usage-Tokens-Return': '*',
    },
    body: JSON.stringify(body),
  });

  const elapsedMs = Date.now() - startTime;

  if (!resp.ok) {
    const text = await resp.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { _raw: text }; }
    return formatError(resp.status, data, { model, baseUrl, url });
  }

  // 响应是分块 JSON，每块 {"code":0, "data":"<base64音频>"} 或 {"code":0, "sentence":{...}}
  // 逐字时间戳来自 sentence.words[]（seed-tts-2.0 enable_subtitle）
  const rawText = await resp.text();
  const parsed = parseChunkedResponse(rawText);

  if (!parsed.audio) {
    // provider 结构化错误块 → 按真实原因分类直出（禁伪装成解码失败）
    if (parsed.errorBlock) {
      return {
        ok: false,
        error_code: parsed.errorBlock.code,
        error_message: parsed.errorBlock.message,
        hint: parsed.hint || '',
        model, base_url: baseUrl,
      };
    }
    return {
      ok: false,
      error_code: 'DECODE_FAILED',
      error_message: '音频解码失败，原始响应: ' + rawText.substring(0, 300),
      model, base_url: baseUrl,
    };
  }

  const outDir = resolveSaveDir(options);
  const fmt = body.req_params.audio_params.format || 'mp3';
  const ext = extForFormat(fmt);
  const fileName = `speech.${ext}`;
  const destPath = path.join(outDir, fileName);

  await fsp.writeFile(destPath, parsed.audio);

  const fileSize = fs.existsSync(destPath) ? fs.statSync(destPath).size : 0;

  // 估算音频时长：mp3 ~64kbps(24kHz单声道) = 8 KB/s
  const estimatedDurationSeconds = Math.round(fileSize / (8 * 1024));

  // 官方字幕（每字 startTime/endTime，秒）→ @remotion/captions 的 Caption[]（毫秒）
  // 有 sentences 就写盘；没有就跳过（enableSubtitle=false 或模型不支持时）
  let captionsPath = null;
  let captionsCount = 0;
  let audioDurationSeconds = null;
  if (parsed.sentences.length > 0) {
    const captions = sentencesToCaptions(parsed.sentences);
    captionsCount = captions.length;
    audioDurationSeconds = captions.length
      ? captions[captions.length - 1].endMs / 1000
      : null;
    captionsPath = path.join(outDir, 'captions.json');
    await fsp.writeFile(captionsPath, JSON.stringify(captions, null, 2));
  }

  return {
    ok: true,
    model,
    voice: body.req_params.speaker,
    voice_name: VOICE_MATRIX[body.req_params.speaker]?.name || body.req_params.speaker,
    input_length: body.req_params.text.length,
    response_format: fmt,
    speed: body.req_params.audio_params.speed_ratio || 1.0,
    local_path: destPath,
    captions_path: captionsPath,
    captions_count: captionsCount,
    audio_duration_seconds: audioDurationSeconds,
    file_size_bytes: fileSize,
    estimated_duration_seconds: estimatedDurationSeconds,
    api_latency_ms: elapsedMs,
  };
}

/* ------------------------------------------------------------------ *
 * 解析分块响应
 * 每块是一个独立 JSON: {"code":0, "message":"", "data":"<b64>"} 或
 *                      {"code":0, "sentence":{"text":"...","words":[{startTime,endTime,word,confidence}]}}
 * 我们分别累积 audio (base64 → Buffer) 和 sentences[]。
 * ------------------------------------------------------------------ */
function parseChunkedResponse(rawText) {
  const sentences = [];
  let audioB64 = '';
  // 错误块直出（add-tts-caption-fallback）：分块响应里若出现「非零 code +
  // 带 message 且无 data 字段」的 JSON 块，是 provider 的结构化报错
  // （如 InvalidSubscription），MUST NOT 当音频解码失败伪装过去。
  let errorBlock = null;

  // 每块是一整个 JSON 对象；用括号计数拆
  const objects = extractJsonObjects(rawText);
  for (const obj of objects) {
    if (obj && typeof obj.data === 'string' && obj.data.length > 0) {
      audioB64 += obj.data;
      continue;
    }
    if (obj && obj.sentence && Array.isArray(obj.sentence.words)) {
      sentences.push(obj.sentence);
      continue;
    }
    if (obj && !errorBlock && typeof obj.code === 'number' && obj.code !== 0 && (obj.message || obj.msg)) {
      errorBlock = { code: obj.code, message: obj.message || obj.msg, raw: obj };
    }
  }

  if (!audioB64 && errorBlock) {
    const hint = /InvalidSubscription/i.test(JSON.stringify(errorBlock.raw))
      ? '火山方舟订阅失效或过期：请到火山方舟控制台续订 AgentPlan，'
        + '或切换 TTS_PROVIDER=ciyuan（萬星词元）继续合成。'
      : '';
    return { audio: null, sentences, errorBlock, hint };
  }

  // 兜底：如果 JSON 拆不出（比如 chunk 没换行），仍然抓 base64
  if (!audioB64) {
    const chunks = rawText.match(/"data"\s*:\s*"([A-Za-z0-9+/=]+)"/g) || [];
    for (const c of chunks) {
      const m = c.match(/"data"\s*:\s*"([A-Za-z0-9+/=]+)"/);
      if (m) audioB64 += m[1];
    }
  }

  let audio = null;
  if (audioB64) {
    try { audio = Buffer.from(audioB64, 'base64'); } catch {}
  }
  return { audio, sentences };
}

// 简单的括号平衡扫描，容忍字符串里的转义
function extractJsonObjects(text) {
  const out = [];
  let depth = 0, start = -1, inStr = false, esc = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (ch === '\\') { esc = true; continue; }
      if (ch === '"') { inStr = false; }
      continue;
    }
    if (ch === '"') { inStr = true; continue; }
    if (ch === '{') { if (depth === 0) start = i; depth++; }
    else if (ch === '}') {
      depth--;
      if (depth === 0 && start !== -1) {
        const raw = text.slice(start, i + 1);
        try { out.push(JSON.parse(raw)); } catch {}
        start = -1;
      }
    }
  }
  return out;
}

// sentences[] → @remotion/captions Caption[]
// Caption 形状: { text, startMs, endMs, timestampMs, confidence }
//
// ⚠️ 接口 quirk:seed-tts-2.0 对英文/拉丁 token(FindDataTechnology、
// github.com、Star 之类)返回的 endTime 是骗人的 —— startTime 之后 30-45ms
// 就"结束",实际读音藏在到下一个 token 的 gap 里。逐字字幕直接用会导致
// 英文一闪就消失、和音频对不上。
// 修法:遇到 `dur < 100ms && gap > 100ms` 的 token,把 endMs 拉到下一个
// token 的 startMs(TTS 内字与字之间没有真空隙,只有句间停顿,所以只在
// 明显是 gap 时才修,汉字的准确时长不动)。幂等 —— 修过再跑不会误伤。
function sentencesToCaptions(sentences) {
  const captions = [];
  for (const s of sentences) {
    for (const w of s.words) {
      const startMs = Math.round((w.startTime || 0) * 1000);
      const endMs = Math.round((w.endTime || w.startTime || 0) * 1000);
      captions.push({
        text: w.word,
        startMs,
        endMs,
        timestampMs: Math.round((startMs + endMs) / 2),
        confidence: typeof w.confidence === 'number' ? w.confidence : null,
      });
    }
  }
  for (let i = 0; i < captions.length - 1; i++) {
    const dur = captions[i].endMs - captions[i].startMs;
    const gap = captions[i + 1].startMs - captions[i].endMs;
    if (dur < 100 && gap > 100) {
      captions[i].endMs = captions[i + 1].startMs;
      captions[i].timestampMs = Math.round(
        (captions[i].startMs + captions[i].endMs) / 2
      );
    }
  }
  return captions;
}

/* ------------------------------------------------------------------ *
 * Error / output formatting
 * ------------------------------------------------------------------ */

function formatError(status, data, ctx) {
  const err = data && data.error ? data.error : {};
  let hint = '';

  if (status === 401) {
    hint = '当前 API Key 被拒绝（401）。' +
      '请确认：1) 该 key 有效；2) 模型已在控制台开通；3) API 入口地址正确。';
  } else if (err.code === 'ModelNotOpen') {
    hint = '该 TTS 模型未在账户开通。请到火山方舟控制台开通对应的 TTS 模型权限。';
  } else if (err.code === 'InvalidVoice') {
    hint = '音色不存在。请使用支持的音色。\n' + formatVoiceList(ctx.model);
  }

  return {
    ok: false,
    status,
    error_code: err.code || `HTTP_${status}`,
    error_message: err.message || (typeof data === 'string' ? data : JSON.stringify(data).slice(0, 500)),
    model: ctx.model,
    base_url: ctx.baseUrl,
    hint,
  };
}

function listVoices(params) {
  const model = params.model || DEFAULT_MODEL;
  const voices = MODEL_VOICE_MAP[model] || MODEL_VOICE_MAP[DEFAULT_MODEL];

  console.log(`\n📢 模型 ${model} 支持的音色列表:\n`);
  console.log(formatVoiceList(model));
  console.log('');
  console.log('💡 使用示例: --voice zh-CN-Yunxia');

  return {
    ok: true,
    model,
    voices: voices.map(v => ({
      id: v,
      name: VOICE_MATRIX[v]?.name || v,
      gender: VOICE_MATRIX[v]?.gender,
      type: VOICE_MATRIX[v]?.type,
      desc: VOICE_MATRIX[v]?.desc,
      sample_rate: VOICE_MATRIX[v]?.sample_rate,
    })),
  };
}

/* ------------------------------------------------------------------ *
 * Synthetic captions — fallback when a provider returns audio without
 * word-level timestamps (ciyuan lane /v1/audio/speech).
 *
 * 算法（2026-11-05/06 生产实证，add-solution-package 三支片）:
 *   1. ffprobe 实测音频时长（VAAS 准入依赖，doctor 检查项）
 *   2. 文本切 token：中文按字、标点并入前字、Latin 连续词元整体一个 token
 *   3. token 数均分单 token 时长 → 全体时间戳 × (实测/估算) 线性缩放
 *      （吸收 MP3 帧填充等估算误差）
 *   4. 末 token endMs 钉到实测总时长
 * 结果形状与官方逐字戳完全一致；captions_source 标记 synthetic。
 * ------------------------------------------------------------------ */

function splitTextIntoTokens(text) {
  const tokens = [];
  let latin = '';
  for (const ch of text) {
    if (ch === '\n' || ch === '\r') { if (latin) { tokens.push(latin); latin = ''; } continue; }
    if (/[A-Za-z0-9@._\-/+]/.test(ch)) { latin += ch; continue; }
    if (latin) { tokens.push(latin); latin = ''; }
    if ('，。！？；、：'.includes(ch)) {
      if (tokens.length) tokens[tokens.length - 1] += ch;
      else tokens.push(ch);
      continue;
    }
    if (ch === ' ') continue;
    tokens.push(ch);
  }
  if (latin) tokens.push(latin);
  return tokens;
}

function probeAudioDurationSeconds(filePath) {
  try {
    const r = spawnSync('ffprobe', [
      '-v', 'error',
      '-show_entries', 'format=duration',
      '-of', 'default=nw=1:nk=1',
      filePath,
    ], { encoding: 'utf8' });
    if (r.status !== 0) return null;
    const d = Number(String(r.stdout).trim());
    return Number.isFinite(d) && d > 0 ? d : null;
  } catch { return null; }
}

// 估算总时长：token 数 × 中文单字基速（约 0.22s/字 @ 常速）。只作缩放基准的
// 初值，最终由实测时长线性缩放覆盖，粗估不影响对齐精度。
const SYNTHETIC_BASE_SECONDS_PER_TOKEN = 0.22;

// 腾讯 TTS 单次请求长度墙（2026-11-06 二分实测：165 字通 / 170 字挂，
// 超限 502 且触发上游熔断摘除约 5 分钟）。分段上限取安全余量。
const CIYUAN_SEGMENT_MAX_CHARS = 150;
const CIYUAN_RETRY_MAX = 3;
const CIYUAN_RETRY_BACKOFF_MS = [1500, 3000];
const CIYUAN_INTER_SEG_GAP_SECONDS = 0.22; // 段间静音（自然句间停顿）

// 把文本切成 ≤maxChars 的合成段：先按句切（。！？；），过长的句再按逗号/字数硬切。
function splitTextIntoSegments(text, maxChars = CIYUAN_SEGMENT_MAX_CHARS) {
  const sentences = [];
  let buf = '';
  for (const ch of text) {
    if (ch === '\n' || ch === '\r') { if (buf.trim()) sentences.push(buf.trim()); buf = ''; continue; }
    buf += ch;
    if ('。！？；'.includes(ch)) { if (buf.trim()) sentences.push(buf.trim()); buf = ''; }
  }
  if (buf.trim()) sentences.push(buf.trim());
  const hardSplit = (s) => {
    const parts = [];
    let cur = '';
    for (const ch of s) {
      cur += ch;
      if ((cur.length >= maxChars && '，、：'.includes(ch)) || cur.length >= maxChars) {
        parts.push(cur); cur = '';
      }
    }
    if (cur.trim()) parts.push(cur);
    return parts;
  };
  const segments = [];
  let cur = '';
  for (const s of sentences) {
    if (s.length > maxChars) {
      if (cur.trim()) { segments.push(cur.trim()); cur = ''; }
      segments.push(...hardSplit(s));
      continue;
    }
    if ((cur + s).length > maxChars) { if (cur.trim()) segments.push(cur.trim()); cur = s; }
    else cur += s;
  }
  if (cur.trim()) segments.push(cur.trim());
  return segments;
}

function sleepMs(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// 段级 captions：每段 token 均分于该段实测时长，段间静音推进时间轴。
// 比「全文单次缩放」更准——句级边界由实测锚定。
function buildSegmentedCaptions(segments, segDurations, gapSeconds) {
  const caps = [];
  let cursor = 0;
  segments.forEach((seg, i) => {
    const tokens = splitTextIntoTokens(seg);
    if (!tokens.length) return;
    const segMs = (segDurations[i] || 0) * 1000;
    const per = segMs / tokens.length;
    for (const tok of tokens) {
      const startMs = Math.round(cursor);
      const endMs = Math.round(cursor + per);
      caps.push({ text: tok, startMs, endMs, timestampMs: Math.round((startMs + endMs) / 2), confidence: null });
      cursor += per;
    }
    if (i < segments.length - 1) cursor += gapSeconds * 1000;
  });
  return caps;
}

// 逐段经 bridge 合成 + ffmpeg 拼接（段间静音），产出完整音频与段级时长表。
// 任一段重试耗尽 → 抛错（调用方整任务失败，不产残缺音频）。
async function synthesizeSegmentedViaBridge(params, options, env) {
  const bridgePath = resolveBridgePath();
  const text = params.input || params.text || '';
  const fmt = (params.responseFormat || params.response_format || 'mp3').toLowerCase();
  const ext = extForFormat(fmt);
  const outDir = resolveSaveDir(options);
  const segDir = fs.mkdtempSync(path.join(os.tmpdir(), 'tts-seg-'));

  const segments = splitTextIntoSegments(text);
  const model = params.model || env.TTS_MODEL || DEFAULT_MODEL;
  const voice = params.voice || env.TTS_VOICE || '';

  const segFiles = [];
  for (let i = 0; i < segments.length; i++) {
    const segPath = path.join(segDir, `s${String(i).padStart(3, '0')}.mp3`);
    let done = false;
    let lastErr = '';
    for (let attempt = 1; attempt <= CIYUAN_RETRY_MAX; attempt++) {
      const args = [bridgePath, 'tts', '--text', segments[i], '--output', segPath, '--format', 'mp3'];
      if (model) args.push('--model', model);
      if (voice) args.push('--voice', voice);
      if (params.speed != null) args.push('--speed', String(params.speed));
      if (options.apiKey) args.push('--api-key', options.apiKey);
      if (options.baseUrl) args.push('--base-url', options.baseUrl);
      const r = spawnSync('python3', args, {
        encoding: 'utf8',
        maxBuffer: 10 * 1024 * 1024,
        env: { ...process.env, ...env },
      });
      if (r.status === 0) { done = true; break; }
      lastErr = (r.stderr || r.stdout || '').trim().slice(0, 300);
      if (attempt < CIYUAN_RETRY_MAX) await sleepMs(CIYUAN_RETRY_BACKOFF_MS[attempt - 1] || 3000);
    }
    if (!done) {
      const err = new Error(`分段合成失败（段 ${i + 1}/${segments.length}）: ${lastErr}`);
      err.code = 'SEGMENT_FAILED';
      throw err;
    }
    segFiles.push(segPath);
    if (i < segments.length - 1) await sleepMs(300); // 段间间隔，避免连环失败触发上游熔断扩大
  }

  // 拼接（mp3 段间垫静音）
  const finalPath = path.join(outDir, `speech.${ext}`);
  if (segFiles.length === 1) {
    fs.copyFileSync(segFiles[0], finalPath);
  } else {
    const gap = path.join(segDir, 'gap.mp3');
    spawnSync('ffmpeg', ['-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono',
      '-t', String(CIYUAN_INTER_SEG_GAP_SECONDS), '-codec:a', 'libmp3lame', '-q:a', '4', gap],
      { stdio: 'pipe' });
    const list = path.join(segDir, 'concat.txt');
    const lines = [];
    segFiles.forEach((f, i) => {
      lines.push(`file '${f}'`);
      if (i < segFiles.length - 1) lines.push(`file '${gap}'`);
    });
    fs.writeFileSync(list, lines.join('\n') + '\n');
    const cc = spawnSync('ffmpeg', ['-y', '-f', 'concat', '-safe', '0', '-i', list,
      '-codec:a', 'libmp3lame', '-q:a', '4', finalPath], { stdio: 'pipe', maxBuffer: 10 * 1024 * 1024 });
    if (cc.status !== 0) {
      const err = new Error(`分段拼接失败: ${(cc.stderr || '').slice(0, 200)}`);
      err.code = 'CONCAT_FAILED';
      throw err;
    }
  }

  // 段级实测时长 → captions 时间轴（段间静音计入）
  const segDurations = segFiles.map((f) => probeAudioDurationSeconds(f) || 0);
  let caps = buildSegmentedCaptions(segments, segDurations, CIYUAN_INTER_SEG_GAP_SECONDS);
  // whisper 对齐升级（2026-11-06 生产教训）：均分时间戳零间隙会让 TikTok 分页
  // 失效（整稿一页糊满全屏——分页只认「空格开头 token + 页超阈值」）。本机有
  // whisper-cli + 模型时，对拼接音频转写拿真实字级时间戳，与口播稿对齐（识别错字
  // 由稿侧文本兜底），并插句首空格 token 触发翻页。失败则回退均分方案。
  if (process.env.VAAS_TTS_WHISPER !== '0') {
    try {
      const { execFileSync } = require('child_process');
      const wav = path.join(segDir, 'align-16k.wav');
      spawnSync('ffmpeg', ['-y', '-i', finalPath, '-vn', '-ar', '16000', '-ac', '1', wav], { stdio: 'pipe' });
      const model = findWhisperModel();
      if (model) {
        const jf = path.join(segDir, 'whisper-full.json');
        const w = spawnSync('whisper-cli', ['-m', model, '-l', 'zh', '-f', wav, '-ojf', '-of',
          jf.replace(/\.json$/, ''), '--max-len', '8', '--split-on-word'], { encoding: 'utf8' });
        if (w.status === 0 && fs.existsSync(jf)) {
          const aligned = alignCaptionsWithWhisper(text, jf, caps);
          if (aligned && aligned.length) caps = aligned;
          console.error(`🎤 whisper 对齐: ${aligned ? aligned.length + ' tokens（真实时间戳）' : '失败，回退均分'}`);
        }
      }
    } catch { /* whisper 不可用——静默回退均分 */ }
  }
  const captionsOut = path.join(outDir, 'captions.json');
  fs.writeFileSync(captionsOut, JSON.stringify(caps, null, 2));

  try { fs.rmSync(segDir, { recursive: true, force: true }); } catch {}

  return {
    ok: true,
    provider: 'ciyuan',
    model,
    voice,
    voice_name: voice,
    input_length: text.length,
    response_format: fmt,
    speed: params.speed != null ? parseFloat(params.speed) : 1.0,
    local_path: finalPath,
    captions_path: captionsOut,
    captions_source: 'synthetic',
    captions_count: caps.length,
    audio_duration_seconds: caps.length ? caps[caps.length - 1].endMs / 1000 : null,
    file_size_bytes: fs.existsSync(finalPath) ? fs.statSync(finalPath).size : 0,
    estimated_duration_seconds: caps.length ? caps[caps.length - 1].endMs / 1000 : 0,
    api_latency_ms: 0,
    segments: segments.length,
  };
}

function buildSyntheticCaptions(text, audioPath) {
  const realSec = probeAudioDurationSeconds(audioPath);
  if (!realSec) return null;
  const tokens = splitTextIntoTokens(text);
  if (!tokens.length) return null;
  const estimatedSec = tokens.length * SYNTHETIC_BASE_SECONDS_PER_TOKEN;
  const scale = realSec / estimatedSec;
  const captions = [];
  let cursor = 0;
  for (const tok of tokens) {
    const segMs = SYNTHETIC_BASE_SECONDS_PER_TOKEN * 1000 * scale;
    const startMs = Math.round(cursor);
    const endMs = Math.round(cursor + segMs);
    captions.push({
      text: tok,
      startMs,
      endMs,
      timestampMs: Math.round((startMs + endMs) / 2),
      confidence: null,
    });
    cursor += segMs;
  }
  captions[captions.length - 1].endMs = Math.round(realSec * 1000);
  return captions;
}


function findWhisperModel() {
  const candidates = [
    '/tmp/ggml-small.bin',
    path.join(os.homedir(), '.cache/whisper-cpp/ggml-small.bin'),
  ];
  for (const c of candidates) { if (fs.existsSync(c)) return c; }
  return null;
}

// whisper 对齐：把稿文本映射到 whisper 字级时间轴（LCS 锚点 + 锚点间插值）。
// 识别错字不影响——锚点取两端共同的字，中间不一致的稿字在锚点区间内均分。
function alignCaptionsWithWhisper(scriptText, whisperJsonPath, fallbackCaps) {
  try {
    const d = JSON.parse(fs.readFileSync(whisperJsonPath, 'utf8'));
    const wTokens = [];
    for (const seg of d.transcription || []) {
      for (const t of seg.tokens || []) {
        if (t.text.startsWith('[')) continue;
        wTokens.push({ text: t.text, from: t.offsets.from, to: t.offsets.to });
      }
    }
    if (!wTokens.length) return null;
    // 去掉稿侧标点（不参与对齐，挂在锚点字上）
    const sChars = [];
    for (const ch of scriptText) {
      if ('，。！？；、：—…'.includes(ch)) continue;
      sChars.push(ch);
    }
    const wChars = wTokens.map(t => t.text);
    // LCS DP（几百字规模可承受）
    const n = sChars.length, m = wChars.length;
    const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
    for (let i = 1; i <= n; i++) {
      for (let j = 1; j <= m; j++) {
        dp[i][j] = sChars[i - 1] === wChars[j - 1]
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
    // 回溯：s 侧每字若命中锚点 → 用 whisper 时间；否则锚点间插值
    const anchors = new Array(n).fill(null);
    let i = n, j = m;
    while (i > 0 && j > 0) {
      if (sChars[i - 1] === wChars[j - 1]) { anchors[i - 1] = wTokens[j - 1]; i--; j--; }
      else if (dp[i - 1][j] >= dp[i][j - 1]) i--;
      else j--;
    }
    const caps = [];
    let prevEnd = 0;
    let k = 0;
    while (k < n) {
      if (anchors[k]) {
        const a = anchors[k];
        caps.push({ text: sChars[k], startMs: a.from, endMs: Math.max(a.to, a.from + 30),
          timestampMs: Math.round((a.from + a.to) / 2), confidence: null });
        prevEnd = a.to; k++;
      } else {
        // 找下一个锚点
        let nk = k;
        while (nk < n && !anchors[nk]) nk++;
        const nextStart = nk < n ? anchors[nk].from : prevEnd + 400;
        const span = (nextStart - prevEnd) / (nk - k);
        for (let x = k; x < nk; x++) {
          const a = Math.round(prevEnd + (x - k) * span);
          const b = Math.round(prevEnd + (x - k + 1) * span);
          caps.push({ text: sChars[x], startMs: a, endMs: Math.max(b, a + 30),
            timestampMs: Math.round((a + b) / 2), confidence: null });
        }
        prevEnd = nextStart; k = nk;
      }
    }
    if (!caps.length) return null;
    // 标点并入前字 + 句首空格 token（翻页触发）
    const merged = [];
    for (const c of caps) {
      if (merged && '，。！？；、：'.includes(c.text)) merged[merged.length - 1].text += c.text;
      else merged.push(c);
    }
    const paged = [];
    let prevPunct = true;
    for (const c of merged) {
      if (prevPunct) paged.push({ text: ' ', startMs: Math.max(0, c.startMs - 30),
        endMs: c.startMs, timestampMs: Math.max(0, c.startMs - 15), confidence: null });
      paged.push(c);
      prevPunct = c.text.endsWith('。') || c.text.endsWith('！') || c.text.endsWith('？') || c.text.endsWith('；');
    }
    return paged;
  } catch { return null; }
}

/* ------------------------------------------------------------------ *
 * LiteLLM bridge — multi-provider TTS via Python bridge script
 * ------------------------------------------------------------------ */

const { spawnSync } = require('child_process');

// Path to the Python bridge — resolve relative to VAAS root
function resolveBridgePath() {
  // Walk up from scripts/ to find VAAS/scripts/litellm-bridge.py
  let dir = SCRIPTS_DIR;
  for (let i = 0; i < 12; i++) {
    const candidate = path.join(dir, 'scripts', 'litellm-bridge.py');
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  // fallback: relative to VAAS root via common path
  return path.join(SCRIPTS_DIR, '..', '..', '..', 'scripts', 'litellm-bridge.py');
}

// Check if we should use litellm path:
// 1. --litellm flag was passed
// 2. TTS_PROVIDER env var is set and != volcengine
function shouldUseLiteLLM(options, env) {
  if (options && options.litellm) return true;
  const envObj = env || findProjectEnv() || {};
  const provider = (envObj.TTS_PROVIDER || 'volcengine').toLowerCase();
  return provider !== 'volcengine';
}

/**
 * Synthesize speech through the Python litellm-bridge.
 * Returns same shape as synthesizeSpeech() for drop-in compatibility.
 */
async function synthesizeSpeechViaLiteLLM(params, options = {}) {
  const bridgePath = resolveBridgePath();
  const env = findProjectEnv() || {};

  // Determine output path (mirror the local save pattern)
  const outDir = resolveSaveDir(options);
  const fmt = (params.responseFormat || params.response_format || 'mp3').toLowerCase();
  const ext = extForFormat(fmt);
  const outPath = path.join(outDir, `speech.${ext}`);
  const captionsOut = path.join(outDir, 'captions.json');

  // 分段合成路径（add-tts-caption-fallback D2）：词元·腾讯档有单次 ~170 字长度墙
  // （超限 502 + 熔断），真实口播稿（500-1600 字）必须分段。文本超阈值时在出口层
  // 逐段合成、拼接、段级时长对齐 captions——管线零感知。
  const textLen = (params.input || params.text || '').length;
  if (textLen > CIYUAN_SEGMENT_MAX_CHARS) {
    try {
      return await synthesizeSegmentedViaBridge(params, options, env);
    } catch (e) {
      return {
        ok: false,
        error_code: e.code || 'SEGMENTED_TTS_FAILED',
        error_message: e.message || String(e),
        hint: '词元·腾讯 TTS 按段重试耗尽。检查词元 audio 车道上游（sub2api accounts）与网络后重试。',
      };
    }
  }

  const args = [bridgePath, 'tts', '--output', outPath];

  if (params.input || params.text) args.push('--text', params.input || params.text);
  if (params.model) args.push('--model', params.model);
  else if (env.TTS_MODEL) args.push('--model', env.TTS_MODEL);

  if (params.voice) args.push('--voice', params.voice);
  else if (env.TTS_VOICE) args.push('--voice', env.TTS_VOICE);

  if (params.speed != null) args.push('--speed', String(params.speed));
  if (fmt) args.push('--format', fmt);
  if (params.enableSubtitle === false) args.push('--no-subtitle');
  else args.push('--captions', captionsOut);

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

  // Normalize to match synthesizeSpeech() return shape.
  // 字幕来源归一：官方逐字戳 → official；provider 无逐字戳（词元档常态）→
  // 合成兜底（句切 token × ffprobe 实测时长线性缩放）。下游管线只认 Caption[]。
  let captionsPath = data.captions_path || (fs.existsSync(captionsOut) ? captionsOut : null);
  let captionsSource = captionsPath ? 'official' : null;
  if (!captionsPath) {
    const synthesized = buildSyntheticCaptions(
      params.input || params.text || '',
      data.local_path || outPath,
    );
    if (synthesized) {
      fs.writeFileSync(captionsOut, JSON.stringify(synthesized, null, 2));
      captionsPath = captionsOut;
      captionsSource = 'synthetic';
    }
  }

  return {
    ok: true,
    model: data.model || '',
    voice: data.voice || '',
    voice_name: data.voice || '',
    input_length: (params.input || params.text || '').length,
    response_format: fmt,
    speed: params.speed != null ? parseFloat(params.speed) : 1.0,
    local_path: data.local_path || outPath,
    captions_path: captionsPath,
    captions_source: captionsSource,
    captions_count: captionsPath
      ? (JSON.parse(fs.readFileSync(captionsPath, 'utf8'))).length
      : 0,
    audio_duration_seconds: data.audio_duration_seconds || null,
    file_size_bytes: data.file_size_bytes || (fs.existsSync(outPath) ? fs.statSync(outPath).size : 0),
    estimated_duration_seconds: data.estimated_duration_seconds || 0,
    api_latency_ms: data.api_latency_ms || 0,
    provider: data.provider || env.TTS_PROVIDER || 'litellm',
  };
}

module.exports = {
  synthesizeSpeech,
  synthesizeSpeechViaLiteLLM,
  shouldUseLiteLLM,
  listVoices,
  resolveApiKey,
  resolveBaseUrl,
  // 合成字幕兜底（add-tts-caption-fallback）：导出供单测与宿主复用
  splitTextIntoTokens,
  probeAudioDurationSeconds,
  buildSyntheticCaptions,
  parseChunkedResponse,
  resolveSaveDir,
  splitTextIntoSegments,
  buildSegmentedCaptions,
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
  DEFAULT_VOICE,
  DEFAULT_RESPONSE_FORMAT,
  VOICE_MATRIX,
};

'use strict';

/**
 * byted-ark-tts-skill — core module.
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
const SKILL_DIR = path.join(SCRIPTS_DIR, '..');

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

function resolveSaveDir() {
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
    return {
      ok: false,
      error_code: 'DECODE_FAILED',
      error_message: '音频解码失败，原始响应: ' + rawText.substring(0, 300),
      model, base_url: baseUrl,
    };
  }

  const outDir = resolveSaveDir();
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

  // 每块是一整个 JSON 对象；用括号计数拆
  const objects = extractJsonObjects(rawText);
  for (const obj of objects) {
    if (obj && typeof obj.data === 'string' && obj.data.length > 0) {
      audioB64 += obj.data;
    }
    if (obj && obj.sentence && Array.isArray(obj.sentence.words)) {
      sentences.push(obj.sentence);
    }
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

module.exports = {
  synthesizeSpeech,
  listVoices,
  resolveApiKey,
  resolveBaseUrl,
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
  DEFAULT_VOICE,
  DEFAULT_RESPONSE_FORMAT,
  VOICE_MATRIX,
};

#!/usr/bin/env node
'use strict';

/**
 * byted-ark-seedream-skill - CLI wrapper.
 * Sibling of seedance-wrapper.js (video). Entry point for image generation.
 *
 * Usage:
 *   node seedream-wrapper.js create --prompt "..." [--size 2K] [--output-format png] ...
 *   node seedream-wrapper.js create --save-model-preference doubao-seedream-5.0-pro --user-id ou_xxx
 *   node seedream-wrapper.js diagnose        # show resolved key source + base url (masked)
 *   node seedream-wrapper.js help
 */

const core = require('./seedream');

/* ---------------- arg parsing ---------------- */

function parseArgs(argv) {
  const args = { _: [], _imageFile: [], _imageUrl: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      const BOOL_KEYS = new Set(['watermark', 'enable-web-search', 'sequential', 'save-api-key', 'no-preference']);
      if (BOOL_KEYS.has(key)) {
        args[toCamel(key)] = true;
        continue;
      }
      // flag with value (next token, unless it's another flag)
      if (next !== undefined && !next.startsWith('--')) {
        if (key === 'image-file') args._imageFile.push(next);
        else if (key === 'image-url') args._imageUrl.push(next);
        else args[toCamel(key)] = next;
        i++;
      } else {
        args[toCamel(key)] = true;
      }
    } else {
      args._.push(a);
    }
  }
  if (args._imageFile.length) args.imageFile = args._imageFile;
  if (args._imageUrl.length) args.imageUrl = args._imageUrl;
  // coerce booleans passed as strings
  for (const k of ['watermark', 'enableWebSearch', 'sequential', 'saveApiKey', 'noPreference']) {
    if (typeof args[k] === 'string') args[k] = ['true', '1', 'yes'].includes(args[k].toLowerCase());
  }
  return args;
}

function toCamel(s) {
  return s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}

/* ---------------- commands ---------------- */

async function cmdCreate(args) {
  // preference-only mode (no prompt)
  if (args.saveModelPreference !== undefined) {
    const saved = core.savePreference(args.userId || 'default', args.saveModelPreference);
    if (!args.prompt) {
      console.log(saved
        ? JSON.stringify({ status: 'success', message: `已成功保存模型偏好: ${saved}` })
        : JSON.stringify({ status: 'success', message: '已清除模型偏好，恢复默认路由' }));
      return;
    }
    // if both prompt + save pref, save then continue to generate
  }

  if (!args.prompt) {
    console.log(JSON.stringify({ ok: false, error_code: 'MISSING_PROMPT', error_message: '缺少 --prompt 参数' }));
    process.exit(1);
  }

  const params = {
    prompt: args.prompt,
    size: args.size,
    outputFormat: args.outputFormat,
    responseFormat: args.responseFormat,
    watermark: args.watermark,
    imageFile: args.imageFile,
    imageUrl: args.imageUrl,
    enableWebSearch: args.enableWebSearch,
    sequential: args.sequential,
    maxImages: args.maxImages,
    seed: args.seed,
    optimizePrompt: args.optimizePrompt,
    quality: args.quality,
    userId: args.userId || 'default',
  };

  try {
    const result = await core.generateImage(params, {
      apiKey: args.apiKey,
      baseUrl: args.baseUrl,
      noPreference: args.noPreference,
    });

    if (!result.ok) {
      printError(result);
      process.exit(1);
    }

    // success
    if (result.change_reason) {
      console.log(JSON.stringify({ model_change_reason: result.change_reason }));
    }
    printSuccess(result);
  } catch (e) {
    if (e.code === 'NO_API_KEY') {
      console.log(JSON.stringify({ ok: false, error_code: 'NO_API_KEY', error_message: e.message.trim() }));
    } else {
      console.log(JSON.stringify({ ok: false, error_code: e.code || 'RUNTIME_ERROR', error_message: e.message }));
    }
    process.exit(1);
  }
}

function printSuccess(r) {
  console.log('');
  console.log('🎉 图片生成完成！');
  console.log('');
  console.log(`🤖 使用模型: ${r.model}`);
  console.log(`📐 尺寸: ${r.size}`);
  console.log(`🖼️ 数量: ${r.count}`);
  r.images.forEach((img, i) => {
    if (img.url) console.log(`🔗 在线图片地址${r.count > 1 ? ' (' + (i + 1) + ')' : ''}: ${img.url}`);
    if (img.local_path) console.log(`💾 已自动下载到本地${r.count > 1 ? ' (' + (i + 1) + ')' : ''}: ${img.local_path}`);
  });
  console.log('');
}

function printError(r) {
  console.log('');
  console.log(`❌ 图片生成失败 (HTTP ${r.status || '?'})`);
  console.log(`   错误码: ${r.error_code}`);
  console.log(`   信息: ${r.error_message}`);
  if (r.model) console.log(`   模型: ${r.model}`);
  if (r.base_url) console.log(`   入口: ${r.base_url}`);
  if (r.key_source) console.log(`   Key 来源: ${r.key_source}`);
  if (r.hint) { console.log(''); console.log(`   💡 ${r.hint}`); }
  console.log('');
}

async function cmdDiagnose(args) {
  try {
    const { key, source, env } = await core.resolveApiKey({ apiKey: args.apiKey });
    const baseUrl = core.resolveBaseUrl({ baseUrl: args.baseUrl }, env);
    console.log(JSON.stringify({
      ok: true,
      key_source: source,
      key_prefix: key.slice(0, 12) + '...',
      key_length: key.length,
      base_url: baseUrl,
      default_model: core.DEFAULT_MODEL,
      env_model: env && env.model,
      env_vol_base_url: env && env.vol_base_url,
      matrix_models: Object.keys(core.loadMatrix()),
    }, null, 2));
  } catch (e) {
    console.log(JSON.stringify({ ok: false, error_code: e.code || 'ERROR', error_message: e.message.trim() }));
  }
}

function cmdHelp() {
  console.log(`
豆包 Seedream 图像生成 Skill (Agent Plan)

用法:
  node seedream-wrapper.js create --prompt "描述" [选项]
  node seedream-wrapper.js diagnose
  node seedream-wrapper.js help

create 选项:
  --prompt <text>           图片描述 (必填)
  --size <2K|3K|4K|WxH>     尺寸 (默认 2K)
  --output-format <png|jpeg> 输出格式 (png 仅 5.0-lite; 默认 jpeg)
  --response-format <url|b64_json> 返回格式 (默认 url)
  --watermark <bool>        是否加水印 (默认 false)
  --image-file <path>       本地参考图 (可多次传入)
  --image-url <url>         在线参考图 URL (可多次传入)
  --enable-web-search       联网搜索 (仅 5.0-lite)
  --sequential              批量顺序生成
  --max-images <n>          批量最大数 [1,15]
  --seed <int>              随机种子 (仅 3.0-t2i)
  --optimize-prompt <standard|fast> 提示词优化
  --quality <ultra>         画质偏好 (ultra 倾向 5.0-pro)
  --model <name>            手动指定模型 (一般不传)
  --save-model-preference <name|none> 保存/清除偏好模型
  --user-id <id>            用户ID (偏好隔离)
  --api-key <ark-...>       临时 API key
  --base-url <url>          覆盖 base url
  --no-preference           本次忽略已保存偏好

示例:
  node seedream-wrapper.js create --prompt "橘猫戴墨镜坐海边" --size 2K --output-format png
  node seedream-wrapper.js create --prompt "按参考图画一只狗" --image-file /path/ref.jpg
`);
}

/* ---------------- main ---------------- */

async function main() {
  const argv = process.argv.slice(2);
  if (!argv.length || argv[0] === 'help' || argv[0] === '--help' || argv[0] === '-h') {
    cmdHelp();
    return;
  }
  const command = argv[0];
  const args = parseArgs(argv.slice(1));
  switch (command) {
    case 'create': await cmdCreate(args); break;
    case 'diagnose': await cmdDiagnose(args); break;
    case 'models': console.log(JSON.stringify(Object.keys(core.loadMatrix()), null, 2)); break;
    default:
      console.log(JSON.stringify({ ok: false, error_code: 'UNKNOWN_COMMAND', error_message: `未知命令: ${command}` }));
      cmdHelp();
      process.exit(1);
  }
}

main().catch((e) => {
  console.log(JSON.stringify({ ok: false, error_code: 'FATAL', error_message: e && e.message ? e.message : String(e) }));
  process.exit(1);
});

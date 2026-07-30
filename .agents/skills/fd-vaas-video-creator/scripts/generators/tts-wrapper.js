#!/usr/bin/env node

/**
 * fd-vaas-video-creator - TTS wrapper.
 *
 * 设计原则（与 seedance/seedream 保持一致）：
 *   1. Agent 层只做语义理解（提取文本、音色偏好、语速）
 *   2. Wrapper 层负责参数校验、默认值填充、API 调用
 *   3. 智能音色推断（根据文本语言自动选择最佳音色）
 */

const fs = require('fs');
const path = require('path');

const SCRIPTS_DIR = __dirname;
const SKILL_DIR = path.join(SCRIPTS_DIR, '..', '..');
const TTS_MODULE = path.join(SCRIPTS_DIR, 'tts.js');

const tts = require(TTS_MODULE);

// ============================================
// 🛠️ 参数工具函数
// ============================================

function getArgValue(args, key, altKey) {
  const idx = args.indexOf(key);
  if (idx !== -1 && args[idx + 1] && !args[idx + 1].startsWith('--')) return args[idx + 1];
  if (altKey) return getArgValue(args, altKey);
  return null;
}

function hasArg(args, key) {
  return args.indexOf(key) !== -1;
}

// 展开 ~ 开头的路径
function expandHome(p) {
  const os = require('os');
  const home = os.homedir();
  if (p === '~') return home;
  if (p.startsWith('~/')) return path.join(home, p.slice(2));
  return p;
}

// 从文件读取文本内容
function readTextFile(filePath) {
  const absPath = expandHome(filePath);
  if (!fs.existsSync(absPath)) {
    console.error(`❌ 文件不存在: ${absPath}`);
    process.exit(1);
  }
  return fs.readFileSync(absPath, 'utf8');
}

// ============================================
// 🎯 handleCreate — 语音合成主入口
// ============================================

async function handleCreate(args) {
  // 提取参数
  const apiKey = getArgValue(args, '--api-key');
  const baseUrl = getArgValue(args, '--base-url');
  const model = getArgValue(args, '--model');
  const voice = getArgValue(args, '--voice');
  const responseFormat = getArgValue(args, '--response-format') || getArgValue(args, '--format');
  const speed = getArgValue(args, '--speed');
  const emotion = getArgValue(args, '--emotion');
  const volume = getArgValue(args, '--volume');
  const pitch = getArgValue(args, '--pitch');
  // 逐字时间戳（默认开启）；传 --no-subtitle 关闭
  const enableSubtitle = !hasArg(args, '--no-subtitle');

  // 文本来源：--input 或 --text 直接传入；--input-file 从文件读取
  let inputText = getArgValue(args, '--input') || getArgValue(args, '--text');
  const inputFile = getArgValue(args, '--input-file') || getArgValue(args, '--file');

  if (inputFile) {
    inputText = readTextFile(inputFile);
  }

  // --list-voices 单独处理
  if (hasArg(args, '--list-voices') || hasArg(args, '--voices')) {
    tts.listVoices({ model });
    return;
  }

  const useLiteLLM = hasArg(args, '--litellm');

  const params = {
    input: inputText,
    model,
    voice,
    responseFormat,
    speed,
    emotion,
    volume,
    pitch,
    enableSubtitle,
  };

  const options = {
    apiKey,
    baseUrl,
    litellm: useLiteLLM,
  };

  // Auto-route: if --litellm flag is set OR TTS_PROVIDER is non-volcengine in .env
  const useBridge = useLiteLLM || tts.shouldUseLiteLLM(options);
  const result = useBridge
    ? await tts.synthesizeSpeechViaLiteLLM(params, options)
    : await tts.synthesizeSpeech(params, options);

  if (!result.ok) {
    console.error('\n❌ 语音合成失败\n');
    console.error(`错误码: ${result.error_code}`);
    console.error(`错误信息: ${result.error_message}`);
    if (result.hint) {
      console.error(`\n💡 提示: ${result.hint}`);
    }
    process.exit(1);
  }

  // 成功输出
  console.log('\n' + '='.repeat(50));
  console.log('🎉 语音合成完成！\n');
  console.log(`🤖 使用模型: ${result.model}`);
  if (result.provider) console.log(`🏢 Provider: ${result.provider}`);
  console.log(`🎤 音色: ${result.voice} (${result.voice_name})`);
  console.log(`📝 文本长度: ${result.input_length} 字符`);
  console.log(`⚡ 速度倍率: ${result.speed}x`);
  console.log(`🎵 格式: ${result.response_format}`);
  console.log(`⏱️ API 耗时: ${result.api_latency_ms}ms`);
  console.log(`📦 文件大小: ${Math.round(result.file_size_bytes / 1024)} KB`);
  if (result.estimated_duration_seconds) console.log(`⏰ 预计时长: ${result.estimated_duration_seconds} 秒`);
  console.log(`\n💾 本地文件路径:`);
  console.log(`   ${result.local_path}`);
  if (result.captions_path) {
    console.log(`📝 字幕文件路径 (${result.captions_count} 个字/词，逐字时间戳):`);
    console.log(`   ${result.captions_path}`);
    if (result.audio_duration_seconds != null) {
      console.log(`⏱️ 官方音频时长: ${result.audio_duration_seconds.toFixed(2)} 秒`);
    }
  }
  console.log('='.repeat(50) + '\n');
}

// ============================================
// 📋 handleListVoices — 列出支持的音色
// ============================================

async function handleListVoices(args) {
  const model = getArgValue(args, '--model');
  tts.listVoices({ model });
}

// ============================================
// 🚪 主入口
// ============================================

async function main() {
  const args = process.argv.slice(2);

  let command = 'create';
  let commandArgs = args;

  if (args.length > 0 && !args[0].startsWith('--')) {
    command = args[0];
    commandArgs = args.slice(1);
  }

  // --help 优先处理
  if (hasArg(args, '--help') || hasArg(args, '-h')) {
    command = 'help';
  }

  switch (command) {
    case 'create':
    case 'synth':
    case 'generate':
      await handleCreate(commandArgs);
      break;
    case 'list-voices':
    case 'voices':
      await handleListVoices(commandArgs);
      break;
    case 'help':
    default:
      console.log(`
Ark TTS Skill - 豆包语音合成

用法:
  node tts-wrapper.js create [options]    生成语音（默认命令，可省略 create）
  node tts-wrapper.js voices [--model m]  列出支持的音色列表
  node tts-wrapper.js help                 显示帮助

常用选项:
  --input, --text <文本>       要合成的文本内容（必填）
  --input-file, --file <路径>  从文本文件读取内容（替代 --input）
  --voice <音色ID>             指定音色（默认: zh-CN-Yunxia，云夏-温柔女声）
  --speed <倍率>               语速 [0.25, 4.0]（默认: 1.0）
  --format, --response-format <fmt>  输出格式: mp3, opus, aac, flac, wav, pcm
  --model <模型名>             指定模型（默认: doubao-tts-2.5l-pro）
  --api-key <key>              临时指定 API Key（默认读取 .env）
  --base-url <url>             自定义 API 入口地址
  --no-subtitle                关闭逐字时间戳（默认开启，输出 captions.json）

音色示例:
  中文女声: zh-CN-Yunxia (温柔), zh-CN-Yunxi (成熟), zh-CN-Yunyang (活泼)
  中文男声: zh-CN-Yunjian (沉稳), zh-CN-Yunhao (阳光), zh-CN-Yunfan (磁性)
  英文: en-US-Aria, en-US-Davis
  日语: ja-JP-Nanami
  韩语: ko-KR-SunHi

快速示例:
  # 简单文本
  node tts-wrapper.js --text "你好，欢迎使用豆包语音合成"

  # 指定音色和语速
  node tts-wrapper.js --text "Hello World" --voice en-US-Aria --speed 1.2

  # 从文件读取
  node tts-wrapper.js --file /path/to/script.txt --voice zh-CN-Yunfan

  # 查看所有音色
  node tts-wrapper.js voices

提示: Agent 层会自动根据文本语言推断最合适的音色！
      `.trim());
  }
}

main().catch(e => {
  console.error('❌ 执行失败:', e.message);
  console.error(e.stack);
  process.exit(1);
});

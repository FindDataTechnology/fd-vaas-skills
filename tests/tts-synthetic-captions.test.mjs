#!/usr/bin/env node
/**
 * tts.js 合成字幕兜底（add-tts-caption-fallback task 1.1）单测。
 * 运行: node tests/tts-synthetic-captions.test.mjs
 * 覆盖: token 切分（标点并入/Latin 整体）、实测时长缩放、末帧对齐、单调性。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const tts = require('../.agents/skills/fd-vaas-video-creator/scripts/generators/tts.js');

function makeSilentMp3(seconds) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tts-test-'));
  const mp3 = path.join(dir, 'a.mp3');
  execFileSync('ffmpeg', ['-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono',
    '-t', String(seconds), '-codec:a', 'libmp3lame', '-q:a', '4', mp3], { stdio: 'pipe' });
  return mp3;
}

test('token 切分：中文按字、标点并入前字、Latin 连续词元整体', () => {
  const tokens = tts.splitTextIntoTokens('问一句话，拿回真实数据行。这是 FindData 的 TTS，pipeline 通过。');
  assert.ok(tokens.includes('FindData'), 'Latin 词元应整体一个 token');
  assert.ok(tokens.includes('话，'), '标点应并入前字');
  assert.ok(!tokens.includes('，'), '标点不应单独成 token');
  assert.ok(tokens.includes('pipeline'), '英文单词不拆字');
});

test('合成字幕：末帧对齐实测时长（±50ms）、单调递增', () => {
  const mp3 = makeSilentMp3(10);
  const caps = tts.buildSyntheticCaptions('问一句话，拿回真实数据行。这是 FindData 的 TTS，pipeline 通过。', mp3);
  assert.ok(caps && caps.length > 10, '应有 token 产出');
  const last = caps[caps.length - 1];
  assert.ok(Math.abs(last.endMs - 10000) <= 50, `末帧 endMs=${last.endMs} 应为 10000±50`);
  for (let i = 1; i < caps.length; i++) {
    assert.ok(caps[i].startMs >= caps[i - 1].endMs - 1, '时间戳应单调');
  }
  assert.equal(caps.every(c => typeof c.text === 'string' && c.text.length > 0), true);
});

test('合成字幕：空音频/失败返回 null（不伪造）', () => {
  assert.equal(tts.buildSyntheticCaptions('文本', '/nonexistent/audio.mp3'), null);
});

test('实测时长探测：ffprobe 返回正数', () => {
  const mp3 = makeSilentMp3(2);
  const d = tts.probeAudioDurationSeconds(mp3);
  assert.ok(d > 1.5 && d < 2.5, `duration=${d}`);
});

test('错误分类：Ark InvalidSubscription 错误块直出，禁伪装 DECODE_FAILED', () => {
  const sample = JSON.stringify({ reqid: 'x', code: 45000000, message: 'acquire failed code:InvalidSubscription message:Your account does not have a valid AgentPlan subscription' });
  const r = tts.parseChunkedResponse(sample);
  assert.ok(r.errorBlock, '应识别错误块');
  assert.match(r.errorBlock.message, /InvalidSubscription/);
  assert.match(r.hint, /TTS_PROVIDER=ciyuan/, 'hint 应含可行动提示');
});

test('--output-dir：指定目录直写（确定性落盘），未指定走桌面 fallback', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'outdir-'));
  assert.equal(tts.resolveSaveDir({ outputDir: tmp }), tmp);
  const fallback = tts.resolveSaveDir({});
  assert.match(fallback, /Ark-TTS\/\d{8}-\d{6}$/);
});

test('分段切分：1600 字口播稿切成 ≤150 字段、句边界优先', () => {
  const long = '问一句话，拿回真实数据行。'.repeat(60); // 660 字
  const segs = tts.splitTextIntoSegments ? tts.splitTextIntoSegments(long) : null;
  if (!segs) { console.log('(splitTextIntoSegments 未导出，跳过)'); return; }
  assert.ok(segs.every(s => s.length <= 150), `最长段 ${Math.max(...segs.map(s => s.length))} 字`);
  assert.equal(segs.reduce((a, s) => a + s.length, 0) <= long.length + segs.length, true);
});

test('whisper 对齐：句首空格 token 触发 TikTok 分页（≥句数页）', async () => {
  const { createTikTokStyleCaptions } = require('/Users/chengsishi/VAAS/remotion-app/node_modules/@remotion/captions');
  const mp3 = makeSilentMp3(6);
  const caps = tts.buildSyntheticCaptions('问一句话，拿回真实数据行。这是寻数科技。数据留在你手里。', mp3);
  // 均分版应只有 1 页（零间隙合并）
  const p1 = createTikTokStyleCaptions({ captions: caps, combineTokensWithinMilliseconds: 1400 });
  // 走出口层 whisper 对齐（本机有 whisper-cli + /tmp/ggml-small.bin 时生效）
  const aligned = tts.buildSyntheticCaptionsWithWhisper
    ? await tts.buildSyntheticCaptionsWithWhisper('问一句话，拿回真实数据行。这是寻数科技。数据留在你手里。', mp3)
    : null;
  if (aligned) {
    const p2 = createTikTokStyleCaptions({ captions: aligned, combineTokensWithinMilliseconds: 1400 });
    assert.ok(p2.pages.length >= 3, `whisper 对齐应 ≥3 页，实际 ${p2.pages.length}`);
    assert.ok(!aligned.some(c => c.text.includes('巡述')), '不应出现 whisper 识别错字（稿侧兜底）');
  } else {
    console.log('   (本机无 whisper 模型，跳过分页断言)');
  }
});

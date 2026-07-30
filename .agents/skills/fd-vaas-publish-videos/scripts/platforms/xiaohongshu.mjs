#!/usr/bin/env node
/**
 * 小红书上传 CLI - ego-browser 版本
 *
 * 用法: node xiaohongshu.mjs --file <mp4> --title <标题> [--desc <描述>] [--tags <标签>]
 *
 * 注意：小红书标题 ≤ 20 字，话题 ≤ 10 个。
 */

import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const args = process.argv.slice(2);
const getArg = (k) => {
  const i = args.indexOf(k);
  return i !== -1 && args[i + 1] && !args[i + 1].startsWith('--')
    ? args[i + 1]
    : null;
};

const file = getArg('--file');
const title = getArg('--title');
const desc = getArg('--desc') || '';
const tagsStr = getArg('--tags') || '';
const cover = getArg('--cover') || '';
const dryRun = args.includes('--dry-run');

if (!file || !title) {
  console.error(`
用法: node xiaohongshu.mjs --file <视频文件> --title <标题> [选项]

必填:
  --file <path>        视频文件路径 (mp4)
  --title <string>     视频标题（≤ 20 字）

可选:
  --desc <string>      视频描述/正文
  --tags <string>      话题标签，逗号分隔（≤ 10 个）
  --cover <path>       封面图片路径
  --dry-run            只打开页面不上传

示例:
  node xiaohongshu.mjs \\
    --file video.mp4 \\
    --title "寻数科技品牌介绍" \\
    --desc "通过开源技术推动信息平权" \\
    --tags "开源,AI,数据"
`);
  process.exit(1);
}

if (!fs.existsSync(file)) {
  console.error(`❌ 视频文件不存在: ${file}`);
  process.exit(1);
}

const absFile = path.resolve(file);
const taskSpace = `xhs-publish-${Date.now()}`;
const tags = tagsStr.split(',').map(t => t.trim()).filter(Boolean);
const titleSliced = title.slice(0, 20);

console.log(`📱 小红书发布
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
视频:   ${absFile}
标题:   ${titleSliced}
描述:   ${desc || '(无)'}
标签:   ${tags.join(', ') || '(无)'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

const escapedFile = absFile.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedTitle = titleSliced.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedDesc = desc.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const tagsJson = JSON.stringify(tags);

const egoScript = `
await useOrCreateTaskSpace('${taskSpace}');

cliLog('🌐 打开小红书发布页...');
await openOrReuseTab('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video', { wait: true, timeout: 30 });
await wait(3);

// 检查登录状态
const info = await pageInfo();
if (/\\/login\\b/.test(info.url)) {
  cliLog('⚠️ 需要登录小红书');
  cliLog('   请切换到 ego-browser 窗口扫码登录');
  for (let i = 0; i < 60; i++) {
    await wait(3);
    const newInfo = await pageInfo();
    if (!/\\/login\\b/.test(newInfo.url)) { cliLog('✅ 登录成功！'); break; }
  }
}

${dryRun ? `
cliLog('🔍 dry-run 模式');
await captureScreenshot();
await handOffTaskSpace('dry-run: 页面已打开');
return;
` : ''}

// 上传视频
cliLog('📤 上传视频...');
await uploadFile("div[class^='upload-content'] input.upload-input", '${escapedFile}');
cliLog('等待上传完成...');

// 等上传完成
for (let i = 0; i < 90; i++) {
  const done = await js(String.raw\\\`(()=>{const p=document.querySelector('input.upload-input');if(p){const n=p.parentElement&&p.parentElement.querySelector('.preview-new');if(n&&/上传成功|分辨率|重新上传|编辑封面|已上传|已选择|100%/.test(n.innerText))return true}return !!document.querySelector('input[placeholder*="填写标题"]')})()\\\`);
  if (done) break;
  await wait(2);
}
cliLog('✅ 视频上传完成');

// 填标题（≤ 20 字）
cliLog('📝 填写标题...');
await waitForElement('input[placeholder*="填写标题"]', { timeout: 60 });
await fillInput('input[placeholder*="填写标题"]', '${escapedTitle}');
await wait(1);

// 填正文
${desc ? `
cliLog('📝 填写正文...');
await click('p[data-placeholder*="输入正文描述"]');
await pressKey('Backspace');
await pressKey('Control+a');
await pressKey('Delete');
await typeText('${escapedDesc}');
await pressKey('Enter');
await wait(1);
` : ''}

// 添加话题（≤ 10 个）
${tags.length > 0 ? `
cliLog('🏷️ 添加话题...');
const tags = ${tagsJson};
for (const t of tags.slice(0, 10)) {
  await typeText('#' + t);
  try {
    await waitForElement('#creator-editor-topic-container', { timeout: 6 });
    await waitForElement('#creator-editor-topic-container .item', { timeout: 4 });
    await click('#creator-editor-topic-container .item');
  } catch (e) {
    for (let k = 0; k < ('#' + t).length; k++) await pressKey('Backspace');
  }
  await wait(0.5);
}
` : ''}

// 发布
cliLog('🚀 点击发布...');
await click('xpath=//button[normalize-space(text())="发布"]');
await wait(3);

// 验证发布
for (let i = 0; i < 30; i++) {
  const url = (await pageInfo()).url;
  if (/\\/publish\\/success\\?/.test(url)) {
    cliLog('✅ 发布成功！');
    break;
  }
  await wait(1);
}

await captureScreenshot();
await completeTaskSpace('${taskSpace}', { keep: false });
`;

console.log('🚀 启动 ego-browser...\n');

const ego = spawn('ego-browser', ['nodejs'], {
  stdio: ['pipe', 'inherit', 'inherit'],
  shell: true
});

ego.stdin.write(egoScript);
ego.stdin.end();

ego.on('close', (code) => {
  console.log(`\n${code === 0 ? '✅' : '⚠️'} 完成 (exit: ${code})`);
});

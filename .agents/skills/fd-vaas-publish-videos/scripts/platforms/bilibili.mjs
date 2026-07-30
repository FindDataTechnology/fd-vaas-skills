#!/usr/bin/env node
/**
 * B站上传 CLI - ego-browser 版本
 *
 * ⚠️ 技术要点：
 * - B站使用 micro-app 微前端框架，页面内容在 micro-app[name=video-up].shadowRoot 内
 * - 所有 DOM 查询必须通过 shadowRoot 访问
 * - uploadFile() 可能失效，需用 CDP DOM.setFileInputFiles 或 HTTP 服务器方案
 *
 * 用法: node bilibili.mjs --file <mp4> --title <标题> [--desc <简介>] [--tags <标签>] [--cover <封面>] [--tid 124]
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
const tid = getArg('--tid') || '124';
const dryRun = args.includes('--dry-run');

if (!file || !title) {
  console.error(`
用法: node bilibili.mjs --file <视频文件> --title <标题> [选项]

必填:
  --file <path>        视频文件路径 (mp4)
  --title <string>     视频标题

可选:
  --desc <string>      视频简介
  --tags <string>      标签，逗号分隔
  --cover <path>       封面图片路径（建议 1920×1080）
  --tid <number>       分区 ID（默认 124=科普，36=科技软件, 208=财经商业）
  --dry-run            只打开页面不上传

⚠️ B站使用 micro-app 微前端，DOM 查询需通过 shadowRoot。
`);
  process.exit(1);
}

if (!fs.existsSync(file)) {
  console.error(`❌ 视频文件不存在: ${file}`);
  process.exit(1);
}

const absFile = path.resolve(file);
const absCover = cover && fs.existsSync(cover) ? path.resolve(cover) : '';
const taskSpace = `bilibili-publish-${Date.now()}`;
const tags = tagsStr.split(',').map(t => t.trim()).filter(Boolean);

console.log(`📺 B站发布
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
视频:   ${absFile}
标题:   ${title}
简介:   ${desc || '(无)'}
标签:   ${tags.join(', ') || '(无)'}
分区:   ${tid}
封面:   ${absCover || '(默认)'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

const escapedFile = absFile.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedTitle = title.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedDesc = desc.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedCover = absCover.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

const egoScript = `
await useOrCreateTaskSpace('${taskSpace}');

cliLog('🌐 打开 B站创作中心上传页...');
await gotoAndWait('https://member.bilibili.com/v2#/upload/video/frame');
await wait(5);

// ⚠️ 等待 micro-app 加载
cliLog('⏳ 等待 micro-app 微前端加载...');
for (let i = 0; i < 15; i++) {
  const ready = await js(\\\`!!document.querySelector('micro-app[name=video-up]')?.shadowRoot\\\`);
  if (ready) { cliLog('✅ micro-app 已加载'); break; }
  await wait(2);
}

// 检查登录
const loginCheck = await js(\\\`(() => {
  const text = document.body.innerText.slice(0, 500);
  return text.includes('扫码登录') || text.includes('登录');
})()\\\`);
if (loginCheck) {
  cliLog('⚠️ 需要登录 B站');
  cliLog('   请切换到 ego-browser 窗口扫码登录');
  for (let i = 0; i < 60; i++) {
    await wait(3);
    const ready = await js(\\\`!!document.querySelector('micro-app[name=video-up]')?.shadowRoot\\\`);
    if (ready) { cliLog('✅ 登录成功！'); break; }
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
// 方案 A: 尝试直接 uploadFile
let uploaded = false;
try {
  await uploadFile('input[type="file"]', '${escapedFile}');
  uploaded = true;
} catch (e) {
  cliLog('uploadFile 失败，尝试 CDP 方案...');
}

if (!uploaded) {
  // 方案 B: 用 CDP DOM.setFileInputFiles（穿透 shadow DOM）
  const doc = await cdp('DOM.getDocument', { depth: -1, pierce: true });
  function findFileInput(node) {
    if (!node) return null;
    if (node.nodeName === 'INPUT' && node.attributes) {
      for (let i = 0; i < node.attributes.length; i += 2) {
        if (node.attributes[i] === 'type' && node.attributes[i+1] === 'file') return node;
      }
    }
    if (node.children) for (const c of node.children) { const r = findFileInput(c); if (r) return r; }
    if (node.shadowRoots) for (const sr of node.shadowRoots) { const r = findFileInput(sr); if (r) return r; }
    return null;
  }
  const fileInput = findFileInput(doc?.root);
  if (fileInput) {
    await cdp('DOM.setFileInputFiles', {
      backendNodeId: fileInput.backendNodeId,
      files: ['${escapedFile}']
    });
    cliLog('CDP setFileInputFiles 完成');
  }
}

cliLog('等待上传完成...');
await wait(30);

// 在 shadow DOM 内填写标题
cliLog('📝 填写标题...');
await js(\\\`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const input = sr?.querySelector('input[placeholder*="标题"]');
  if (input) {
    input.focus();
    input.value = '${escapedTitle}';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return 'title set';
  }
  return 'no title input';
})()\\\`);
await wait(1);

// 填写简介
${desc ? `
cliLog('📝 填写简介...');
await js(\\\`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const textarea = sr?.querySelector('textarea');
  if (textarea) {
    textarea.focus();
    textarea.value = '${escapedDesc}';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    return 'desc set';
  }
  return 'no textarea';
})()\\\`);
await wait(1);
` : ''}

// 添加标签
${tags.length > 0 ? `
cliLog('🏷️ 添加标签...');
for (const tag of ${JSON.stringify(tags)}) {
  await js(\\\`(() => {
    const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
    const tagInput = sr?.querySelector('input[placeholder*="标签"]');
    if (tagInput) {
      tagInput.focus();
      tagInput.value = '\\\${tag}';
      tagInput.dispatchEvent(new Event('input', { bubbles: true }));
      tagInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      return 'tag: ' + '\\\${tag}';
    }
    return 'no tag input';
  })()\\\`);
  await wait(1);
}
` : ''}

// 上传封面
${absCover ? `
cliLog('🖼️ 上传封面...');
await js(\\\`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const coverArea = sr?.querySelector('[class*="cover"] [class*="upload"], [class*="cover-upload"]');
  coverArea?.click();
  return coverArea ? 'clicked' : 'no cover area';
})()\\\`);
await wait(2);
try {
  await uploadFile('input[type="file"][accept*="image"]', '${escapedCover}');
  await wait(5);
  cliLog('✅ 封面已上传');
} catch(e) {
  cliLog('⚠️ 封面上传失败: ' + e.message);
}
` : ''}

// 点击发布
cliLog('🚀 点击发布...');
await js(\\\`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const btn = sr?.querySelector('button.submit, [class*="submit"]');
  if (btn) { btn.click(); return 'clicked submit'; }
  return 'no submit btn';
})()\\\`);
await wait(5);

// 验证
const url = await js('window.location.href');
const success = url.includes('success') || url.includes('manager');
cliLog(success ? '✅ 发布成功！' : '⚠️ 请检查发布状态');

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

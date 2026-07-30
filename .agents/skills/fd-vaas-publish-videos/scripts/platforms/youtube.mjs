#!/usr/bin/env node
/**
 * YouTube 上传 CLI - ego-browser 版本
 *
 * ⚠️ 技术要点：
 * - Polymer Web Components：tp-yt-paper-dialog 需强制 opened=true + display:block
 * - 4 步上传对话框：Details -> Video elements -> Checks -> Visibility
 * - "Not made for kids" 必答，否则 Next 按钮禁用
 * - 标题用 execCommand（contenteditable，不能用 .value）
 *
 * 用法: node youtube.mjs --file <mp4> --title <标题> [--desc <描述>] [--tags <标签>] [--thumbnail <缩略图>] [--visibility public]
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
const thumbnail = getArg('--thumbnail') || '';
const visibility = getArg('--visibility') || 'public';
const dryRun = args.includes('--dry-run');

if (!file || !title) {
  console.error(`
用法: node youtube.mjs --file <视频文件> --title <标题> [选项]

必填:
  --file <path>         视频文件路径 (mp4)
  --title <string>      视频标题

可选:
  --desc <string>       视频描述
  --tags <string>       标签，逗号分隔
  --thumbnail <path>    缩略图路径（建议 1280×720）
  --visibility <string> 可见性：public (默认), unlisted, private
  --dry-run             只打开页面不上传

⚠️ YouTube 使用 Polymer Web Components，对话框需强制打开。
`);
  process.exit(1);
}

if (!fs.existsSync(file)) {
  console.error(`❌ 视频文件不存在: ${file}`);
  process.exit(1);
}

const absFile = path.resolve(file);
const absThumbnail = thumbnail && fs.existsSync(thumbnail) ? path.resolve(thumbnail) : '';
const taskSpace = `youtube-publish-${Date.now()}`;
const tags = tagsStr.split(',').map(t => t.trim()).filter(Boolean);

console.log(`▶️ YouTube 发布
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
视频:     ${absFile}
标题:     ${title}
描述:     ${desc || '(无)'}
标签:     ${tags.join(', ') || '(无)'}
缩略图:   ${absThumbnail || '(无)'}
可见性:   ${visibility}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

const escapedFile = absFile.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedTitle = title.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedDesc = desc.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedThumb = absThumbnail.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedVis = visibility.replace(/'/g, "\\'");

const egoScript = `
(async () => {
await useOrCreateTaskSpace('${taskSpace}');

cliLog('🌐 打开 YouTube Studio 上传页...');
await gotoAndWait('https://studio.youtube.com/videos/upload');
await wait(5);

// 检查登录
const loginCheck = await js(\`(() => {
  const text = document.body.innerText.slice(0, 500);
  return text.includes('Sign in') || text.includes('sign in') || text.includes('登录');
})()\`);
if (loginCheck) {
  cliLog('⚠️ 需要登录 Google 账号');
  cliLog('   请切换到 ego-browser 窗口完成登录（可能需要 2FA）');
  for (let i = 0; i < 100; i++) {
    await wait(3);
    const stillLogin = await js(\`document.body.innerText.includes('Sign in')\`);
    if (!stillLogin) { cliLog('✅ 登录成功！'); break; }
  }
}

${dryRun ? `
cliLog('🔍 dry-run 模式');
await captureScreenshot();
cliLog('dry-run: 页面已打开');
await handOffTaskSpace();
return;
` : ''}

// 上传视频
cliLog('📤 上传视频...');
await uploadFile('input[type="file"]', '${escapedFile}');
cliLog('等待上传完成...');
await wait(30);

// 等待上传对话框出现
cliLog('⏳ 等待上传对话框...');
for (let i = 0; i < 15; i++) {
  const hasDialog = await js(\`!!document.querySelector('ytcp-uploads-dialog')\`);
  if (hasDialog) break;
  await wait(3);
}

// ⚠️ 强制打开 Polymer 对话框
cliLog('🔓 强制打开 Polymer 对话框...');
await js(\`(() => {
  const dialog = document.querySelector('ytcp-uploads-dialog');
  if (!dialog) return 'no dialog';
  const paper = dialog.querySelector('tp-yt-paper-dialog');
  if (paper) {
    paper.opened = true;
    paper.style.display = 'block';
    paper.setAttribute('opened', '');
  }
  return 'forced open';
})()\`);
await wait(2);

// 填写标题（contenteditable #textbox，用 execCommand）
cliLog('📝 填写标题...');
await js(\`(() => {
  const textbox = document.querySelector('#textbox');
  if (!textbox) return 'no textbox';
  textbox.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, '${escapedTitle}');
  return 'title set';
})()\`);
await wait(1);

// 填写描述（第二个 #textbox）
${desc ? `
cliLog('📝 填写描述...');
await js(\`(() => {
  const textboxes = document.querySelectorAll('#textbox[contenteditable]');
  if (textboxes.length >= 2) {
    textboxes[1].focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
    document.execCommand('insertText', false, '${escapedDesc}');
    return 'desc set';
  }
  return 'no desc textbox';
})()\`);
await wait(1);
` : ''}

// ⚠️ 选择 "No, it's not made for kids"（必答！否则 Next 禁用）
cliLog('👶 选择 "Not made for kids"...');
await js(\`(() => {
  const radios = document.querySelectorAll('tp-yt-paper-radio-button');
  for (const r of radios) {
    if (r.textContent?.includes('No') && r.textContent?.includes('kids')) {
      r.click();
      return 'clicked not for kids';
    }
  }
  return 'not found';
})()\`);
await wait(1);

// 上传缩略图（可选）
${absThumbnail ? `
cliLog('🖼️ 上传缩略图...');
await js(\`document.querySelector('#thumbnail [class*="upload"]')?.click()\`);
await wait(1);
try {
  await uploadFile('input[type="file"][accept*="image"]', '${escapedThumb}');
  await wait(5);
  cliLog('✅ 缩略图已上传');
} catch(e) {
  cliLog('⚠️ 缩略图上传失败: ' + e.message);
}
` : ''}

// 点击 Next 3 次（Details -> Video elements -> Checks -> Visibility）
cliLog('➡️ 导航到 Visibility 步骤...');
for (let i = 0; i < 3; i++) {
  await js(\`(() => {
    // 先找 ytcp-button 含 "Next"
    const btns = document.querySelectorAll('ytcp-button, #next-button');
    for (const b of btns) {
      if (b.textContent?.trim() === 'Next' && !b.hasAttribute('disabled') && !b.disabled) {
        b.click();
        return 'next ' + (\${i}+1);
      }
    }
    return 'no next (may be processing)';
  })()\`);
  await wait(5);  // Checks 步骤需要等待处理
}

// 选择可见性
cliLog('👁️ 选择可见性: ${escapedVis}...');
await js(\`(() => {
  const radios = document.querySelectorAll('tp-yt-paper-radio-button');
  for (const r of radios) {
    if (r.textContent?.includes('${escapedVis}')) {
      r.click();
      return '${escapedVis} selected';
    }
  }
  return 'not found';
})()\`);
await wait(1);

// 点击 Publish（多候选 + 滚动 + JS 点击兜底）
cliLog('🚀 点击 Publish...');
try {
  const publishResult = await js(\`(async () => {
  window.scrollTo(0, document.body.scrollHeight);
  await new Promise(r => setTimeout(r, 500));
  const candidates = ['Publish', 'Save', '发布'];
  const isVisible = (el) => {
    if (!el || !el.getClientRects) return false;
    const rects = el.getClientRects();
    if (!rects.length) return false;
    const rect = rects[0];
    if (rect.width === 0 || rect.height === 0) return false;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || s.opacity === '0' || s.pointerEvents === 'none') return false;
    return true;
  };
  const doClick = (el) => { el.scrollIntoView({ block: 'center' }); el.click(); };
  const findIn = (root) => {
    const sels = ['button', '[role="button"]', 'a', 'div'];
    for (const sel of sels) {
      for (const el of root.querySelectorAll(sel)) {
        if (!isVisible(el)) continue;
        const t = (el.textContent || '').trim();
        if (candidates.includes(t)) { doClick(el); return { clicked: true, text: t, match: 'exact' }; }
      }
    }
    for (const sel of sels) {
      for (const el of root.querySelectorAll(sel)) {
        if (!isVisible(el)) continue;
        const t = (el.textContent || '').trim();
        if (t.length > 0 && t.length <= 20 && candidates.some(c => t.includes(c))) { doClick(el); return { clicked: true, text: t, match: 'contains' }; }
      }
    }
    return null;
  };
  let result = findIn(document);
  if (!result) {
    const btn = document.querySelector('#done-button');
    if (btn && isVisible(btn) && !btn.hasAttribute('disabled') && !btn.disabled) { doClick(btn); result = { clicked: true, text: 'Publish', match: 'id' }; }
  }
  if (!result) {
    const btns = document.querySelectorAll('ytcp-button');
    for (const b of btns) {
      if (b.textContent && b.textContent.trim() === 'Publish' && !b.hasAttribute('disabled') && !b.disabled) { doClick(b); result = { clicked: true, text: 'Publish', match: 'ytcp' }; break; }
    }
  }
  return JSON.stringify(result || { clicked: false });
})()\`);
  let r;
  try { r = typeof publishResult === 'string' ? JSON.parse(publishResult) : publishResult; } catch (pe) { r = {}; }
  if (!r || !r.clicked) {
    throw new Error('未找到 Publish 按钮' + (r && r.text ? ': ' + r.text : ''));
  }
  cliLog('✅ 已点击 Publish 按钮: ' + r.text + ' (' + r.match + ')');
} catch (e) {
  cliLog('⚠️ Publish 按钮点击失败: ' + e.message);
  cliLog('请在浏览器中手动点击「Publish」按钮完成发布');
  await handOffTaskSpace();
  return;
}
await wait(5);

// 验证
const url = await js('window.location.href');
const success = url.includes('dashboard') || url.includes('videos');
cliLog(success ? '✅ 发布成功！' : '⚠️ 请检查发布状态');

await captureScreenshot();
await completeTaskSpace('${taskSpace}', { keep: false });
})();
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

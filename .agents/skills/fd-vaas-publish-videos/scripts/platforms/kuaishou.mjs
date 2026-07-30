#!/usr/bin/env node
/**
 * 快手上传 CLI - ego-browser 版本
 *
 * ⚠️ 技术要点：
 * - React Joyride 遮罩需移除（否则拦截所有点击）
 * - 封面选择用 Ant Design Modal + CDP 鼠标事件
 * - 发布按钮在视口外，需 scrollIntoView
 * - 话题标签 ≤ 4 个
 *
 * 用法: node kuaishou.mjs --file <mp4> --title <标题> [--desc <描述>] [--tags <标签>]
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
const title = getArg('--title') || '';
const desc = getArg('--desc') || '';
const tagsStr = getArg('--tags') || '';
const cover = getArg('--cover') || '';
const dryRun = args.includes('--dry-run');

if (!file) {
  console.error(`
用法: node kuaishou.mjs --file <视频文件> [选项]

必填:
  --file <path>        视频文件路径 (mp4)

可选:
  --title <string>     视频标题
  --desc <string>      视频描述（支持 #话题，最多 4 个）
  --cover <path>       封面图片路径
  --dry-run            只打开页面不上传

⚠️ 快手话题标签上限 4 个（不是 5 个）
`);
  process.exit(1);
}

if (!fs.existsSync(file)) {
  console.error(`❌ 视频文件不存在: ${file}`);
  process.exit(1);
}

const absFile = path.resolve(file);
const taskSpace = `kuaishou-publish-${Date.now()}`;
// 快手话题 ≤ 4 个
const tags = tagsStr.split(',').map(t => t.trim()).filter(Boolean).slice(0, 4);
// 快手标题和描述合一
const fullDesc = [title, desc, tags.map(t => `#${t}`).join(' ')].filter(Boolean).join(' ');

console.log(`📱 快手发布
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
视频:   ${absFile}
描述:   ${fullDesc}
标签:   ${tags.join(', ')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

const escapedFile = absFile.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
const escapedDesc = fullDesc.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/`/g, '\\`');

const egoScript = `
(async () => {
await useOrCreateTaskSpace('${taskSpace}');

cliLog('🌐 打开快手创作者平台...');
await gotoAndWait('https://cp.kuaishou.com/article/publish/video');
await wait(5);

// 检查登录
const loginCheck = await js(\`(() => {
  const text = document.body.innerText.slice(0, 500);
  return text.includes('扫码登录') || text.includes('密码登录');
})()\`);
if (loginCheck) {
  cliLog('⚠️ 需要登录快手');
  cliLog('   请切换到 ego-browser 窗口扫码登录');
  for (let i = 0; i < 60; i++) {
    await wait(3);
    const stillLogin = await js(\`document.body.innerText.includes('扫码登录')\`);
    if (!stillLogin) { cliLog('✅ 登录成功！'); break; }
  }
}

// ⚠️ 移除 React Joyride 遮罩（关键！否则拦截所有点击）
cliLog('🧹 移除 React Joyride 遮罩...');
await js(\`(() => {
  const overlays = document.querySelectorAll('[class*="react-joyride"], [class*="joyride"]');
  overlays.forEach(el => el.remove());
  return 'removed ' + overlays.length + ' joyride elements';
})()\`);
await wait(1);

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

// 填写描述（contenteditable，用 execCommand）
cliLog('📝 填写描述...');
await js(\`(() => {
  const editor = document.querySelector('[contenteditable="true"]');
  if (!editor) return 'no editor';
  editor.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, '${escapedDesc}');
  return 'filled: ' + editor.textContent.trim().slice(0, 40);
})()\`);
await wait(2);

// 设置封面（点击默认封面区域打开 Ant Design Modal）
cliLog('🖼️ 设置封面...');
await js(\`document.querySelector('._default-cover')?.click()\`);
await wait(2);

// 在模态框中确认选帧
const coverResult = await js(\`(() => {
  const modal = document.querySelector('.ant-modal-body');
  if (!modal) return 'no modal';
  const confirmBtn = modal.querySelector('.ant-btn-primary');
  if (confirmBtn) { confirmBtn.click(); return 'cover confirmed'; }
  return 'no confirm btn';
})()\`);
cliLog('封面: ' + coverResult);
await wait(2);

// 点击发布（多候选 + 滚动 + JS 点击兜底，按钮可能在视口外）
cliLog('🚀 点击发布...');
try {
  const publishResult = await js(\`(async () => {
  window.scrollTo(0, document.body.scrollHeight);
  await new Promise(r => setTimeout(r, 500));
  const candidates = ['发布', '发布视频'];
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
    const btn = document.querySelector('._button-primary_3a3lq_60');
    if (btn && isVisible(btn)) { doClick(btn); result = { clicked: true, text: (btn.textContent || '').trim(), match: 'class' }; }
  }
  if (!result) {
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const bg = getComputedStyle(b).backgroundColor;
      if (bg.includes('254, 54, 102') && b.textContent && b.textContent.includes('发布')) { doClick(b); result = { clicked: true, text: b.textContent.trim(), match: 'color' }; break; }
    }
  }
  return JSON.stringify(result || { clicked: false });
})()\`);
  let r;
  try { r = typeof publishResult === 'string' ? JSON.parse(publishResult) : publishResult; } catch (pe) { r = {}; }
  if (!r || !r.clicked) {
    throw new Error('未找到发布按钮' + (r && r.text ? ': ' + r.text : ''));
  }
  cliLog('✅ 已点击发布按钮: ' + r.text + ' (' + r.match + ')');
} catch (e) {
  cliLog('⚠️ 发布按钮点击失败: ' + e.message);
  cliLog('请在浏览器中手动点击「发布」按钮完成发布');
  await handOffTaskSpace();
  return;
}
await wait(5);

// 验证（URL 应变为 manage/video?status=2）
const url = await js('window.location.href');
const success = url.includes('status=2') || (url.includes('manage') && url.includes('video'));
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

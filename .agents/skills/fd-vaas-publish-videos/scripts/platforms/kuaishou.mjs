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
const absCover = cover && fs.existsSync(cover) ? path.resolve(cover) : '';
const escapedCover = absCover ? absCover.replace(/\\/g, '\\\\').replace(/'/g, "\\'") : '';

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

// 设置封面（上传自定义封面图）
${absCover ? `
cliLog('🖼️ 上传封面...');
try {
  // 点击封面区域打开 modal（多选择器兜底）
  let coverOpen = await js(\`(() => {
    const sels = ['._default-cover', '[class*="cover-default"]', '[class*="default-cover"]', '[class*="cover-card"]', '[class*="video-cover"]', '[class*="cover"] img'];
    for (const s of sels) {
      const el = document.querySelector(s);
      if (el && el.getClientRects && el.getClientRects().length) { el.click(); return 'clicked ' + s; }
    }
    return 'no cover area found';
  })()\`);
  cliLog('封面区域: ' + coverOpen);
  await wait(2);
  // modal 里找"上传"tab（切换到上传自定义封面，而非选帧）
  await js(\`(() => {
    const modal = document.querySelector('.ant-modal-body') || document.querySelector('[class*="modal-body"]') || document.querySelector('[role="dialog"]');
    if (!modal) return 'no modal';
    const tabs = modal.querySelectorAll('[class*="tab"], .ant-tabs-tab, [role="tab"], div, span');
    for (const t of tabs) {
      const tx = (t.textContent || '').trim();
      if ((tx === '上传' || tx === '上传封面' || tx === '自定义') && t.getClientRects && t.getClientRects().length) { t.click(); return 'tab: ' + tx; }
    }
    return 'no upload tab (may direct upload)';
  })()\`);
  await wait(1);
  // 上传封面图
  await uploadFile('input[type="file"][accept*="image"]', '${escapedCover}');
  await wait(3);
  // 确认封面
  let coverConfirm = await js(\`(() => {
    const modal = document.querySelector('.ant-modal-body') || document.querySelector('[class*="modal-body"]');
    if (!modal) return 'no modal for confirm';
    const btns = modal.querySelectorAll('.ant-btn-primary, button[class*="primary"], button[class*="confirm"]');
    for (const b of btns) { if (!b.disabled && b.getClientRects && b.getClientRects().length) { b.click(); return 'confirmed'; } }
    return 'no confirm btn';
  })()\`);
  cliLog('封面确认: ' + coverConfirm);
  await wait(2);
} catch (e) {
  cliLog('⚠️ 封面上传失败: ' + e.message + '，请手动设置封面');
}
` : `
cliLog('⏭️ 未提供封面，跳过');
`}

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
  await wait(2);
  // 处理可能的二次确认弹窗
  let confirmResult = await js(\`(() => {
    const modals = document.querySelectorAll('.ant-modal-confirm, .ant-modal-body, [class*="modal-body"], [role="dialog"]');
    for (const modal of modals) {
      if (!modal.getClientRects || !modal.getClientRects().length) continue;
      const btns = modal.querySelectorAll('.ant-btn-primary, button[class*="primary"], button[class*="confirm"], [class*="ok"]');
      for (const b of btns) {
        if (!b.disabled && b.getClientRects && b.getClientRects().length) {
          const t = (b.textContent || '').trim();
          if (t.includes('确认') || t.includes('发布') || t.includes('确定') || t === 'OK') { b.click(); return 'confirm: ' + t; }
        }
      }
    }
    return 'no confirm modal';
  })()\`);
  cliLog('二次确认: ' + confirmResult);
  await wait(3);
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
cliLog('发布流程完成，请确认发布状态（如未发布，手动点 div.publish-button）');
await handOffTaskSpace();
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

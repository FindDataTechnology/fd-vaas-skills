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
await useOrCreateTaskSpace('${taskSpace}');

cliLog('🌐 打开快手创作者平台...');
await gotoAndWait('https://cp.kuaishou.com/article/publish/video');
await wait(5);

// 检查登录
const loginCheck = await js(\\\`(() => {
  const text = document.body.innerText.slice(0, 500);
  return text.includes('扫码登录') || text.includes('密码登录');
})()\\\`);
if (loginCheck) {
  cliLog('⚠️ 需要登录快手');
  cliLog('   请切换到 ego-browser 窗口扫码登录');
  for (let i = 0; i < 60; i++) {
    await wait(3);
    const stillLogin = await js(\\\`document.body.innerText.includes('扫码登录')\\\`);
    if (!stillLogin) { cliLog('✅ 登录成功！'); break; }
  }
}

// ⚠️ 移除 React Joyride 遮罩（关键！否则拦截所有点击）
cliLog('🧹 移除 React Joyride 遮罩...');
await js(\\\`(() => {
  const overlays = document.querySelectorAll('[class*="react-joyride"], [class*="joyride"]');
  overlays.forEach(el => el.remove());
  return 'removed ' + overlays.length + ' joyride elements';
})()\\\`);
await wait(1);

${dryRun ? `
cliLog('🔍 dry-run 模式');
await captureScreenshot();
await handOffTaskSpace('dry-run: 页面已打开');
return;
` : ''}

// 上传视频
cliLog('📤 上传视频...');
await uploadFile('input[type="file"]', '${escapedFile}');
cliLog('等待上传完成...');
await wait(30);

// 填写描述（contenteditable，用 execCommand）
cliLog('📝 填写描述...');
await js(\\\`(() => {
  const editor = document.querySelector('[contenteditable="true"]');
  if (!editor) return 'no editor';
  editor.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, '${escapedDesc}');
  return 'filled: ' + editor.textContent.trim().slice(0, 40);
})()\\\`);
await wait(2);

// 设置封面（点击默认封面区域打开 Ant Design Modal）
cliLog('🖼️ 设置封面...');
await js(\\\`document.querySelector('._default-cover')?.click()\\\`);
await wait(2);

// 在模态框中确认选帧
const coverResult = await js(\\\`(() => {
  const modal = document.querySelector('.ant-modal-body');
  if (!modal) return 'no modal';
  const confirmBtn = modal.querySelector('.ant-btn-primary');
  if (confirmBtn) { confirmBtn.click(); return 'cover confirmed'; }
  return 'no confirm btn';
})()\\\`);
cliLog('封面: ' + coverResult);
await wait(2);

// ⚠️ 滚动到发布按钮并点击（按钮在视口外！）
cliLog('📜 滚动到发布按钮...');
await js(\\\`(() => {
  // 先找按钮（class 含 hash，可能变化）
  let btn = document.querySelector('._button-primary_3a3lq_60');
  if (!btn) {
    // 备用：找粉色按钮
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const bg = getComputedStyle(b).backgroundColor;
      if (bg.includes('254, 54, 102') && b.textContent?.trim()) {
        btn = b;
        break;
      }
    }
  }
  if (btn) {
    btn.scrollIntoView({ block: 'center' });
    return 'scrolled to: ' + btn.textContent?.trim();
  }
  return 'no publish btn';
})()\\\`);
await wait(1);

// 点击发布
cliLog('🚀 点击发布...');
const publishResult = await js(\\\`(() => {
  let btn = document.querySelector('._button-primary_3a3lq_60');
  if (!btn) {
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const bg = getComputedStyle(b).backgroundColor;
      if (bg.includes('254, 54, 102') && b.textContent?.includes('发布')) {
        btn = b;
        break;
      }
    }
  }
  if (btn) { btn.click(); return 'clicked: ' + btn.textContent?.trim(); }
  return 'no publish btn';
})()\\\`);
cliLog('发布: ' + publishResult);
await wait(5);

// 验证（URL 应变为 manage/video?status=2）
const url = await js('window.location.href');
const success = url.includes('status=2') || (url.includes('manage') && url.includes('video'));
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

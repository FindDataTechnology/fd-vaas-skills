#!/usr/bin/env node
/**
 * 微信视频号上传 CLI - ego-browser 版本
 * 
 * ⚠️ 视频号使用 Wujie 微前端（shadow DOM），文件上传必须用 HTTP 服务器 + DataTransfer 方案。
 * 详见 SKILL.md "核心技术挑战" 章节。
 *
 * 用法: node weixin.mjs --file <mp4> --desc <描述> [--cover <封面图>]
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
const desc = getArg('--desc') || '';
const cover = getArg('--cover') || '';
const dryRun = args.includes('--dry-run');

if (!file) {
  console.error(`
用法: node weixin.mjs --file <视频文件> [选项]

必填:
  --file <path>        视频文件路径 (mp4)

可选:
  --desc <string>      视频描述/正文（支持 #话题）
  --cover <path>       封面图片路径（建议 1080×1260）
  --dry-run            只打开页面不上传

⚠️ 视频号使用 Wujie shadow DOM，文件上传需 HTTP 服务器 + DataTransfer 方案。

示例:
  node weixin.mjs \\
    --file video.mp4 \\
    --desc "寻数科技｜探索更开放更公平的AI未来 #科技 #开源"
`);
  process.exit(1);
}

if (!fs.existsSync(file)) {
  console.error(`❌ 视频文件不存在: ${file}`);
  process.exit(1);
}

const absFile = path.resolve(file);
const PORT = 18765 + Math.floor(Math.random() * 1000);
const taskSpace = `weixin-publish-${Date.now()}`;

console.log(`📱 微信视频号发布
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
视频:   ${absFile}
描述:   ${desc || '(无)'}
封面:   ${cover || '(默认截取)'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

const escapedDesc = desc.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/`/g, '\\`');
const escapedFile = absFile.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

const egoScript = `
(async () => {
  const http = require('http');
  const fs = require('fs');

  await useOrCreateTaskSpace('${taskSpace}');

  cliLog('🌐 打开视频号助手发布页...');
  await gotoAndWait('https://channels.weixin.qq.com/platform/post/create');
  await wait(5);

  // 等待 wujie-app shadow DOM 加载
  cliLog('⏳ 等待 Wujie 微前端加载...');
  for (let i = 0; i < 15; i++) {
    const ready = await js(\\\`!!document.querySelector('wujie-app')?.shadowRoot?.querySelector('input[type="file"]')\\\`);
    if (ready) { cliLog('✅ Wujie 已加载'); break; }
    await wait(2);
  }

  // 检查是否需要登录
  const needsLogin = await js(\\\`(() => {
    const sr = document.querySelector('wujie-app')?.shadowRoot;
    if (!sr) return true;
    // 如果有登录二维码或登录按钮，说明未登录
    const text = sr.textContent || '';
    return text.includes('扫码登录') || text.includes('二维码') || !sr.querySelector('input[type="file"]');
  })()\\\`);

  if (needsLogin) {
    cliLog('⚠️ 需要登录视频号');
    cliLog('   请切换到 ego-browser 窗口，用微信扫码登录');
    for (let i = 0; i < 60; i++) {
      await wait(3);
      const loggedIn = await js(\\\`!!document.querySelector('wujie-app')?.shadowRoot?.querySelector('input[type="file"]')\\\`);
      if (loggedIn) { cliLog('✅ 登录成功！'); break; }
    }
  }

  ${dryRun ? `
  cliLog('🔍 dry-run 模式，仅打开页面');
  await captureScreenshot();
  await handOffTaskSpace('dry-run: 页面已打开');
  return;
  ` : ''}

  // === 核心：通过 HTTP 服务器 + DataTransfer 上传文件 ===
  cliLog('📤 启动本地 HTTP 服务器...');
  const server = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'video/mp4');
    fs.createReadStream('${escapedFile}').pipe(res);
  });
  server.listen(${PORT});
  await wait(1);

  cliLog('📤 通过 fetch + DataTransfer 上传视频...');
  const uploadResult = await js(String.raw\\\`(() => {
    return fetch('http://localhost:${PORT}/video.mp4')
      .then(r => r.blob())
      .then(blob => {
        const wujie = document.querySelector('wujie-app');
        const sr = wujie?.shadowRoot;
        if (!sr) return 'no shadow';
        const input = sr.querySelector('input[type="file"]');
        if (!input) return 'no input';
        const file = new File([blob], 'video.mp4', { type: 'video/mp4' });
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
        return 'file set: count=' + input.files.length + ', size=' + input.files[0].size;
      })
      .catch(e => 'error: ' + e.message);
  })()\\\`);
  cliLog('上传结果: ' + uploadResult);

  server.close();
  cliLog('📡 HTTP 服务器已关闭');

  // 等待上传完成
  cliLog('⏳ 等待视频上传完成...');
  for (let i = 0; i < 30; i++) {
    await wait(10);
    const status = await js(\\\`(() => {
      const sr = document.querySelector('wujie-app')?.shadowRoot;
      const form = sr?.querySelector('.form');
      const text = form?.textContent?.trim() || '';
      const uploading = text.includes('文件上传中');
      return { uploading, text: text.slice(0, 40) };
    })()\\\`);
    if (!status.uploading) {
      cliLog('✅ 视频上传完成！');
      break;
    }
    if (i % 3 === 0) cliLog('   仍在上传... ' + (i+1)*10 + 's');
  }

  // 填写描述
  ${desc ? `
  cliLog('📝 填写描述...');
  await js(\\\`(() => {
    const sr = document.querySelector('wujie-app')?.shadowRoot;
    const editor = sr?.querySelector('.input-editor');
    if (!editor) return 'no editor';
    editor.focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
    document.execCommand('insertText', false, '${escapedDesc}');
    return 'desc filled: ' + editor.textContent.trim().slice(0, 40);
  })()\\\`);
  await wait(2);
  ` : ''}

  // 点击发表
  cliLog('🚀 点击发表按钮...');
  const publishResult = await js(\\\`(() => {
    const sr = document.querySelector('wujie-app')?.shadowRoot;
    const btns = sr?.querySelectorAll('.weui-desktop-btn_primary');
    for (const btn of btns) {
      if (btn.textContent?.trim() === '发表' && !btn.disabled) {
        btn.click();
        return 'clicked 发表';
      }
    }
    return 'no publish btn';
  })()\\\`);
  cliLog('发表: ' + publishResult);
  await wait(5);

  // 验证
  const url = await js('window.location.href');
  const success = url.includes('/platform/post/list');
  cliLog(success ? '✅ 发布成功！视频将在处理完后自动发布' : '⚠️ 请检查发布状态');

  await captureScreenshot();

  // 发布已完成，关闭任务窗口，不要留给用户自己关
  try {
    const r = await completeTaskSpace('${taskSpace}', { keep: false });
    cliLog('🧹 已关闭任务窗口: ' + JSON.stringify(r));
  } catch (e) {
    cliLog('⚠️ 关闭任务窗口失败: ' + e.message);
  }
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

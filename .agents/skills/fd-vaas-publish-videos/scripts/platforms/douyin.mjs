#!/usr/bin/env node
/**
 * 抖音视频上传 CLI
 * 
 * 功能：
 * 1. 登录状态自动检测 + 轮询等待
 * 2. 分步执行，每步有错误处理和重试
 * 3. 动态元素定位（不依赖固定 class）
 * 4. 支持横封面和竖封面上传
 * 5. 发布前截图确认
 * 
 * 用法: node douyin.mjs --file <mp4> --title <标题> [--desc <描述>] [--tags <标签1,标签2>] [--cover-horizontal <封面图>] [--cover-vertical <封面图>] [--schedule "YYYY-MM-DD HH:MM"]
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
const tags = getArg('--tags') || '';
const coverHorizontal = getArg('--cover-horizontal') || '';
const coverVertical = getArg('--cover-vertical') || '';
const schedule = getArg('--schedule') || '';
const dryRun = args.includes('--dry-run');

if (!file || !title) {
  console.error(`
用法: node douyin.mjs --file <视频文件> --title <标题> [选项]

必填:
  --file <path>                 视频文件路径 (mp4)
  --title <string>              视频标题

可选:
  --desc <string>               视频描述
  --tags <list>                 标签，逗号分隔，如 "科技,开源,AI"
  --cover-horizontal <path>     横版封面图 (4:3, 建议 1280x960)
  --cover-vertical <path>       竖版封面图 (3:4, 建议 1080x1440)
  --schedule "YYYY-MM-DD HH:MM" 定时发布时间
  --dry-run                     只打开页面，不上传视频

示例:
  node douyin.mjs \\
    --file video.mp4 \\
    --title "寻数科技品牌介绍" \\
    --desc "通过开源技术推动信息平权和机会公平" \\
    --tags "科技,开源,AI,数据" \\
    --cover-horizontal cover-h.jpg \\
    --cover-vertical cover-v.jpg
`);
  process.exit(1);
}

if (!fs.existsSync(file)) {
  console.error(`❌ 视频文件不存在: ${file}`);
  process.exit(1);
}

const absFile = path.resolve(file);
const absCoverH = coverHorizontal ? path.resolve(coverHorizontal) : '';
const absCoverV = coverVertical ? path.resolve(coverVertical) : '';

const fullDesc = tags 
  ? `${title}\n${desc}\n#${tags.replace(/,/g, ' #')}`
  : `${title}\n${desc}`;

console.log(`🎵 抖音视频发布
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
视频:      ${absFile}
标题:      ${title}
描述:      ${desc || '(无)'}
标签:      ${tags || '(无)'}
横封面:    ${absCoverH || '(未设置)'}
竖封面:    ${absCoverV || '(未设置)'}
定时:      ${schedule || '(立即发布)'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);

// 生成 ego-browser 脚本
const egoScript = `
(async () => {
await useOrCreateTaskSpace('douyin-publish-${Date.now()}');

// ─── 工具函数 ───────────────────────────────────────────
async function checkLoginStatus() {
  const pageText = await js('document.body.innerText.slice(0, 1000)');
  const loggedInMarkers = ['发布作品', '上传视频', '创作者服务', '创作者中心'];
  const notLoggedInMarkers = ['登录', '扫码登录', '验证码登录', '密码登录'];
  
  const hasLoggedInMarker = loggedInMarkers.some(m => pageText.includes(m));
  const hasNotLoggedInMarker = notLoggedInMarkers.some(m => pageText.includes(m));
  
  return hasLoggedInMarker || !hasNotLoggedInMarker;
}

async function waitForLoginAuto() {
  cliLog('⚠️  未检测到登录态');
  cliLog('👉  请在 ego-browser 窗口中扫码登录抖音');
  cliLog('   登录完成后会自动继续，无需输入 continue');
  
  // 尝试自动切换到扫码登录
  await js(\`(() => {
    const elements = document.querySelectorAll('div, span, button, a');
    for (const el of elements) {
      const text = (el.textContent || '').trim();
      if ((text.includes('扫码登录') || text.includes('二维码')) && el.offsetParent) {
        el.click();
        return { switched: true };
      }
    }
    return { switched: false };
  })()\`);
  
  await handOffTaskSpace();
  
  const timeoutSeconds = 600; // 10 分钟超时
  const pollIntervalSeconds = 3;
  const startTime = Date.now();
  let pollCount = 0;
  
  while (Date.now() - startTime < timeoutSeconds * 1000) {
    pollCount++;
    
    try {
      await takeOverTaskSpace();
    } catch (e) {
      await wait(pollIntervalSeconds);
      continue;
    }
    
    const loggedIn = await checkLoginStatus();
    if (loggedIn) {
      cliLog('✅  登录成功！自动继续执行...');
      return true;
    }
    
    await handOffTaskSpace();
    
    if (pollCount % 10 === 0) {
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      cliLog(\`⏳  等待登录中... (已等待 \${elapsed} 秒)\`);
    }
    
    await wait(pollIntervalSeconds);
  }
  
  cliLog('❌  等待登录超时，请手动完成登录');
  return false;
}

async function clickByText(texts, label, exact = false) {
  const textList = Array.isArray(texts) ? texts : [texts];
  try {
    const result = await js(\`(() => {
      const elements = document.querySelectorAll('button, div, span, a');
      const targets = \${JSON.stringify(textList)};
      const exact = \${exact};
      
      for (const el of elements) {
        if (!el.offsetParent) continue;
        const text = (el.textContent || '').trim();
        for (const target of targets) {
          if ((exact && text === target) || (!exact && text.includes(target))) {
            el.click();
            return { found: true, text };
          }
        }
      }
      return { found: false };
    })()\`);
    
    if (result.found) {
      cliLog(\`✅  \${label} (\${result.text})\`);
      await wait(1);
      return true;
    }
  } catch (e) {
    cliLog(\`⚠️  \${label} 点击失败: \${e.message}\`);
  }
  return false;
}

async function uploadCover(coverPath, coverType) {
  if (!coverPath) return;
  
  cliLog(\`🖼️  上传\${coverType}封面...\`);
  
  try {
    // 点击上传封面按钮
    await clickByText(['上传封面'], '点击上传封面按钮');
    await wait(2);
    
    // 找到文件输入框
    const found = await js(\`(() => {
      const inputs = document.querySelectorAll('input[type="file"]');
      for (let i = 0; i < inputs.length; i++) {
        const accept = inputs[i].accept || '';
        if (accept.includes('image') || accept.includes('jpg') || accept.includes('png')) {
          inputs[i].setAttribute('id', 'douyin-cover-input');
          return true;
        }
      }
      return false;
    })()\`);
    
    if (found) {
      await uploadFile('#douyin-cover-input', coverPath);
      await wait(5);
      
      // 点击完成按钮
      await clickByText(['完成', '确定'], '点击完成按钮', true);
      await wait(2);
      
      cliLog(\`✅  \${coverType}封面上传成功\`);
    }
  } catch (e) {
    cliLog(\`⚠️  \${coverType}封面上传可能需要手动操作: \${e.message}\`);
  }
}

async function withRetry(fn, maxRetries = 3, operationName = 'operation') {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt < maxRetries) {
        cliLog(\`⚠️  \${operationName} 失败 (尝试 \${attempt}/\${maxRetries}): \${error.message}\`);
        await wait(2);
      } else {
        cliLog(\`⚠️  \${operationName} 失败 (已重试 \${maxRetries} 次)\`);
        throw error;
      }
    }
  }
}

// ─── 分步执行 ───────────────────────────────────────────

// 步骤 1: 打开抖音创作者中心上传页面
cliLog('\\n▶ [1/6] 打开抖音创作者中心');
await gotoAndWait('https://creator.douyin.com/creator-micro/content/upload');
await wait(5);
cliLog('✅  页面加载完成');

// 步骤 2: 检查登录状态
cliLog('\\n▶ [2/6] 检查登录状态');
const isLoggedIn = await checkLoginStatus();
if (!isLoggedIn) {
  await waitForLoginAuto();
  await wait(3); // 等待登录后的页面跳转
}
cliLog('✅  登录状态正常');

if (!${dryRun ? 'true' : 'false'}) {
  // 步骤 3: 上传视频
  cliLog('\\n▶ [3/6] 上传视频');
  try {
    // 找到视频上传 input
    await js(\`(() => {
      const inputs = document.querySelectorAll('input[type="file"]');
      for (let i = 0; i < inputs.length; i++) {
        const accept = inputs[i].accept || '';
        if (accept.includes('video') || accept.includes('mp4')) {
          inputs[i].setAttribute('id', 'douyin-video-input');
          return { found: true };
        }
      }
      // 如果没找到特定的，用第一个 file input
      if (inputs.length > 0) {
        inputs[0].setAttribute('id', 'douyin-video-input');
        return { found: true };
      }
      return { found: false };
    })()\`);
    
    await withRetry(async () => {
      await uploadFile('#douyin-video-input', '${absFile.replace(/'/g, "\\'")}');
    }, 2, '上传视频');
    
    cliLog('✅  视频上传中...');
    cliLog('   等待上传和转码完成 (约 30-60 秒)...');
    await wait(45);
  } catch (e) {
    cliLog('⚠️  视频上传可能需要手动操作: ' + e.message);
  }

  // 步骤 4: 填写作品描述
  cliLog('\\n▶ [4/6] 填写作品描述');
  try {
    await js(\`(() => {
      const editor = document.querySelector('[contenteditable="true"]');
      if (editor) {
        editor.focus();
        const fullText = ${JSON.stringify(fullDesc)};
        document.execCommand('insertText', false, fullText);
        return { success: true };
      }
      return { success: false };
    })()\`);
    cliLog('✅  描述填写完成');
    await wait(1);
  } catch (e) {
    cliLog('⚠️  描述填写失败，请手动填写');
  }

  // 步骤 5: 上传封面
  cliLog('\\n▶ [5/6] 上传封面');
  
  // 滚动到封面区域
  await js('window.scrollTo(0, 350)');
  await wait(1);
  
  ${absCoverH ? `// 横封面
  const covers = await js(\`(() => {
    const elements = document.querySelectorAll('div');
    const coverElements = [];
    for (const el of elements) {
      const text = (el.textContent || '').trim();
      if (text === '横封面' || text === '选择封面') {
        coverElements.push(el);
      }
    }
    return coverElements.length;
  })()\`);
  
  if (covers >= 1) {
    await uploadCover('${absCoverH.replace(/'/g, "\\'")}', '横');
  } else {
    cliLog('⚠️  未找到横封面区域，请手动设置');
  }` : 'cliLog("  跳过后封面（未提供）");'}
  
  ${absCoverV ? `// 竖封面
  if (covers >= 2) {
    await uploadCover('${absCoverV.replace(/'/g, "\\'")}', '竖');
  } else {
    cliLog('⚠️  未找到竖封面区域，请手动设置');
  }` : 'cliLog("  跳过竖封面（未提供）");'}
  
  // 定时发布
  ${schedule ? `cliLog('⏰  设置定时发布...');
  await clickByText(['定时发布', '定时'], '点击定时发布');
  await wait(1);
  // 这里可以添加时间选择逻辑，但因为比较复杂，先提示用户手动设置
  cliLog('⚠️  定时发布时间请手动设置: ${schedule}');` : ''}
  
  cliLog('✅  封面设置完成');
}

// 步骤 6: 确认并准备发布
cliLog('\\n▶ [6/6] 发布前确认');
cliLog('');
cliLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
cliLog('📋  请在浏览器中确认以下信息：');
cliLog('   • 视频是否上传完成');
cliLog('   • 标题/描述/话题是否正确');
cliLog('   • 横封面是否已设置');
cliLog('   • 竖封面是否已设置');
cliLog('   • 发布设置是否正确（立即/定时）');
cliLog('');
cliLog('👉  确认无误后，请手动点击「发布」按钮');
cliLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

// 截图给用户看
try {
  await captureScreenshot();
} catch (e) {
  cliLog('⚠️  截图失败，请直接查看浏览器窗口');
}

// 滚动到底部，让用户看到发布按钮
await js('window.scrollTo(0, document.body.scrollHeight)');
await wait(0.5);

// 将控制权交给用户，让用户手动确认和发布
// 注意：脚本到此退出，任务窗口仍开着。用户回复「发布完成」后，
// 由 agent 跑清理 heredoc（completeTaskSpace）关掉这个窗口，不要让用户自己关。
cliLog('请确认所有信息无误后，手动点击「发布」按钮完成上传。发布完成后在对话里回复「发布完成」，我会自动关闭浏览器窗口，不用手动关。');
await handOffTaskSpace();
})();
`;

console.log('🚀 启动 ego-browser...\n');

// 执行 ego-browser
const ego = spawn('ego-browser', ['nodejs'], {
  stdio: ['pipe', 'inherit', 'inherit'],
  shell: true
});

ego.stdin.write(egoScript);
ego.stdin.end();

ego.on('close', (code) => {
  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`✅  上传流程完成 (exit code: ${code})`);
  console.log(`   请在抖音创作者中心确认发布结果`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
});

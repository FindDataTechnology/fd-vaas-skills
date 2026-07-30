/**
 * 浏览器自动化通用工具模块
 * 
 * 提供：
 * 1. 登录状态检测 + 自动轮询等待
 * 2. 元素定位增强（多 selector 备选、文本匹配）
 * 3. 错误处理和重试机制
 * 4. 分步执行框架
 */

/**
 * 检查是否已登录
 * @param {Array<string>} loggedInMarkers - 表示已登录的文本标记（如 "上传视频", "创作者中心" 等）
 * @param {Array<string>} notLoggedInMarkers - 表示未登录的文本标记（如 "登录", "Sign in" 等）
 * @returns {Promise<boolean>}
 */
export async function isLoggedIn(loggedInMarkers, notLoggedInMarkers) {
  try {
    const pageText = await js('document.body.innerText');
    // 检查是否有已登录标记
    const hasLoggedInMarker = loggedInMarkers.some(marker => 
      pageText.includes(marker)
    );
    // 检查是否有未登录标记
    const hasNotLoggedInMarker = notLoggedInMarkers.some(marker => 
      pageText.includes(marker)
    );
    // 有已登录标记 或 没有未登录标记 → 认为已登录
    return hasLoggedInMarker || !hasNotLoggedInMarker;
  } catch (e) {
    cliLog('⚠️  检查登录状态失败: ' + e.message);
    return false;
  }
}

/**
 * 等待用户登录完成（自动轮询）
 * @param {Object} options
 * @param {Array<string>} options.loggedInMarkers - 已登录的文本标记
 * @param {Array<string>} options.notLoggedInMarkers - 未登录的文本标记
 * @param {number} options.timeoutSeconds - 超时时间（秒），默认 600 秒（10 分钟）
 * @param {number} options.pollIntervalSeconds - 轮询间隔（秒），默认 3 秒
 * @param {string} options.hint - 给用户的提示信息
 * @returns {Promise<boolean>} - 是否成功登录
 */
export async function waitForLogin(options) {
  const {
    loggedInMarkers,
    notLoggedInMarkers,
    timeoutSeconds = 600,
    pollIntervalSeconds = 3,
    hint = '请在浏览器中完成登录'
  } = options;

  cliLog('⚠️  未检测到登录态');
  cliLog(`👉  ${hint}`);
  cliLog(`   登录完成后会自动继续，无需输入 continue`);
  
  // 将控制权交给用户
  await handOffTaskSpace();
  
  const startTime = Date.now();
  let pollCount = 0;
  
  while (Date.now() - startTime < timeoutSeconds * 1000) {
    pollCount++;
    
    // 尝试夺回控制权（如果用户还在操作，这会失败）
    try {
      await takeOverTaskSpace();
    } catch (e) {
      // 用户还在操作，继续等待
      await wait(pollIntervalSeconds);
      continue;
    }
    
    // 检查登录状态
    const loggedIn = await isLoggedIn(loggedInMarkers, notLoggedInMarkers);
    
    if (loggedIn) {
      cliLog('✅  登录成功！自动继续执行...');
      return true;
    }
    
    // 没登录成功，把控制权还给用户，继续等待
    await handOffTaskSpace();
    
    // 每 10 次轮询（约 30 秒）提示一次
    if (pollCount % 10 === 0) {
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      cliLog(`⏳  等待登录中... (已等待 ${elapsed} 秒)`);
    }
    
    await wait(pollIntervalSeconds);
  }
  
  // 超时
  cliLog(`❌  等待登录超时（${timeoutSeconds} 秒）`);
  cliLog('   请手动完成登录后，脚本会继续执行后续步骤');
  return false;
}

/**
 * 查找元素（多 selector 备选 + 文本匹配）
 * @param {Array<string>} selectors - CSS 选择器列表，按优先级尝试
 * @param {Object} options
 * @param {Array<string>} options.textMatches - 文本内容匹配列表（如 ["标题", "title"]）
 * @param {string} options.attribute - 检查的属性（如 "placeholder", "aria-label"）
 * @param {boolean} options.returnSelector - 是否返回找到的 selector，否则返回元素信息
 * @returns {Promise<string|null>} - 找到的 selector 或 null
 */
export async function findElement(selectors, options = {}) {
  const { textMatches = [], attribute = null, returnSelector = true } = options;
  
  const result = await js(`(() => {
    // 先尝试直接的 CSS 选择器
    for (const sel of ${JSON.stringify(selectors)}) {
      const el = document.querySelector(sel);
      if (el && el.offsetParent) {
        return { found: true, selector: sel };
      }
    }
    
    // 如果有文本匹配要求，遍历相关元素
    const textMatches = ${JSON.stringify(textMatches)};
    const attribute = ${JSON.stringify(attribute)};
    
    if (textMatches.length > 0 || attribute) {
      const tagNames = attribute === 'contenteditable' 
        ? ['[contenteditable="true"]'] 
        : ['input', 'textarea', 'button', 'div', 'span'];
      
      const elements = document.querySelectorAll(tagNames.join(','));
      
      for (const el of elements) {
        if (!el.offsetParent) continue;
        
        // 检查属性值
        if (attribute) {
          const attrValue = el.getAttribute(attribute) || '';
          const matchesText = textMatches.some(text => 
            attrValue.toLowerCase().includes(text.toLowerCase())
          );
          if (matchesText) {
            return { found: true, selector: null, element: el.tagName };
          }
        }
        
        // 检查文本内容
        if (textMatches.length > 0) {
          const text = (el.textContent || '').trim().toLowerCase();
          const matchesText = textMatches.some(t => text.includes(t.toLowerCase()));
          if (matchesText) {
            // 尝试生成一个 selector
            const id = el.id ? '#' + el.id : '';
            const classes = el.className ? '.' + el.className.split(/\s+/).filter(Boolean).join('.') : '';
            const guessed = id || (classes.length > 3 ? classes : null);
            return { found: true, selector: guessed, element: el.tagName };
          }
        }
      }
    }
    
    return { found: false };
  })()`);
  
  if (result.found) {
    return returnSelector ? (result.selector || null) : result;
  }
  return null;
}

/**
 * 带重试的操作执行器
 * @param {Function} operation - 要执行的操作（异步函数）
 * @param {Object} options
 * @param {number} options.maxRetries - 最大重试次数，默认 3
 * @param {number} options.retryDelaySeconds - 重试间隔（秒），默认 2
 * @param {string} options.operationName - 操作名称，用于日志
 * @param {Function} options.onError - 错误回调
 * @returns {Promise<any>}
 */
export async function withRetry(operation, options = {}) {
  const {
    maxRetries = 3,
    retryDelaySeconds = 2,
    operationName = 'operation',
    onError = null
  } = options;
  
  let lastError;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (onError) {
        onError(error, attempt);
      }
      
      if (attempt < maxRetries) {
        cliLog(`⚠️  ${operationName} 失败 (尝试 ${attempt}/${maxRetries}): ${error.message}`);
        cliLog(`   ${retryDelaySeconds} 秒后重试...`);
        await wait(retryDelaySeconds);
      } else {
        cliLog(`❌  ${operationName} 失败 (已重试 ${maxRetries} 次): ${error.message}`);
      }
    }
  }
  
  throw lastError;
}

/**
 * 安全地点击元素
 * @param {string|Array<string>} selector - CSS 选择器或选择器列表
 * @param {Object} options
 * @param {string} options.label - 操作描述，用于日志
 * @param {number} options.maxRetries - 最大重试次数
 * @returns {Promise<boolean>} - 是否成功点击
 */
export async function safeClick(selector, options = {}) {
  const { label = 'click', maxRetries = 2 } = options;
  
  const selectors = Array.isArray(selector) ? selector : [selector];
  
  try {
    return await withRetry(async () => {
      for (const sel of selectors) {
        try {
          await click(sel, { label });
          await wait(0.5);
          return true;
        } catch (e) {
          // 尝试下一个 selector
          continue;
        }
      }
      throw new Error('所有 selector 都失败');
    }, { maxRetries, operationName: label });
  } catch (e) {
    cliLog(`⚠️  ${label} 无法自动完成，请手动操作`);
    return false;
  }
}

/**
 * 安全地填写输入框
 * @param {string|Array<string>} selector - CSS 选择器或选择器列表
 * @param {string} value - 要填写的值
 * @param {Object} options
 * @param {string} options.label - 操作描述，用于日志
 * @param {boolean} options.useExecCommand - 是否使用 execCommand（用于 contenteditable 元素）
 * @returns {Promise<boolean>}
 */
export async function safeFillInput(selector, value, options = {}) {
  const { label = 'fill input', useExecCommand = false } = options;
  
  const selectors = Array.isArray(selector) ? selector : [selector];
  
  try {
    for (const sel of selectors) {
      try {
        if (useExecCommand) {
          await js(`(() => {
            const el = document.querySelector('${sel.replace(/'/g, "\\'")}');
            if (el) {
              el.focus();
              document.execCommand('insertText', false, '${value.replace(/'/g, "\\'")}');
              return true;
            }
            return false;
          })()`);
        } else {
          await fillInput(sel, value);
        }
        cliLog(`✅  ${label}`);
        await wait(0.3);
        return true;
      } catch (e) {
        continue;
      }
    }
    throw new Error('所有 selector 都失败');
  } catch (e) {
    cliLog(`⚠️  ${label} 无法自动完成，请手动输入`);
    return false;
  }
}

/**
 * 分步执行框架
 * 
 * 使用示例：
 * ```
 * const runner = new StepRunner();
 * runner.addStep('打开页面', async () => await gotoAndWait(url));
 * runner.addStep('检查登录', async () => {
 *   if (!await isLoggedIn()) await waitForLogin();
 * });
 * await runner.runAll();
 * ```
 */
export class StepRunner {
  constructor() {
    this.steps = [];
    this.results = [];
  }
  
  /**
   * 添加一个步骤
   * @param {string} name - 步骤名称
   * @param {Function} fn - 步骤函数（异步）
   * @param {Object} options
   * @param {boolean} options.required - 是否是必需步骤，如果失败则终止，默认 true
   * @param {number} options.maxRetries - 重试次数，默认 2
   */
  addStep(name, fn, options = {}) {
    this.steps.push({ name, fn, ...options });
    return this;
  }
  
  /**
   * 运行所有步骤
   * @returns {Promise<Array>} 步骤结果
   */
  async runAll() {
    cliLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    cliLog(`开始执行流程，共 ${this.steps.length} 个步骤`);
    cliLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    
    for (let i = 0; i < this.steps.length; i++) {
      const step = this.steps[i];
      const stepNum = i + 1;
      
      cliLog(`\n▶ [${stepNum}/${this.steps.length}] ${step.name}`);
      
      try {
        const result = await withRetry(step.fn, {
          maxRetries: step.maxRetries ?? 2,
          operationName: step.name
        });
        
        this.results.push({ step: step.name, success: true, result });
        cliLog(`✅ ${step.name} 完成`);
        
      } catch (error) {
        this.results.push({ step: step.name, success: false, error: error.message });
        
        if (step.required !== false) {
          cliLog(`❌ ${step.name} 失败，终止流程`);
          cliLog(`   错误: ${error.message}`);
          throw error;
        } else {
          cliLog(`⚠️  ${step.name} 失败，继续执行（非必需步骤）`);
        }
      }
    }
    
    cliLog('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    cliLog('所有步骤执行完成');
    cliLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    
    return this.results;
  }
  
  /**
   * 获取执行摘要
   */
  getSummary() {
    const success = this.results.filter(r => r.success).length;
    const total = this.results.length;
    return {
      success,
      total,
      failed: total - success,
      results: this.results
    };
  }
}

/**
 * 截图并提示用户确认
 * @param {string} prompt - 确认提示
 * @returns {Promise<void>}
 */
export async function confirmWithScreenshot(prompt) {
  cliLog(`\n📸  截取当前页面...`);
  await captureScreenshot();
  
  cliLog(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  cliLog(`⚠️  用户确认`);
  cliLog(`   ${prompt}`);
  cliLog('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  
  await handOffTaskSpace('请确认页面信息无误后继续');
  await takeOverTaskSpace();
}

export default {
  isLoggedIn,
  waitForLogin,
  findElement,
  withRetry,
  safeClick,
  safeFillInput,
  StepRunner,
  confirmWithScreenshot
};

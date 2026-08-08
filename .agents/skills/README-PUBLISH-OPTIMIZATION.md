# 发布流程优化说明

## 本次优化概述

针对发布相关的 skill 进行了全面优化，重点解决以下问题：

1. ✅ **handOffTaskSpace 机制缺陷** - 调用后脚本直接退出，无法等待用户登录完成
2. ✅ **登录流程改进** - 自动轮询检测登录状态，登录成功后自动继续
3. ✅ **错误处理完善** - 每步操作都有错误处理和重试机制
4. ✅ **元素定位增强** - 不依赖固定 selector，使用文本匹配，支持中英文
5. ✅ **新增抖音 CLI** - 基于 ego-browser 的抖音上传脚本

## 优化内容详解

### 1. 通用工具模块

**文件**: `lib/browser-utils.mjs`

提供可复用的浏览器自动化工具：

- `checkLoginStatus()` - 检查登录状态
- `waitForLoginAuto()` - 自动轮询等待用户登录，10分钟超时
- `findElement()` - 元素定位（多 selector 备选、文本匹配）
- `clickByText()` - 通过文本内容点击元素
- `safeFillInputByPlaceholder()` - 安全填写输入框
- `withRetry()` - 带重试的操作执行器
- `StepRunner` - 分步执行框架

### 2. B站上传脚本 (优化)

**文件**: `bilibili-upload/scripts/bilibili-upload.mjs`

**新增功能**:
- 登录状态自动检测 + 轮询等待
- 分步执行（6个步骤），每步有状态提示
- 元素定位增强：通过 placeholder/aria-label 匹配
- 表单填写重试机制
- 发布前自动截图

**用法**:
```bash
node .agents/skills/bilibili-upload/scripts/bilibili-upload.mjs \
  --file video.mp4 \
  --title "视频标题" \
  --desc "视频描述" \
  --tags "科技,开源,AI" \
  --cover cover.jpg \
  --tid 124
```

### 3. YouTube 上传脚本 (优化)

**文件**: `youtube-upload/scripts/youtube-upload.mjs`

**新增功能**:
- 登录状态自动检测 + 轮询等待
- 分步执行（6个步骤）
- 元素定位增强：中英文文本匹配
- 通过文本内容点击按钮（"创建"/"CREATE"/"Create"）
- 表单填写重试机制
- 发布前自动截图

**用法**:
```bash
node .agents/skills/youtube-upload/scripts/youtube-upload.mjs \
  --file video.mp4 \
  --title "Video Title" \
  --desc "Video Description" \
  --tags "Tech,OpenSource,AI" \
  --thumbnail cover.jpg \
  --visibility public
```

### 4. 抖音上传脚本 (新增)

**文件**: `douyin-upload/scripts/douyin-upload.mjs`

**功能**:
- 登录状态自动检测 + 自动切换到扫码登录
- 自动轮询等待用户登录
- 分步执行（6个步骤）
- 支持横封面和竖封面上传
- 动态元素定位（不依赖固定 class 名称）
- 发布前自动截图

**用法**:
```bash
node .agents/skills/douyin-upload/scripts/douyin-upload.mjs \
  --file video.mp4 \
  --title "视频标题" \
  --desc "视频描述" \
  --tags "科技,开源,AI" \
  --cover-horizontal cover-4-3.jpg \
  --cover-vertical cover-3-4.jpg \
  --schedule "2026-07-20 21:30"
```

### 5. fd-vaas-publish (整合)

**文件**: `d-vaas-publish-videos/scripts/publish.mjs`

**改进**:
- 支持新旧两种 CLI 脚本
  - 新版（ego-browser）: douyin, bilibili, youtube
  - 旧版（Playwright）: xiaohongshu, kuaishou 等
- 自动检测平台可用的 CLI 类型
- 统一的参数处理和错误输出
- 发布记录写入 task.json

**用法**:
```bash
# 多平台一起发布
node .agents/skills/d-vaas-publish-videos/scripts/publish.mjs \
  --slug findata-intro \
  --title "寻数科技品牌介绍" \
  --platforms douyin,bilibili,youtube \
  --tags "科技,开源,AI,数据" \
  --dry-run
```

## 登录流程机制详解

### 旧流程的问题

```javascript
// 旧: 直接 handOff，控制权交给用户后脚本退出
if (notLoggedIn) {
  await handOffTaskSpace('请登录...');
  // 脚本执行到这里，但控制权不在 agent，后续操作会失败
}
// 后面的代码无法在用户登录后继续执行
```

### 新流程的解决

```javascript
// 新: 轮询等待登录
async function waitForLoginAuto() {
  await handOffTaskSpace();  // 先把控制权交给用户
  
  const timeoutSeconds = 600; // 10分钟超时
  const pollIntervalSeconds = 3;
  
  while (Date.now() - startTime < timeoutSeconds * 1000) {
    try {
      // 尝试夺回控制权
      await takeOverTaskSpace();
    } catch (e) {
      // 用户还在操作，继续等待
      await wait(pollIntervalSeconds);
      continue;
    }
    
    // 检查是否已登录
    if (await checkLoginStatus()) {
      cliLog('✅ 登录成功！自动继续执行...');
      return true;
    }
    
    // 还没登录，把控制权还给用户，继续等待
    await handOffTaskSpace();
    await wait(pollIntervalSeconds);
  }
  
  return false;
}
```

**关键原理**:
1. 未登录时调用 `handOffTaskSpace()`，把控制权交给用户
2. 每 3 秒尝试 `takeOverTaskSpace()` 夺回控制权
3. 夺回控制权后，通过页面文本内容检测是否已登录
4. 如果已登录，继续执行后续步骤；如果未登录，把控制权还给用户继续等待
5. 10分钟超时提示

## 元素定位增强

### 旧方式的问题

依赖固定 CSS selector，前端稍微改动就会失效：

```javascript
await click('.publish-btn');  // 很容易因为 class 改名失效
```

### 新方式

多种策略兜底：

1. **文本匹配** - 通过元素的文本内容定位
   ```javascript
   await clickByText(['发布', 'Publish', '发布作品'], '点击发布按钮');
   ```

2. **属性匹配** - 通过 placeholder / aria-label 定位输入框
   ```javascript
   await safeFillInputByPlaceholder(['标题', 'title'], value, '填写标题');
   ```

3. **多 selector 备选** - 第一个失败了试第二个
   ```javascript
   selectors: ['button.primary', '.publish-btn', '[type="submit"]']
   ```

## 分步执行框架

每个脚本都采用统一的 6 步结构：

1. ✅ 打开目标页面
2. ✅ 检查登录状态（未登录则等待）
3. ✅ 上传视频
4. ✅ 填写表单（标题/描述/标签）
5. ✅ 设置封面/缩略图
6. ✅ 发布前确认（截图 + 手动发布）

每步都有清晰的日志输出，方便排查问题。

## 与 Playwright 脚本的区别

| 特性 | ego-browser 新版 | Playwright 旧版 |
|------|----------------|--------------|
| 自动登录等待 | ✅ 支持，自动轮询 | ❌ 不支持，手动 |
| 元素定位 | ✅ 文本匹配，更鲁棒 | ⚠️ 依赖固定 selector |
| 错误重试 | ✅ 内置重试机制 | ❌ 单次执行 |
| 发布确认 | ✅ 截图 + 手动点击发布 | ⚠️ 部分自动点击 |
| 并发发布 | ❌ 依次发布，需手动操作 | ✅ 可全自动并发 |
| 适用平台 | 抖音、B站、YouTube | 小红书、快手等 |

## 注意事项

1. **发布按钮需要手动点击** - ego-browser 脚本不会自动点击发布按钮，
   会在最后一步截图并把控制权交给用户，由用户确认后手动点击发布。

2. **浏览器窗口不要关闭** - 脚本执行期间不要关闭 ego-browser 窗口。

3. **登录超时** - 登录等待超时时间是 10 分钟，超时后脚本会继续执行后续步骤，
   用户可以在后续手动完成登录。

4. **封面上传** - 封面上传失败时会提示用户手动操作，不会中断整个流程。

## 测试命令

```bash
# 测试单个平台 (dry-run)
node .agents/skills/douyin-upload/scripts/douyin-upload.mjs \
  --file test.mp4 \
  --title "测试视频" \
  --dry-run

# 测试多平台整合 (dry-run)
node .agents/skills/d-vaas-publish-videos/scripts/publish.mjs \
  --slug test \
  --title "测试视频" \
  --platforms douyin,bilibili,youtube \
  --dry-run
```

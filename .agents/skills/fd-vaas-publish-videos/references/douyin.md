
# 抖音上传 Skill (douyin-upload)

通过 ego-browser 浏览器自动化，将视频发布到抖音创作者中心（creator.douyin.com）。
**完全基于真实浏览器操作**，复用用户已有的登录态，不需要额外登录或 cookie 文件。

---

## 前置条件（硬性）

1. **ego-browser 已安装**（`which ego-browser` 能找到）
2. **抖音创作者中心已登录** —— ego-browser 继承用户 Chrome 的登录态。如果没登录，
   打开页面后把浏览器控制权交给用户，让用户扫码登录，完成后再继续。
3. **视频文件已准备好**（mp4 格式，≤ 60 分钟，≤ 16GB）
4. **封面图可选但推荐** —— 横版 16:9，竖版 3:4，优先用 `fd-cover-image` skill 生成

---

## 发布流程（标准工作流）

### 第一步：上传视频 + 填基础信息

```bash
# 用 ego-browser 操作（所有操作通过 heredoc 调用 ego-browser nodejs）
ego-browser nodejs <<'EOF'
await useOrCreateTaskSpace('douyin-publish-<slug>')

// 打开上传页面
await openOrReuseTab('https://creator.douyin.com/creator-micro/content/upload', { wait: true })
await wait(5)

// 上传视频
await uploadFile('input[type="file"][accept*="video"]', '/path/to/video.mp4')
await wait(20)  // 等上传完成，时间取决于文件大小

// 填描述（标题 + 正文 + 话题）
// 抖音的作品描述是 contenteditable，用 execCommand 输入
await js(`(() => {
  const editor = document.querySelector('[contenteditable="true"]')
  editor?.focus()
  document.execCommand('insertText', false, '你的描述内容 #话题1 #话题2')
})()`)
EOF
```

### 第二步：设置封面（重要，推荐必做）

抖音有**横封面（4:3）**和**竖封面（3:4）**两个，都建议设置。
优先使用 `fd-cover-image` skill 生成的品牌封面。

```bash
ego-browser nodejs <<'EOF'
await useOrCreateTaskSpace('douyin-publish-<slug>')

// 滚动到封面区域
await js('window.scrollTo(0, 350)')
await wait(1)

// === 设置横封面 ===
// 1. 点击横封面区域
await js(`document.querySelectorAll('.cover-Jg3T4p')[0].click()`)
await wait(3)

// 2. 点击"上传封面"按钮
await js(`(() => {
  const all = document.querySelectorAll('div, button, span')
  for (const el of all) {
    if (el.textContent?.trim() === '上传封面') { el.click(); break }
  }
})()`)
await wait(2)

// 3. 上传封面图（通过 .selectArea-BCIYQD 里的 file input）
await js(`(() => {
  const area = document.querySelector('.selectArea-BCIYQD')
  const input = area?.querySelector('input[type="file"]')
  if (input) input.setAttribute('id', 'douyin-h-cover')
})()`)
await uploadFile('#douyin-h-cover', '/path/to/cover-horizontal.jpg')
await wait(5)

// 4. 点"完成"确认
await js(`(() => {
  const btns = document.querySelectorAll('button')
  for (const b of btns) {
    if (b.textContent?.trim() === '完成' && b.className?.includes('primary')) {
      b.click(); break
    }
  }
})()`)
await wait(2)

// === 设置竖封面 === （同样的流程，第二个 .cover-Jg3T4p）
await js(`document.querySelectorAll('.cover-Jg3T4p')[1].click()`)
// ... 重复上面的 2-4 步
EOF
```

### 第三步：确认 + 发布

**发布前必须让用户确认以下信息：**
- [ ] 视频是正确的
- [ ] 标题/描述/话题正确
- [ ] 横封面 OK
- [ ] 竖封面 OK
- [ ] 发布设置：立即发布 / 定时发布
- [ ] 可见范围：公开 / 好友可见 / 仅自己可见

确认后才点发布按钮：

```bash
ego-browser nodejs <<'EOF'
await useOrCreateTaskSpace('douyin-publish-<slug>')

// 滚动到底部
await js('window.scrollTo(0, document.body.scrollHeight)')

// 点发布（class 含 primary + "发布" 文本）
await js(`(() => {
  const btns = document.querySelectorAll('button')
  for (const b of btns) {
    if (b.textContent?.trim() === '发布' && b.className?.includes('primary')) {
      b.click(); return 'clicked'
    }
  }
  return 'not found'
})()`)

await wait(5)

// 验证发布结果
const status = await js(`document.body.innerText`)
const success = status.includes('发布成功') || status.includes('已发布') || status.includes('审核中')
cliLog('发布结果: ' + (success ? '✅ 成功' : '⚠️ 请手动确认'))
EOF
```

---

## 关键 DOM 选择器（抖音创作者中心，2024-2025 版）

> ⚠️ 抖音前端经常改 class 名，选择器可能失效。操作前先 `snapshotText()` 验证页面状态，
> 找不到元素时用 `js()` 动态遍历定位，不要死依赖固定 class。

| 元素 | 选择器 / 定位方式 | 说明 |
|---|---|---|
| 视频上传 input | `input[type="file"][accept*="video"]` | 上传视频文件 |
| 描述输入框 | `[contenteditable="true"]` | 第一个 contenteditable |
| 封面区域（横+竖） | `.cover-Jg3T4p` | 两个，第一个横版，第二个竖版 |
| 封面编辑器上传区域 | `.selectArea-BCIYQD input[type="file"]` | 上传自定义封面 |
| 封面「完成」按钮 | `button:contains("完成").semi-button-primary` | 确认封面 |
| 发布按钮 | `button:contains("发布").primary-*` | 页面底部的主按钮 |
| 定时发布选项 | 文字「定时发布」 | 切换发布时间 |

---

## 常见问题

### 没登录怎么办？

**标准 3 步登录引导（硬性）**：不要一看到登录页就停住等用户。

1. **自动切到扫码登录** —— 在登录页找「扫码登录」「二维码登录」按钮/tab，自动点击切换。
2. **明确提示用户** —— 告诉用户切到 ego-browser 窗口扫码，不要让用户猜。
3. **自动轮询检测** —— 每 3 秒检查一次登录状态，检测到登录成功自动继续，不用等用户说 continue。
   超时 120 秒才提醒用户。

参考 `fd-vaas-publish` skill 的「登录处理标准流程」章节，有完整的 `waitForLogin` 轮询函数模板。

### 发布按钮是灰的？

说明有必填项没填。检查：
1. 视频是否上传完成
2. 描述是否填写（至少 1 个字）
3. 有没有违规提示（页面上有红色文字警告）

### 封面上传不上？

抖音封面编辑器的 file input 是动态渲染的，可能需要先点「上传封面」按钮
让 input 出现，再用 `uploadFile`。如果还是不行，让用户手动上传封面。

---

## 与其他 Skill 的关系

- **fd-vaas-publish**：多平台分发编排，调用本 skill 执行抖音上传。
- **fd-cover-image**：生成封面图（优先用 Remotion，不要用 AI 生图）。
- **ego-browser**：底层浏览器自动化引擎，本 skill 所有操作都通过它。

---

## 注意事项

1. **发布前必须用户确认** —— 发出去撤不回来，不要自动点发布。
2. **每步操作后验证状态** —— 抖音页面可能加载慢、有弹窗，不要盲目连续点击。
3. **遇到异常交还给用户** —— 选择器失效、弹出验证码、风控提示时，
   用 `handOffTaskSpace()` 把浏览器交给用户手动处理。
4. **一个任务一个 task space** —— 命名 `douyin-publish-<slug>`，方便后续追溯。

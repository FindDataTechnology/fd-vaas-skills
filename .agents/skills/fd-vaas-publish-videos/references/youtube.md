
# YouTube 上传 Skill (youtube-upload)

通过 ego-browser 浏览器自动化，将视频发布到 YouTube Studio。

---

## ⚠️ 核心技术挑战：Polymer Web Components

YouTube Studio 使用 **Polymer Web Components** (`tp-yt-paper-dialog`, `ytcp-*`)，
这些自定义元素有内部状态管理，不能简单用 DOM 操作控制。

### 上传对话框无法打开

YouTube 的上传编辑对话框 (`ytcp-uploads-dialog`) 包含一个 `tp-yt-paper-dialog` 子元素，
该元素即使父元素 `display: flex`，自身也保持 `display: none`。需要**强制设置 opened 属性**：

```js
await js(`(() => {
  const dialog = document.querySelector('ytcp-uploads-dialog');
  if (!dialog) return 'no dialog';
  const paper = dialog.querySelector('tp-yt-paper-dialog');
  if (paper) {
    paper.opened = true;
    paper.style.display = 'block';
    paper.setAttribute('opened', '');
  }
  return 'forced open';
})()`);
```

### 4 步上传对话框

上传编辑对话框有 4 个步骤，每步需要点 "Next" 按钮前进：
1. **Details** - 标题、描述、"Not made for kids" 选择
2. **Video elements** - 视频元素（可跳过）
3. **Checks** - 版权检查（需等待自动完成）
4. **Visibility** - 可见性选择（Public/Unlisted/Private）+ Publish 按钮

### "Not made for kids" 阻塞 Next 按钮

Details 步骤中必须回答 "Is this video made for kids?" 问题，否则 Next 按钮禁用：

```js
// 点击 "No, it's not made for kids"
await js(`(() => {
  const radios = document.querySelectorAll('tp-yt-paper-radio-button');
  for (const r of radios) {
    if (r.textContent?.includes('No') && r.textContent?.includes('kids')) {
      r.click();
      return 'clicked not for kids';
    }
  }
  return 'not found';
})()`);
```

### 标题修改用 execCommand

YouTube 的标题输入框是 contenteditable DIV (`#textbox`)，不能用 `.value =` 设置，
必须用 `execCommand`：

```js
await js(`(() => {
  const textbox = document.querySelector('#textbox');
  if (!textbox) return 'no textbox';
  textbox.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, '你的标题');
  return 'title set';
})()`);
```

---

## 快速使用

```bash
SKILL=/Users/chengsishi/VAAS/.agents/skills/fd-vaas-publish/scripts/platforms

node $SKILL/youtube.mjs \
  --file /path/to/video.mp4 \
  --title "视频标题" \
  --desc "视频描述" \
  --tags "标签1,标签2" \
  --thumbnail /path/to/thumbnail.jpg \
  --visibility public
```

### 命令行参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `--file` | ✅ | 视频文件路径 |
| `--title` | ✅ | 视频标题 |
| `--desc` | ❌ | 视频描述 |
| `--tags` | ❌ | 标签，逗号分隔 |
| `--thumbnail` | ❌ | 缩略图路径（建议 1280×720） |
| `--visibility` | ❌ | public (默认), unlisted, private |
| `--dry-run` | ❌ | 只打开页面不上传 |

---

## 完整发布流程（ego-browser 直接操作）

```bash
ego-browser nodejs <<'EOF'
await useOrCreateTaskSpace('youtube-publish');

// 1. 打开 YouTube Studio 上传页
await gotoAndWait('https://studio.youtube.com/channel/UCxxxx/videos/upload');
await wait(5);

// 2. 上传视频文件
await uploadFile('input[type="file"]', '/path/to/video.mp4');
cliLog('等待上传...');
await wait(30);

// 3. 等待上传对话框出现
for (let i = 0; i < 10; i++) {
  const hasDialog = await js(`!!document.querySelector('ytcp-uploads-dialog')`);
  if (hasDialog) break;
  await wait(3);
}

// 4. 强制打开 Polymer 对话框
await js(`(() => {
  const dialog = document.querySelector('ytcp-uploads-dialog');
  if (!dialog) return 'no dialog';
  const paper = dialog.querySelector('tp-yt-paper-dialog');
  if (paper) {
    paper.opened = true;
    paper.style.display = 'block';
    paper.setAttribute('opened', '');
  }
  return 'forced open';
})()`);
await wait(2);

// 5. 填写标题
await js(`(() => {
  const textbox = document.querySelector('#textbox');
  if (!textbox) return 'no textbox';
  textbox.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, '你的标题');
  return 'title set';
})()`);
await wait(1);

// 6. 填写描述（第二个 #textbox）
await js(`(() => {
  const textboxes = document.querySelectorAll('#textbox[contenteditable]');
  if (textboxes.length >= 2) {
    textboxes[1].focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
    document.execCommand('insertText', false, '你的描述');
    return 'desc set';
  }
  return 'no desc textbox';
})()`);
await wait(1);

// 7. 选择 "No, it's not made for kids"
await js(`(() => {
  const radios = document.querySelectorAll('tp-yt-paper-radio-button');
  for (const r of radios) {
    if (r.textContent?.includes('No') && r.textContent?.includes('kids')) {
      r.click();
      return 'clicked';
    }
  }
  return 'not found';
})()`);
await wait(1);

// 8. 上传缩略图（可选）
// 缩略图上传按钮: #thumbnail > .thumb-container
await js(`document.querySelector('#thumbnail [class*="upload"]')?.click()`);
await wait(1);
await uploadFile('input[type="file"][accept*="image"]', '/path/to/thumbnail.jpg');
await wait(5);

// 9. 点击 Next 4次，到达 Visibility 步骤
for (let i = 0; i < 3; i++) {
  await js(`(() => {
    const btns = document.querySelectorAll('ytcp-button');
    for (const b of btns) {
      if (b.textContent?.trim() === 'Next' && !b.hasAttribute('disabled')) {
        b.click();
        return 'next ' + ${i+1};
      }
    }
    // 也检查 #next-button
    const next = document.querySelector('#next-button');
    if (next && !next.hasAttribute('disabled')) {
      next.click();
      return 'next via id';
    }
    return 'no next';
  })()`);
  await wait(3);
}

// 10. 选择 Public 可见性
await js(`(() => {
  const radios = document.querySelectorAll('tp-yt-paper-radio-button');
  for (const r of radios) {
    if (r.textContent?.includes('Public')) {
      r.click();
      return 'public selected';
    }
  }
  return 'not found';
})()`);
await wait(1);

// 11. 点击 Publish
await js(`(() => {
  const btn = document.querySelector('#done-button');
  if (btn && !btn.hasAttribute('disabled')) {
    btn.click();
    return 'published';
  }
  // 备用
  const btns = document.querySelectorAll('ytcp-button');
  for (const b of btns) {
    if (b.textContent?.trim() === 'Publish') {
      b.click();
      return 'published via ytcp';
    }
  }
  return 'no publish btn';
})()`);
await wait(5);

// 12. 验证
const url = await js('window.location.href');
cliLog(url.includes('dashboard') || url.includes('videos') ? '✅ 发布成功' : '⚠️ 请检查');
EOF
```

---

## 关键 DOM 选择器

| 元素 | 选择器 | 说明 |
|---|---|---|
| 文件上传 input | `input[type="file"]` | 视频上传 |
| 上传对话框 | `ytcp-uploads-dialog` | Polymer 自定义元素 |
| 对话框内层 | `tp-yt-paper-dialog` | 需强制 `opened=true` + `display:block` |
| 标题输入框 | `#textbox` (第一个) | contenteditable，用 execCommand |
| 描述输入框 | `#textbox` (第二个) | contenteditable |
| Kids 选项 | `tp-yt-paper-radio-button` | 含 "No" + "kids" 文字 |
| Next 按钮 | `ytcp-button` (含"Next") 或 `#next-button` | 可能有 disabled 属性 |
| 可见性选项 | `tp-yt-paper-radio-button` | 含 "Public"/"Unlisted"/"Private" |
| Publish 按钮 | `#done-button` 或 `ytcp-button` (含"Publish") | 最后一步 |
| 缩略图上传 | `#thumbnail` 区域 | 需点击触发 file input |

---

## 常见问题

### 对话框打不开？

`tp-yt-paper-dialog` 有内部 Polymer 状态，简单 `.open()` 或 `display:block` 可能不生效。
需要同时设置：`paper.opened = true` + `paper.style.display = 'block'` + `paper.setAttribute('opened', '')`。

### Next 按钮是灰的？

说明当前步骤有必填项未完成：
1. Details 步骤：必须选择 "Not made for kids"
2. Checks 步骤：需等待版权检查自动完成（可能需要 30-60 秒）

### 标题修改不生效？

YouTube 标题是 contenteditable DIV，不能用 `.value =`。必须用 `document.execCommand('insertText', false, text)`。

### 上传了重复视频？

如果多次上传生成了重复的 Draft，可以在 Content 页面删除多余的 Draft（`ytcp-icon-button` 菜单 -> Delete）。

---

## 注意事项

1. **Polymer 对话框需强制打开**：`tp-yt-paper-dialog` 不会自动显示
2. **"Not made for kids" 必答**：不选则 Next 按钮禁用
3. **标题用 execCommand**：contenteditable 不能用 `.value`
4. **Checks 步骤需等待**：版权检查自动运行，需等完成才能 Next
5. **Google 登录**：可能需要 2FA，遇到时交给用户处理

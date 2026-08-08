
# 快手上传 Skill (kuaishou-upload)

通过 ego-browser 浏览器自动化，将视频发布到快手创作者平台。

---

## ⚠️ 核心技术挑战

### 1. React Joyride 引导遮罩

快手创作者平台首次使用时会加载 **React Joyride** 新手引导，生成一个全屏遮罩
(`react-joyride__overlay`)，**拦截所有点击事件**。必须先移除它：

```js
await js(`(() => {
  const overlays = document.querySelectorAll('[class*="react-joyride"], [class*="joyride"]');
  overlays.forEach(el => el.remove());
  return 'removed ' + overlays.length + ' joyride elements';
})()`);
```

### 2. 封面选择

快手的封面设置是通过 **Ant Design Modal** 实现的：
- 点击封面区域 (`._default-cover`) 打开模态框
- 模态框中可选择视频帧或上传自定义封面
- 需要用 **CDP `Input.dispatchMouseEvent`** 模拟真实点击（JS click 不触发框架事件）

```js
// 点击封面区域打开模态框
await js(`document.querySelector('._default-cover')?.click()`);
await wait(2);

// 在模态框中确认选帧
await js(`(() => {
  const modal = document.querySelector('.ant-modal-body');
  if (!modal) return 'no modal';
  // 点击"确认"按钮
  const confirmBtn = modal.querySelector('.ant-btn-primary');
  if (confirmBtn) { confirmBtn.click(); return 'confirmed'; }
  return 'no confirm btn';
})()`);
```

### 3. 发布按钮在视口外

快手的发布按钮 (`._button-primary_3a3lq_60`) 通常在页面底部，**在视口之外**。
直接 `click()` 不生效，必须先 `scrollIntoView`：

```js
await js(`(() => {
  const btn = document.querySelector('._button-primary_3a3lq_60');
  if (!btn) return 'no btn';
  btn.scrollIntoView({ block: 'center' });
  return 'scrolled';
})()`);
await wait(1);
// scrollIntoView 后用 element.click() 点击
await js(`document.querySelector('._button-primary_3a3lq_60')?.click()`);
```

### 4. 话题标签数量上限

快手话题标签**上限 4 个**（不是 5 个）。超过会报错"话题标签数量超过上限：4"。
即使删除多余标签文本，旧的 hashtag entities 可能残留在框架状态中，需要**刷新页面重新填写**。

---

## 快速使用

```bash
export VAAS=<VAAS 仓库根目录,如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代
SKILL=$VAAS/.agents/skills/d-vaas-publish-videos/scripts/platforms

node $SKILL/kuaishou.mjs \
  --file /path/to/video.mp4 \
  --title "视频标题" \
  --desc "视频描述 #标签1 #标签2" \
  --tags "标签1,标签2"
```

### 命令行参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `--file` | ✅ | 视频文件路径 |
| `--title` | ❌ | 视频标题（快手标题和描述合一） |
| `--desc` | ❌ | 视频描述/正文（支持 #话题，**最多 4 个**） |
| `--cover` | ❌ | 封面图片路径 |
| `--dry-run` | ❌ | 只打开页面不上传 |

---

## 完整发布流程（ego-browser 直接操作）

```bash
ego-browser nodejs <<'EOF'
await useOrCreateTaskSpace('kuaishou-publish');

// 1. 打开上传页
await gotoAndWait('https://cp.kuaishou.com/article/publish/video');
await wait(5);

// 2. 移除 React Joyride 遮罩（关键！）
await js(`(() => {
  const overlays = document.querySelectorAll('[class*="react-joyride"], [class*="joyride"]');
  overlays.forEach(el => el.remove());
  return 'removed ' + overlays.length;
})()`);
await wait(1);

// 3. 上传视频
await uploadFile('input[type="file"]', '/path/to/video.mp4');
cliLog('等待上传...');
await wait(30);

// 4. 填写描述（contenteditable，用 execCommand）
await js(`(() => {
  const editor = document.querySelector('[contenteditable="true"]');
  if (!editor) return 'no editor';
  editor.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('delete', false, null);
  document.execCommand('insertText', false, '描述内容 #标签1 #标签2');
  return 'filled';
})()`);
await wait(2);

// 5. 设置封面（点击默认封面区域打开模态框）
await js(`document.querySelector('._default-cover')?.click()`);
await wait(2);

// 在模态框中确认选帧
await js(`(() => {
  const modal = document.querySelector('.ant-modal-body');
  if (!modal) return 'no modal';
  const confirmBtn = modal.querySelector('.ant-btn-primary');
  if (confirmBtn) { confirmBtn.click(); return 'confirmed'; }
  return 'no confirm btn';
})()`);
await wait(2);

// 6. 滚动到发布按钮并点击（关键！按钮在视口外）
await js(`(() => {
  const btn = document.querySelector('._button-primary_3a3lq_60');
  if (!btn) {
    // 备用：找所有粉色按钮
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const bg = getComputedStyle(b).backgroundColor;
      if (bg.includes('254, 54, 102') && b.textContent?.trim()) {
        b.scrollIntoView({ block: 'center' });
        return 'scrolled to pink btn: ' + b.textContent.trim();
      }
    }
    return 'no publish btn';
  }
  btn.scrollIntoView({ block: 'center' });
  return 'scrolled';
})()`);
await wait(1);

// 点击发布
await js(`(() => {
  const btn = document.querySelector('._button-primary_3a3lq_60');
  if (btn) { btn.click(); return 'clicked'; }
  // 备用
  const btns = document.querySelectorAll('button');
  for (const b of btns) {
    const bg = getComputedStyle(b).backgroundColor;
    if (bg.includes('254, 54, 102') && b.textContent?.includes('发布')) {
      b.click(); return 'clicked pink: ' + b.textContent.trim();
    }
  }
  return 'not found';
})()`);
await wait(5);

// 7. 验证（URL 应变为 manage/video?status=2）
const url = await js('window.location.href');
const success = url.includes('status=2') || url.includes('publish') && url.includes('manage');
cliLog(success ? '✅ 发布成功' : '⚠️ 请检查');
EOF
```

---

## 关键 DOM 选择器

| 元素 | 选择器 | 说明 |
|---|---|---|
| 视频上传 input | `input[type="file"]` | 标准文件上传 |
| 描述输入框 | `[contenteditable="true"]` | contenteditable DIV |
| 封面区域 | `._default-cover` | 点击打开封面选择模态框 |
| 封面模态框 | `.ant-modal-body` | Ant Design Modal |
| 模态框确认按钮 | `.ant-modal-body .ant-btn-primary` | 确认选帧 |
| 发布按钮 | `._button-primary_3a3lq_60` | 粉色按钮 bg: rgb(254, 54, 102) |
| Joyride 遮罩 | `[class*="react-joyride"]` | 首次使用时出现，需移除 |

### 发布按钮备用定位

class 名含 hash，可能变化。备用方案：找背景色为粉色 `rgb(254, 54, 102)` 且有文字的按钮。

---

## 常见问题

### 点击发布没反应？

1. **React Joyride 遮罩**：检查是否有 `[class*="react-joyride"]` 元素，有则移除
2. **按钮在视口外**：先 `scrollIntoView({ block: 'center' })` 再 click
3. **话题标签超限**：快手上限 4 个 #话题，超过会报错且旧标签残留在状态中，需刷新页面

### 封面设置不了？

1. 点击 `._default-cover` 打开模态框
2. 如果 JS click 不生效，用 CDP `Input.dispatchMouseEvent` 模拟真实鼠标点击
3. 模态框打开后点 `.ant-btn-primary` 确认选帧

### 上传后页面卡住？

刷新页面重新上传。快手的 React 状态可能因为话题标签错误等操作进入异常状态，
刷新是最可靠的恢复方式。

---

## 注意事项

1. **话题标签 ≤ 4 个**：超过会报错且需要刷新页面
2. **首次使用移除 Joyride**：新手引导遮罩会拦截所有点击
3. **发布按钮需 scrollIntoView**：按钮在页面底部视口外
4. **登录**：第一次使用需要扫码登录


# B站上传 Skill (bilibili-upload)

通过 ego-browser 浏览器自动化，将视频发布到 B站创作中心。

---

## ⚠️ 核心技术挑战：micro-app 微前端

B站创作中心使用 **micro-app 微前端框架**，页面内容渲染在 `micro-app[name=video-up]`
元素的 **shadow DOM** 内部。标准 `document.querySelector()` 无法直接访问页面元素。

### Shadow DOM 访问方式

```js
const microApp = document.querySelector('micro-app[name=video-up]');
const sr = microApp?.shadowRoot;
if (!sr) return 'micro-app not loaded';

// 所有查询都用 sr.querySelector
const titleInput = sr.querySelector('input[placeholder*="标题"]');
const submitBtn = sr.querySelector('button.submit');
```

> **注意**：micro-app 的 shadow DOM 通常是 **open** 模式，可以通过 `.shadowRoot` 访问。
> 如果返回 null，可能页面还没加载完，需轮询等待。

### 文件上传

文件 input 也在 shadow DOM 内，`uploadFile()` 可能无法直接找到。两种方案：

**方案 1**：给 input 设置 ID 后用 `uploadFile`（如果 ego-browser 支持 shadow DOM 穿透）
```js
await js(`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const input = sr?.querySelector('input[type="file"]');
  if (input) { input.id = 'bili-upload'; return 'set id'; }
  return 'no input';
})()`);
// uploadFile 可能找不到 shadow DOM 内的元素
```

**方案 2**（推荐）：用 CDP `DOM.setFileInputFiles` 或 HTTP 服务器 + DataTransfer（同 weixin-upload）

---

## 快速使用

```bash
export VAAS=<VAAS 仓库根目录,如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代
SKILL=$VAAS/.agents/skills/d-vaas-publish-videos/scripts/platforms

node $SKILL/bilibili.mjs \
  --file /path/to/video.mp4 \
  --title "视频标题" \
  --desc "视频简介" \
  --tags "标签1,标签2" \
  --cover /path/to/cover.jpg \
  --tid 124
```

### 命令行参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `--file` | ✅ | 视频文件路径 |
| `--title` | ✅ | 视频标题 |
| `--desc` | ❌ | 视频简介 |
| `--tags` | ❌ | 标签，逗号分隔 |
| `--cover` | ❌ | 封面图片路径（建议 1920×1080） |
| `--tid` | ❌ | 分区 ID，默认 124（科普） |
| `--dry-run` | ❌ | 只打开页面不上传 |

### 常用分区 ID (tid)

| 分区 | tid |
|---|---|
| 科技 -> 软件应用 | 36 |
| 科技 -> 科普 | 124 |
| 财经 -> 商业 | 208 |
| 知识 -> 校园学习 | 201 |

---

## 完整发布流程（ego-browser 直接操作）

```bash
ego-browser nodejs <<'EOF'
await useOrCreateTaskSpace('bilibili-publish');

// 1. 打开上传页
await gotoAndWait('https://member.bilibili.com/v2#/upload/video/frame');
await wait(5);

// 2. 等待 micro-app 加载
for (let i = 0; i < 15; i++) {
  const ready = await js(`!!document.querySelector('micro-app[name=video-up]')?.shadowRoot?.querySelector('input[type="file"]')`);
  if (ready) break;
  await wait(2);
}

// 3. 上传视频
// 方案 A: 尝试直接 uploadFile
try {
  await uploadFile('input[type="file"]', '/path/to/video.mp4');
} catch (e) {
  // 方案 B: 用 CDP 在 shadow DOM 内设置文件
  const doc = await cdp('DOM.getDocument', { depth: -1, pierce: true });
  // 递归查找 file input 的 backendNodeId
  function findFileInput(node) {
    if (!node) return null;
    if (node.nodeName === 'INPUT' && node.attributes) {
      for (let i = 0; i < node.attributes.length; i += 2) {
        if (node.attributes[i] === 'type' && node.attributes[i+1] === 'file') return node;
      }
    }
    if (node.children) for (const c of node.children) { const r = findFileInput(c); if (r) return r; }
    if (node.shadowRoots) for (const sr of node.shadowRoots) { const r = findFileInput(sr); if (r) return r; }
    return null;
  }
  const fileInput = findFileInput(doc?.root);
  if (fileInput) {
    await cdp('DOM.setFileInputFiles', {
      backendNodeId: fileInput.backendNodeId,
      files: ['/path/to/video.mp4']
    });
  }
}
cliLog('等待上传...');
await wait(30);

// 4. 填写标题（在 shadow DOM 内）
await js(`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const input = sr?.querySelector('input[placeholder*="标题"]');
  if (input) {
    input.focus();
    input.value = '你的标题';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return 'title set';
  }
  return 'no title input';
})()`);
await wait(1);

// 5. 填写简介
await js(`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const textarea = sr?.querySelector('textarea');
  if (textarea) {
    textarea.focus();
    textarea.value = '你的简介';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    return 'desc set';
  }
  return 'no textarea';
})()`);
await wait(1);

// 6. 设置标签
await js(`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const tagInput = sr?.querySelector('input[placeholder*="标签"]');
  if (tagInput) {
    tagInput.focus();
    tagInput.value = '标签1';
    tagInput.dispatchEvent(new Event('input', { bubbles: true }));
    tagInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    return 'tag added';
  }
  return 'no tag input';
})()`);
await wait(1);

// 7. 上传封面
// 封面上传 input 也在 shadow DOM 内
// ...用 CDP setFileInputFiles 或 HTTP 服务器方案

// 8. 选择分区
await js(`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  // 点击分区下拉框
  const select = sr?.querySelector('[class*="tid"], .select-wrapper');
  select?.click();
  return 'clicked select';
})()`);
await wait(1);

// 9. 点击发布
await js(`(() => {
  const sr = document.querySelector('micro-app[name=video-up]')?.shadowRoot;
  const btn = sr?.querySelector('button.submit, [class*="submit"]');
  if (btn) { btn.click(); return 'clicked submit'; }
  return 'no submit btn';
})()`);
await wait(5);

// 10. 验证
const url = await js('window.location.href');
cliLog(url.includes('success') || url.includes('manager') ? '✅ 发布成功' : '⚠️ 请检查');
EOF
```

---

## 关键 DOM 选择器（Shadow DOM 内）

> ⚠️ 所有选择器需通过 `micro-app[name=video-up].shadowRoot` 访问

| 元素 | 选择器 | 说明 |
|---|---|---|
| micro-app 容器 | `micro-app[name=video-up]` | shadow DOM 宿主 |
| 文件上传 input | `input[type="file"]` | 在 shadow DOM 内 |
| 标题输入框 | `input[placeholder*="标题"]` | 普通 input |
| 简介输入框 | `textarea` | 第一个 textarea |
| 标签输入框 | `input[placeholder*="标签"]` | 输入后按 Enter |
| 分区选择 | `[class*="tid"]` 或 `.select-wrapper` | 下拉选择 |
| 封面上传 | 封面区域的 `input[type="file"]` | 可能需要先点击封面区域 |
| 发布按钮 | `button.submit` 或 `[class*="submit"]` | 页面底部 |

---

## 常见问题

### uploadFile 找不到 input？

B站的 file input 在 micro-app shadow DOM 内，`uploadFile()` 只搜索主文档。
用 CDP `DOM.getDocument({pierce: true})` 找到 `backendNodeId`，再用 `DOM.setFileInputFiles`。

### shadowRoot 返回 null？

micro-app 还没加载完。轮询等待：
```js
for (let i = 0; i < 15; i++) {
  const ready = await js(`!!document.querySelector('micro-app[name=video-up]')?.shadowRoot`);
  if (ready) break;
  await wait(2);
}
```

### 发布按钮点击无反应？

1. 检查是否有必填项未完成（标题、分区）
2. 检查视频是否上传完成（进度条 100%）
3. micro-app 框架可能需要真实用户事件，尝试 CDP `Input.dispatchMouseEvent`

---

## 注意事项

1. **micro-app shadow DOM**：所有页面元素在 shadow DOM 内，需用 `.shadowRoot` 访问
2. **文件上传**：`uploadFile()` 可能失效，用 CDP `DOM.setFileInputFiles` 或 HTTP 服务器方案
3. **分区选择**：B站要求选择分区，不选无法发布
4. **审核**：发布后进入审核，审核时间几分钟到几小时
5. **登录**：第一次使用需要扫码登录

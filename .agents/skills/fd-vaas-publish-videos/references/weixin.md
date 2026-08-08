
# 微信视频号上传 Skill (weixin-upload)

通过 ego-browser 浏览器自动化，将视频发布到微信视频号助手。

---

## ⚠️ 核心技术挑战：Wujie Shadow DOM

视频号助手使用 **Wujie 微前端框架**，所有页面内容都渲染在 `wujie-app` 元素的
**shadow DOM** 内部。这意味着：

1. `document.querySelector()` **无法**直接找到页面元素
2. `uploadFile()` **无法**直接上传文件（找不到 shadow DOM 内的 input）
3. CDP 的 `DOM.setFileInputFiles` **能**设置文件，但 **不会**触发 React/Ant Design
   的 `change` 事件（React 事件委托无法跨越 shadow DOM 边界）

### 解决方案：本地 HTTP 服务器 + DataTransfer API

**唯一可靠的文件上传方式**：

1. 在 Node.js 中启动本地 HTTP 服务器提供视频文件
2. 在浏览器中 `fetch('http://localhost:PORT/video.mp4')` 获取文件
3. 将响应转为 `Blob` -> `new File([blob], 'name.mp4', {type:'video/mp4'})`
4. 用 `DataTransfer` API 设置 `input.files = dt.files`
5. 手动 dispatch `change` 事件

### Shadow DOM 访问方式

所有页面元素都需要通过 `wujie-app.shadowRoot` 访问：

```js
const wujie = document.querySelector('wujie-app');
const sr = wujie?.shadowRoot;
if (!sr) return 'wujie not loaded yet';

// 所有查询都用 sr.querySelector 而不是 document.querySelector
const fileInput = sr.querySelector('input[type="file"]');
const editor = sr.querySelector('.input-editor');
const publishBtn = sr.querySelector('.weui-desktop-btn_primary');
```

---

## 快速使用

### 一键发布

```bash
export VAAS=<VAAS 仓库根目录,如 ~/fd-vaas-skills>   # 后续命令都用 $VAAS 指代
SKILL=$VAAS/.agents/skills/d-vaas-publish-videos/scripts/platforms

node $SKILL/weixin.mjs \
  --file /path/to/video.mp4 \
  --title "视频描述" \
  --desc "详细描述 #话题"
```

### 命令行参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `--file` | ✅ | 视频文件路径 |
| `--desc` | ❌ | 视频描述/正文（支持 #话题） |
| `--cover` | ❌ | 封面图片路径（建议 1080×1260） |
| `--dry-run` | ❌ | 只打开页面不上传 |

> **注意**：视频号没有单独的标题字段，描述就是正文内容。

---

## 完整发布流程（ego-browser 直接操作）

```bash
ego-browser nodejs <<'EOF'
(async () => {
  const http = require('http');
  const fs = require('fs');

  await useOrCreateTaskSpace('weixin-publish');

  // 1. 打开发布页
  await gotoAndWait('https://channels.weixin.qq.com/platform/post/create');
  await wait(5);

  // 2. 等待 wujie-app 加载
  for (let i = 0; i < 10; i++) {
    const hasWujie = await js(`!!document.querySelector('wujie-app')?.shadowRoot?.querySelector('input[type="file"]')`);
    if (hasWujie) break;
    await wait(2);
  }

  // 3. 启动本地 HTTP 服务器
  const filePath = '/path/to/video.mp4';
  const server = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'video/mp4');
    fs.createReadStream(filePath).pipe(res);
  });
  server.listen(18765);
  await wait(1);

  // 4. 通过 HTTP fetch + DataTransfer 上传文件
  const uploadResult = await js(String.raw`(() => {
    return fetch('http://localhost:18765/video.mp4')
      .then(r => r.blob())
      .then(blob => {
        const wujie = document.querySelector('wujie-app');
        const sr = wujie?.shadowRoot;
        if (!sr) return 'no shadow';
        const input = sr.querySelector('input[type="file"]');
        if (!input) return 'no input';

        // 创建真实的 File 对象
        const file = new File([blob], 'video.mp4', { type: 'video/mp4' });

        // 用 DataTransfer 设置 input.files
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;

        // dispatch change 事件触发 Ant Design 上传
        input.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
        return 'file set: count=' + input.files.length + ', size=' + input.files[0].size;
      })
      .catch(e => 'error: ' + e.message);
  })()`);
  cliLog('上传: ' + uploadResult);

  server.close();

  // 5. 等待上传完成（检测 form 文字变化）
  for (let i = 0; i < 30; i++) {
    await wait(10);
    const status = await js(`(() => {
      const sr = document.querySelector('wujie-app')?.shadowRoot;
      const form = sr?.querySelector('.form');
      const text = form?.textContent?.trim() || '';
      const uploading = text.includes('文件上传中');
      return { uploading, text: text.slice(0, 60) };
    })()`);
    cliLog((i+1)*10 + 's: ' + (status.uploading ? '上传中' : '完成'));
    if (!status.uploading) break;
  }

  // 6. 填写描述
  await js(`(() => {
    const sr = document.querySelector('wujie-app')?.shadowRoot;
    const editor = sr?.querySelector('.input-editor');
    if (!editor) return 'no editor';
    editor.focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
    document.execCommand('insertText', false, '你的描述 #话题');
    return 'desc: ' + editor.textContent.trim().slice(0, 40);
  })()`);

  // 7. 点击发表按钮
  await js(`(() => {
    const sr = document.querySelector('wujie-app')?.shadowRoot;
    const btns = sr?.querySelectorAll('.weui-desktop-btn_primary');
    for (const btn of btns) {
      if (btn.textContent?.trim() === '发表' && !btn.disabled) {
        btn.click();
        return 'clicked 发表';
      }
    }
    return 'no publish btn';
  })()`);

  await wait(5);

  // 8. 验证发布（URL 应跳转到 /platform/post/list）
  const url = await js('window.location.href');
  const success = url.includes('/platform/post/list');
  cliLog(success ? '✅ 发布成功' : '⚠️ 请检查');
})();
EOF
```

---

## 关键 DOM 选择器（Shadow DOM 内）

> ⚠️ 所有选择器都需要通过 `wujie-app.shadowRoot` 访问，不能直接用 `document.querySelector`

| 元素 | 选择器 | 说明 |
|---|---|---|
| 文件上传 input | `input[type="file"]` | accept: video/mp4，隐藏在 `.ant-upload-drag` 内 |
| 上传拖拽区 | `.ant-upload-drag` | Ant Design 上传组件 |
| 上传按钮 | `.ant-upload-btn` | 点击触发 file input |
| 描述输入框 | `.input-editor` | contenteditable DIV |
| 发表按钮 | `.weui-desktop-btn_primary` | 文字为"发表" |
| 保存草稿按钮 | `.weui-desktop-btn_default` | 文字为"保存草稿" |
| 表单容器 | `.form` | 包含封面预览、描述等 |
| 上传区域 | `.upload` | 上传前 display:block，上传后 display:none |

---

## 上传状态检测

上传开始后，`.upload` 区域变为 `display: none`，`.form` 区域显示"文件上传中，请等待完成后再编辑"。

```js
// 检测上传是否完成
const status = await js(`(() => {
  const sr = document.querySelector('wujie-app')?.shadowRoot;
  const form = sr?.querySelector('.form');
  const text = form?.textContent?.trim() || '';
  return {
    uploading: text.includes('文件上传中'),
    uploadDone: !text.includes('文件上传中')
  };
})()`);
```

上传完成后，form 文字变为"封面预览编辑个人主页卡片..."，表示可以编辑和发布了。

视频发布后状态为"处理中 - 将在处理完后发布"，即视频号会在转码完成后自动发布。

---

## ❌ 不可用的方法

| 方法 | 原因 |
|---|---|
| `uploadFile(selector, path)` | 找不到 shadow DOM 内的 input |
| `DOM.setFileInputFiles` + dispatchEvent | React 事件不跨越 shadow DOM 边界 |
| `DOM.setFileInputFiles` 单独使用 | 文件被设置但 Ant Design 不触发上传 |
| `Page.setInterceptFileChooserDialog` | `drainEvents()` 不捕获 CDP 域事件 |

---

## 注意事项

1. **微信扫码登录**：视频号必须用微信扫码，无法账号密码登录
2. **Wujie 加载延迟**：页面打开后 wujie-app 需要几秒加载，需轮询等待
3. **描述字数**：视频号描述无严格字数限制，但建议简洁
4. **自动发布**：上传完成后点"发表"，视频进入"处理中"状态，转码完成后自动发布
5. **审核**：视频号内容审核较严格，确保内容合规

# 小红书 ego-browser 故障排查

## 1. 话题候选不出来，卡在 `#tag` 文本

- 小红书话题候选依赖联想接口，网络抖动/无匹配时等不到 `#creator-editor-topic-container`。
- 等不到就退格清掉已键入的 `#tag`，跳过该标签继续，不要死等。
- 话题总数硬上限 10 个，超过会死循环卡住发布。

## 2. 视频上传完判断不到

- 预览区 `.preview-new` 文案以「上传成功/分辨率/重新上传/编辑封面/已上传/已选择/100%」任一为准。
- 实在等不到，标题框 `input[placeholder*="填写标题"]` 出现也算进入编辑态，可继续。

## 3. 标题字数超限

- 小红书标题最多 20 字，发布前 `TITLE.slice(0, 20)`。

## 4. 点「发布」没跳 success 页

- 用 `captureScreenshot()` 看是否有弹窗/原创声明没勾。
- 定时发布要点「定时发布」按钮而不是「发布」。

## 5. 被踢回登录页

- ego-browser profile 登录态过期。跑登录 handoff 重新扫码。注意登录页默认是短信登录，要点 `img.css-wemwzq` 切到「扫一扫」。

## 6. 封面弹窗打不开

- 确认 `cover-plugin-title`「设置封面」存在；小红书改版时封面入口结构会变，用 `snapshotText()` 找当前入口 ref。

## 7. 任务空间残留

- 结束务必 `completeTaskSpace(id, { keep: false })`；残留用 `listTaskSpaces` + `claimTaskSpace` 清理。

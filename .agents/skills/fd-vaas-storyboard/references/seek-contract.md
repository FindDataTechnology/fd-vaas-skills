# Seek 契约参考——场景模板片段

`render_video(storyboard=...)` 的每个场景都是一段时间轴,渲染器逐帧调用 `window.seek(t)` 重放画面。本文给出四种 kind 的可抄模板。契约五条(违反即翻车):

1. 页面声明 `window.__DURATION__`(本场景秒数)与 `window.__SIZE__=[w,h]`。
2. 实现 `window.seek(t)`,画面状态是 t 的**纯函数**(无随机数 / 时钟 / 网络 / CSS animation / rAF)。
3. 顶层 `<div data-stage>` 为截图区域:w×h、`overflow:hidden`。
4. 无外链:CSS / JS 内联,位图只能 `data:` URI(`about:blank` origin 取不到 file:// 与相对资源;kenburns 的 images 由服务端自动内联,html_full 要自己转)。
5. 脚本末尾 `window.seek(0)` 摆好首帧。

---

## html_intro / html_outro(内置版式)

服务端内置版式,只需给字段,不用写 HTML:

```json
{"kind": "html_intro", "duration_s": 4, "title": "主标题", "sub": "副标题"}
{"kind": "html_outro", "duration_s": 3, "title": "关注看更多", "sub": "点赞 · 收藏 · 转发"}
```

内置行为(想复刻到 html_full 时照此实现):

- 底色:深蓝渐变 `linear-gradient(160deg,#070a20,#141a4d 60%,#3b2a8f)`,白字,中文字体栈 PingFang SC / Noto Sans CJK SC 优先。
- `title`:随进度 `p = t/DURATION` 淡入(`opacity=p`)并从下方 30px 上移(`translateY((1-p)*30px)`)。
- `sub`:延迟 25% 淡入(`opacity=(p-0.25)/0.75`,钳到 0)。
- `css` 字段可整体覆盖底色样式(传完整 CSS 声明串)。

## html_full(完全自定义一屏)

```json
{"kind": "html_full", "duration_s": 5, "html": "<!DOCTYPE html>…(下面骨架)"}
```

骨架(数字进度条示例——纯函数式动画的标范):

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script>window.__DURATION__=5;window.__SIZE__=[1080,1920];</script>
<style>
  html,body{margin:0;padding:0;background:#070a20}
  [data-stage]{position:relative;width:1080px;height:1920px;overflow:hidden;
               color:#fff;font-family:'PingFang SC','Noto Sans CJK SC',sans-serif}
  .num{position:absolute;left:0;right:0;top:42%;text-align:center;
       font-size:160px;font-weight:800;letter-spacing:2px}
  .bar{position:absolute;left:10%;right:10%;top:60%;height:14px;
       border-radius:7px;background:rgba(255,255,255,.15)}
  .bar>i{display:block;height:100%;border-radius:7px;background:#4f7cff;width:0}
  .cap{position:absolute;left:0;right:0;top:68%;text-align:center;font-size:36px;opacity:.8}
</style></head>
<body><div data-stage>
  <div class="num" id="num">0%</div>
  <div class="bar"><i id="fill"></i></div>
  <div class="cap">营收同比增速</div>
</div>
<script>
  const D = window.__DURATION__;
  const num = document.getElementById('num');
  const fill = document.getElementById('fill');
  const clamp = (v,a,b)=>Math.min(b,Math.max(a,v));
  const ease = p => 1 - Math.pow(1 - p, 3);          // 缓动也是纯函数
  window.seek = function(t){
    const p = ease(clamp(t / D, 0, 1));
    num.textContent = Math.round(p * 34) + '%';      // 34% = 目标数值
    fill.style.width = (p * 100) + '%';
  };
  window.seek(0);
</script></body></html>
```

往 html_full 里放位图:先读文件转 base64(`data:image/png;base64,…`),直接写进 `<img src>` 或 CSS background。**不要**引用文件路径或 URL。

## kenburns(图片缓推缓拉)

不用写 HTML,给字段:

```json
{"kind": "kenburns", "duration_s": 9,
 "images": ["/abs/p1.png", "/abs/p2.png", "/abs/p3.png"],
 "caption": "三张图各 3 秒,均分场景时长",
 "motion": "zoom_in"}
```

行为要点:

- `images`:宿主机文件路径数组(相对 / 绝对均可),**必须存在**——渲染前统一校验,缺失会在一条报错里逐个列出。
- 多图**均分** `duration_s`,逐张切换;`caption` 在每段前 1/4 淡入,白色大字带投影,置于左下 6%。
- `motion`:`pan_down`(默认,下移 + 微放大)/ `zoom_in`(放大 1→1.08)/ `pan_right`(右移,恒定 1.06 倍)。
- 图片由服务端自动转 data: URI 内联——调用方只管给路径。

## chart → kenburns 完整示例(数据 → 视频)

```text
# 第一步:数据 → 图表静帧(品牌主题自动注入,勿在 option 里手配默认色)
render_still(kind="chart", spec={
  "echarts_option": {
    "xAxis": {"type":"category","data":["7月","8月","9月"]},
    "yAxis": {"type":"value"},
    "series": [{"type":"bar","data":[820,932,1201]}]
  },
  "size": {"width":1080,"height":1920}
})
# 返回 file_path: "chart/chart-3f9a…/chart-3f9a….png"
# 绝对路径 = <VAAS_ROOT>/downloads/chart/chart-3f9a…/chart-3f9a….png

# 第二步:静帧 → kenburns 场景(绝对路径喂 images)
render_video(storyboard={
  "size": [1080, 1920],
  "scenes": [
    {"kind":"html_intro","duration_s":3,"title":"9 月经营速览","sub":"三个数字"},
    {"kind":"kenburns","duration_s":6,
     "images":["<VAAS_ROOT>/downloads/chart/chart-3f9a…/chart-3f9a….png"],
     "caption":"三季度营收逐月加速","motion":"zoom_in"},
    {"kind":"html_outro","duration_s":3,"title":"关注看更多","sub":""}
  ]
})
```

size 对齐口诀:**图表 size == storyboard.size**,否则竖屏画幅里横版图会留黑边。

## 排片速查

- 场景 `duration_s` 总和 = 视频时长;有配音时音频时长必须 ≥ 视频时长(`-shortest` 裁短边)。
- `fps` 默认 30;`format` 默认 mp4;`slug` 缺省按内容哈希派生(同 storyboard 幂等重放)。
- 产物目录保留 `storyboard.json`(真相源),PNG 帧不保留。

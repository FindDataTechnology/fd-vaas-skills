"""卡片底座的共享视觉常量（四族 builder 共用，改一处全族生效）。

为什么单独放一份：
- 底座渐变 + 品牌家具此前在 news-flash / listicle / kinetic-quote / data-viz
  各抄一遍，改一次要改四处，已经在「家具被不透明底座盖住」这件事上踩过坑
  （家具在 DOM 里先于 .stage-bg，必须靠 z-index 抬层，四族都要一致）。
- 底色的明度直接决定成片观感：brand.bg=#0a0e14 单色铺满时整帧 YAVG≈38，
  肉眼就是「一片黑」。这里用品牌色做两处柔光 + surface 提亮的竖向渐变，
  把底子抬起来，但仍然是品牌深色系（不引入新色值）。

使用约定：
- 背景规则用 ``background:{BASE_BG}``，元素类名各族自定（.stage-bg / .dv-bg /
  .kq-bg 都行），定位与 z-index 分层由各族 CSS 自己写（底 0 < 家具 1 < 内容 2）。
- 家具用 ``FURNITURE_HTML``，它必须与 ``position:absolute;z-index:1`` 的
  .furn-* 规则配套；ghost 序号另加 ``ghost_html()``。
"""

# 底座渐变：左上强调色柔光 + 右下第二色柔光 + 竖向 surface 提亮。
# 三处 color-mix 都基于品牌变量，brand 改了这里自动跟随。
BASE_BG = (
    "radial-gradient(120% 80% at 12% 0%,"
    "color-mix(in srgb,var(--vaas-accent) 34%,transparent) 0%,transparent 58%),"
    "radial-gradient(90% 60% at 100% 100%,"
    "color-mix(in srgb,var(--vaas-palette-2) 16%,transparent) 0%,transparent 62%),"
    "linear-gradient(160deg,var(--vaas-bg1) 0%,"
    "color-mix(in srgb,var(--vaas-surface) 55%,var(--vaas-bg1)) 52%,"
    "var(--vaas-surface) 100%)"
)

# 家具基础三件：左侧强调竖条 + 底部品牌带 + 品牌落款（样式见各族 CSS）
FURNITURE_HTML = ('<div class="furn-side"></div>'
                  '<div class="furn-band"></div>'
                  '<div class="furn-mark">寻数 · 萬星</div>')


def ghost_html(text: str) -> str:
    """背景巨型半透明序号（填充画幅空白的一层家具）。"""
    from html import escape

    return f'<div class="furn-idx">{escape(str(text))}</div>' if text else ""


# 家具 + 巨引号（kinetic-quote 用，引号是它的语义符号）
def quote_html(chr_: str = "\u201c") -> str:
    from html import escape

    return f'<div class="furn-q">{escape(chr_)}</div>'

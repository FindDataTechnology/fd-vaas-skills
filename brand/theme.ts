// Shared design system for the FindDataOfficial introduce videos.
// Dark "developer" aesthetic, GitHub-dark inspired palette.

export const COLORS = {
  bg0: "#0a0e14",
  bg1: "#0d1117",
  surface: "#161b22",
  surface2: "#1c2330",
  border: "#30363d",
  text: "#e6edf3",
  muted: "#8b949e",
  dim: "#6e7681",
  green: "#3fb950",
  greenDim: "#238636",
  blue: "#58a6ff",
  purple: "#bc8cff",
  orange: "#d29922",
  red: "#f85149",
  cyan: "#39c5cf",
  // 兼容字段：部分场景用了这些别名，补上避免 undefined（文字回退黑色、背景失效）
  bg: "#0d1117",
  bgDark: "#0a1628",
  textMuted: "#94a3b8", // 深色背景上可读的浅灰
};

// System fonts only (no network fetch) -> robust against the env's proxy/TLS issues.
// PingFang SC is present on macOS; Noto/Microsoft YaHei as fallbacks for portability.
export const FONT_SANS =
  "'PingFang SC','Noto Sans SC','Microsoft YaHei','Helvetica Neue',sans-serif";
export const FONT_MONO =
  "'SF Mono','Menlo','JetBrains Mono','Consolas','Courier New',monospace";

// Easing curves (cubic-bezier control points) used with Easing.bezier(...).
export const EASE_OUT = [0.16, 1, 0.3, 1] as const;
export const EASE_INOUT = [0.65, 0, 0.35, 1] as const;

// Composition dimensions / fps shared by all three videos.
export const VIDEO = { width: 1920, height: 1080, fps: 30 } as const;

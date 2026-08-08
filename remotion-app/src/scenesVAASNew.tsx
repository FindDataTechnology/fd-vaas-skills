import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig, interpolate, Sequence } from "remotion";
import { COLORS } from "./theme";

// ============================================================
// 1. Architecture - 架构图展示
// ============================================================
export const ArchitectureVAAS: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const layers = [
    { name: "自然语言输入", color: COLORS.blue, y: 120 },
    { name: "Claude Code / Agent Runtime", color: "#8b5cf6", y: 240 },
    { name: "fd-vaas-* 技能层", color: "#06b6d4", y: 360 },
    { name: "Remotion 渲染引擎", color: "#3fb950", y: 480 },
    { name: "分发到 15 个平台", color: "#f59e0b", y: 600 },
  ];

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(180deg, #0a1628 0%, ${COLORS.bgDark} 100%)`,
        padding: 60,
      }}
    >
      <h2
        style={{
          fontSize: 48,
          fontWeight: 700,
          color: "white",
          margin: "0 0 50px 0",
        }}
      >
        VAAS 技术架构
      </h2>

      <div style={{ width: "100%", maxWidth: 1000 }}>
        {layers.map((layer, i) => {
          const delay = i * 12;
          const progress = spring({
            frame: frame - delay,
            fps,
            from: 0,
            to: 1,
            config: { damping: 14 },
          });
          return (
            <div key={layer.name} style={{ marginBottom: 24 }}>
              <div
                style={{
                  height: 72,
                  width: `${progress * 100}%`,
                  background: `linear-gradient(90deg, ${layer.color}dd, ${layer.color}99)`,
                  borderRadius: 10,
                  display: "flex",
                  alignItems: "center",
                  paddingLeft: 28,
                  fontSize: 24,
                  fontWeight: 600,
                  color: "white",
                  boxShadow: `0 4px 20px ${layer.color}40`,
                }}
              >
                {layer.name}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ============================================================
// 2. BrowserDemo - 模拟浏览器操作演示
// ============================================================
export const BrowserDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const windowIn = spring({ frame, fps, from: 0, to: 1, config: { damping: 14 } });
  const contentIn = spring({ frame: frame - 30, fps, from: 0, to: 1, config: { damping: 14 } });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(225deg, #0c1a2e 0%, ${COLORS.bgDark} 100%)`,
      }}
    >
      <h2
        style={{
          fontSize: 44,
          fontWeight: 700,
          color: "white",
          margin: "0 0 30px 0",
          opacity: windowIn,
        }}
      >
        ego-browser 自动化演示
      </h2>

      {/* 浏览器窗口 */}
      <div
        style={{
          width: 1000,
          background: "#1e1e2e",
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 25px 80px rgba(0,0,0,0.5)",
          opacity: windowIn,
          transform: `scale(${0.9 + windowIn * 0.1})`,
        }}
      >
        {/* 标题栏 */}
        <div
          style={{
            padding: "14px 18px",
            background: "#2d2d3f",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#ff5f56" }} />
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#ffbd2e" }} />
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#27ca40" }} />
          <div
            style={{
              marginLeft: 16,
              flex: 1,
              height: 32,
              background: "#3d3d5c",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              padding: "0 14px",
              fontSize: 16,
              color: "#94a3b8",
              fontFamily: "monospace",
            }}
          >
            🔒 example.com/upload
          </div>
        </div>

        {/* 内容区 */}
        <div style={{ padding: 36, minHeight: 380 }}>
          <div style={{ opacity: contentIn, transform: `translateY(${(1 - contentIn) * 20}px)` }}>
            {/* 上传卡片 */}
            <div
              style={{
                padding: 28,
                background: "#2a2a3e",
                borderRadius: 12,
                marginBottom: 22,
                border: "2px dashed #3b82f6",
              }}
            >
              <div style={{ fontSize: 20, color: "white", fontWeight: 600, marginBottom: 10 }}>
                📹 视频上传中...
              </div>
              <div style={{ fontSize: 18, color: COLORS.textMuted }}>
                my-video.mp4
              </div>
              <div
                style={{
                  marginTop: 18,
                  height: 10,
                  background: "#3d3d5c",
                  borderRadius: 5,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.min(frame / 2, 100)}%`,
                    height: "100%",
                    background: "linear-gradient(90deg, #3b82f6, #8b5cf6)",
                    transition: "width 0.1s",
                  }}
                />
              </div>
            </div>

            {/* 表单填写 */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
              <div
                style={{
                  padding: 20,
                  background: "#2a2a3e",
                  borderRadius: 8,
                  fontSize: 18,
                  color: "white",
                }}
              >
                🏷️ 标题已填写
              </div>
              <div
                style={{
                  padding: 20,
                  background: "#2a2a3e",
                  borderRadius: 8,
                  fontSize: 18,
                  color: "white",
                }}
              >
                ✅ 标签已添加
              </div>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================
// 3. ComparisonTable - Windows vs Mac 对比
// ============================================================
export const ComparisonTable: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const features = [
    { feature: "自动化浏览器", mac: "ego-browser", win: "patchright" },
    { feature: "登录态复用", mac: "✅ Chrome 继承", win: "✅ Profile 持久化" },
    { feature: "Cookie 管理", mac: "✅ 无需手动", win: "✅ 自动管理" },
    { feature: "后台运行", mac: "⚠️ 需窗口", win: "✅ 完全无头" },
    { feature: "发布平台数", mac: "15 个", win: "15 个" },
  ];

  const tableIn = spring({ frame, fps, from: 0, to: 1, config: { damping: 14 } });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(135deg, #0a1628 0%, #0f172a 100%)`,
        padding: 60,
      }}
    >
      <h2
        style={{
          fontSize: 48,
          fontWeight: 700,
          color: "white",
          margin: "0 0 40px 0",
          opacity: tableIn,
        }}
      >
        Windows vs Mac 发布对比
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr",
          gap: 2,
          background: "#ffffff15",
          borderRadius: 12,
          overflow: "hidden",
          opacity: tableIn,
          transform: `scale(${0.95 + tableIn * 0.05})`,
          width: "100%",
          maxWidth: 1200,
        }}
      >
        {/* 表头 */}
        <div style={{ padding: "20px 24px", background: "#ffffff20", fontSize: 22, fontWeight: 700, color: "white" }}>
          特性
        </div>
        <div style={{ padding: "20px 24px", background: "#3b82f640", fontSize: 22, fontWeight: 700, color: "white", textAlign: "center" }}>
          🍎 Mac
        </div>
        <div style={{ padding: "20px 24px", background: "#06b6d440", fontSize: 22, fontWeight: 700, color: "white", textAlign: "center" }}>
          🪟 Windows
        </div>

        {/* 内容行 */}
        {features.map((row, i) => {
          const rowIn = spring({
            frame: frame - i * 15,
            fps,
            from: 0,
            to: 1,
            config: { damping: 14 },
          });
          return (
            <>
              <div
                style={{
                  padding: "18px 24px",
                  background: i % 2 === 0 ? "#ffffff08" : "transparent",
                  fontSize: 20,
                  color: "white",
                  opacity: rowIn,
                  transform: `translateX(${(1 - rowIn) * 30}px)`,
                }}
              >
                {row.feature}
              </div>
              <div
                style={{
                  padding: "18px 24px",
                  background: i % 2 === 0 ? "#3b82f615" : "transparent",
                  fontSize: 20,
                  color: "white",
                  textAlign: "center",
                  opacity: rowIn,
                }}
              >
                {row.mac}
              </div>
              <div
                style={{
                  padding: "18px 24px",
                  background: i % 2 === 0 ? "#06b6d415" : "transparent",
                  fontSize: 20,
                  color: "white",
                  textAlign: "center",
                  opacity: rowIn,
                }}
              >
                {row.win}
              </div>
            </>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ============================================================
// 4. CodeBlock - 代码块演示（地址已修正；平台名改泛称占位）
// ============================================================
export const CodeBlockVAAS: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const windowIn = spring({ frame, fps, from: 0, to: 1, config: { damping: 14 } });
  const typeProgress = Math.min((frame - 30) / 2, 100);

  const codeLines = [
    "# 一键安装 VAAS",
    "curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-vaas-skills/main/install.sh | bash",
    "",
    "# 创建视频任务",
    "node scripts/new-task.mjs --slug my-video --script script.txt",
    "",
    "# 一键渲染 + 发布",
    "node scripts/task-render.mjs --slug my-video",
    "node scripts/publish.mjs --slug my-video --platforms platform1,platform2",
  ];

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(180deg, #0d1117 0%, #0a1628 100%)`,
      }}
    >
      <h2
        style={{
          fontSize: 44,
          fontWeight: 700,
          color: "white",
          margin: "0 0 36px 0",
          opacity: windowIn,
        }}
      >
        三行命令完成全流程
      </h2>

      {/* 终端窗口 */}
      <div
        style={{
          width: 1200,
          background: "#161b22",
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 25px 80px rgba(0,0,0,0.5)",
          border: "1px solid #30363d",
          opacity: windowIn,
        }}
      >
        {/* 标题栏 */}
        <div
          style={{
            padding: "12px 18px",
            background: "#21262d",
            display: "flex",
            alignItems: "center",
            gap: 8,
            borderBottom: "1px solid #30363d",
          }}
        >
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#ff5f56" }} />
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#ffbd2e" }} />
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#27ca40" }} />
          <span style={{ marginLeft: 16, color: "#8b949e", fontSize: 16 }}>Terminal - VAAS</span>
        </div>

        {/* 代码内容 */}
        <div style={{ padding: "36px 32px", fontFamily: "'SF Mono', 'Menlo', monospace" }}>
          {codeLines.map((line, i) => {
            const lineVisible = (typeProgress - i * 8) / 8;
            const isComment = line.startsWith("#") || line === "";
            const isCmd = line.startsWith("curl") || line.startsWith("node");

            return (
              <div
                key={i}
                style={{
                  fontSize: 22,
                  lineHeight: 1.8,
                  color: lineVisible >= 0 ? (isComment ? "#8b949e" : isCmd ? "#79c0ff" : "#c9d1d9") : "transparent",
                  opacity: lineVisible >= 0 ? 1 : 0,
                  whiteSpace: "pre",
                }}
              >
                {line.startsWith("#") ? "$ " : ""}{line}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================
// 5. FeatureGrid - 功能特性网格
// ============================================================
export const FeatureGrid: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const features = [
    { icon: "🎤", title: "AI 配音", desc: "豆包 TTS，10+ 音色" },
    { icon: "📝", title: "逐字字幕", desc: "时间戳精确对齐" },
    { icon: "🎬", title: "Remotion 渲染", desc: "专业级动画效果" },
    { icon: "🌐", title: "15 个平台", desc: "一键全网分发" },
    { icon: "💬", title: "自然语言", desc: "说话就能操作" },
    { icon: "🔄", title: "登录态复用", desc: "无需 Cookie 文件" },
  ];

  const gridIn = spring({ frame, fps, from: 0, to: 1, config: { damping: 14 } });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(225deg, #0a1628 0%, #0f172a 100%)`,
        padding: 60,
      }}
    >
      <h2
        style={{
          fontSize: 48,
          fontWeight: 700,
          color: "white",
          margin: "0 0 50px 0",
          opacity: gridIn,
        }}
      >
        核心功能特性
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 24,
          maxWidth: 1300,
          width: "100%",
          opacity: gridIn,
        }}
      >
        {features.map((f, i) => {
          const cardIn = spring({
            frame: frame - i * 10,
            fps,
            from: 0,
            to: 1,
            config: { damping: 14 },
          });
          return (
            <div
              key={f.title}
              style={{
                padding: "32px 28px",
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 16,
                textAlign: "center",
                opacity: cardIn,
                transform: `translateY(${(1 - cardIn) * 30}px) scale(${0.95 + cardIn * 0.05})`,
              }}
            >
              <div style={{ fontSize: 48, marginBottom: 14 }}>{f.icon}</div>
              <div style={{ fontSize: 26, fontWeight: 700, color: "white", marginBottom: 10 }}>
                {f.title}
              </div>
              <div style={{ fontSize: 20, color: COLORS.textMuted }}>{f.desc}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

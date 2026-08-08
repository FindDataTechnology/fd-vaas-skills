import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import { COLORS, FONT_SANS, VIDEO } from "./theme";
import React, { useEffect, useState } from "react";

type CostRevolutionProps = {
  audioSrc: string;
  captionsSrc: string;
  durationInFrames: number;
  subtitleColor?: string;
  subtitleSize?: number;
};

const SceneBackground: React.FC<{ accent?: string }> = ({ accent = COLORS.green }) => {
  return (
    <>
      <AbsoluteFill style={{ background: `linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)` }} />
      <AbsoluteFill
        style={{
          backgroundImage: `
            radial-gradient(circle at 20% 80%, rgba(${accent.replace("#", "")}, 0.15) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(${accent.replace("#", "")}, 0.1) 0%, transparent 50%)
          `,
        }}
      />
    </>
  );
};

// Hook 场景
const HookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 60, 120], [0, 1, 1], { extrapolateRightTransition: Easing.out(Easing.exp) });
  const translateY = interpolate(frame, [0, 60, 120], [100, 0, 0], { extrapolateRightTransition: Easing.out(Easing.exp) });

  return (
    <AbsoluteFill style={{ display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT_SANS }}>
      <div style={{ opacity, transform: `translateY(${translateY}px)` }}>
        <h1 style={{ fontSize: 80, fontWeight: 800, color: "#ffffff", textAlign: "center", marginBottom: 40, lineHeight: 1.2 }}>
          同样的软件开发
        </h1>
        <h1 style={{ fontSize: 70, fontWeight: 600, color: COLORS.green, textAlign: "center", marginBottom: 30 }}>
          为什么利润结构完全不同？
        </h1>
        <p style={{ fontSize: 42, color: "#94a3b8", textAlign: "center" }}>
          今天讲清楚三种成本曲线和正确演进路径
        </p>
      </div>
    </AbsoluteFill>
  );
};

// 抛物线成本图（字幕放在下方空白处）
const ParabolicCostChart: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0f172a" }}>
      <svg viewBox="0 0 1920 1080" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}>
        {/* 标题区 */}
        <text x="60" y="80" fill="#ffffff" fontSize="50" fontWeight="700">第一条曲线 · 传统 SaaS</text>

        {/* 坐标轴 */}
        <line x1="150" y1="150" x2="150" y2="850" stroke="#64748b" strokeWidth="3" />
        <line x1="150" y1="850" x2="1770" y2="850" stroke="#64748b" strokeWidth="3" />
        {[300, 450, 600, 750].map((y) => (
          <line key={y} x1="150" y1={y} x2="1770" y2={y} stroke="#334155" strokeWidth="1" strokeDasharray="8,8" />
        ))}

        {/* 成本曲线 */}
        <path d="M 150 200 Q 500 300, 900 550 T 1770 780" fill="none" stroke="#ef4444" strokeWidth="6" strokeLinecap="round" />
        <defs>
          <linearGradient id="grad1" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style={{ stopColor: "#ef4444", stopOpacity: 0.3 }} />
            <stop offset="100%" style={{ stopColor: "#ef4444", stopOpacity: 0 }} />
          </linearGradient>
        </defs>
        <path d="M 150 200 Q 500 300, 900 550 T 1770 780 L 1770 850 L 150 850 Z" fill="url(#grad1)" />

        {/* 标签 */}
        <text x="180" y="180" fill="#ef4444" fontSize="32" fontWeight="600">初始开发成本高</text>
        <text x="1400" y="760" fill="#22c55e" fontSize="32" fontWeight="600">边际成本趋零</text>
        <text x="960" y="920" fill="#94a3b8" fontSize="28" textAnchor="middle">用户数量增长 →</text>
        <rect x="1350" y="120" width="380" height="60" rx="8" fill="rgba(34, 197, 94, 0.2)" stroke="#22c55e" strokeWidth="2" />
        <text x="1540" y="160" fill="#22c55e" fontSize="28" fontWeight="700" textAnchor="middle">规模经济护城河</text>
      </svg>
    </AbsoluteFill>
  );
};

// 折线成本图
const LinearCostChart: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0f172a" }}>
      <svg viewBox="0 0 1920 1080" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}>
        <text x="60" y="80" fill="#ffffff" fontSize="50" fontWeight="700">第二条曲线 · AI 应用</text>
        <line x1="150" y1="150" x2="150" y2="850" stroke="#64748b" strokeWidth="3" />
        <line x1="150" y1="850" x2="1770" y2="850" stroke="#64748b" strokeWidth="3" />
        {[300, 450, 600, 750].map((y) => (
          <line key={y} x1="150" y1={y} x2="1770" y2={y} stroke="#334155" strokeWidth="1" strokeDasharray="8,8" />
        ))}
        <path d="M 150 780 L 500 750 L 800 680 L 1100 550 L 1400 350 L 1770 180" fill="none" stroke="#fbbf24" strokeWidth="6" strokeLinecap="round" />
        <defs>
          <linearGradient id="grad2" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" style={{ stopColor: "#fbbf24", stopOpacity: 0 }} />
            <stop offset="100%" style={{ stopColor: "#fbbf24", stopOpacity: 0.3 }} />
          </linearGradient>
        </defs>
        <path d="M 150 780 L 500 750 L 800 680 L 1100 550 L 1400 350 L 1770 180 L 1770 850 L 150 850 Z" fill="url(#grad2)" />
        <text x="180" y="760" fill="#22c55e" fontSize="32" fontWeight="600">初期成本低</text>
        <text x="1400" y="200" fill="#ef4444" fontSize="32" fontWeight="700">Token 成本刚性支出</text>
        <text x="960" y="920" fill="#94a3b8" fontSize="28" textAnchor="middle">用户数量增长 →</text>
        <rect x="200" y="120" width="450" height="60" rx="8" fill="rgba(239, 68, 68, 0.2)" stroke="#ef4444" strokeWidth="2" />
        <text x="425" y="160" fill="#ef4444" fontSize="28" fontWeight="700" textAnchor="middle">同质化竞争 → 价格战陷阱</text>
      </svg>
    </AbsoluteFill>
  );
};

// 演进路径图
const EvolutionPath: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0f172a" }}>
      <svg viewBox="0 0 1920 1080" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}>
        <text x="60" y="80" fill="#ffffff" fontSize="50" fontWeight="700">正确的演进路径</text>
        <circle cx="300" cy="350" r="120" fill="rgba(59, 130, 246, 0.2)" stroke="#3b82f6" strokeWidth="4" />
        <text x="300" y="340" fill="#60a5fa" fontSize="36" fontWeight="800" textAnchor="middle">第一阶段</text>
        <text x="300" y="380" fill="#ffffff" fontSize="32" fontWeight="700" textAnchor="middle">0-1</text>
        <text x="300" y="420" fill="#94a3b8" fontSize="24" textAnchor="middle">直接用大模型 API</text>
        <text x="300" y="450" fill="#94a3b8" fontSize="24" textAnchor="middle">快速验证 PMF</text>
        <line x1="420" y1="350" x2="580" y2="350" stroke="#64748b" strokeWidth="4" markerEnd="url(#arrow)" />
        <circle cx="750" cy="350" r="120" fill="rgba(34, 197, 94, 0.2)" stroke="#22c55e" strokeWidth="4" />
        <text x="750" y="340" fill="#4ade80" fontSize="36" fontWeight="800" textAnchor="middle">第二阶段</text>
        <text x="750" y="380" fill="#ffffff" fontSize="32" fontWeight="700" textAnchor="middle">1-10</text>
        <text x="750" y="420" fill="#94a3b8" fontSize="24" textAnchor="middle">积累领域数据</text>
        <text x="750" y="450" fill="#94a3b8" fontSize="24" textAnchor="middle">构建数据飞轮</text>
        <line x1="870" y1="350" x2="1030" y2="350" stroke="#64748b" strokeWidth="4" markerEnd="url(#arrow)" />
        <circle cx="1200" cy="350" r="120" fill="rgba(168, 85, 247, 0.2)" stroke="#a855f7" strokeWidth="4" />
        <text x="1200" y="340" fill="#d8b4fe" fontSize="36" fontWeight="800" textAnchor="middle">第三阶段</text>
        <text x="1200" y="380" fill="#ffffff" fontSize="32" fontWeight="700" textAnchor="middle">10-100</text>
        <text x="1200" y="420" fill="#94a3b8" fontSize="24" textAnchor="middle">构建基础设施层</text>
        <text x="1200" y="450" fill="#94a3b8" fontSize="24" textAnchor="middle">形成商业护城河</text>
        <defs>
          <marker id="arrow" markerWidth="20" markerHeight="20" refX="18" refY="6" orient="auto">
            <path d="M0,0 L20,6 L0,12" fill="#64748b" />
          </marker>
        </defs>
      </svg>
    </AbsoluteFill>
  );
};

// 产品矩阵 - 使用绝对定位
const ProductMatrix: React.FC = () => {
  const products = [
    { name: "fd-open-bench", color: "#3b82f6", description: "AI Agent 能力评估标准", detail: "打破商业和 AI 能力的结构隔离" },
    { name: "fd-paas-private", color: "#22c55e", description: "行业定制化智能系统", detail: "类似 Codex + ChatGPT 的私有化部署" },
    { name: "fd-paas-cloud", color: "#22c55e", description: "云原生行业智能平台", detail: "基于成熟框架快速构建" },
    { name: "fd-open-data-mcp", color: "#a855f7", description: "行业数据协议", detail: "让数据像自来水一样流动" },
    { name: "fd-open-data-protocol", color: "#a855f7", description: "开放数据连接标准", detail: "降低接入门槛到近乎零" },
    { name: "fd-vaas-skills", color: "#f59e0b", description: "Agent 友好型产品生成器", detail: "三天做出能被 Agent 调用的产品" },
  ];

  return (
    <AbsoluteFill style={{ backgroundColor: "#0f172a" }}>
      {/* 标题 */}
      <div style={{ position: "absolute", top: 60, left: 60, right: 60 }}>
        <h2 style={{ fontSize: 50, fontWeight: 700, color: "#ffffff", margin: 0 }}>我们的产品矩阵</h2>
      </div>

      {/* 产品卡片网格 - 左中右三列 */}
      <div style={{ position: "absolute", top: 180, left: 40, right: 40, bottom: 250, display: "flex", gap: 30 }}>
        {/* 左列 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 30 }}>
          <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", borderLeft: `6px solid #3b82f6`, borderRadius: 12, padding: 25, boxShadow: `0 8px 32px #3b82f61a` }}>
            <h3 style={{ fontSize: 32, fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>fd-open-bench</h3>
            <p style={{ fontSize: 24, color: "#3b82f6", fontWeight: 600, marginBottom: 10 }}>AI Agent 能力评估标准</p>
            <p style={{ fontSize: 20, color: "#94a3b8", lineHeight: 1.4 }}>打破商业和 AI 能力的结构隔离</p>
          </div>
          <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", borderLeft: `6px solid #22c55e`, borderRadius: 12, padding: 25, boxShadow: `0 8px 32px #22c55e1a` }}>
            <h3 style={{ fontSize: 32, fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>fd-paas-private</h3>
            <p style={{ fontSize: 24, color: "#22c55e", fontWeight: 600, marginBottom: 10 }}>行业定制化智能系统</p>
            <p style={{ fontSize: 20, color: "#94a3b8", lineHeight: 1.4 }}>类似 Codex + ChatGPT 的私有化部署</p>
          </div>
          <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", borderLeft: `6px solid #a855f7`, borderRadius: 12, padding: 25, boxShadow: `0 8px 32px #a855f71a` }}>
            <h3 style={{ fontSize: 32, fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>fd-open-data-mcp</h3>
            <p style={{ fontSize: 24, color: "#a855f7", fontWeight: 600, marginBottom: 10 }}>行业数据协议</p>
            <p style={{ fontSize: 20, color: "#94a3b8", lineHeight: 1.4 }}>让数据像自来水一样流动</p>
          </div>
        </div>

        {/* 中列 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 30 }}>
          <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", borderLeft: `6px solid #22c55e`, borderRadius: 12, padding: 25, boxShadow: `0 8px 32px #22c55e1a` }}>
            <h3 style={{ fontSize: 32, fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>fd-paas-cloud</h3>
            <p style={{ fontSize: 24, color: "#22c55e", fontWeight: 600, marginBottom: 10 }}>云原生行业智能平台</p>
            <p style={{ fontSize: 20, color: "#94a3b8", lineHeight: 1.4 }}>基于成熟框架快速构建</p>
          </div>
          <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", borderLeft: `6px solid #a855f7`, borderRadius: 12, padding: 25, boxShadow: `0 8px 32px #a855f71a` }}>
            <h3 style={{ fontSize: 32, fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>fd-open-data-protocol</h3>
            <p style={{ fontSize: 24, color: "#a855f7", fontWeight: 600, marginBottom: 10 }}>开放数据连接标准</p>
            <p style={{ fontSize: 20, color: "#94a3b8", lineHeight: 1.4 }}>降低接入门槛到近乎零</p>
          </div>
          <div style={{ backgroundColor: "rgba(30, 41, 59, 0.8)", borderLeft: `6px solid #f59e0b`, borderRadius: 12, padding: 25, boxShadow: `0 8px 32px #f59e0b1a` }}>
            <h3 style={{ fontSize: 32, fontWeight: 700, color: "#ffffff", marginBottom: 8 }}>fd-vaas-skills</h3>
            <p style={{ fontSize: 24, color: "#f59e0b", fontWeight: 600, marginBottom: 10 }}>Agent 友好型产品生成器</p>
            <p style={{ fontSize: 20, color: "#94a3b8", lineHeight: 1.4 }}>三天做出能被 Agent 调用的产品</p>
          </div>
        </div>

        {/* 右列留白用于平衡视觉 */}
        <div style={{ flex: 1 }}></div>
      </div>

      {/* 底部宣言 */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(to top, rgba(15, 23, 42, 1) 0%, transparent 100%)",
        }}
      >
        <p style={{ fontSize: 32, color: "#cbd5e1", textAlign: "center", maxWidth: 1600, lineHeight: 1.5 }}>
          不是慈善，这是生态建设。让独立分析师、自由职业者都能拥有和专业机构同等的工具和能力。
        </p>
      </div>
    </AbsoluteFill>
  );
};

// Agent 生态展望
const AgentEcosystem: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0f172a" }}>
      <svg viewBox="0 0 1920 1080" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}>
        <text x="60" y="80" fill="#ffffff" fontSize="50" fontWeight="700">未来：AI Agent 时代的基础设施</text>
        <circle cx="960" cy="400" r="90" fill="rgba(168, 85, 247, 0.3)" stroke="#a855f7" strokeWidth="4" />
        <text x="960" y="395" fill="#d8b4fe" fontSize="34" fontWeight="800" textAnchor="middle">AI Agent</text>
        {[
          { x: 250, y: 200, label: "fd-paas", color: "#22c55e" },
          { x: 1670, y: 200, label: "fd-open-data", color: "#a855f7" },
          { x: 250, y: 600, label: "fd-bench", color: "#3b82f6" },
          { x: 1670, y: 600, label: "fd-vaas", color: "#f59e0b" },
        ].map((item, i) => (
          <g key={i}>
            <line x1="960" y1="400" x2={item.x} y2={item.y} stroke={item.color} strokeWidth="2" strokeDasharray="10,5" />
            <circle cx={item.x} cy={item.y} r="80" fill={`rgba(${item.color.slice(1)}, 0.2)`} stroke={item.color} strokeWidth="3" />
            <text x={item.x} y={item.y + 8} fill="#fff" fontSize="26" fontWeight="700" textAnchor="middle">{item.label}</text>
          </g>
        ))}
        <text x="960" y="920" fill="#64748b" fontSize="38" textAnchor="middle">一次集成，万次调用</text>
      </svg>
    </AbsoluteFill>
  );
};

// CTA 场景
const CTAScene: React.FC = () => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 60, 120], [0.8, 1, 1], { extrapolateRightTransition: Easing.out(Easing.exp) });

  return (
    <AbsoluteFill style={{ display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT_SANS }}>
      <div style={{ transform: `scale(${scale})` }}>
        <h1 style={{ fontSize: 52, fontWeight: 700, color: "#ffffff", textAlign: "center", marginBottom: 30, lineHeight: 1.4 }}>
          成本决定生死，价值决定溢价，生态决定未来
        </h1>
        <h1 style={{ fontSize: 44, fontWeight: 600, color: COLORS.green, textAlign: "center", marginBottom: 40 }}>
          想了解更多实战方法论？
        </h1>
        <div
          style={{
            fontSize: 38,
            color: "#cbd5e1",
            textAlign: "center",
            padding: 25,
            backgroundColor: "rgba(30, 41, 59, 0.7)",
            borderRadius: 16,
            display: "inline-block",
          }}
        >
          关注我，获取更多实战方法论
        </div>
      </div>
    </AbsoluteFill>
  );
};

// Logo 片尾场景
const LogoEndScreen: React.FC = () => {
  return (
    <AbsoluteFill style={{ display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT_SANS, backgroundColor: "#0f172a" }}>
      <div style={{ textAlign: "center" }}>
        <img src={staticFile("logo.png")} alt="寻数科技" style={{ width: 200, marginBottom: 30 }} />
        <h1 style={{ fontSize: 48, fontWeight: 800, color: "#ffffff", marginBottom: 20 }}>寻数科技 FindData Technology</h1>
        <p style={{ fontSize: 28, color: "#94a3b8", marginBottom: 40 }}>探索更开放更公平的 AI 未来</p>
        <div style={{ fontSize: 24, color: "#64748b" }}>开源 · 数据 · AI</div>
      </div>
    </AbsoluteFill>
  );
};

export const CostRevolution: React.FC<CostRevolutionProps> = ({ audioSrc, captionsSrc, durationInFrames, subtitleColor = "#3fb950", subtitleSize = 56 }) => {
  const fps = useVideoConfig().fps;

  // 场景时长分配（总计约 298 秒 = 8944 帧）
  const hookDuration = 12 * fps; // 12 秒 - Hook
  const parabolicDuration = 23 * fps; // 23 秒 - 抛物线图
  const linearDuration = 35 * fps; // 35 秒 - 折线图
  const evolutionDuration = 45 * fps; // 45 秒 - 演进路径
  const productDuration = 50 * fps; // 50 秒 - 产品矩阵
  const agentDuration = 35 * fps; // 35 秒 - Agent 生态
  const ctaDuration = 25 * fps; // 25 秒 - CTA
  const logoDuration = 20 * fps; // 20 秒 - Logo 片尾

  // 字幕组件（按句子分段，标准字幕格式）
  const SubtitleBar: React.FC<{ captionsSrc: string; color: string; size: number; bottom: number }> = ({ captionsSrc, color, size, bottom }) => {
    const frame = useCurrentFrame();
    const { fps: videoFps } = useVideoConfig();
    const [sentences, setSentences] = useState([]);

    useEffect(() => {
      fetch(staticFile(captionsSrc))
        .then((res) => res.json())
        .then((tokens) => {
          // 将 token 按句子分组（遇到标点符号就分段）
          const sentenceGroups = [];
          let currentSentence = { text: "", startMs: tokens[0]?.startMs || 0, endMs: 0 };

          for (const token of tokens) {
            currentSentence.text += token.text;
            currentSentence.endMs = token.endMs;

            // 如果遇到标点符号，结束当前句子
            if (/[，。！？、；：\n]/.test(token.text)) {
              sentenceGroups.push({ ...currentSentence });
              currentSentence = { text: "", startMs: token.endMs, endMs: 0 };
            }
          }

          // 添加最后一个不完整的句子
          if (currentSentence.text) {
            sentenceGroups.push(currentSentence);
          }

          setSentences(sentenceGroups);
        });
    }, [captionsSrc]);

    const currentTimeMs = (frame / videoFps) * 1000;

    // 找到当前时间点对应的句子
    const currentSentence = sentences.find((s) => currentTimeMs >= s.startMs && currentTimeMs < s.endMs);

    if (!currentSentence) return null;

    return (
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none", zIndex: 100 }}>
        <div
          style={{
            position: "absolute",
            bottom: bottom,
            left: 0,
            right: 0,
            padding: "40px 120px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              fontSize: size,
              fontWeight: 800,
              color: "#ffffff",
              whiteSpace: "pre-wrap",
              textAlign: "center",
              lineHeight: 1.4,
              textShadow: "0 2px 8px rgba(0,0,0,0.8), 0 0 4px rgba(0,0,0,0.95)",
            }}
          >
            {currentSentence.text}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", backgroundColor: "#0f172a", fontFamily: FONT_SANS }}>
      <Audio src={staticFile(audioSrc)} />
      <SceneBackground accent={COLORS.green} />

      <Sequence from={0} durationInFrames={hookDuration}><HookScene /></Sequence>
      <Sequence from={hookDuration} durationInFrames={parabolicDuration}><ParabolicCostChart /></Sequence>
      <Sequence from={hookDuration + parabolicDuration} durationInFrames={linearDuration}><LinearCostChart /></Sequence>
      <Sequence from={hookDuration + parabolicDuration + linearDuration} durationInFrames={evolutionDuration}><EvolutionPath /></Sequence>
      <Sequence from={hookDuration + parabolicDuration + linearDuration + evolutionDuration} durationInFrames={productDuration}><ProductMatrix /></Sequence>
      <Sequence from={hookDuration + parabolicDuration + linearDuration + evolutionDuration + productDuration} durationInFrames={agentDuration}><AgentEcosystem /></Sequence>
      <Sequence from={hookDuration + parabolicDuration + linearDuration + evolutionDuration + productDuration + agentDuration} durationInFrames={ctaDuration}><CTAScene /></Sequence>
      <Sequence from={hookDuration + parabolicDuration + linearDuration + evolutionDuration + productDuration + agentDuration + ctaDuration} durationInFrames={logoDuration}><LogoEndScreen /></Sequence>

      {/* 字幕放在最后，确保在最上层 */}
      <SubtitleBar captionsSrc={captionsSrc} color={subtitleColor} size={subtitleSize} bottom={60} />
    </div>
  );
};

import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { useState } from "react";
import { Background, GradientOverlay } from "./ui";
import { COLORS } from "./theme";

// ============================================================
// Hook - 开场介绍
// ============================================================
export const HookVAAS: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleIn = spring({ frame, fps, from: 0, to: 1, config: { damping: 12 } });
  const subtitleIn = spring({ frame: frame - 20, fps, from: 0, to: 1, config: { damping: 12 } });
  const badgeIn = spring({ frame: frame - 40, fps, from: 0, to: 1, config: { damping: 12 } });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(135deg, ${COLORS.bgDark} 0%, #0a1628 100%)`,
      }}
    >
      {/* 科技感网格背景 */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          backgroundImage: `
            linear-gradient(rgba(59, 130, 246, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(59, 130, 246, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: "50px 50px",
        }}
      />

      {/* 寻数科技 Badge */}
      <div
        style={{
          opacity: badgeIn,
          transform: `translateY(${(1 - badgeIn) * 30}px)`,
          marginBottom: 28,
        }}
      >
        <span
          style={{
            padding: "10px 28px",
            background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
            borderRadius: 100,
            fontSize: 22,
            fontWeight: 600,
            color: "white",
            letterSpacing: "0.1em",
          }}
        >
          寻数科技 · 开源项目
        </span>
      </div>

      {/* 主标题 */}
      <h1
        style={{
          fontSize: 88,
          fontWeight: 800,
          color: "white",
          margin: 0,
          opacity: titleIn,
          transform: `translateY(${(1 - titleIn) * 50}px)`,
          letterSpacing: "-0.02em",
        }}
      >
        VAAS
      </h1>

      {/* 副标题 */}
      <p
        style={{
          fontSize: 36,
          color: COLORS.textMuted,
          margin: "16px 0 0 0",
          opacity: subtitleIn,
          transform: `translateY(${(1 - subtitleIn) * 30}px)`,
        }}
      >
        视频自动化分发系统
      </p>
    </AbsoluteFill>
  );
};

// ============================================================
// PlatformGrid - 平台覆盖（泛称两大卡片，不暴露具体平台名以规避限流）
// ============================================================
export const PlatformGrid: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const leftIn = spring({ frame, fps, from: 0, to: 1, config: { damping: 14 } });
  const rightIn = spring({ frame: frame - 20, fps, from: 0, to: 1, config: { damping: 14 } });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(180deg, ${COLORS.bgDark} 0%, #0c1a2e 100%)`,
        padding: 80,
      }}
    >
      <h2
        style={{
          fontSize: 56,
          fontWeight: 700,
          color: "white",
          margin: "0 0 70px 0",
          textAlign: "center",
        }}
      >
        覆盖 15 个平台一键发布
      </h2>

      <div style={{ display: "flex", gap: 60, alignItems: "stretch", width: "100%", maxWidth: 1400 }}>
        {/* 短视频 */}
        <div
          style={{
            flex: 1,
            padding: "56px 60px",
            background: "rgba(59, 130, 246, 0.12)",
            border: "2px solid rgba(59, 130, 246, 0.4)",
            borderRadius: 24,
            textAlign: "center",
            opacity: leftIn,
            transform: `translateY(${(1 - leftIn) * 30}px)`,
          }}
        >
          <div style={{ fontSize: 30, color: COLORS.blue, fontWeight: 600, marginBottom: 20 }}>
            短视频平台
          </div>
          <div style={{ fontSize: 110, fontWeight: 800, color: "white", lineHeight: 1 }}>6</div>
          <div style={{ fontSize: 24, color: COLORS.textMuted, marginTop: 20 }}>
            主流短视频全覆盖
          </div>
        </div>
        {/* 图文与财经 */}
        <div
          style={{
            flex: 1,
            padding: "56px 60px",
            background: "rgba(52, 211, 153, 0.1)",
            border: "2px solid rgba(52, 211, 153, 0.35)",
            borderRadius: 24,
            textAlign: "center",
            opacity: rightIn,
            transform: `translateY(${(1 - rightIn) * 30}px)`,
          }}
        >
          <div style={{ fontSize: 30, color: COLORS.green, fontWeight: 600, marginBottom: 20 }}>
            图文与财经平台
          </div>
          <div style={{ fontSize: 110, fontWeight: 800, color: "white", lineHeight: 1 }}>9</div>
          <div style={{ fontSize: 24, color: COLORS.textMuted, marginTop: 20 }}>
            图文 / 财经资讯全覆盖
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================
// SkillCards - 技能卡片展示
// ============================================================
export const SkillCards: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const skills = [
    {
      name: "fd-vaas-video-creator",
      desc: "文案 -> 配音 + 字幕 + Remotion 渲染",
      color: "#3b82f6",
    },
    {
      name: "fd-vaas-publish-videos",
      desc: "一键发布到 6 个视频平台",
      color: "#8b5cf6",
    },
    {
      name: "fd-vaas-publish-docs",
      desc: "一键发布到 9 个图文平台",
      color: "#10b981",
    },
    {
      name: "fd-vaas-brainstorm",
      desc: "AI 选题 + 口播/图文脚本",
      color: "#f59e0b",
    },
    {
      name: "fd-vaas-dashboard",
      desc: "内容管理仪表盘",
      color: "#ec4899",
    },
    {
      name: "fd-vaas-dashboard-sharing",
      desc: "一键生成公开分享链接",
      color: "#06b6d4",
    },
  ];

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(225deg, #0a1628 0%, ${COLORS.bgDark} 100%)`,
        padding: 60,
      }}
    >
      <h2
        style={{
          fontSize: 52,
          fontWeight: 700,
          color: "white",
          margin: "0 0 50px 0",
        }}
      >
        六大核心技能
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 24,
          width: "100%",
          maxWidth: 1400,
        }}
      >
        {skills.map((skill, i) => {
          const delay = i * 8;
          const inView = spring({
            frame: frame + delay,
            fps,
            from: 0,
            to: 1,
            config: { damping: 14 },
          });
          return (
            <div
              key={skill.name}
              style={{
                padding: "28px 32px",
                background: `${skill.color}15`,
                borderLeft: `5px solid ${skill.color}`,
                borderRadius: 12,
                opacity: inView,
                transform: `translateX(${(1 - inView) * 40}px)`,
              }}
            >
              <div
                style={{
                  fontSize: 26,
                  fontWeight: 700,
                  color: "white",
                  marginBottom: 10,
                  fontFamily: "'SF Mono', monospace",
                }}
              >
                /{skill.name}
              </div>
              <div
                style={{
                  fontSize: 20,
                  color: COLORS.textMuted,
                }}
              >
                {skill.desc}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ============================================================
// DownloadSection - 下载安装（地址已修正为 FindDataTechnology/fd-vaas-skills）
// ============================================================
export const DownloadSection: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleIn = spring({ frame, fps, from: 0, to: 1, config: { damping: 12 } });
  const cmdIn = spring({ frame: frame - 30, fps, from: 0, to: 1, config: { damping: 12 } });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(135deg, #0c1a2e 0%, #0a1628 50%, #0f172a 100%)`,
      }}
    >
      <h2
        style={{
          fontSize: 52,
          fontWeight: 700,
          color: "white",
          margin: "0 0 50px 0",
          opacity: titleIn,
          transform: `translateY(${(1 - titleIn) * 30}px)`,
        }}
      >
        一键下载安装
      </h2>

      {/* 终端模拟 */}
      <div
        style={{
          width: 1300,
          background: "#1a1a2e",
          borderRadius: 16,
          overflow: "hidden",
          boxShadow: "0 25px 80px rgba(0,0,0,0.4)",
          opacity: cmdIn,
          transform: `scale(${0.9 + cmdIn * 0.1})`,
        }}
      >
        {/* 标题栏 */}
        <div
          style={{
            padding: "14px 18px",
            background: "#252542",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div
            style={{ width: 14, height: 14, borderRadius: "50%", background: "#ff5f56" }}
          />
          <div
            style={{ width: 14, height: 14, borderRadius: "50%", background: "#ffbd2e" }}
          />
          <div
            style={{ width: 14, height: 14, borderRadius: "50%", background: "#27ca40" }}
          />
          <span
            style={{
              marginLeft: 14,
              color: "#888",
              fontSize: 16,
              fontFamily: "'SF Mono', monospace",
            }}
          >
            Terminal
          </span>
        </div>
        {/* 命令内容 */}
        <div
          style={{
            padding: "40px 48px",
            fontFamily: "'SF Mono', 'Menlo', monospace",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
            <span style={{ color: COLORS.green, fontSize: 24 }}>$</span>
            <code
              style={{
                color: "#e2e8f0",
                fontSize: 24,
                lineHeight: 1.6,
              }}
            >
              curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-vaas-skills/main/install.sh | bash
            </code>
          </div>
          <div style={{ color: "#94a3b8", fontSize: 20, marginTop: 10 }}>
            # 自动完成：克隆项目 → 安装依赖 → 初始化配置
          </div>
        </div>
      </div>

      <p
        style={{
          marginTop: 40,
          fontSize: 24,
          color: COLORS.textMuted,
          opacity: cmdIn,
        }}
      >
        开源地址：github.com/FindDataTechnology/fd-vaas-skills
      </p>
    </AbsoluteFill>
  );
};

// ============================================================
// CTA - 结尾号召
// ============================================================
export const CTAVAAS: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleIn = spring({ frame, fps, from: 0, to: 1, config: { damping: 12 } });
  const subtitleIn = spring({
    frame: frame - 20,
    fps,
    from: 0,
    to: 1,
    config: { damping: 12 },
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(180deg, #0a1628 0%, ${COLORS.bgDark} 100%)`,
      }}
    >
      {/* 装饰性圆环 */}
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            width: 200 + i * 150,
            height: 200 + i * 150,
            border: `2px solid rgba(59, 130, 246, ${0.15 - i * 0.04})`,
            borderRadius: "50%",
            opacity: 0.5 + Math.sin((frame + i * 20) / 30) * 0.3,
            transform: `scale(${1 + Math.sin((frame + i * 15) / 40) * 0.05})`,
          }}
        />
      ))}

      <h1
        style={{
          fontSize: 72,
          fontWeight: 800,
          color: "white",
          margin: 0,
          opacity: titleIn,
          textAlign: "center",
        }}
      >
        用自然语言说话
      </h1>
      <h1
        style={{
          fontSize: 72,
          fontWeight: 800,
          background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          margin: "8px 0 0 0",
          opacity: titleIn,
        }}
      >
        AI 帮你做视频
      </h1>

      <p
        style={{
          fontSize: 28,
          color: COLORS.textMuted,
          marginTop: 40,
          opacity: subtitleIn,
        }}
      >
        节省 90% 的内容创作时间
      </p>

      <div
        style={{
          marginTop: 60,
          padding: "18px 44px",
          background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
          borderRadius: 12,
          fontSize: 24,
          fontWeight: 600,
          color: "white",
          opacity: subtitleIn,
        }}
      >
        立即开始 · VAAS
      </div>
    </AbsoluteFill>
  );
};

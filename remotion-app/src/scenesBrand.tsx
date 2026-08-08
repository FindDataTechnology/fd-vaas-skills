// Brand 2026 scenes for FindDataTechnology — 7-scene animated brand video.
// Builds on the existing design system (theme.ts + ui.tsx), same visual language
// as scenesOrg.tsx but with all-new content matching the expanded product matrix.
//
// Scene breakdown (local frames, 30fps):
//   0. CoverBrand      ~60f   (2.0s)  — 品牌封面，静音
//   1. HookBrand       ~180f  (6.0s)  — 钩子 + 愿景
//   2. WhyBrand        ~240f  (8.0s)  — 为什么要做（痛点）
//   3. DataLayerBrand  ~420f  (14.0s) — 数据层：open-data-mcp + daas-mcp
//   4. ToolLayerBrand  ~390f  (13.0s) — 工具层：paas-private + paas-cloud
//   5. ContentLayerBrand ~360f (12.0s) — 内容层：vaas-skills + paper-trading + open-bench
//   6. ValueBrand      ~300f  (10.0s) — 价值升华 + 开源理念
//   7. CTABrand        ~270f  (9.0s)  — 结尾 + CTA

import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  spring,
} from "remotion";
import { COLORS, EASE_OUT, FONT_MONO, FONT_SANS } from "./theme";
import {
  Card,
  FadeUp,
  Pill,
  Terminal,
  Typewriter,
  useCountUp,
  fmt,
  CTAItem,
} from "./ui";

// ===========================================================================
// 0. CoverBrand — 品牌封面 (silent, 60f)
// ===========================================================================
export const CoverBrand: React.FC = () => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 30], [0.7, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });
  const opacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        fontFamily: FONT_SANS,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 36,
      }}
    >
      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          fontSize: 220,
          lineHeight: 1,
          color: COLORS.green,
          filter: `drop-shadow(0 0 50px ${COLORS.green}66)`,
        }}
      >
        ⬢
      </div>
      <FadeUp
        delay={18}
        style={{
          fontSize: 88,
          fontWeight: 700,
          color: COLORS.text,
          letterSpacing: "-0.01em",
        }}
      >
        寻数科技
      </FadeUp>
      <FadeUp
        delay={28}
        style={{
          fontFamily: FONT_MONO,
          fontSize: 28,
          color: COLORS.muted,
          letterSpacing: "0.12em",
        }}
      >
        FindDataTechnology
      </FadeUp>
      <FadeUp
        delay={40}
        style={{
          fontSize: 30,
          color: COLORS.green,
          marginTop: 12,
        }}
      >
        让数据驱动决策
      </FadeUp>
    </AbsoluteFill>
  );
};

// ===========================================================================
// 1. HookBrand — 钩子 + 愿景
// ===========================================================================
export const HookBrand: React.FC = () => (
  <AbsoluteFill
    style={{
      fontFamily: FONT_SANS,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 40,
      paddingBottom: 150,
    }}
  >
    <FadeUp
      delay={0}
      style={{
        fontFamily: FONT_MONO,
        fontSize: 24,
        color: COLORS.muted,
        letterSpacing: "0.12em",
      }}
    >
      <span style={{ color: COLORS.red }}>⚠</span> 数据鸿沟 · THE DATA DIVIDE
    </FadeUp>
    <FadeUp
      delay={10}
      style={{
        fontSize: 80,
        fontWeight: 700,
        color: COLORS.text,
        textAlign: "center",
        lineHeight: 1.25,
      }}
    >
      数据，正在成为这个时代
      <br />
      <span style={{ color: COLORS.red }}>最不公平的资源</span>
    </FadeUp>
    <FadeUp
      delay={60}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 20,
        marginTop: 20,
      }}
    >
      <div
        style={{
          width: 60,
          height: 2,
          background: COLORS.green,
        }}
      />
      <span style={{ fontSize: 32, color: COLORS.green }}>
        我们想改变这件事
      </span>
      <div
        style={{
          width: 60,
          height: 2,
          background: COLORS.green,
        }}
      />
    </FadeUp>
  </AbsoluteFill>
);

// ===========================================================================
// 2. WhyBrand — 为什么要做（愿景 + 使命）
// ===========================================================================
export const WhyBrand: React.FC = () => (
  <AbsoluteFill
    style={{
      fontFamily: FONT_SANS,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 50,
      paddingBottom: 150,
      paddingLeft: 100,
      paddingRight: 100,
    }}
  >
    <FadeUp delay={0} style={{ fontSize: 44, fontWeight: 700, color: COLORS.text }}>
      在 AI 时代
    </FadeUp>
    <div
      style={{
        display: "flex",
        gap: 80,
        alignItems: "stretch",
        width: "100%",
        justifyContent: "center",
      }}
    >
      <Card delay={10} accent={COLORS.red} style={{ width: 520, textAlign: "center" }}>
        <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.red }}>
          有人一骑绝尘
        </div>
        <div
          style={{
            fontSize: 24,
            color: COLORS.muted,
            marginTop: 16,
            lineHeight: 1.6,
          }}
        >
          手握海量数据
          <br />
          模型越用越强
        </div>
        <div style={{ fontSize: 60, marginTop: 20 }}>📈</div>
      </Card>
      <Card delay={35} accent={COLORS.blue} style={{ width: 520, textAlign: "center" }}>
        <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.blue }}>
          有人寸步难行
        </div>
        <div
          style={{
            fontSize: 24,
            color: COLORS.muted,
            marginTop: 16,
            lineHeight: 1.6,
          }}
        >
          公开信息找不到、用不起
          <br />
          技术门槛越来越高
        </div>
        <div style={{ fontSize: 60, marginTop: 20 }}>🚧</div>
      </Card>
    </div>
    <FadeUp delay={100} style={{ marginTop: 10 }}>
      <Pill color={COLORS.green}>信息平权 · 机会公平</Pill>
    </FadeUp>
  </AbsoluteFill>
);

// ===========================================================================
// 3. DataLayerBrand — 数据层
// ===========================================================================
export const DataLayerBrand: React.FC = () => {
  const frame = useCurrentFrame();
  const connector1 = interpolate(frame, [40, 80], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });
  const connector2 = interpolate(frame, [70, 110], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });

  return (
    <AbsoluteFill
      style={{
        fontFamily: FONT_SANS,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 44,
        paddingBottom: 150,
      }}
    >
      <FadeUp delay={0}>
        <Pill color={COLORS.purple}>📊 数据层 · DATA LAYER</Pill>
      </FadeUp>
      <FadeUp
        delay={8}
        style={{
          fontSize: 52,
          fontWeight: 700,
          color: COLORS.text,
          textAlign: "center",
        }}
      >
        连接全球主流数据源
      </FadeUp>
      <div style={{ display: "flex", gap: 40, alignItems: "stretch" }}>
        <Card delay={16} accent={COLORS.purple} style={{ width: 520 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
            <span
              style={{
                fontFamily: FONT_MONO,
                fontSize: 28,
                color: COLORS.purple,
                fontWeight: 700,
              }}
            >
              fd-open-data-mcp
            </span>
          </div>
          <div
            style={{
              fontSize: 32,
              fontWeight: 700,
              color: COLORS.text,
              marginTop: 14,
            }}
          >
            对话式访问全球公开数据
          </div>
          <div
            style={{
              fontSize: 22,
              color: COLORS.muted,
              marginTop: 18,
              lineHeight: 1.6,
            }}
          >
            连接 AKShare · World Bank · yfinance · EDGAR
            <br />
            AI Agent 统一调用全球优质数据资源
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 20, flexWrap: "wrap" }}>
            {["AKShare", "World Bank", "yfinance", "EDGAR"].map((tag, i) => (
              <span
                key={i}
                style={{
                  fontSize: 18,
                  padding: "4px 12px",
                  borderRadius: 6,
                  background: `${COLORS.purple}22`,
                  color: COLORS.purple,
                  fontFamily: FONT_MONO,
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        </Card>
        <Card delay={40} accent={COLORS.blue} style={{ width: 520 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
            <span
              style={{
                fontFamily: FONT_MONO,
                fontSize: 28,
                color: COLORS.blue,
                fontWeight: 700,
              }}
            >
              fd-daas-mcp
            </span>
          </div>
          <div
            style={{
              fontSize: 32,
              fontWeight: 700,
              color: COLORS.text,
              marginTop: 14,
            }}
          >
            个人研究分析一站式方案
          </div>
          <div
            style={{
              fontSize: 22,
              color: COLORS.muted,
              marginTop: 18,
              lineHeight: 1.6,
            }}
          >
            股票池筛选 → 指标体系构建
            <br />
            数据看板 → 研究报告生成
            <br />
            实时数据更新 + 通知推送
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
            {["选股", "指标", "看板", "研报"].map((tag, i) => (
              <span
                key={i}
                style={{
                  fontSize: 18,
                  padding: "4px 12px",
                  borderRadius: 6,
                  background: `${COLORS.blue}22`,
                  color: COLORS.blue,
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        </Card>
      </div>
    </AbsoluteFill>
  );
};

// ===========================================================================
// 4. ToolLayerBrand — 工具层
// ===========================================================================
export const ToolLayerBrand: React.FC = () => (
  <AbsoluteFill
    style={{
      fontFamily: FONT_SANS,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 44,
      paddingBottom: 150,
    }}
  >
    <FadeUp delay={0}>
      <Pill color={COLORS.cyan}>🛠️ 工具层 · TOOL LAYER</Pill>
    </FadeUp>
    <FadeUp
      delay={8}
      style={{
        fontSize: 52,
        fontWeight: 700,
        color: COLORS.text,
        textAlign: "center",
      }}
    >
      每个人都能拥有自己的
      <br />
      <span style={{ color: COLORS.cyan }}>AI 工作平台</span>
    </FadeUp>
    <div style={{ display: "flex", gap: 40, alignItems: "stretch" }}>
      <Card delay={16} accent={COLORS.cyan} style={{ width: 520 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <span
            style={{
              fontFamily: FONT_MONO,
              fontSize: 28,
              color: COLORS.cyan,
              fontWeight: 700,
            }}
          >
            fd-paas-private
          </span>
          <span style={{ fontSize: 18, color: COLORS.dim }}>本地版</span>
        </div>
        <div
          style={{
            fontSize: 32,
            fontWeight: 700,
            color: COLORS.text,
            marginTop: 14,
          }}
        >
          面向本地环境的 AI 开发平台
        </div>
        <div
          style={{
            fontSize: 22,
            color: COLORS.muted,
            marginTop: 18,
            lineHeight: 1.6,
          }}
        >
          以 Pi 为核心
          <br />
          集成 LiteLLM · OpenConnector
          <br />
          模型调用 · 工具连接 · 自动化
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
          {["Pi", "LiteLLM", "OpenConnector"].map((tag, i) => (
            <span
              key={i}
              style={{
                fontSize: 18,
                padding: "4px 12px",
                borderRadius: 6,
                background: `${COLORS.cyan}22`,
                color: COLORS.cyan,
                fontFamily: FONT_MONO,
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      </Card>
      <Card delay={40} accent={COLORS.orange} style={{ width: 520 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <span
            style={{
              fontFamily: FONT_MONO,
              fontSize: 28,
              color: COLORS.orange,
              fontWeight: 700,
            }}
          >
            fd-paas-cloud
          </span>
          <span style={{ fontSize: 18, color: COLORS.dim }}>云端版</span>
        </div>
        <div
          style={{
            fontSize: 32,
            fontWeight: 700,
            color: COLORS.text,
            marginTop: 14,
          }}
        >
          云端 AI 助手服务
        </div>
        <div
          style={{
            fontSize: 22,
            color: COLORS.muted,
            marginTop: 18,
            lineHeight: 1.6,
          }}
        >
          以 Pi 为核心
          <br />
          结合 Nango · NewAPI 开源组件
          <br />
          打造 ChatGPT 式智能工作平台
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
          {["Nango", "NewAPI", "ChatGPT 式"].map((tag, i) => (
            <span
              key={i}
              style={{
                fontSize: 18,
                padding: "4px 12px",
                borderRadius: 6,
                background: `${COLORS.orange}22`,
                color: COLORS.orange,
                fontFamily: FONT_MONO,
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      </Card>
    </div>
  </AbsoluteFill>
);

// ===========================================================================
// 5. ContentLayerBrand — 内容层 + open-bench
// ===========================================================================
export const ContentLayerBrand: React.FC = () => (
  <AbsoluteFill
    style={{
      fontFamily: FONT_SANS,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 36,
      paddingBottom: 150,
    }}
  >
    <FadeUp delay={0}>
      <Pill color={COLORS.green}>🎬 内容层 + 评测 · CONTENT & BENCH</Pill>
    </FadeUp>
    <FadeUp
      delay={8}
      style={{
        fontSize: 50,
        fontWeight: 700,
        color: COLORS.text,
        textAlign: "center",
      }}
    >
      AI 帮你做内容、跑策略、评能力
    </FadeUp>
    <div style={{ display: "flex", gap: 28, alignItems: "stretch" }}>
      <Card delay={14} accent={COLORS.green} style={{ width: 380 }}>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 24,
            color: COLORS.green,
            fontWeight: 700,
          }}
        >
          fd-vaas-skills
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, color: COLORS.text, marginTop: 12 }}>
          内容生产与运营
        </div>
        <div
          style={{
            fontSize: 20,
            color: COLORS.muted,
            marginTop: 14,
            lineHeight: 1.6,
          }}
        >
          AI 自动生成口播视频、PPT
          <br />
          多平台一键分发
        </div>
        <div style={{ fontSize: 48, marginTop: 14 }}>🎬</div>
      </Card>
      <Card delay={34} accent={COLORS.orange} style={{ width: 380 }}>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 24,
            color: COLORS.orange,
            fontWeight: 700,
          }}
        >
          fd-paper-trading
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, color: COLORS.text, marginTop: 12 }}>
          模拟交易平台
        </div>
        <div
          style={{
            fontSize: 20,
            color: COLORS.muted,
            marginTop: 14,
            lineHeight: 1.6,
          }}
        >
          基于 NautilusTrader 构建
          <br />
          策略验证 + 能力训练
        </div>
        <div style={{ fontSize: 48, marginTop: 14 }}>📊</div>
      </Card>
      <Card delay={54} accent={COLORS.purple} style={{ width: 380 }}>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 24,
            color: COLORS.purple,
            fontWeight: 700,
          }}
        >
          fd-open-bench
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, color: COLORS.text, marginTop: 12 }}>
          Agent 能力评测
        </div>
        <div
          style={{
            fontSize: 20,
            color: COLORS.muted,
            marginTop: 14,
            lineHeight: 1.6,
          }}
        >
          专业领域真实表现评估
          <br />
          记录 · 评估 · 优化 · 通知
        </div>
        <div style={{ fontSize: 48, marginTop: 14 }}>🏆</div>
      </Card>
    </div>
  </AbsoluteFill>
);

// ===========================================================================
// 6. ValueBrand — 价值升华
// ===========================================================================
export const ValueBrand: React.FC = () => {
  const frame = useCurrentFrame();
  const strike = interpolate(frame, [30, 55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });

  return (
    <AbsoluteFill
      style={{
        fontFamily: FONT_SANS,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 46,
        paddingBottom: 150,
        paddingLeft: 120,
        paddingRight: 120,
      }}
    >
      <FadeUp delay={0}>
        <Pill color={COLORS.green}>开源 · OPEN SOURCE</Pill>
      </FadeUp>
      <FadeUp
        delay={12}
        style={{
          fontSize: 64,
          fontWeight: 700,
          color: COLORS.text,
          textAlign: "center",
          lineHeight: 1.3,
        }}
      >
        开源，不是口号
        <br />
        是我们的<span style={{ color: COLORS.green }}>武器</span>
      </FadeUp>
      <div
        style={{
          display: "flex",
          gap: 60,
          alignItems: "center",
          marginTop: 10,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <FadeUp
            delay={40}
            style={{
              fontSize: 32,
              color: COLORS.dim,
              textDecoration: strike > 0.05 ? "line-through" : "none",
              textDecorationColor: COLORS.red,
              textDecorationThickness: 3,
            }}
          >
            高门槛 · 高成本
          </FadeUp>
        </div>
        <FadeUp delay={60} style={{ fontSize: 48, color: COLORS.green }}>
          ▶
        </FadeUp>
        <div style={{ textAlign: "center" }}>
          <FadeUp delay={70}>
            <div
              style={{
                fontSize: 48,
                fontWeight: 700,
                color: COLORS.green,
              }}
            >
              人人可用
            </div>
          </FadeUp>
        </div>
      </div>
      <FadeUp
        delay={100}
        style={{
          fontSize: 32,
          color: COLORS.muted,
          textAlign: "center",
          lineHeight: 1.7,
          maxWidth: 1200,
        }}
      >
        连接全球优质的<span style={{ color: COLORS.purple }}>数据</span>、
        <span style={{ color: COLORS.blue }}>工具</span>和
        <span style={{ color: COLORS.green }}>知识</span>
      </FadeUp>
    </AbsoluteFill>
  );
};

// ===========================================================================
// 7. CTABrand — 结尾
// ===========================================================================
export const CTABrand: React.FC = () => (
  <AbsoluteFill
    style={{
      fontFamily: FONT_SANS,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 30,
      paddingBottom: 150,
    }}
  >
    <FadeUp delay={0}>
      <Pill color={COLORS.green}>信息平权 · 机会公平</Pill>
    </FadeUp>
    <FadeUp
      delay={14}
      style={{
        fontSize: 80,
        fontWeight: 700,
        color: COLORS.text,
        textAlign: "center",
        lineHeight: 1.2,
      }}
    >
      寻数科技
      <br />
      <span style={{ fontSize: 36, fontWeight: 500, color: COLORS.muted }}>
        FindDataTechnology
      </span>
    </FadeUp>
    <FadeUp
      delay={40}
      style={{
        fontSize: 36,
        color: COLORS.text,
        textAlign: "center",
        lineHeight: 1.6,
        maxWidth: 1100,
      }}
    >
      一个更开放、更公平的 AI 未来
      <br />
      <span style={{ color: COLORS.green }}>我们一起探索。</span>
    </FadeUp>
    <FadeUp
      delay={68}
      style={{
        fontFamily: FONT_MONO,
        fontSize: 34,
        color: COLORS.blue,
        marginTop: 10,
      }}
    >
      github.com/FindDataOfficial
    </FadeUp>
    <FadeUp delay={88} style={{ display: "flex", gap: 48, marginTop: 6 }}>
      <CTAItem icon="⭐" text="Star" color={COLORS.orange} delay={0} />
      <CTAItem icon="💬" text="关注" color={COLORS.blue} delay={10} />
      <CTAItem icon="🤝" text="合作" color={COLORS.green} delay={20} />
    </FadeUp>
  </AbsoluteFill>
);

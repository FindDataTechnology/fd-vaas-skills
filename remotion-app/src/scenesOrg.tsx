// Org-level brand scenes for the FindDataTechnology introduce video.
// Six scenes: CoverOrg -> HookOrg -> ThreeStepsOrg -> ProjectsOrg -> ValueOrg -> CTAOrg.
// Reuses ui.tsx primitives + theme.ts design system for visual consistency with
// the existing IntroduceGov/IntroduceReport videos. Scenes are placed inside
// <Sequence> blocks (local frame starts at 0 in each), so all delays are local.
// Content is biased to the upper 2/3 to leave room for the bottom SubtitleBar.

import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { COLORS, EASE_OUT, FONT_MONO, FONT_SANS } from "./theme";
import {
  Card,
  CTAItem,
  FadeUp,
  Pill,
  Terminal,
  Typewriter,
  useCountUp,
  fmt,
} from "./ui";

// ===========================================================================
// 0. CoverOrg - 品牌封面 (60f / 2s, before narration starts)
// Logo mark + name + tagline，纯静态、无字幕、无配音。
// ===========================================================================
export const CoverOrg: React.FC = () => {
  const frame = useCurrentFrame();
  const logoScale = interpolate(frame, [0, 20], [0.7, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });
  const logoOpacity = interpolate(frame, [0, 15], [0, 1], {
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
        gap: 40,
      }}
    >
      <div
        style={{
          opacity: logoOpacity,
          transform: `scale(${logoScale})`,
          fontSize: 240,
          lineHeight: 1,
          color: COLORS.green,
          filter: `drop-shadow(0 0 40px ${COLORS.green}55)`,
        }}
      >
        ⬢
      </div>
      <FadeUp
        delay={12}
        style={{
          fontSize: 96,
          fontWeight: 700,
          color: COLORS.text,
          letterSpacing: "-0.01em",
        }}
      >
        FindDataTechnology
      </FadeUp>
      <FadeUp
        delay={22}
        style={{
          fontFamily: FONT_MONO,
          fontSize: 32,
          color: COLORS.muted,
          letterSpacing: "0.14em",
        }}
      >
        让世界的公开信息 · 真正可被计算
      </FadeUp>
    </AbsoluteFill>
  );
};

// ===========================================================================
// 1. HookOrg - mission opener
// ===========================================================================
export const HookOrg: React.FC = () => (
  <AbsoluteFill
    style={{
      fontFamily: FONT_SANS,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 34,
      paddingBottom: 150,
    }}
  >
    <FadeUp
      delay={0}
      style={{
        fontFamily: FONT_MONO,
        fontSize: 26,
        color: COLORS.muted,
        letterSpacing: "0.12em",
      }}
    >
      <span style={{ color: COLORS.green }}>⬢</span> FindDataTechnology · OPEN SOURCE
    </FadeUp>
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
      <FadeUp
        delay={10}
        style={{
          fontSize: 92,
          fontWeight: 700,
          color: COLORS.text,
          textAlign: "center",
          lineHeight: 1.15,
        }}
      >
        让世界的公开信息
      </FadeUp>
      <FadeUp
        delay={26}
        style={{
          fontSize: 92,
          fontWeight: 700,
          textAlign: "center",
          lineHeight: 1.15,
        }}
      >
        <span style={{ color: COLORS.text }}>真正</span>
        <span style={{ color: COLORS.green }}>可被计算</span>
      </FadeUp>
    </div>
    <FadeUp delay={52}>
      <Pill color={COLORS.blue}>信息平权 · Information Equity</Pill>
    </FadeUp>
  </AbsoluteFill>
);

// ===========================================================================
// 2. ThreeStepsOrg - Harvest -> Structure -> Serve flow
// ===========================================================================
const StepCard: React.FC<{
  index: string;
  title: string;
  en: string;
  desc: string;
  accent: string;
  delay: number;
}> = ({ index, title, en, desc, accent, delay }) => (
  <Card delay={delay} accent={accent} style={{ width: 460 }}>
    <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
      <span style={{ fontFamily: FONT_MONO, fontSize: 30, color: accent }}>
        {index}
      </span>
      <span style={{ fontSize: 40, fontWeight: 700, color: COLORS.text }}>
        {title}
      </span>
    </div>
    <div
      style={{
        fontFamily: FONT_MONO,
        fontSize: 22,
        color: COLORS.dim,
        marginTop: 6,
      }}
    >
      {en}
    </div>
    <div
      style={{
        fontSize: 27,
        color: COLORS.muted,
        marginTop: 20,
        lineHeight: 1.5,
      }}
    >
      {desc}
    </div>
  </Card>
);

export const ThreeStepsOrg: React.FC = () => {
  const frame = useCurrentFrame();
  const arrow1 = interpolate(frame, [20, 60], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });
  const arrow2 = interpolate(frame, [50, 90], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });
  const flow = (frame % 30) / 30;

  const Arrow: React.FC<{ progress: number; colorStart: string; colorEnd: string }> = ({
    progress,
    colorStart,
    colorEnd,
  }) => (
    <div
      style={{
        width: 80,
        height: 70,
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: "50%",
          height: 3,
          background: COLORS.border,
          transform: "translateY(-50%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          top: "50%",
          height: 3,
          width: `${progress * 100}%`,
          background: `linear-gradient(90deg, ${colorStart}, ${colorEnd})`,
          transform: "translateY(-50%)",
        }}
      />
      {[0, 1].map((d) => {
        const x = (flow + d / 2) % 1;
        return (
          <div
            key={d}
            style={{
              position: "absolute",
              left: `${x * 100}%`,
              top: "50%",
              width: 9,
              height: 9,
              borderRadius: 5,
              background: colorEnd,
              transform: "translate(-50%, -50%)",
              opacity: 0.85,
            }}
          />
        );
      })}
    </div>
  );

  return (
    <AbsoluteFill
      style={{
        fontFamily: FONT_SANS,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 50,
        paddingBottom: 150,
        paddingLeft: 80,
        paddingRight: 80,
      }}
    >
      <FadeUp delay={0} style={{ fontSize: 50, fontWeight: 700, color: COLORS.text }}>
        我们做三件事
      </FadeUp>
      <div style={{ display: "flex", alignItems: "center", gap: 0, width: "100%" }}>
        <StepCard
          index="01"
          title="采集"
          en="Harvest"
          desc="各国政府与统计栏目，目录化抓成干净记录"
          accent={COLORS.green}
          delay={14}
        />
        <Arrow progress={arrow1} colorStart={COLORS.green} colorEnd={COLORS.blue} />
        <StepCard
          index="02"
          title="结构化"
          en="Structure"
          desc="财报与公告，用规则变成带 schema 的字段"
          accent={COLORS.blue}
          delay={40}
        />
        <Arrow progress={arrow2} colorStart={COLORS.blue} colorEnd={COLORS.purple} />
        <StepCard
          index="03"
          title="服务"
          en="Serve"
          desc="每个数据集封装成 MCP 服务器，AI 可调用"
          accent={COLORS.purple}
          delay={66}
        />
      </div>
      <FadeUp delay={92}>
        <Terminal title="any AI agent" style={{ width: 820, fontSize: 26 }}>
          <div style={{ display: "flex", gap: 12, whiteSpace: "nowrap" }}>
            <span style={{ color: COLORS.green }}>»</span>
            <Typewriter text="mcp: finddata.search(query='央行利率')" start={96} speed={1.2} />
          </div>
        </Terminal>
      </FadeUp>
    </AbsoluteFill>
  );
};

// ===========================================================================
// 3. ProjectsOrg - open-source portfolio, anchored on China
// ===========================================================================
const ProjectCard: React.FC<{
  name: string;
  role: string;
  accent: string;
  target: number;
  suffix?: string;
  statLabel: string;
  detail: string;
  delay: number;
}> = ({ name, role, accent, target, suffix = "", statLabel, detail, delay }) => {
  const n = useCountUp(target, delay + 12, 48);
  return (
    <Card delay={delay} accent={accent} style={{ width: 500 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
        <span
          style={{
            fontFamily: FONT_MONO,
            fontSize: 36,
            color: accent,
            fontWeight: 700,
          }}
        >
          {name}
        </span>
        <span style={{ fontSize: 22, color: COLORS.dim }}>{role}</span>
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 56,
          fontWeight: 700,
          color: COLORS.text,
          marginTop: 22,
          lineHeight: 1,
          letterSpacing: "-0.02em",
        }}
      >
        {fmt(n)}
        {suffix}
      </div>
      <div style={{ fontSize: 22, color: COLORS.muted, marginTop: 8 }}>
        {statLabel}
      </div>
      <div
        style={{
          fontSize: 24,
          color: COLORS.muted,
          marginTop: 20,
          lineHeight: 1.5,
        }}
      >
        {detail}
      </div>
    </Card>
  );
};

export const ProjectsOrg: React.FC = () => (
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
    <FadeUp delay={0} style={{ fontSize: 46, fontWeight: 700, color: COLORS.text }}>
      开源 · 从中国开始
    </FadeUp>
    <div style={{ display: "flex", gap: 36, alignItems: "stretch" }}>
      <ProjectCard
        name="DAAS"
        role="多源 MCP 平台"
        accent={COLORS.purple}
        target={673}
        suffix="+"
        statLabel="金融函数 · 一个接口调全世界"
        detail="AKShare · CKAN · WorldBank · CNStats"
        delay={14}
      />
      <ProjectCard
        name="fd-cn-gov"
        role="政策面"
        accent={COLORS.green}
        target={11}
        statLabel="部委公告 · 一键目录化采集"
        detail="自描述数据源注册表 · pip install fd-cn-gov"
        delay={30}
      />
      <ProjectCard
        name="fd-cn-report"
        role="公司面"
        accent={COLORS.blue}
        target={21698}
        statLabel="抽取规则 · 31 个申万一级行业"
        detail="年报 PDF -> 结构化指标 · 44 个 MCP 工具"
        delay={46}
      />
    </div>
    <FadeUp delay={70} style={{ display: "flex", gap: 24 }}>
      <Pill color={COLORS.cyan}>Platform · 把一切串起来</Pill>
      <Pill color={COLORS.orange}>coding · 设计到实现</Pill>
    </FadeUp>
  </AbsoluteFill>
);

// ===========================================================================
// 4. ValueOrg - days of research -> one query
// ===========================================================================
export const ValueOrg: React.FC = () => {
  const frame = useCurrentFrame();
  const strike = interpolate(frame, [40, 70], [0, 1], {
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
        gap: 40,
        paddingBottom: 150,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
        <FadeUp delay={0} style={{ textAlign: "center" }}>
          <div
            style={{
              fontSize: 40,
              color: COLORS.dim,
              textDecoration: strike > 0.05 ? "line-through" : "none",
              textDecorationColor: COLORS.red,
              textDecorationThickness: 3,
            }}
          >
            几天人工调研
          </div>
        </FadeUp>
        <FadeUp delay={28} style={{ fontSize: 48, color: COLORS.green }}>
          ▶
        </FadeUp>
        <FadeUp delay={40} style={{ textAlign: "center" }}>
          <div style={{ fontSize: 64, fontWeight: 700, color: COLORS.green }}>
            一次查询
          </div>
        </FadeUp>
      </div>
      <FadeUp
        delay={72}
        style={{
          fontSize: 44,
          color: COLORS.text,
          textAlign: "center",
          maxWidth: 1200,
          lineHeight: 1.4,
        }}
      >
        无论提问者是<span style={{ color: COLORS.blue }}>分析师</span>，还是{" "}
        <span style={{ color: COLORS.green }}>AI</span>。
      </FadeUp>
    </AbsoluteFill>
  );
};

// ===========================================================================
// 5. CTAOrg - close
// ===========================================================================
export const CTAOrg: React.FC = () => (
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
      <Pill color={COLORS.green}>信息平权 · Information Equity</Pill>
    </FadeUp>
    <FadeUp
      delay={12}
      style={{
        fontSize: 76,
        fontWeight: 700,
        color: COLORS.text,
        textAlign: "center",
      }}
    >
      FindDataTechnology
    </FadeUp>
    <FadeUp
      delay={28}
      style={{ fontSize: 38, color: COLORS.muted, textAlign: "center" }}
    >
      让世界的信息，人人可用
    </FadeUp>
    <FadeUp
      delay={50}
      style={{
        fontFamily: FONT_MONO,
        fontSize: 40,
        color: COLORS.blue,
        marginTop: 6,
      }}
    >
      github.com/FindDataOfficial
    </FadeUp>
    <FadeUp delay={74} style={{ display: "flex", gap: 40, marginTop: 4 }}>
      <CTAItem icon="⭐" text="Star" color={COLORS.orange} delay={0} />
      <CTAItem icon="🐛" text="Issue" color={COLORS.red} delay={8} />
      <CTAItem icon="🤝" text="PR" color={COLORS.green} delay={16} />
    </FadeUp>
  </AbsoluteFill>
);

// fd-cn-report focused scenes: HookReport, PainReport, ReportDeepDive, CTAReport.
// ReportDeepDive is also reused inside the combined IntroduceVideo composition.

import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS, FONT_MONO } from "./theme";
import {
  Card,
  Chip,
  CTAItem,
  FadeUp,
  fmt,
  InfoRow,
  PainItem,
  phaseVis,
  Pill,
  Stat,
  Terminal,
  Typewriter,
  useCountUp,
} from "./ui";

export const HookReport: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 32,
    }}
  >
    <FadeUp
      delay={0}
      style={{
        fontFamily: FONT_MONO,
        fontSize: 30,
        color: COLORS.muted,
        letterSpacing: "0.08em",
      }}
    >
      OPEN SOURCE · MIT · PyPI · MCP
    </FadeUp>
    <FadeUp
      delay={8}
      style={{
        fontFamily: FONT_MONO,
        fontSize: 96,
        fontWeight: 700,
        color: COLORS.blue,
      }}
    >
      fd-cn-report
    </FadeUp>
    <FadeUp delay={22} style={{ fontSize: 44, color: COLORS.text }}>
      财报 PDF，一键变结构化指标
    </FadeUp>
    <FadeUp delay={38} style={{ fontSize: 26, color: COLORS.muted }}>
      44 个工具 · 31 个行业 · 2.1 万条抽取规则
    </FadeUp>
    <FadeUp delay={54} style={{ marginTop: 6 }}>
      <Terminal title="bash" style={{ width: 720 }}>
        <div style={{ display: "flex", gap: 14 }}>
          <span style={{ color: COLORS.green }}>$</span>
          <Typewriter text="pip install fd-cn-report" start={66} speed={1.4} />
        </div>
      </Terminal>
    </FadeUp>
  </AbsoluteFill>
);

export const PainReport: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 50,
    }}
  >
    <FadeUp delay={0} style={{ fontSize: 40, color: COLORS.muted }}>
      财报 PDF，为什么这么痛？
    </FadeUp>
    <PainItem
      delay={28}
      text="一份年报上百页，三大报表、管理层讨论、股东信息散落不同章节"
    />
    <PainItem delay={66} text="人工抄写既慢又错，换个公司又得重来一遍" />
  </AbsoluteFill>
);

const STEPS: { code: string; c: string }[] = [
  { code: `co      = get_company("600519")`, c: `# 贵州茅台` },
  {
    code: `filings = list_filings("600519", form="年度报告", year=2023)`,
    c: `# 披露列表`,
  },
  {
    code: `sec     = get_section("600519", year=2023, section="管理层讨论与分析")`,
    c: `# 章节定位`,
  },
  { code: `records = ai_extract(text=sec["text"], schema={...})`, c: `# 结构化营收` },
];

const LAYERS: { name: string; color: string }[] = [
  { name: "公司 API", color: COLORS.blue },
  { name: "港股 HKEX", color: COLORS.green },
  { name: "交易所 SSE / SZSE / BSE", color: COLORS.purple },
  { name: "证监会 CSRC", color: COLORS.orange },
  { name: "部委统计", color: COLORS.cyan },
  { name: "PDF / AI / ES", color: COLORS.red },
  { name: "指标引擎", color: COLORS.blue },
];

export const ReportDeepDive: React.FC = () => {
  const frame = useCurrentFrame();
  const rules = useCountUp(21698, 40, 36);
  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "90px 120px 110px",
      }}
    >
      <FadeUp
        delay={0}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 54,
            fontWeight: 700,
            color: COLORS.blue,
          }}
        >
          fd-cn-report
        </div>
        <div style={{ fontSize: 34, color: COLORS.text }}>
          财报 PDF，一键变结构化指标
        </div>
        <div
          style={{
            display: "inline-flex",
            gap: 10,
            alignItems: "center",
            marginTop: 8,
            padding: "6px 18px",
            borderRadius: 999,
            border: `1px solid ${COLORS.blue}55`,
            background: `${COLORS.blue}1a`,
            fontSize: 22,
            color: COLORS.blue,
          }}
        >
          MCP 服务器 · 44 个工具
        </div>
      </FadeUp>

      {/* Phase A: hero stats */}
      <div
        style={{
          position: "absolute",
          inset: "300px 120px 110px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 44,
          opacity: phaseVis(frame, 20, 130),
        }}
      >
        <div style={{ display: "flex", gap: 90, alignItems: "flex-end" }}>
          <Stat value="31" label="申万一级行业" color={COLORS.blue} delay={20} />
          <Stat
            value={fmt(rules)}
            label="条 LLM 抽取规则"
            color={COLORS.purple}
            delay={32}
          />
          <Stat value="44" label="个 MCP 工具" color={COLORS.green} delay={44} />
        </div>
        <FadeUp
          delay={70}
          style={{
            fontSize: 26,
            color: COLORS.muted,
            textAlign: "center",
            maxWidth: 1200,
            lineHeight: 1.5,
          }}
        >
          从真实年报 PDF 出发，为每个行业生成一套抽取规则--把指标映射到它在年报中的精确章节位置。
        </FadeUp>
      </div>

      {/* Phase B: 4-step chain */}
      <div
        style={{
          position: "absolute",
          inset: "290px 120px 110px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: phaseVis(frame, 145, 320),
        }}
      >
        <Terminal title="python · fd-cn-report" style={{ width: 1280 }} fontSize={24}>
          {STEPS.map((s, i) => (
            <div
              key={i}
              style={{ display: "flex", gap: 16, whiteSpace: "nowrap" }}
            >
              <span style={{ color: COLORS.purple }}>{">"}</span>
              <Typewriter
                text={s.code}
                start={150 + i * 34}
                speed={1.5}
                style={{ color: COLORS.text }}
              />
              <span style={{ color: COLORS.muted }}>
                <Typewriter
                  text={s.c}
                  start={150 + i * 34 + 24}
                  speed={1.4}
                  cursor={false}
                />
              </span>
            </div>
          ))}
        </Terminal>
      </div>

      {/* Phase C: tool layers */}
      <div
        style={{
          position: "absolute",
          inset: "300px 120px 110px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 32,
          opacity: phaseVis(frame, 335, 455),
        }}
      >
        <FadeUp delay={0} style={{ fontSize: 30, color: COLORS.text }}>
          44 个工具，按层划分
        </FadeUp>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 16,
            justifyContent: "center",
            maxWidth: 1400,
          }}
        >
          {LAYERS.map((l, i) => (
            <Chip key={l.name} color={l.color} delay={10 + i * 6}>
              {l.name}
            </Chip>
          ))}
        </div>
      </div>

      {/* Phase D: highlight pills */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 90,
          display: "flex",
          justifyContent: "center",
          gap: 18,
          flexWrap: "wrap",
          opacity: phaseVis(frame, 462, 533),
        }}
      >
        <Pill color={COLORS.green} delay={0}>
          CNINFO / akshare 免密
        </Pill>
        <Pill color={COLORS.blue} delay={8}>
          两级缓存，重跑不烧 token
        </Pill>
        <Pill color={COLORS.purple} delay={16}>
          可插拔抽取器
        </Pill>
        <Pill color={COLORS.orange} delay={24}>
          批量并发
        </Pill>
      </div>
    </AbsoluteFill>
  );
};

export const CTAReport: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 36,
    }}
  >
    <Card delay={0} accent={COLORS.blue} style={{ width: 720 }}>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 40,
          color: COLORS.blue,
          fontWeight: 700,
        }}
      >
        fd-cn-report
      </div>
      <InfoRow k="版本" v="0.2.0" />
      <InfoRow k="PyPI" v="pypi.org/project/fd-cn-report" />
      <InfoRow k="GitHub" v="cn-financial-reports" />
      <InfoRow k="协议" v="MIT · Python ≥ 3.10" />
    </Card>
    <FadeUp delay={30} style={{ display: "flex", gap: 40 }}>
      <CTAItem icon="⭐" text="Star" color={COLORS.orange} delay={0} />
      <CTAItem icon="🐛" text="Issue" color={COLORS.red} delay={8} />
      <CTAItem icon="🤝" text="PR" color={COLORS.green} delay={16} />
    </FadeUp>
    <FadeUp
      delay={60}
      style={{ fontFamily: FONT_MONO, fontSize: 38, color: COLORS.blue }}
    >
      github.com/FindDataOfficial
    </FadeUp>
    <FadeUp delay={84} style={{ fontSize: 26, color: COLORS.muted }}>
      FindDataOfficial · 让中国数据更好用一点
    </FadeUp>
  </AbsoluteFill>
);

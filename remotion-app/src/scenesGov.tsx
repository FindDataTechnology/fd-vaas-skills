// fd-cn-gov focused scenes: HookGov, PainGov, GovDeepDive, CTAGov.
// GovDeepDive is also reused inside the combined IntroduceVideo composition.

import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS, FONT_MONO } from "./theme";
import {
  Card,
  CardTitle,
  Chip,
  CTAItem,
  FadeUp,
  InfoRow,
  PainItem,
  phaseVis,
  Pill,
  Stat,
  Terminal,
  Typewriter,
} from "./ui";

export const HookGov: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 36,
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
      OPEN SOURCE · MIT · PyPI
    </FadeUp>
    <FadeUp
      delay={8}
      style={{
        fontFamily: FONT_MONO,
        fontSize: 96,
        fontWeight: 700,
        color: COLORS.green,
      }}
    >
      fd-cn-gov
    </FadeUp>
    <FadeUp delay={22} style={{ fontSize: 44, color: COLORS.text }}>
      政府公开信息，一键目录化采集
    </FadeUp>
    <FadeUp delay={40} style={{ marginTop: 8 }}>
      <Terminal title="bash" style={{ width: 640 }}>
        <div style={{ display: "flex", gap: 14 }}>
          <span style={{ color: COLORS.green }}>$</span>
          <Typewriter text="pip install fd-cn-gov" start={50} speed={1.4} />
        </div>
      </Terminal>
    </FadeUp>
  </AbsoluteFill>
);

export const PainGov: React.FC = () => (
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
      抓政府数据，为什么这么累？
    </FadeUp>
    <PainItem
      delay={28}
      text="财政部、央行、发改委……每个部委页面都不一样，批量抓只能一个个写解析"
    />
    <PainItem
      delay={66}
      text="抓下来还没有统一的「数据源清单」--字段从哪来、主键是什么，全靠自己记"
    />
  </AbsoluteFill>
);

const MINISTRIES: [string, string][] = [
  ["财政部", "MOF"],
  ["人民银行", "PBC"],
  ["发改委", "NDRC"],
  ["商务部", "MOFCOM"],
  ["住建部", "MOHURD"],
  ["交通运输部", "MOT"],
  ["农业农村部", "MOA"],
  ["外汇局", "SAFE"],
  ["自然资源部", "MNR"],
  ["生态环境部", "MEE"],
  ["应急管理部", "MEM"],
];

const CLI: string[] = [
  "fd-cn-gov list",
  "fd-cn-gov describe mof_gkml_archive",
  "fd-cn-gov crawl mof_gkml_archive --max-pages 2 > records.json",
  "fd-cn-gov build-registry",
];

export const GovDeepDive: React.FC = () => {
  const frame = useCurrentFrame();
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
            color: COLORS.green,
          }}
        >
          fd-cn-gov
        </div>
        <div style={{ fontSize: 34, color: COLORS.text }}>
          政府公开信息，目录化采集
        </div>
        <div style={{ fontSize: 24, color: COLORS.muted, marginTop: 4 }}>
          11 部委公告档案，一键目录化 · 自描述数据源注册表
        </div>
      </FadeUp>

      {/* Phase A: two capability cards */}
      <div
        style={{
          position: "absolute",
          inset: "290px 120px 110px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: phaseVis(frame, 20, 150),
        }}
      >
        <div style={{ display: "flex", gap: 32, width: "100%", maxWidth: 1500 }}>
          <Card delay={28} accent={COLORS.green} style={{ flex: 1 }}>
            <CardTitle n="①" t="目录级采集" c={COLORS.green} />
            <div style={{ fontSize: 25, lineHeight: 1.6, color: COLORS.text }}>
              对 11 个部委公开信息档案做「列表页」抓取，每条公告产出一条
              JSON（title / date / url）。
            </div>
            <div
              style={{
                fontSize: 23,
                lineHeight: 1.6,
                color: COLORS.muted,
                marginTop: 12,
              }}
            >
              抓的是档案目录，不是正文--轻量、礼貌、可重复。
            </div>
          </Card>
          <Card delay={46} accent={COLORS.blue} style={{ flex: 1 }}>
            <CardTitle n="②" t="自描述数据源注册表" c={COLORS.blue} />
            <div style={{ fontSize: 25, lineHeight: 1.6, color: COLORS.text }}>
              每个数据源带完整字段 schema：字段名、类型、是否主键、来源、语义类型。
            </div>
            <div
              style={{
                fontSize: 23,
                lineHeight: 1.6,
                color: COLORS.muted,
                marginTop: 12,
              }}
            >
              打包 SQLite + JSON，自包含，pip install 完就能用。
            </div>
          </Card>
        </div>
      </div>

      {/* Phase B: 11 ministries */}
      <div
        style={{
          position: "absolute",
          inset: "290px 120px 110px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 40,
          opacity: phaseVis(frame, 165, 295),
        }}
      >
        <Stat value="11" label="部委公开信息档案" color={COLORS.green} delay={0} />
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 16,
            justifyContent: "center",
            maxWidth: 1400,
          }}
        >
          {MINISTRIES.map(([zh, en], i) => (
            <Chip key={en} color={COLORS.green} delay={20 + i * 5}>
              <span style={{ color: COLORS.text }}>{zh}</span>
              <span
                style={{
                  color: COLORS.muted,
                  fontFamily: FONT_MONO,
                  fontSize: 18,
                }}
              >
                {en}
              </span>
            </Chip>
          ))}
        </div>
      </div>

      {/* Phase C: CLI terminal */}
      <div
        style={{
          position: "absolute",
          inset: "300px 120px 110px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: phaseVis(frame, 310, 420),
        }}
      >
        <Terminal title="fd-cn-gov" style={{ width: 1100 }} fontSize={28}>
          {CLI.map((line, i) => (
            <div
              key={line}
              style={{ display: "flex", gap: 14, whiteSpace: "nowrap" }}
            >
              <span style={{ color: COLORS.green }}>$</span>
              <Typewriter text={line} start={315 + i * 26} speed={1.8} />
            </div>
          ))}
          <div
            style={{
              marginTop: 8,
              color: COLORS.muted,
              fontSize: 22,
              whiteSpace: "nowrap",
            }}
          >
            <Typewriter
              text="# 输出可 diff 的 registry.json"
              start={405}
              speed={1.6}
              cursor={false}
            />
          </div>
        </Terminal>
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
          gap: 20,
          opacity: phaseVis(frame, 425, 478),
        }}
      >
        <Pill color={COLORS.green} delay={0}>
          CLI 即用，无需写代码
        </Pill>
        <Pill color={COLORS.blue} delay={8}>
          礼貌爬取 ≈0.3s / 页
        </Pill>
        <Pill color={COLORS.purple} delay={16}>
          幂等可重建
        </Pill>
      </div>
    </AbsoluteFill>
  );
};

export const CTAGov: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 36,
    }}
  >
    <Card delay={0} accent={COLORS.green} style={{ width: 720 }}>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 40,
          color: COLORS.green,
          fontWeight: 700,
        }}
      >
        fd-cn-gov
      </div>
      <InfoRow k="版本" v="0.1.1" />
      <InfoRow k="PyPI" v="pypi.org/project/fd-cn-gov" />
      <InfoRow k="GitHub" v="cn-goverment-datasource" />
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

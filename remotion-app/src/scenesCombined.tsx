// Combined-video-only scenes: HookBoth, PainBoth, Split, Loop, CTABoth.
// (The two deep dives are imported from scenesGov / scenesReport into Composition.)

import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { COLORS, EASE_OUT, FONT_MONO } from "./theme";
import {
  Card,
  CTAItem,
  FadeUp,
  InfoRow,
  PainItem,
  Terminal,
  Typewriter,
} from "./ui";

export const HookBoth: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 40,
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
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 18,
      }}
    >
      <FadeUp
        delay={8}
        style={{
          fontSize: 64,
          fontWeight: 700,
          color: COLORS.text,
          textAlign: "center",
          lineHeight: 1.2,
        }}
      >
        把中国政务与 A 股财报数据
      </FadeUp>
      <FadeUp
        delay={20}
        style={{ fontSize: 64, fontWeight: 700, textAlign: "center", lineHeight: 1.2 }}
      >
        装进两条{" "}
        <span style={{ fontFamily: FONT_MONO, color: COLORS.green }}>pip</span>{" "}
        命令
      </FadeUp>
    </div>
    <FadeUp delay={40} style={{ marginTop: 10 }}>
      <Terminal title="bash" style={{ width: 760 }}>
        <div style={{ display: "flex", gap: 14, whiteSpace: "nowrap" }}>
          <span style={{ color: COLORS.green }}>$</span>
          <Typewriter text="pip install fd-cn-gov" start={50} speed={1.4} />
        </div>
        <div style={{ display: "flex", gap: 14, whiteSpace: "nowrap" }}>
          <span style={{ color: COLORS.green }}>$</span>
          <Typewriter text="pip install fd-cn-report" start={84} speed={1.4} />
        </div>
      </Terminal>
    </FadeUp>
  </AbsoluteFill>
);

export const PainBoth: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 44,
    }}
  >
    <FadeUp delay={0} style={{ fontSize: 40, color: COLORS.muted, marginBottom: 10 }}>
      做中国数据的人，大概都经历过这种痛苦
    </FadeUp>
    <PainItem
      delay={30}
      text="各部委「信息公开」页面长得都不一样，批量抓只能一个一个写解析"
    />
    <PainItem
      delay={70}
      text="上市公司年报是上百页 PDF，三大报表散落不同章节，人工抄写既慢又错"
    />
    <PainItem
      delay={110}
      text="好不容易抓下来，还没有统一的「数据源清单」告诉你字段从哪来"
    />
  </AbsoluteFill>
);

export const Split: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 50,
    }}
  >
    <FadeUp delay={0} style={{ fontSize: 42, color: COLORS.text }}>
      我们拆成了两个独立、可单独安装的包
    </FadeUp>
    <div style={{ display: "flex", gap: 48, alignItems: "stretch" }}>
      <Card delay={20} accent={COLORS.green} style={{ width: 560 }}>
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
        <div style={{ fontSize: 26, color: COLORS.muted, marginTop: 10 }}>
          政策面
        </div>
        <div
          style={{
            fontSize: 28,
            color: COLORS.text,
            marginTop: 18,
            lineHeight: 1.5,
          }}
        >
          11 部委公告档案，一键目录化采集 + 自描述数据源注册表
        </div>
      </Card>
      <Card delay={34} accent={COLORS.blue} style={{ width: 560 }}>
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
        <div style={{ fontSize: 26, color: COLORS.muted, marginTop: 10 }}>
          公司面
        </div>
        <div
          style={{
            fontSize: 28,
            color: COLORS.text,
            marginTop: 18,
            lineHeight: 1.5,
          }}
        >
          31 个申万一级行业、44 个 MCP 工具，财报 PDF -&gt; 结构化指标
        </div>
      </Card>
    </div>
  </AbsoluteFill>
);

export const Loop: React.FC = () => {
  const frame = useCurrentFrame();
  const arrowProgress = interpolate(frame, [30, 120], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });
  const flow = (frame % 30) / 30; // moving dots, deterministic
  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 70,
      }}
    >
      <FadeUp
        delay={0}
        style={{ fontSize: 42, color: COLORS.text, textAlign: "center" }}
      >
        政策面 -&gt; 公司面，一条数据闭环
      </FadeUp>
      <div style={{ display: "flex", alignItems: "center" }}>
        <Card delay={10} accent={COLORS.green} style={{ width: 480 }}>
          <div
            style={{
              fontFamily: FONT_MONO,
              fontSize: 34,
              color: COLORS.green,
              fontWeight: 700,
            }}
          >
            fd-cn-gov
          </div>
          <div style={{ fontSize: 24, color: COLORS.muted, marginTop: 12 }}>
            政策 / 监管 / 行业公开信息
          </div>
          <div style={{ fontSize: 22, color: COLORS.dim, marginTop: 6 }}>
            目录 + 字段 schema
          </div>
        </Card>

        {/* animated arrow */}
        <div
          style={{
            width: 260,
            height: 80,
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
              height: 4,
              background: COLORS.border,
              transform: "translateY(-50%)",
            }}
          />
          <div
            style={{
              position: "absolute",
              left: 0,
              top: "50%",
              height: 4,
              width: `${arrowProgress * 100}%`,
              background: `linear-gradient(90deg, ${COLORS.green}, ${COLORS.blue})`,
              transform: "translateY(-50%)",
            }}
          />
          {[0, 1, 2].map((d) => {
            const x = (flow + d / 3) % 1;
            return (
              <div
                key={d}
                style={{
                  position: "absolute",
                  left: `${x * 100}%`,
                  top: "50%",
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  background: COLORS.blue,
                  transform: "translate(-50%, -50%)",
                  opacity: 0.9,
                }}
              />
            );
          })}
          <div
            style={{
              position: "absolute",
              right: -2,
              top: "50%",
              transform: "translateY(-50%)",
              color: COLORS.blue,
              fontSize: 28,
            }}
          >
            ▶
          </div>
        </div>

        <Card delay={20} accent={COLORS.blue} style={{ width: 480 }}>
          <div
            style={{
              fontFamily: FONT_MONO,
              fontSize: 34,
              color: COLORS.blue,
              fontWeight: 700,
            }}
          >
            fd-cn-report
          </div>
          <div style={{ fontSize: 24, color: COLORS.muted, marginTop: 12 }}>
            上市公司财报 PDF
          </div>
          <div style={{ fontSize: 22, color: COLORS.dim, marginTop: 6 }}>
            -&gt; 结构化财务指标（MCP 可调用）
          </div>
        </Card>
      </div>
      <FadeUp
        delay={140}
        style={{
          fontSize: 26,
          color: COLORS.muted,
          textAlign: "center",
          maxWidth: 1100,
        }}
      >
        同一套数据源注册表思路：字段自描述、可重建、可 diff
      </FadeUp>
    </AbsoluteFill>
  );
};

export const CTABoth: React.FC = () => (
  <AbsoluteFill
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 40,
    }}
  >
    <FadeUp delay={0} style={{ fontSize: 40, color: COLORS.text }}>
      两个包，都已上 PyPI
    </FadeUp>
    <div style={{ display: "flex", gap: 36 }}>
      <Card delay={12} accent={COLORS.green} style={{ width: 540 }}>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 36,
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
      <Card delay={24} accent={COLORS.blue} style={{ width: 540 }}>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 36,
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
    </div>
    <FadeUp delay={60} style={{ display: "flex", gap: 40, marginTop: 6 }}>
      <CTAItem icon="⭐" text="Star" color={COLORS.orange} delay={0} />
      <CTAItem icon="🐛" text="Issue" color={COLORS.red} delay={8} />
      <CTAItem icon="🤝" text="PR" color={COLORS.green} delay={16} />
    </FadeUp>
    <FadeUp
      delay={90}
      style={{
        fontFamily: FONT_MONO,
        fontSize: 40,
        color: COLORS.blue,
        marginTop: 6,
      }}
    >
      github.com/FindDataOfficial
    </FadeUp>
    <FadeUp delay={120} style={{ fontSize: 28, color: COLORS.muted, marginTop: 4 }}>
      FindDataOfficial · 让中国数据更好用一点
    </FadeUp>
  </AbsoluteFill>
);

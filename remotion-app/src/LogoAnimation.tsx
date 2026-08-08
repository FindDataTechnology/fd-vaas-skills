import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Easing,
  staticFile,
  Audio,
} from "remotion";
import { FONT_SANS, VIDEO } from "./theme";

/**
 * 寻数科技 / Find Data Technology — Logo Animation
 *
 * 变形： || → X → = → ||
 * 人声：TTS 品牌口号播报
 *
 * 时间线：
 *   0.0 – 0.3s  背景淡入
 *   0.2 – 0.8s  || 弹出
 *   1.0 – 1.8s  || → X
 *   2.0 – 2.8s  X → =
 *   2.8 – 3.2s  定格 =
 *   3.2s 起     语音开始 + slogan 滑入（同步）
 *   3.6s 起     公司名跟上
 *   语音结束    = → || 回旋落定，定格
 */

const BRAND = {
  primary: "#4A98A9",
  primaryBright: "#5CB5C9",
  primaryGlow: "rgba(74, 152, 169, 0.5)",
  primarySoft: "rgba(74, 152, 169, 0.08)",
  bg0: "#070c10",
  bg1: "#0c151a",
  text: "#e6f2f5",
  muted: "#7a8e95",
};

const BAR_WIDTH = 48;
const BAR_HEIGHT = 280;
const BAR_GAP = 72;
const BAR_RADIUS = 14;
const GAP = (BAR_GAP + BAR_WIDTH) / 2;

// 变形节奏（帧）— 紧凑 4s，语音从第 0 帧起
const T_GROW_START = 0;
const T_TOX_START = 12;
const T_TOX_END = 32;
const T_TOEQ_START = 36;
const T_TOEQ_END = 54;
const T_TOEQ_HOLD = 58;
// 语音关键时间点（帧 @ 30fps，相对语音起点）
// 语音总长 ≈ 2.16s = 65 帧
//   0 帧    = 「寻」字开始
//   24 帧   = 「寻数科技」结束
//   24–44 帧 = 逗号停顿
//   44 帧   = 「让」字开始
//   64 帧   = 语音全部结束
const VOICE_NAME_START = 0;
const VOICE_NAME_END = 24;
const VOICE_SLOGAN_START = 44;
const VOICE_TOTAL = 64;
const MORPH_BACK_DUR = 20;

// ---------------------------------------------------------------------------
// Logo 变形
// ---------------------------------------------------------------------------
const MorphLogo: React.FC<{ backStartFrame: number; totalFrames: number }> = ({
  backStartFrame,
  totalFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Phase 1: 弹出
  const grow = spring({
    frame: frame - T_GROW_START,
    fps,
    config: { damping: 12, stiffness: 120, mass: 0.7 },
    durationInFrames: 20,
  });
  const barH = BAR_HEIGHT * grow;

  // Phase 2: || → X
  const p1 = interpolate(frame, [T_TOX_START, T_TOX_END], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.65, 0, 0.35, 1),
  });

  // Phase 3: X → =
  const p2 = interpolate(frame, [T_TOEQ_START, T_TOEQ_END], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.65, 0, 0.35, 1),
  });

  // Phase 4: = → || 回旋
  const p3 = interpolate(
    frame,
    [backStartFrame, backStartFrame + MORPH_BACK_DUR],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.65, 0, 0.35, 1),
    }
  );

  // phase: 0(||) → 1(X) → 2(=) → 0(||)
  const phase = p1 + p2 - p3 * 2;

  const angleA = interpolate(phase, [0, 1, 2], [0, 45, 90], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const angleB = interpolate(phase, [0, 1, 2], [0, -45, -90], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const xA = interpolate(phase, [0, 1, 2], [-GAP, 0, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const yA = interpolate(phase, [0, 1, 2], [0, 0, GAP], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const xB = interpolate(phase, [0, 1, 2], [GAP, 0, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const yB = interpolate(phase, [0, 1, 2], [0, 0, -GAP], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // 光晕
  const glow = interpolate(
    frame,
    [6, 24, 42, 72, 90, totalFrames],
    [0, 0.4, 0.8, 1.0, 0.7, 0.75],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const size = 480;

  return (
    <div
      style={{
        width: size,
        height: size,
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: size * 0.9,
          height: size * 0.9,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${BRAND.primaryGlow} 0%, transparent 60%)`,
          opacity: glow,
          filter: "blur(30px)",
        }}
      />

      <svg
        width={size}
        height={size}
        viewBox={`${-size / 2} ${-size / 2} ${size} ${size}`}
        style={{ overflow: "visible" }}
      >
        <g style={{ filter: "blur(10px)", opacity: glow * 0.6 }}>
          <Bar
            x={xA}
            y={yA}
            angle={angleA}
            width={BAR_WIDTH}
            height={barH}
            radius={BAR_RADIUS}
            color={BRAND.primaryBright}
          />
          <Bar
            x={xB}
            y={yB}
            angle={angleB}
            width={BAR_WIDTH}
            height={barH}
            radius={BAR_RADIUS}
            color={BRAND.primaryBright}
          />
        </g>
        <g>
          <Bar
            x={xA}
            y={yA}
            angle={angleA}
            width={BAR_WIDTH}
            height={barH}
            radius={BAR_RADIUS}
            color={BRAND.primary}
          />
          <Bar
            x={xB}
            y={yB}
            angle={angleB}
            width={BAR_WIDTH}
            height={barH}
            radius={BAR_RADIUS}
            color={BRAND.primary}
          />
        </g>
      </svg>
    </div>
  );
};

const Bar: React.FC<{
  x: number;
  y: number;
  angle: number;
  width: number;
  height: number;
  radius: number;
  color: string;
}> = ({ x, y, angle, width, height, radius, color }) => (
  <g transform={`translate(${x}, ${y}) rotate(${angle})`}>
    <rect
      x={-width / 2}
      y={-height / 2}
      width={width}
      height={height}
      rx={radius}
      ry={radius}
      fill={color}
    />
  </g>
);

// ---------------------------------------------------------------------------
// 文字
// ---------------------------------------------------------------------------
const BrandText: React.FC<{
  lang: "zh" | "en";
  sloganStartFrame: number;
  nameStartFrame: number;
}> = ({ lang, sloganStartFrame, nameStartFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sloganIn = spring({
    frame: frame - sloganStartFrame,
    fps,
    config: { damping: 14, stiffness: 90, mass: 0.8 },
    durationInFrames: 30,
  });
  const sloganY = interpolate(sloganIn, [0, 1], [50, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const sloganOpacity = interpolate(sloganIn, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const lineW = interpolate(sloganIn, [0, 1], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const nameIn = spring({
    frame: frame - nameStartFrame,
    fps,
    config: { damping: 14, stiffness: 90, mass: 0.8 },
    durationInFrames: 25,
  });
  const nameY = interpolate(nameIn, [0, 1], [30, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const nameOpacity = interpolate(nameIn, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const sloganText = lang === "zh" ? "让数据优化决策" : "Data Optimizes Decisions";
  const nameText = lang === "zh" ? "寻数科技" : "FIND DATA TECHNOLOGY";

  const sloganSize = lang === "zh" ? 68 : 52;
  const sloganSpacing = lang === "zh" ? 12 : 4;
  const nameSize = lang === "zh" ? 30 : 24;
  const nameSpacing = lang === "zh" ? 22 : 14;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: lang === "zh" ? 24 : 20,
      }}
    >
      {/* Slogan — 主标题 */}
      <div
        style={{
          transform: `translateY(${sloganY}px)`,
          opacity: sloganOpacity,
          display: "flex",
          alignItems: "center",
          gap: 24,
        }}
      >
        <div
          style={{
            width: lineW,
            height: 2,
            background: `linear-gradient(90deg, transparent, ${BRAND.primary})`,
          }}
        />
        <div
          style={{
            fontSize: sloganSize,
            fontWeight: 700,
            color: BRAND.text,
            fontFamily: FONT_SANS,
            letterSpacing: sloganSpacing,
            textShadow: `0 2px 20px ${BRAND.primaryGlow}`,
          }}
        >
          {sloganText}
        </div>
        <div
          style={{
            width: lineW,
            height: 2,
            background: `linear-gradient(90deg, ${BRAND.primary}, transparent)`,
          }}
        />
      </div>

      {/* 公司名 */}
      <div
        style={{
          transform: `translateY(${nameY}px)`,
          opacity: nameOpacity,
          fontSize: nameSize,
          fontWeight: 500,
          color: BRAND.muted,
          fontFamily: FONT_SANS,
          letterSpacing: nameSpacing,
          textTransform: lang === "en" ? "uppercase" : "none",
        }}
      >
        {nameText}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// 背景
// ---------------------------------------------------------------------------
const BackgroundFX: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = frame / durationInFrames;
  const gx = 50 + Math.sin(t * Math.PI * 2) * 12;
  const gy = 45 + Math.cos(t * Math.PI * 2) * 8;

  return (
    <>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at ${gx}% ${gy}%, ${BRAND.bg1} 0%, ${BRAND.bg0} 65%, #04080a 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(${BRAND.primarySoft} 1px, transparent 1px),
            linear-gradient(90deg, ${BRAND.primarySoft} 1px, transparent 1px)
          `,
          backgroundSize: "80px 80px",
          maskImage:
            "radial-gradient(ellipse 60% 50% at 50% 45%, black 20%, transparent 75%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 60% 50% at 50% 45%, black 20%, transparent 75%)",
        }}
      />
      <Particles />
    </>
  );
};

const Particles: React.FC = () => {
  const frame = useCurrentFrame();
  const dots = Array.from({ length: 24 }, (_, i) => ({
    id: i,
    x: (i * 83) % 100,
    baseY: (i * 37) % 100,
    size: 1.5 + (i % 5),
    speed: 0.1 + (i % 6) * 0.06,
    phase: (i * 19) % 70,
  }));

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {dots.map((d) => {
        const y =
          (((d.baseY + (frame + d.phase) * d.speed) % 110) + 110) % 110 - 5;
        const twinkle = 0.12 + Math.sin((frame + d.phase) / 28) * 0.18;
        return (
          <div
            key={d.id}
            style={{
              position: "absolute",
              left: `${d.x}%`,
              top: `${y}%`,
              width: d.size,
              height: d.size,
              borderRadius: "50%",
              background: BRAND.primaryBright,
              opacity: twinkle,
              filter: "blur(1px)",
              boxShadow: `0 0 ${d.size * 2}px ${BRAND.primary}`,
            }}
          />
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------------------
// 分隔线
// ---------------------------------------------------------------------------
const DividerLine: React.FC<{ startFrame: number }> = ({ startFrame }) => {
  const frame = useCurrentFrame();
  const width = interpolate(frame, [startFrame, startFrame + 25], [0, 220], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.ease),
  });
  const opacity = interpolate(frame, [startFrame, startFrame + 15], [0, 0.5], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "relative",
        zIndex: 2,
        width,
        height: 1,
        background: `linear-gradient(90deg, transparent, ${BRAND.primary}, transparent)`,
        opacity,
      }}
    />
  );
};

// ---------------------------------------------------------------------------
// 主组件
// ---------------------------------------------------------------------------
export const LogoAnimationMain: React.FC<{
  lang?: "zh" | "en";
  voiceStartFrame?: number;
  voiceDurationFrames?: number;
}> = ({ lang = "zh", voiceStartFrame = 96, voiceDurationFrames = 96 }) => {
  const { durationInFrames } = useVideoConfig();

  // 语音从视频第 0 帧就开始播（audio 已剪去头尾静音）
  // 所有画面以此为基准对位
  const voiceStart = 0; // 语音开始帧

  // 字比声早一点点（8 帧 ≈ 0.27s）出来，话音跟上
  const nameAppear = voiceStart + VOICE_NAME_START - 8;
  const sloganAppear = voiceStart + VOICE_SLOGAN_START - 12;

  // 回旋：语音结束前 12 帧启动，话音落时 logo 刚好回 ||
  const backStart = Math.max(
    T_TOEQ_HOLD + 8,
    voiceStart + VOICE_TOTAL - MORPH_BACK_DUR + 6
  );

  const voiceSrc =
    lang === "zh" ? "voice-logo-zh-clean.mp3" : "voice-logo-en.mp3";

  return (
    <AbsoluteFill
      style={{
        fontFamily: FONT_SANS,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
      }}
    >
      {/* 人声 - 从第 0 帧开始，完整播放 */}
      <Audio src={staticFile(voiceSrc)} volume={1} />

      <BackgroundFX />

      {/* 上半区：Logo */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          width: "100%",
          height: "55%",
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "center",
          paddingBottom: 32,
        }}
      >
        <MorphLogo
          backStartFrame={backStart}
          totalFrames={durationInFrames}
        />
      </div>

      <DividerLine startFrame={sloganAppear} />

      {/* 下半区：文字 — 字先到，声后到，每句对位 */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          width: "100%",
          flex: 1,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
          paddingTop: 32,
        }}
      >
        <BrandText
          lang={lang}
          sloganStartFrame={sloganAppear}
          nameStartFrame={nameAppear}
        />
      </div>
    </AbsoluteFill>
  );
};

// 时长：中文 ~5.8s，英文 ~7.0s
export const LOGO_DURATION_ZH = 120; // 4.0s @ 30fps
export const LOGO_DURATION_EN = 150; // 5.0s @ 30fps
export const LOGO_VIDEO = { ...VIDEO };

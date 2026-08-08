// Shared UI primitives + background + overlays for the introduce videos.
// Motion rules (per remotion-markup skill): interpolate() + Easing.bezier(),
// inline in style, scale/translate/rotate shorthands. No CSS animations,
// no Tailwind animation classes.

import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { COLORS, EASE_OUT, FONT_MONO } from "./theme";

// ---------------------------------------------------------------------------
// Timing helpers
// ---------------------------------------------------------------------------

// Opacity window for a "phase" that is fully visible during [a, b] with 15f
// crossfades on either side. Use to swap body content over time inside a scene.
export const phaseVis = (frame: number, a: number, b: number) =>
  interpolate(frame, [a - 15, a, b, b + 15], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

// Count a number up from 0 -> target across [delay, delay+duration].
export const useCountUp = (
  target: number,
  delay = 0,
  duration = 30
): number => {
  const frame = useCurrentFrame();
  const v = interpolate(frame, [delay, delay + duration], [0, target], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(...EASE_OUT),
  });
  return Math.round(v);
};

export const fmt = (n: number): string => n.toLocaleString("en-US");

// ---------------------------------------------------------------------------
// Animation wrappers
// ---------------------------------------------------------------------------

export const FadeUp: React.FC<{
  children: React.ReactNode;
  delay?: number;
  duration?: number;
  y?: number;
  style?: React.CSSProperties;
}> = ({ children, delay = 0, duration = 18, y = 28, style }) => {
  const frame = useCurrentFrame();
  const e = Easing.bezier(...EASE_OUT);
  const opacity = interpolate(frame, [delay, delay + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: e,
  });
  const ty = interpolate(frame, [delay, delay + duration], [y, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: e,
  });
  return (
    <div style={{ opacity, translate: `0px ${ty}px`, ...style }}>{children}</div>
  );
};

// Typewriter: reveals `text` character-by-character from `start` frame.
export const Typewriter: React.FC<{
  text: string;
  start?: number;
  speed?: number;
  cursor?: boolean;
  style?: React.CSSProperties;
}> = ({ text, start = 0, speed = 1.3, cursor = true, style }) => {
  const frame = useCurrentFrame();
  const count = Math.max(0, Math.floor((frame - start) * speed));
  const shown = text.slice(0, Math.min(count, text.length));
  const done = count >= text.length;
  // Frame-driven blink (deterministic, renders correctly).
  const cursorOpacity = done
    ? Math.floor(frame / 14) % 2 === 0
      ? 1
      : 0.25
    : 1;
  return (
    <span style={style}>
      {shown}
      {cursor && (
        <span style={{ opacity: cursorOpacity, color: COLORS.green }}>▋</span>
      )}
    </span>
  );
};

// ---------------------------------------------------------------------------
// Surfaces
// ---------------------------------------------------------------------------

const Dot: React.FC<{ color: string }> = ({ color }) => (
  <span
    style={{
      width: 12,
      height: 12,
      borderRadius: 6,
      background: color,
      display: "inline-block",
    }}
  />
);

export const Terminal: React.FC<{
  title?: string;
  children: React.ReactNode;
  fontSize?: number;
  style?: React.CSSProperties;
}> = ({ title = "bash", children, fontSize = 30, style }) => (
  <div
    style={{
      background: COLORS.surface,
      border: `1px solid ${COLORS.border}`,
      borderRadius: 16,
      overflow: "hidden",
      boxShadow: "0 30px 80px rgba(0,0,0,0.55)",
      ...style,
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "12px 18px",
        borderBottom: `1px solid ${COLORS.border}`,
        background: "#010409",
      }}
    >
      <Dot color="#ff5f56" />
      <Dot color="#ffbd2e" />
      <Dot color="#27c93f" />
      <span
        style={{
          marginLeft: 10,
          fontFamily: FONT_MONO,
          fontSize: 15,
          color: COLORS.muted,
        }}
      >
        {title}
      </span>
    </div>
    <div
      style={{
        padding: "22px 26px",
        fontFamily: FONT_MONO,
        color: COLORS.text,
        fontSize,
        lineHeight: 1.7,
      }}
    >
      {children}
    </div>
  </div>
);

export const Card: React.FC<{
  children: React.ReactNode;
  delay?: number;
  accent?: string;
  style?: React.CSSProperties;
}> = ({ children, delay = 0, accent = COLORS.blue, style }) => {
  const frame = useCurrentFrame();
  const e = Easing.bezier(...EASE_OUT);
  const scale = interpolate(frame, [delay, delay + 22], [0.92, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: e,
  });
  return (
    <FadeUp
      delay={delay}
      duration={22}
      style={{
        background: COLORS.surface,
        border: `1px solid ${COLORS.border}`,
        borderLeft: `4px solid ${accent}`,
        borderRadius: 18,
        padding: "30px 34px",
        boxShadow: "0 20px 50px rgba(0,0,0,0.4)",
        scale,
        ...style,
      }}
    >
      {children}
    </FadeUp>
  );
};

export const CardTitle: React.FC<{ n?: string; t: string; c?: string }> = ({
  n,
  t,
  c = COLORS.green,
}) => (
  <div
    style={{
      display: "flex",
      alignItems: "baseline",
      gap: 14,
      marginBottom: 14,
    }}
  >
    {n && (
      <span style={{ fontFamily: FONT_MONO, fontSize: 34, color: c }}>{n}</span>
    )}
    <span style={{ fontSize: 30, fontWeight: 700, color: COLORS.text }}>{t}</span>
  </div>
);

export const Stat: React.FC<{
  value: string;
  label: string;
  color?: string;
  delay?: number;
}> = ({ value, label, color = COLORS.blue, delay = 0 }) => (
  <FadeUp
    delay={delay}
    style={{
      textAlign: "center",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
    }}
  >
    <div
      style={{
        fontFamily: FONT_MONO,
        fontSize: 96,
        fontWeight: 700,
        color,
        lineHeight: 1,
        letterSpacing: "-0.02em",
      }}
    >
      {value}
    </div>
    <div style={{ fontSize: 26, color: COLORS.muted, marginTop: 14 }}>
      {label}
    </div>
  </FadeUp>
);

export const Chip: React.FC<{
  children: React.ReactNode;
  color?: string;
  delay?: number;
  style?: React.CSSProperties;
}> = ({ children, color = COLORS.blue, delay = 0, style }) => (
  <FadeUp
    delay={delay}
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 8,
      padding: "10px 18px",
      borderRadius: 999,
      background: COLORS.surface,
      border: `1px solid ${COLORS.border}`,
      fontSize: 24,
      color: COLORS.text,
      ...style,
    }}
  >
    <span
      style={{ width: 8, height: 8, borderRadius: 4, background: color }}
    />
    {children}
  </FadeUp>
);

export const Pill: React.FC<{
  children: React.ReactNode;
  color?: string;
  delay?: number;
}> = ({ children, color = COLORS.green, delay = 0 }) => (
  <FadeUp
    delay={delay}
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      padding: "14px 24px",
      borderRadius: 12,
      background: `${color}1a`,
      border: `1px solid ${color}55`,
      fontSize: 26,
      color,
    }}
  >
    {children}
  </FadeUp>
);

// ---------------------------------------------------------------------------
// Shared scene helpers (used across pain + CTA scenes)
// ---------------------------------------------------------------------------

export const PainItem: React.FC<{
  text: string;
  delay?: number;
}> = ({ text, delay = 0 }) => (
  <FadeUp
    delay={delay}
    style={{ display: "flex", alignItems: "center", gap: 24, maxWidth: 1300 }}
  >
    <span
      style={{
        fontFamily: FONT_MONO,
        fontSize: 40,
        color: COLORS.red,
        width: 48,
        flexShrink: 0,
      }}
    >
      ✗
    </span>
    <span style={{ fontSize: 34, color: COLORS.text, lineHeight: 1.5 }}>
      {text}
    </span>
  </FadeUp>
);

export const InfoRow: React.FC<{ k: string; v: string }> = ({ k, v }) => (
  <div
    style={{
      display: "flex",
      gap: 14,
      alignItems: "baseline",
      marginTop: 12,
      lineHeight: 1.4,
    }}
  >
    <span
      style={{ color: COLORS.dim, width: 70, flexShrink: 0, fontSize: 24 }}
    >
      {k}
    </span>
    <span style={{ color: COLORS.text, fontFamily: FONT_MONO, fontSize: 22 }}>
      {v}
    </span>
  </div>
);

export const CTAItem: React.FC<{
  icon: string;
  text: string;
  color: string;
  delay?: number;
}> = ({ icon, text, color, delay = 0 }) => (
  <FadeUp
    delay={delay}
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 12,
      fontSize: 28,
      color: COLORS.text,
    }}
  >
    <span style={{ color, fontSize: 30 }}>{icon}</span>
    {text}
  </FadeUp>
);

// ---------------------------------------------------------------------------
// Background + persistent overlays (use GLOBAL frame -> render at main level)
// ---------------------------------------------------------------------------

export const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 120], [0, 44], {
    extrapolateRight: "extend",
    easing: Easing.linear,
  });
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(130% 110% at 50% -10%, ${COLORS.bg1} 0%, ${COLORS.bg0} 65%)`,
      }}
    >
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(${COLORS.border}55 1.2px, transparent 1.2px)`,
          backgroundSize: "44px 44px",
          backgroundPosition: `0px ${drift}px`,
          opacity: 0.5,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(100% 90% at 50% 50%, transparent 55%, ${COLORS.bg0} 100%)`,
          opacity: 0.7,
        }}
      />
    </AbsoluteFill>
  );
};

export const Overlays: React.FC<{
  durationInFrames: number;
  accent?: string;
}> = ({ durationInFrames, accent = COLORS.green }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const brandOpacity = interpolate(frame, [0, 25], [0, 0.85], {
    extrapolateRight: "clamp",
  });
  return (
    <>
      <div
        style={{
          position: "absolute",
          top: 34,
          right: 50,
          fontFamily: FONT_MONO,
          fontSize: 18,
          color: COLORS.dim,
          opacity: brandOpacity,
          letterSpacing: "0.04em",
        }}
      >
        <span style={{ color: accent }}>⬢</span> FindDataOfficial
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 4,
          background: "rgba(255,255,255,0.05)",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${p * 100}%`,
            background: `linear-gradient(90deg, ${COLORS.green}, ${COLORS.blue})`,
          }}
        />
      </div>
    </>
  );
};

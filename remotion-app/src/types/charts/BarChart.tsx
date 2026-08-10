import { COLORS, FONT_SANS, FONT_MONO } from "../../theme";

/**
 * BarChart - 柱状生长图
 *
 * 纯展示组件：progress 0→1 时柱子从 0 长到满高，数值随进度累加。
 * 配色只取 theme.ts COLORS；多柱用 PALETTE 轮转。
 */
export type BarChartProps = {
  labels: string[];
  values: number[];
  unit?: string;
  progress: number; // 0..1
  title?: string;
};

const PALETTE = [
  COLORS.green,
  COLORS.blue,
  COLORS.purple,
  COLORS.orange,
  COLORS.cyan,
  COLORS.red,
];

const VB_W = 1000;
const VB_H = 600;
const PAD = { top: 70, right: 40, bottom: 80, left: 90 };

export const BarChart: React.FC<BarChartProps> = ({
  labels,
  values,
  unit = "",
  progress,
  title,
}) => {
  const chartW = VB_W - PAD.left - PAD.right;
  const chartH = VB_H - PAD.top - PAD.bottom;
  const maxVal = Math.max(...values, 1);
  const barSlot = chartW / values.length;
  const barW = barSlot * 0.55;

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${VB_H}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ width: "100%", height: "100%" }}
    >
      {title ? (
        <text
          x={VB_W / 2}
          y={40}
          textAnchor="middle"
          fontSize={32}
          fontWeight={700}
          fill={COLORS.text}
          fontFamily={FONT_SANS}
        >
          {title}
        </text>
      ) : null}

      {/* gridlines + y-axis ticks */}
      {[0, 0.25, 0.5, 0.75, 1].map((f, i) => {
        const y = VB_H - PAD.bottom - f * chartH;
        return (
          <g key={i}>
            <line
              x1={PAD.left}
              y1={y}
              x2={VB_W - PAD.right}
              y2={y}
              stroke={COLORS.surface2}
              strokeWidth={1}
              strokeDasharray="4 4"
            />
            <text
              x={PAD.left - 12}
              y={y + 6}
              textAnchor="end"
              fontSize={20}
              fill={COLORS.muted}
              fontFamily={FONT_MONO}
            >
              {Math.round(maxVal * f)}
              {unit}
            </text>
          </g>
        );
      })}

      {/* baseline */}
      <line
        x1={PAD.left}
        y1={VB_H - PAD.bottom}
        x2={VB_W - PAD.right}
        y2={VB_H - PAD.bottom}
        stroke={COLORS.border}
        strokeWidth={2}
      />

      {/* bars */}
      {values.map((v, i) => {
        const fullH = (v / maxVal) * chartH;
        const h = fullH * progress;
        const y = VB_H - PAD.bottom - h;
        const x = PAD.left + barSlot * i + (barSlot - barW) / 2;
        const color = PALETTE[i % PALETTE.length];
        return (
          <g key={i}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={Math.max(0, h)}
              rx={6}
              fill={color}
            />
            <text
              x={x + barW / 2}
              y={y - 12}
              textAnchor="middle"
              fontSize={24}
              fontWeight={700}
              fill={COLORS.text}
              fontFamily={FONT_MONO}
            >
              {Math.round(v * progress)}
              {unit}
            </text>
            <text
              x={x + barW / 2}
              y={VB_H - PAD.bottom + 28}
              textAnchor="middle"
              fontSize={22}
              fill={COLORS.muted}
              fontFamily={FONT_SANS}
            >
              {labels[i]}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

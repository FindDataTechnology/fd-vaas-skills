import { COLORS, FONT_SANS, FONT_MONO } from "../../theme";

/**
 * PieChart - 环形展开图（donut）
 *
 * 纯展示组件：progress 0→1 时饼图从顶部顺时针展开（wipe reveal），
 * 到位后显示标签与百分比，中心显示总量。配色只取 theme.ts COLORS。
 */
export type PieChartProps = {
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

/** 极坐标→直角坐标（0°=顶部，顺时针） */
function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.sin(rad), y: cy - r * Math.cos(rad) };
}

/** donut 切片 SVG path */
function donutSlice(
  cx: number,
  cy: number,
  rOuter: number,
  rInner: number,
  startAngle: number,
  endAngle: number,
) {
  const p1 = polar(cx, cy, rOuter, startAngle);
  const p2 = polar(cx, cy, rOuter, endAngle);
  const p3 = polar(cx, cy, rInner, endAngle);
  const p4 = polar(cx, cy, rInner, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return [
    `M ${p1.x} ${p1.y}`,
    `A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${p2.x} ${p2.y}`,
    `L ${p3.x} ${p3.y}`,
    `A ${rInner} ${rInner} 0 ${largeArc} 0 ${p4.x} ${p4.y}`,
    "Z",
  ].join(" ");
}

export const PieChart: React.FC<PieChartProps> = ({
  labels,
  values,
  unit = "",
  progress,
  title,
}) => {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  const cx = VB_W / 2;
  const cy = VB_H / 2 + 10;
  const rOuter = 200;
  const rInner = 120;

  // 累计角度
  let acc = 0;
  const slices = values.map((v, i) => {
    const startAngle = (acc / total) * 360;
    acc += v;
    const endAngle = (acc / total) * 360;
    return {
      startAngle,
      endAngle,
      value: v,
      label: labels[i],
      color: PALETTE[i % PALETTE.length],
      pct: (v / total) * 100,
    };
  });

  const revealAngle = progress * 360;

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

      {slices.map((s, i) => {
        if (s.startAngle >= revealAngle) return null;
        const drawnEnd = Math.min(s.endAngle, revealAngle);
        const path = donutSlice(cx, cy, rOuter, rInner, s.startAngle, drawnEnd);
        const midAngle = (s.startAngle + s.endAngle) / 2;
        const labelPos = polar(cx, cy, rOuter + 36, midAngle);
        const showLabel = progress >= 0.99;
        return (
          <g key={i}>
            <path
              d={path}
              fill={s.color}
              stroke={COLORS.bg0}
              strokeWidth={2}
            />
            {showLabel ? (
              <>
                <text
                  x={labelPos.x}
                  y={labelPos.y}
                  textAnchor="middle"
                  dy="0.35em"
                  fontSize={22}
                  fontWeight={700}
                  fill={COLORS.text}
                  fontFamily={FONT_SANS}
                >
                  {s.label}
                </text>
                <text
                  x={labelPos.x}
                  y={labelPos.y + 26}
                  textAnchor="middle"
                  fontSize={20}
                  fill={COLORS.muted}
                  fontFamily={FONT_MONO}
                >
                  {Math.round(s.pct)}
                  {unit}
                </text>
              </>
            ) : null}
          </g>
        );
      })}

      {/* 中心总量 */}
      {progress >= 0.5 ? (
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          dy="0.35em"
          fontSize={40}
          fontWeight={900}
          fill={COLORS.text}
          fontFamily={FONT_MONO}
          opacity={Math.min(1, (progress - 0.5) * 4)}
        >
          {total}
          {unit}
        </text>
      ) : null}
    </svg>
  );
};

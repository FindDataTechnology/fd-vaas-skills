import { COLORS, FONT_SANS, FONT_MONO } from "../../theme";

/**
 * LineChart - 折线描画图
 *
 * 纯展示组件：progress 0→1 时折线从左描到右（pathLength + dashoffset），
 * 数据点随进度逐个亮起。多 series 各自带色。
 * 配色只取 theme.ts COLORS。
 */
export type LineSeries = {
  name: string;
  values: number[];
  color: string;
};

export type LineChartProps = {
  labels: string[];
  series: LineSeries[];
  unit?: string;
  progress: number; // 0..1
  title?: string;
};

const VB_W = 1000;
const VB_H = 600;
const PAD = { top: 70, right: 40, bottom: 80, left: 90 };

export const LineChart: React.FC<LineChartProps> = ({
  labels,
  series,
  unit = "",
  progress,
  title,
}) => {
  const chartW = VB_W - PAD.left - PAD.right;
  const chartH = VB_H - PAD.top - PAD.bottom;
  const allVals = series.flatMap((s) => s.values);
  const maxVal = Math.max(...allVals, 1);
  const n = labels.length;
  const xStep = n > 1 ? chartW / (n - 1) : 0;

  const pointX = (i: number) => PAD.left + xStep * i;
  const pointY = (v: number) => VB_H - PAD.bottom - (v / maxVal) * chartH;

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

      {/* gridlines */}
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

      {/* x-axis labels */}
      {labels.map((label, i) => (
        <text
          key={i}
          x={pointX(i)}
          y={VB_H - PAD.bottom + 28}
          textAnchor="middle"
          fontSize={20}
          fill={COLORS.muted}
          fontFamily={FONT_SANS}
        >
          {label}
        </text>
      ))}

      {/* series: draw-on line + points */}
      {series.map((s, si) => {
        const pts = s.values.map((v, i) => `${pointX(i)},${pointY(v)}`).join(" ");
        return (
          <g key={si}>
            <polyline
              points={pts}
              fill="none"
              stroke={s.color}
              strokeWidth={4}
              strokeLinecap="round"
              strokeLinejoin="round"
              pathLength={100}
              strokeDasharray={100}
              strokeDashoffset={100 * (1 - progress)}
            />
            {s.values.map((v, i) => {
              const ptProgress = n > 1 ? i / (n - 1) : 1;
              const visible = progress >= ptProgress ? 1 : 0;
              return (
                <circle
                  key={i}
                  cx={pointX(i)}
                  cy={pointY(v)}
                  r={6}
                  fill={COLORS.bg0}
                  stroke={s.color}
                  strokeWidth={3}
                  opacity={visible}
                />
              );
            })}
          </g>
        );
      })}

      {/* legend */}
      {series.map((s, si) => (
        <g
          key={`leg-${si}`}
          transform={`translate(${PAD.left + si * 220}, ${VB_H - 18})`}
        >
          <rect x={0} y={-14} width={16} height={16} rx={3} fill={s.color} />
          <text
            x={24}
            y={0}
            fontSize={20}
            fill={COLORS.text}
            fontFamily={FONT_SANS}
          >
            {s.name}
          </text>
        </g>
      ))}
    </svg>
  );
};

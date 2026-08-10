import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { spring, interpolate } from "remotion";
import { COLORS, FONT_SANS, FONT_MONO } from "../theme";
import { useJsonFile, scaleFor, Subtitles, type SceneAlignScene } from "./shared";
import type { Caption } from "@remotion/captions";
import { BarChart } from "./charts/BarChart";
import { LineChart } from "./charts/LineChart";
import { PieChart } from "./charts/PieChart";

/**
 * DataVizVideo - 数据可视化讲解
 *
 * 固定结构：标题卡(hook) -> 图表卡×N -> CTA。图表数与口播段数由
 * validate-data 步骤在渲染前校验。data.json 提供 title / charts / source。
 * 每个图表场景的进度动画占段帧的 40%（生长/描画/展开），到位后静止配合口播。
 */
export type DataVizVideoProps = {
  audioSrc: string;
  captionsSrc: string;
  scenesSrc: string;
  dataSrc: string;
  durationInFrames: number;
  width?: number;
  height?: number;
  accentColor?: string;
  bgColor?: string;
  textColor?: string;
  subtitleColor?: string;
  subtitleSize?: number;
  baseSize?: number;
};

const DEFAULTS = {
  width: 1080,
  height: 1920,
  accentColor: COLORS.cyan,
  bgColor: COLORS.bg0,
  textColor: "#ffffff",
  subtitleColor: COLORS.green,
  subtitleSize: 64,
  baseSize: 64,
};

type Chart = {
  type: "bar" | "line" | "pie";
  title?: string;
  labels?: string[];
  values?: number[];
  series?: { name: string; values: number[]; color?: string }[];
  unit?: string;
};

type DataVizData = {
  title: string;
  charts: Chart[];
  source?: string;
};

// 多 series 默认配色轮转，全部取自 theme.ts COLORS。
const SERIES_PALETTE = [
  COLORS.green,
  COLORS.blue,
  COLORS.purple,
  COLORS.orange,
  COLORS.cyan,
  COLORS.red,
];

const Card: React.FC<{
  children: React.ReactNode;
  bgColor: string;
  durationInFrames: number;
}> = ({ children, bgColor, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({
    frame,
    fps,
    config: { damping: 200 },
    durationInFrames: 12,
  });
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const ty = interpolate(enter, [0, 1], [40, 0]);
  const exitStart = Math.max(0, durationInFrames - 8);
  const exitOpacity =
    frame < exitStart
      ? 1
      : interpolate(frame, [exitStart, durationInFrames], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: bgColor,
        opacity: opacity * exitOpacity,
        transform: `translateY(${ty}px)`,
        fontFamily: FONT_SANS,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

/** 单个图表场景：进度动画占段帧 40%，到位后静止。 */
const ChartScene: React.FC<{
  chart: Chart;
  sceneFrames: number;
}> = ({ chart, sceneFrames }) => {
  const frame = useCurrentFrame();
  const growFrames = Math.max(1, Math.round(sceneFrames * 0.4));
  const progress = interpolate(frame, [0, growFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const wrapStyle: React.CSSProperties = {
    position: "absolute",
    left: "6%",
    right: "6%",
    top: "10%",
    bottom: "14%",
  };

  if (chart.type === "line") {
    const series = (chart.series ?? []).map((s, i) => ({
      name: s.name,
      values: s.values,
      color: s.color || SERIES_PALETTE[i % SERIES_PALETTE.length],
    }));
    return (
      <div style={wrapStyle}>
        <LineChart
          labels={chart.labels ?? []}
          series={series}
          unit={chart.unit}
          progress={progress}
          title={chart.title}
        />
      </div>
    );
  }

  if (chart.type === "pie") {
    return (
      <div style={wrapStyle}>
        <PieChart
          labels={chart.labels ?? []}
          values={chart.values ?? []}
          unit={chart.unit}
          progress={progress}
          title={chart.title}
        />
      </div>
    );
  }

  // bar
  return (
    <div style={wrapStyle}>
      <BarChart
        labels={chart.labels ?? []}
        values={chart.values ?? []}
        unit={chart.unit}
        progress={progress}
        title={chart.title}
      />
    </div>
  );
};

const DataVizVideoComp: React.FC<DataVizVideoProps> = (rawProps) => {
  const props = { ...DEFAULTS, ...rawProps };
  const scenes = useJsonFile<SceneAlignScene[]>(props.scenesSrc);
  const captions = useJsonFile<Caption[]>(props.captionsSrc);
  const data = useJsonFile<DataVizData>(props.dataSrc);
  const scale = scaleFor(props.width ?? DEFAULTS.width);
  const baseSize = (props.baseSize ?? DEFAULTS.baseSize) * scale;

  if (!scenes || !captions || !data) return null;

  const hasCta =
    scenes.length >= 2 && scenes[scenes.length - 1].role === "cta";

  return (
    <AbsoluteFill style={{ backgroundColor: props.bgColor, fontFamily: FONT_SANS }}>
      {scenes.map((scene, i) => {
        const isHook = i === 0;
        const isCta = hasCta && i === scenes.length - 1;
        const chartIdx = i - 1;
        const chart =
          !isHook && !isCta && chartIdx >= 0 && chartIdx < data.charts.length
            ? data.charts[chartIdx]
            : null;

        return (
          <Sequence
            key={i}
            from={scene.from}
            durationInFrames={scene.durationInFrames}
            name={isHook ? "hook" : isCta ? "cta" : `chart-${chartIdx + 1}`}
          >
            <Card bgColor={props.bgColor} durationInFrames={scene.durationInFrames}>
              {isHook ? (
                <AbsoluteFill
                  style={{
                    justifyContent: "center",
                    alignItems: "center",
                    padding: 60,
                    borderTop: `12px solid ${props.accentColor}`,
                  }}
                >
                  <div
                    style={{
                      fontSize: 56 * scale,
                      fontWeight: 900,
                      color: props.accentColor,
                      letterSpacing: 8,
                      fontFamily: FONT_MONO,
                      marginBottom: 32,
                    }}
                  >
                    数据
                  </div>
                  <div
                    style={{
                      fontSize: baseSize * 1.1,
                      fontWeight: 800,
                      color: props.textColor,
                      textAlign: "center",
                      lineHeight: 1.35,
                      textShadow: "0 2px 12px rgba(0,0,0,0.6)",
                    }}
                  >
                    {data.title}
                  </div>
                  {data.source ? (
                    <div
                      style={{
                        position: "absolute",
                        bottom: 220,
                        fontSize: 30 * scale,
                        color: COLORS.muted,
                      }}
                    >
                      来源：{data.source}
                    </div>
                  ) : null}
                </AbsoluteFill>
              ) : isCta ? (
                <AbsoluteFill
                  style={{
                    justifyContent: "center",
                    alignItems: "center",
                    padding: 60,
                  }}
                >
                  <div
                    style={{
                      fontSize: baseSize * 1.2,
                      fontWeight: 900,
                      color: props.accentColor,
                      textAlign: "center",
                      lineHeight: 1.35,
                    }}
                  >
                    {scene.text}
                  </div>
                </AbsoluteFill>
              ) : chart ? (
                <ChartScene chart={chart} sceneFrames={scene.durationInFrames} />
              ) : null}
            </Card>
          </Sequence>
        );
      })}

      <Audio src={staticFile(props.audioSrc)} />

      <Subtitles
        captionsSrc={props.captionsSrc}
        color={props.subtitleColor}
        size={(props.subtitleSize ?? DEFAULTS.subtitleSize) * scale}
      />
    </AbsoluteFill>
  );
};

export const DataVizVideo: React.FC<DataVizVideoProps> = (props) => (
  <DataVizVideoComp {...props} />
);

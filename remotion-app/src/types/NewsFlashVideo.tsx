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

/**
 * NewsFlashVideo - 热点速报
 *
 * 固定结构：标题卡(hook) -> 要点卡×N -> CTA。要点数与口播段数由
 * validate-structure 步骤在渲染前校验。meta.json 提供 headline / points / source。
 */
export type NewsFlashVideoProps = {
  audioSrc: string;
  captionsSrc: string;
  scenesSrc: string;
  metaSrc: string;
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
  accentColor: COLORS.red,
  bgColor: COLORS.bg0,
  textColor: "#ffffff",
  subtitleColor: COLORS.green,
  subtitleSize: 64,
  baseSize: 64,
};

type Meta = {
  headline: string;
  points: ({ text: string } | string)[];
  source?: string;
};

function pointText(p: { text: string } | string): string {
  return typeof p === "string" ? p : p?.text ?? "";
}

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
  // 退场（最后 8 帧淡出）
  const exitStart = Math.max(0, durationInFrames - 8);
  const exitOpacity =
    frame < exitStart ? 1 : interpolate(frame, [exitStart, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
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

const NewsFlashVideoComp: React.FC<NewsFlashVideoProps> = (rawProps) => {
  const props = { ...DEFAULTS, ...rawProps };
  const { fps } = useVideoConfig();
  const scenes = useJsonFile<SceneAlignScene[]>(props.scenesSrc);
  const captions = useJsonFile<Caption[]>(props.captionsSrc);
  const meta = useJsonFile<Meta>(props.metaSrc);
  const scale = scaleFor(props.width ?? DEFAULTS.width);
  const baseSize = (props.baseSize ?? DEFAULTS.baseSize) * scale;

  if (!scenes || !captions || !meta) return null;

  const hasCta =
    scenes.length >= 2 && scenes[scenes.length - 1].role === "cta";
  const pointsScenes = hasCta ? scenes.slice(1, -1) : scenes.slice(1);

  return (
    <AbsoluteFill style={{ backgroundColor: props.bgColor, fontFamily: FONT_SANS }}>
      {scenes.map((scene, i) => {
        const isHook = i === 0;
        const isCta = hasCta && i === scenes.length - 1;
        const pointIdx = isHook || isCta ? -1 : i - 1;
        const point = pointIdx >= 0 ? meta.points[pointIdx] : null;

        return (
          <Sequence
            key={i}
            from={scene.from}
            durationInFrames={scene.durationInFrames}
            name={isHook ? "headline" : isCta ? "cta" : `point-${pointIdx + 1}`}
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
                    速报
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
                    {meta.headline}
                  </div>
                  {meta.source ? (
                    <div
                      style={{
                        position: "absolute",
                        bottom: 220,
                        fontSize: 30 * scale,
                        color: COLORS.muted,
                      }}
                    >
                      来源：{meta.source}
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
              ) : (
                <AbsoluteFill
                  style={{
                    justifyContent: "center",
                    alignItems: "center",
                    padding: 60,
                  }}
                >
                  <div
                    style={{
                      fontSize: 220 * scale,
                      fontWeight: 900,
                      color: props.accentColor,
                      lineHeight: 1,
                      marginBottom: 24,
                      fontFamily: FONT_MONO,
                      opacity: 0.9,
                    }}
                  >
                    {String(pointIdx + 1).padStart(2, "0")}
                  </div>
                  <div
                    style={{
                      fontSize: baseSize,
                      fontWeight: 800,
                      color: props.textColor,
                      textAlign: "center",
                      lineHeight: 1.4,
                      maxWidth: "90%",
                    }}
                  >
                    {point ? pointText(point) : scene.text}
                  </div>
                </AbsoluteFill>
              )}
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

export const NewsFlashVideo: React.FC<NewsFlashVideoProps> = (props) => (
  <NewsFlashVideoComp {...props} />
);

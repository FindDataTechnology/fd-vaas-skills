import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { spring, interpolate } from "remotion";
import { COLORS, FONT_SANS } from "../theme";
import { useJsonFile, scaleFor, type SceneAlignScene } from "./shared";
import type { Caption } from "@remotion/captions";

/**
 * KineticQuoteVideo - 金句文字动画
 *
 * 每个口播段 = 一屏动态文字：段内逐 token（字幕时间戳）高亮，关键词恒放大变色，
 * 段入场用 spring 弹入。无图片，纯排版。关键词来自 extract-keywords 步骤。
 */
export type KineticQuoteVideoProps = {
  audioSrc: string;
  captionsSrc: string;
  scenesSrc: string;
  keywordsSrc: string;
  durationInFrames: number;
  width?: number;
  height?: number;
  textColor?: string;
  activeColor?: string;
  keywordColor?: string;
  bgColor?: string;
  baseSize?: number;
};

const DEFAULTS = {
  width: 1080,
  height: 1920,
  textColor: "#ffffff",
  activeColor: COLORS.green,
  keywordColor: COLORS.orange,
  bgColor: COLORS.bg0,
  baseSize: 72,
};

type KeywordEntry = { keyword: string | null; source: string };

function norm(s: string): string {
  return (s ?? "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

const SceneBlock: React.FC<{
  scene: SceneAlignScene;
  index: number;
  tokens: Caption[];
  keyword: string | null;
  activeColor: string;
  keywordColor: string;
  textColor: string;
  baseSize: number;
  bgColor: string;
}> = ({ scene, index, tokens, keyword, activeColor, keywordColor, textColor, baseSize, bgColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const globalMs = ((scene.from + frame) / fps) * 1000;

  // 段入场 spring
  const entrance = spring({
    frame,
    fps,
    config: { damping: 200 },
    durationInFrames: 14,
  });
  const opacity = interpolate(entrance, [0, 1], [0, 1]);
  const ty = interpolate(entrance, [0, 1], [28, 0]);

  const normKeyword = keyword ? norm(keyword) : "";

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: 60,
        backgroundColor: bgColor,
        fontFamily: FONT_SANS,
        opacity,
        transform: `translateY(${ty}px)`,
      }}
    >
      <div
        style={{
          maxWidth: "100%",
          lineHeight: 1.45,
          fontWeight: 800,
          textAlign: "center",
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "center",
          rowGap: 8,
        }}
      >
        {tokens.map((tok, i) => {
          const isActive =
            tok.fromMs <= globalMs && tok.toMs > globalMs;
          const isKeyword =
            normKeyword.length > 0 && norm(tok.text).includes(normKeyword);
          const activeScale = isActive ? 1.18 : 1;
          const kwScale = isKeyword ? 1.12 : 1;
          const color = isKeyword
            ? keywordColor
            : isActive
              ? activeColor
              : textColor;
          return (
            <span
              key={i}
              style={{
                fontSize: baseSize * activeScale * kwScale,
                color,
                margin: "0 2px",
                transition: "color 80ms linear",
                textShadow: isActive
                  ? "0 0 24px " + activeColor + "55"
                  : "0 2px 12px rgba(0,0,0,0.6)",
                whiteSpace: "pre",
              }}
            >
              {tok.text.replace(/\*/g, "")}
            </span>
          );
        })}
      </div>
      {/* 段序角标 */}
      <div
        style={{
          position: "absolute",
          top: 48,
          left: 60,
          fontSize: 28,
          fontWeight: 700,
          color: COLORS.muted,
          letterSpacing: 2,
        }}
      >
        {String(index + 1).padStart(2, "0")}
      </div>
    </AbsoluteFill>
  );
};

const KineticQuoteVideoComp: React.FC<KineticQuoteVideoProps> = (rawProps) => {
  const props = { ...DEFAULTS, ...rawProps };
  const { fps } = useVideoConfig();
  const scenes = useJsonFile<SceneAlignScene[]>(props.scenesSrc);
  const captions = useJsonFile<Caption[]>(props.captionsSrc);
  const keywords = useJsonFile<KeywordEntry[]>(props.keywordsSrc);
  const scale = scaleFor(props.width ?? DEFAULTS.width);
  const baseSize = (props.baseSize ?? DEFAULTS.baseSize) * scale;

  if (!scenes || !captions || !keywords) return null;

  return (
    <AbsoluteFill style={{ backgroundColor: props.bgColor, fontFamily: FONT_SANS }}>
      {scenes.map((scene, i) => {
        const startMs = (scene.from / fps) * 1000;
        const endMs = ((scene.from + scene.durationInFrames) / fps) * 1000;
        const toks = captions.filter(
          (t) => t.startMs >= startMs - 40 && t.startMs < endMs + 40,
        );
        const kw = keywords[i]?.keyword ?? null;
        return (
          <Sequence
            key={i}
            from={scene.from}
            durationInFrames={scene.durationInFrames}
            name={`scene-${i + 1}`}
          >
            <SceneBlock
              scene={scene}
              index={i}
              tokens={toks}
              keyword={kw}
              activeColor={props.activeColor}
              keywordColor={props.keywordColor}
              textColor={props.textColor}
              baseSize={baseSize}
              bgColor={props.bgColor}
            />
          </Sequence>
        );
      })}

      <Audio src={staticFile(props.audioSrc)} />
    </AbsoluteFill>
  );
};

export const KineticQuoteVideo: React.FC<KineticQuoteVideoProps> = (props) => (
  <KineticQuoteVideoComp {...props} />
);

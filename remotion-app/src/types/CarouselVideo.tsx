import {
  AbsoluteFill,
  Audio,
  Img,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { interpolate } from "remotion";
import { COLORS, FONT_SANS } from "../theme";
import { useJsonFile, scaleFor, Subtitles, type SceneAlignScene } from "./shared";

/**
 * CarouselVideo - 图文轮播口播视频
 *
 * 画面层：一张图对应 scene-align 的一个口播段；Ken Burns 缓推/拉 + 交叉淡入。
 * 图少于段时循环复用且相邻段不重复。字幕/配音由 shared 提供。
 * 所有数据驱动：props.scenesSrc（段表）、props.images（public 图名数组）。
 */
export type CarouselVideoProps = {
  audioSrc: string;
  captionsSrc: string;
  scenesSrc: string;
  images: string[];
  durationInFrames: number;
  width?: number;
  height?: number;
  subtitleColor?: string;
  subtitleSize?: number;
  switchEveryMs?: number;
  bgColor?: string;
  kenBurns?: boolean;
  crossfadeFrames?: number;
};

const DEFAULTS = {
  width: 1080,
  height: 1920,
  subtitleColor: COLORS.green,
  subtitleSize: 84,
  switchEveryMs: 1400,
  bgColor: COLORS.bg0,
  kenBurns: true,
  crossfadeFrames: 8,
};

/** 构造无相邻重复的段->图映射。 */
function buildImagePlan(scenes: SceneAlignScene[], images: string[]): number[] {
  const n = scenes.length;
  const m = images.length;
  if (m === 0) return [];
  if (m === 1) return scenes.map(() => 0);
  const plan: number[] = [];
  for (let i = 0; i < n; i++) {
    let idx = i % m;
    // 避免与上一段相同
    if (i > 0 && idx === plan[i - 1]) idx = (idx + 1) % m;
    plan.push(idx);
  }
  return plan;
}

const CarouselLayer: React.FC<{
  scenes: SceneAlignScene[];
  images: string[];
  durationInFrames: number;
  kenBurns: boolean;
  crossfadeFrames: number;
}> = ({ scenes, images, durationInFrames, kenBurns, crossfadeFrames }) => {
  const frame = useCurrentFrame();
  const plan = buildImagePlan(scenes, images);
  const n = scenes.length;

  return (
    <>
      {scenes.map((scene, i) => {
        const start = scene.from;
        const nextStart =
          i < n - 1 ? scenes[i + 1].from : durationInFrames;
        const isLast = i === n - 1;
        const xFade = Math.min(crossfadeFrames, Math.floor(scene.durationInFrames / 3) || 1);

        // 可见区间：延伸到下一段开始 + xFade，与下张图淡入重叠 -> 交叉淡入
        const fadeOutStart = nextStart;
        const fadeOutEnd = nextStart + xFade;

        let opacity: number;
        if (frame < start) {
          opacity = 0;
        } else if (frame < start + xFade) {
          opacity = interpolate(frame, [start, start + xFade], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
        } else if (isLast || frame < fadeOutStart) {
          opacity = 1;
        } else if (frame < fadeOutEnd) {
          opacity = interpolate(frame, [fadeOutStart, fadeOutEnd], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
        } else {
          opacity = 0;
        }

        if (opacity <= 0.001) return null;

        const img = images[plan[i] ?? 0];
        const span = Math.max(1, (isLast ? durationInFrames : fadeOutEnd) - start);
        const p = (frame - start) / span; // 0..1 进度
        const zoomIn = i % 2 === 0;
        const scale = kenBurns
          ? interpolate(
              p,
              [0, 1],
              zoomIn ? [1.06, 1.14] : [1.14, 1.06],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            )
          : 1.08;
        const tx = kenBurns
          ? interpolate(p, [0, 1], zoomIn ? [-12, 12] : [12, -12], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })
          : 0;

        return (
          <AbsoluteFill key={i} style={{ opacity }}>
            <Img
              src={staticFile(img)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: `scale(${scale}) translateX(${tx}px)`,
              }}
            />
            {/* 底部渐隐压暗，托住字幕可读性 */}
            <AbsoluteFill
              style={{
                background:
                  "linear-gradient(to bottom, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)",
              }}
            />
          </AbsoluteFill>
        );
      })}
    </>
  );
};

const CarouselVideoComp: React.FC<CarouselVideoProps> = (rawProps) => {
  const props = { ...DEFAULTS, ...rawProps };
  const scenes = useJsonFile<SceneAlignScene[]>(props.scenesSrc);

  if (!scenes) return null;

  return (
    <AbsoluteFill
      style={{ backgroundColor: props.bgColor, fontFamily: FONT_SANS }}
    >
      {props.images && props.images.length > 0 ? (
        <CarouselLayer
          scenes={scenes}
          images={props.images}
          durationInFrames={props.durationInFrames}
          kenBurns={props.kenBurns}
          crossfadeFrames={props.crossfadeFrames}
        />
      ) : null}

      <Audio src={staticFile(props.audioSrc)} />

      <Subtitles
        captionsSrc={props.captionsSrc}
        color={props.subtitleColor}
        size={props.subtitleSize * scaleFor(props.width ?? DEFAULTS.width)}
        switchEveryMs={props.switchEveryMs}
      />
    </AbsoluteFill>
  );
};

export const CarouselVideo: React.FC<CarouselVideoProps> = (props) => (
  <CarouselVideoComp {...props} />
);

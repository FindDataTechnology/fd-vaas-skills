import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { spring, interpolate } from "remotion";
import { COLORS, FONT_SANS, FONT_MONO } from "../theme";
import { useJsonFile, scaleFor, Subtitles, type SceneAlignScene } from "./shared";

/**
 * ListicleVideo - 榜单合集
 *
 * 倒数排名卡片视频：hook 大字卡 -> 条目卡×N（排名弹出动画，可选配图）-> CTA。
 * items.json 提供 title/items；条目数与口播段数由 validate-items 步骤渲染前校验。
 * 排名倒数：第 1 个条目 = rank N（最大），最后一个 = rank 1。
 */
export type ListicleVideoProps = {
  audioSrc: string;
  captionsSrc: string;
  scenesSrc: string;
  itemsSrc: string;
  itemImages?: (string | null)[];
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
  accentColor: COLORS.orange,
  bgColor: COLORS.bg0,
  textColor: "#ffffff",
  subtitleColor: COLORS.green,
  subtitleSize: 64,
  baseSize: 60,
};

type ListicleData = {
  title: string;
  items: { title: string; text?: string; image?: string }[];
  source?: string;
};

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

/** 条目卡：排名数字弹出（欠阻尼 spring，自然过冲）+ 标题/正文 + 可选配图 */
const ItemCard: React.FC<{
  rank: number;
  item: { title: string; text?: string } | null;
  fallbackText: string;
  img: string | null;
  accentColor: string;
  textColor: string;
  baseSize: number;
  scale: number;
}> = ({ rank, item, fallbackText, img, accentColor, textColor, baseSize, scale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 200 },
    durationInFrames: 18,
  });
  const rankScale = interpolate(pop, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "extend",
  });
  const rankOpacity = interpolate(pop, [0, 0.3, 1], [0, 0.7, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (img) {
    return (
      <AbsoluteFill>
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: "55%",
            overflow: "hidden",
          }}
        >
          <Img
            src={staticFile(img)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              background:
                "linear-gradient(to bottom, rgba(0,0,0,0) 40%, rgba(0,0,0,0.7) 100%)",
            }}
          />
        </div>
        <div
          style={{
            position: "absolute",
            top: 36,
            left: 40,
            transform: `scale(${rankScale})`,
            transformOrigin: "top left",
            fontSize: 140 * scale,
            fontWeight: 900,
            color: accentColor,
            fontFamily: FONT_MONO,
            lineHeight: 1,
            opacity: rankOpacity,
            textShadow: "0 4px 20px rgba(0,0,0,0.85)",
          }}
        >
          {String(rank).padStart(2, "0")}
        </div>
        <div
          style={{
            position: "absolute",
            top: "55%",
            left: 0,
            right: 0,
            bottom: 0,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            padding: 50,
          }}
        >
          <div
            style={{
              fontSize: baseSize * 1.05,
              fontWeight: 800,
              color: textColor,
              textAlign: "center",
              lineHeight: 1.4,
              marginBottom: item?.text ? 18 : 0,
            }}
          >
            {item?.title ?? fallbackText}
          </div>
          {item?.text ? (
            <div
              style={{
                fontSize: baseSize * 0.5,
                fontWeight: 500,
                color: COLORS.muted,
                textAlign: "center",
                lineHeight: 1.5,
                maxWidth: "88%",
              }}
            >
              {item.text}
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill
      style={{ justifyContent: "center", alignItems: "center", padding: 60 }}
    >
      <div
        style={{
          fontSize: 280 * scale,
          fontWeight: 900,
          color: accentColor,
          lineHeight: 1,
          marginBottom: 32,
          fontFamily: FONT_MONO,
          transform: `scale(${rankScale})`,
          opacity: rankOpacity,
        }}
      >
        {String(rank).padStart(2, "0")}
      </div>
      <div
        style={{
          fontSize: baseSize * 1.1,
          fontWeight: 800,
          color: textColor,
          textAlign: "center",
          lineHeight: 1.4,
          maxWidth: "90%",
          marginBottom: item?.text ? 20 : 0,
        }}
      >
        {item?.title ?? fallbackText}
      </div>
      {item?.text ? (
        <div
          style={{
            fontSize: baseSize * 0.5,
            fontWeight: 500,
            color: COLORS.muted,
            textAlign: "center",
            lineHeight: 1.5,
            maxWidth: "88%",
          }}
        >
          {item.text}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const ListicleVideoComp: React.FC<ListicleVideoProps> = (rawProps) => {
  const props = { ...DEFAULTS, ...rawProps };
  const scenes = useJsonFile<SceneAlignScene[]>(props.scenesSrc);
  const data = useJsonFile<ListicleData>(props.itemsSrc);
  const scale = scaleFor(props.width ?? DEFAULTS.width);
  const baseSize = (props.baseSize ?? DEFAULTS.baseSize) * scale;

  if (!scenes || !data) return null;

  const hasCta =
    scenes.length >= 2 && scenes[scenes.length - 1].role === "cta";
  const itemCount = data.items.length;

  return (
    <AbsoluteFill
      style={{ backgroundColor: props.bgColor, fontFamily: FONT_SANS }}
    >
      {scenes.map((scene, i) => {
        const isHook = i === 0;
        const isCta = hasCta && i === scenes.length - 1;
        const itemIdx = isHook || isCta ? -1 : i - 1;
        const item = itemIdx >= 0 ? data.items[itemIdx] : null;
        const rank = itemIdx >= 0 ? itemCount - itemIdx : 0;
        const img =
          itemIdx >= 0 && props.itemImages
            ? props.itemImages[itemIdx] ?? null
            : null;

        return (
          <Sequence
            key={i}
            from={scene.from}
            durationInFrames={scene.durationInFrames}
            name={isHook ? "hook" : isCta ? "cta" : `item-rank-${rank}`}
          >
            <Card bgColor={props.bgColor} durationInFrames={scene.durationInFrames}>
              {isHook ? (
                <AbsoluteFill
                  style={{
                    justifyContent: "center",
                    alignItems: "center",
                    padding: 60,
                  }}
                >
                  <div
                    style={{
                      fontSize: 48 * scale,
                      fontWeight: 700,
                      color: props.accentColor,
                      letterSpacing: 6,
                      fontFamily: FONT_MONO,
                      marginBottom: 24,
                    }}
                  >
                    榜单
                  </div>
                  <div
                    style={{
                      fontSize: baseSize * 1.3,
                      fontWeight: 900,
                      color: props.textColor,
                      textAlign: "center",
                      lineHeight: 1.3,
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
              ) : (
                <ItemCard
                  rank={rank}
                  item={item}
                  fallbackText={scene.text}
                  img={img}
                  accentColor={props.accentColor ?? DEFAULTS.accentColor}
                  textColor={props.textColor ?? DEFAULTS.textColor}
                  baseSize={baseSize}
                  scale={scale}
                />
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

export const ListicleVideo: React.FC<ListicleVideoProps> = (props) => (
  <ListicleVideoComp {...props} />
);

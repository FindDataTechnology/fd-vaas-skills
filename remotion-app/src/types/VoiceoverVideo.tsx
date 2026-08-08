import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  staticFile,
  useCurrentFrame,
  useDelayRender,
  useVideoConfig,
  Video,
} from "remotion";
import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption, TikTokPage } from "@remotion/captions";
import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * VoiceoverVideo — 参数化口播视频合成
 *
 * 由 --props 驱动,无需为每条视频改 React。
 * 三层:画面(视频/图片/轮播,静音)+ 配音 + TikTok 风逐字高亮字幕。
 *
 * 注册见 references/setup.md。props 字段见 SKILL.md 的渲染表。
 */
export type VoiceoverVideoProps = {
  audioSrc: string;
  captionsSrc: string;
  durationInFrames: number;
  width?: number;
  height?: number;
  // 视觉层三选一
  videoSrc?: string;
  imageSrc?: string;
  images?: string[];
  // 封面(可选):前 coverFrames 帧显示 coverImage,静音无字幕
  coverImage?: string;
  coverFrames?: number;
  // 字幕样式
  subtitleColor?: string;
  subtitleSize?: number;
  switchEveryMs?: number;
  bgColor?: string;
};

const DEFAULTS = {
  width: 1080,
  height: 1920,
  subtitleColor: "#39E508",
  subtitleSize: 90,
  switchEveryMs: 1400,
  bgColor: "#0a0e14",
  coverFrames: 60,
};

const CaptionPage: React.FC<{
  page: TikTokPage;
  color: string;
  size: number;
}> = ({ page, color, size }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTimeMs = (frame / fps) * 1000;
  const absoluteTimeMs = page.startMs + currentTimeMs;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: 40,
      }}
    >
      <div
        style={{
          fontSize: size,
          fontWeight: 800,
          color: "#ffffff",
          whiteSpace: "pre",
          textAlign: "center",
          lineHeight: 1.3,
          textShadow:
            "0 4px 16px rgba(0,0,0,0.85), 0 0 6px rgba(0,0,0,0.95)",
        }}
      >
        {page.tokens.map((token, i) => {
          const isActive =
            token.fromMs <= absoluteTimeMs && token.toMs > absoluteTimeMs;
          return (
            <span key={i} style={{ color: isActive ? color : "#ffffff" }}>
              {token.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const VoiceoverVideoComp: React.FC<VoiceoverVideoProps> = (rawProps) => {
  const props = { ...DEFAULTS, ...rawProps };
  const { fps } = useVideoConfig();

  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const { delayRender, continueRender, cancelRender } = useDelayRender();
  const [handle] = useState(() => delayRender("loading captions"));

  const fetchCaptions = useCallback(async () => {
    try {
      const res = await fetch(staticFile(props.captionsSrc));
      const data = (await res.json()) as Caption[];
      setCaptions(data);
      continueRender(handle);
    } catch (e) {
      cancelRender(e instanceof Error ? e : new Error(String(e)));
    }
  }, [props.captionsSrc, continueRender, cancelRender, handle]);

  useEffect(() => {
    fetchCaptions();
  }, [fetchCaptions]);

  const pages = useMemo(() => {
    if (!captions) return [];
    const { pages: p } = createTikTokStyleCaptions({
      captions,
      combineTokensWithinMilliseconds: props.switchEveryMs,
    });
    return p;
  }, [captions, props.switchEveryMs]);

  // 图片轮播:等分时长,最后一张吃掉余数
  const imgCount = props.images?.length ?? 0;
  const slideFrames =
    imgCount > 0 ? Math.floor(props.durationInFrames / imgCount) : 0;

  // 封面:coverImage 有值时,前 coverFrames 帧显示封面,音频+字幕整体后移
  const hasCover = Boolean(props.coverImage);
  const coverFrames = hasCover ? props.coverFrames : 0;

  const Body = (
    <>
      {/* 画面层 */}
      {props.videoSrc ? (
        <Video
          src={staticFile(props.videoSrc)}
          muted
          volume={0}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : null}

      {props.imageSrc ? (
        <Img
          src={staticFile(props.imageSrc)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : null}

      {props.images && imgCount > 0
        ? props.images.map((src, i) => {
            const from = i * slideFrames;
            const dur =
              i === imgCount - 1
                ? props.durationInFrames - from - coverFrames
                : slideFrames;
            return (
              <Sequence key={i} from={from} durationInFrames={dur}>
                <Img
                  src={staticFile(src)}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              </Sequence>
            );
          })
        : null}

      {/* 配音(唯一音轨) */}
      <Audio src={staticFile(props.audioSrc)} />

      {/* 字幕 */}
      {pages.map((page, i) => {
        const next = pages[i + 1] ?? null;
        const startFrame = (page.startMs / 1000) * fps;
        const endFrame = Math.min(
          next ? (next.startMs / 1000) * fps : Infinity,
          startFrame + (props.switchEveryMs / 1000) * fps,
        );
        const durationInFrames = Math.round(endFrame - startFrame);
        if (durationInFrames <= 0) return null;
        return (
          <Sequence
            key={i}
            from={Math.round(startFrame)}
            durationInFrames={durationInFrames}
          >
            <CaptionPage
              page={page}
              color={props.subtitleColor}
              size={props.subtitleSize}
            />
          </Sequence>
        );
      })}
    </>
  );

  return (
    <AbsoluteFill style={{ backgroundColor: props.bgColor }}>
      {hasCover ? (
        <>
          <Sequence from={0} durationInFrames={coverFrames} name="Cover">
            <Img
              src={staticFile(props.coverImage)}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </Sequence>
          <Sequence from={coverFrames} name="Narration">
            {Body}
          </Sequence>
        </>
      ) : (
        Body
      )}
    </AbsoluteFill>
  );
};

export const VoiceoverVideo: React.FC<VoiceoverVideoProps> = (props) => (
  <VoiceoverVideoComp {...props} />
);

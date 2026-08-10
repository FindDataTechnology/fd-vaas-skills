import {
  AbsoluteFill,
  Sequence,
  staticFile,
  useCurrentFrame,
  useDelayRender,
  useVideoConfig,
} from "remotion";
import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption, TikTokPage } from "@remotion/captions";
import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * shared - 类型模板共用的加载钩子与字幕组件
 *
 * scene-align 产物结构（task-render.mjs stepSceneAlign 写入 <slug>-scenes.json）。
 * 模板通过 useJsonFile<SceneAlignScene[]>(props.scenesSrc) 读取。
 */
export type SceneAlignScene = {
  from: number;
  durationInFrames: number;
  text: string;
  role?: "hook" | "body" | "cta" | string;
};

/**
 * useJsonFile - 拉取 public/ 下的 JSON 并阻塞渲染直到就绪。
 * 模板可多次调用（scenes / meta / items / data 各一个 handle）。
 */
export function useJsonFile<T>(src: string | undefined): T | null {
  const [data, setData] = useState<T | null>(null);
  const { delayRender, continueRender, cancelRender } = useDelayRender();
  const [handle] = useState(() =>
    delayRender(`loading ${src ?? "json"}`),
  );

  const fetchIt = useCallback(async () => {
    if (!src) {
      continueRender(handle);
      return;
    }
    try {
      const res = await fetch(staticFile(src));
      const json = (await res.json()) as T;
      setData(json);
      continueRender(handle);
    } catch (e) {
      cancelRender(e instanceof Error ? e : new Error(String(e)));
    }
  }, [src, continueRender, cancelRender, handle]);

  useEffect(() => {
    fetchIt();
  }, [fetchIt]);

  return data;
}

/** 按基准宽度 1080 做响应式缩放（横屏时 >1）。 */
export function scaleFor(width: number): number {
  return width / 1080;
}

/** 单页 TikTok 风逐字高亮字幕。 */
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
        justifyContent: "flex-end",
        alignItems: "center",
        padding: 40,
        paddingBottom: 160,
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

/**
 * Subtitles - 读 captionsSrc，渲染 TikTok 风逐字字幕页（Sequence 分页）。
 * 与 VoiceoverVideo 等价，抽出供所有新类型复用。
 */
export const Subtitles: React.FC<{
  captionsSrc: string;
  color: string;
  size: number;
  switchEveryMs?: number;
}> = ({ captionsSrc, color, size, switchEveryMs = 1400 }) => {
  const { fps } = useVideoConfig();
  const captions = useJsonFile<Caption[]>(captionsSrc);

  const pages = useMemo(() => {
    if (!captions) return [];
    const { pages: p } = createTikTokStyleCaptions({
      captions,
      combineTokensWithinMilliseconds: switchEveryMs,
    });
    return p;
  }, [captions, switchEveryMs]);

  if (!captions) return null;

  return (
    <>
      {pages.map((page, i) => {
        const next = pages[i + 1] ?? null;
        const startFrame = (page.startMs / 1000) * fps;
        const endFrame = Math.min(
          next ? (next.startMs / 1000) * fps : Infinity,
          startFrame + (switchEveryMs / 1000) * fps,
        );
        const durationInFrames = Math.round(endFrame - startFrame);
        if (durationInFrames <= 0) return null;
        return (
          <Sequence
            key={i}
            from={Math.round(startFrame)}
            durationInFrames={durationInFrames}
          >
            <CaptionPage page={page} color={color} size={size} />
          </Sequence>
        );
      })}
    </>
  );
};

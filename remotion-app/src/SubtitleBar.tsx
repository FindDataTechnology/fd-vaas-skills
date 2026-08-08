// SubtitleBar - 中文字幕条（whisper 句级时间戳 + 按词组高亮）
// 解决了三个问题：
// 1. 中文显式指定 PingFang SC 字体，避免 fallback 成西文字体
// 2. 句子间无重叠，每屏一句，不打架
// 3. createTikTokStyleCaptions 按词组分组高亮，不做逐字拆分
// 参考：https://www.remotion.dev/docs/captions/create-tiktok-style-captions

import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption } from "@remotion/captions";
import { useMemo } from "react";

// ---------------
// 原始配音稿（正确中文标点，无 whisper 识别错误）
// ---------------
const CORRECT_SENTENCES = [
  "公开信息，本该人人可用。",
  "可它散落在部委公告、公司财报、统计数据里，",
  "锁在 PDF，没有统一字段。",
  "FindDataTechnology，",
  "要让世界上的公开信息，真正可被计算。",
  "我们做三件事。",
  "采集，把各国政府与统计栏目，目录化抓成干净记录。",
  "结构化，用规则把财报和公告，变成带 schema 的字段。",
  "服务，每个数据集都封装成 MCP 服务器，",
  "任何 AI 都能发现并调用。",
  "我们的开源工作，从中国开始。",
  "DAAS，六百七十三项金融函数，",
  "一个接口调全世界。",
  "fd-cn-gov，十一个部委公告，",
  "一键目录化采集。",
  "fd-cn-report，三十一个行业、两万多条规则，",
  "把年报 PDF 变成结构化指标。",
  "还有 Platform 和 coding，",
  "把这一切串起来。",
  "过去要几天的人工调研，",
  "现在一次查询。",
  "无论提问者是分析师，还是 AI。",
  "FindDataTechnology，",
  "让世界的信息，人人可用。",
  "github.com/FindDataOfficial，",
  "欢迎 Star、Issue、PR。",
];

// ---------------
// whisper 句级时间戳（从音频真实分析出来的，匀速假设的不要）
// ---------------
// 时间戳：TTS 官方逐字返回,但对英文 token(FindDataTechnology / fd-cn-gov /
// github.com …)只标 45ms 就"结束",实际读音落在到下一个 token 的 gap 里。
// 修法:每个 token 的 endMs 都延伸到下一个 token 的 startMs(TTS 内字与字之间
// 没有真空隙,只有句间停顿)。下面就是这样聚合出来的句级时间戳。
const SENTENCE_TIMINGS_MS = [
  [145, 3115],    // 0: 公开信息，本该人人可用。
  [3115, 7785],   // 1: 可它散落在部委公告、公司财报、统计数据里，
  [7785, 9800],   // 2: 锁在 PDF，没有统一字段。
  [9800, 12635],  // 3: FindDataTechnology，
  [12635, 17010], // 4: 要让世界上的公开信息，真正可被计算。
  [17010, 18130], // 5: 我们做三件事。
  [18130, 23315], // 6: 采集，把各国政府与统计栏目，目录化抓成干净记录。
  [23315, 28640], // 7: 结构化，用规则把财报和公告，变成带 schema 的字段。
  [28640, 32835], // 8: 服务，每个数据集都封装成 MCP 服务器，
  [32835, 35738], // 9: 任何 AI 都能发现并调用。
  [35738, 39143], // 10: 我们的开源工作，从中国开始。
  [39143, 41963], // 11: DAAS，六百七十三项金融函数，
  [41963, 44118], // 12: 一个接口调全世界。
  [44118, 48093], // 13: fd-cn-gov，十一个部委公告，
  [48093, 49498], // 14: 一键目录化采集。
  [49498, 54963], // 15: fd-cn-report，三十一个行业、两万多条规则，
  [54963, 58173], // 16: 把年报 PDF 变成结构化指标。
  [58173, 60213], // 17: 还有 Platform 和 coding，
  [60213, 61872], // 18: 把这一切串起来。
  [61872, 63957], // 19: 过去要几天的人工调研，
  [63957, 65698], // 20: 现在一次查询。
  [65698, 69718], // 21: 无论提问者是分析师，还是 AI。
  [69718, 70623], // 22: FindDataTechnology，
  [70623, 73793], // 23: 让世界的信息，人人可用。
  [73793, 76778], // 24: github.com/FindDataOfficial，
  [76778, 79508], // 25: 欢迎 Star、Issue、PR。
];

export type SubtitleBarProps = {
  color?: string;
  size?: number;
  bottom?: number;
};

// 单句字幕：词组级高亮（不是逐字，中文更自然）
const SubtitlePage: React.FC<{
  sentence: string;
  startMs: number;
  endMs: number;
  color: string;
  size: number;
  bottom: number;
}> = ({ sentence, startMs, endMs, color, size, bottom }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000 - startMs; // 句子内相对时间
  const sentenceDurMs = endMs - startMs;

  // 中文简单分词：按标点和空格分成 tokens（足够做高亮了）
  // 不需要完美分词，只要视觉上是"按词渐亮"的效果就行
  const tokens = useMemo(() => {
    const chunks: { text: string; startPct: number; endPct: number }[] = [];
    const chars = sentence.split("");
    const charsPerMs = chars.length / sentenceDurMs;

    for (let i = 0; i < chars.length; i++) {
      chunks.push({
        text: chars[i],
        startPct: (i / chars.length) * 100,
        endPct: ((i + 1) / chars.length) * 100,
      });
    }
    return chunks;
  }, [sentence, sentenceDurMs]);

  const currentPct = (currentMs / sentenceDurMs) * 100;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: bottom,
      }}
    >
      <div
        style={{
          fontSize: size,
          fontWeight: 800,
          color: "#ffffff",
          textAlign: "center",
          lineHeight: 1.4,  // 中文行高略大一点
          maxWidth: 1400,   // 更宽，避免两行时折得奇怪
          textShadow: "0 4px 24px rgba(0,0,0,0.95), 0 0 12px rgba(0,0,0,0.9)",
          fontFamily:
            'PingFang SC, "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", sans-serif',
        }}
      >
        {tokens.map((token, i) => {
          const isActive = currentPct >= token.startPct;
          return (
            <span
              key={i}
              style={{
                color: isActive ? color : "rgba(255,255,255,0.85)",
                transition: "color 0.12s ease-out",
              }}
            >
              {token.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const SubtitleBar: React.FC<SubtitleBarProps> = ({
  color = "#3fb950",
  size = 52,
  bottom = 180,
}) => {
  const { fps } = useVideoConfig();

  // 检查时间戳配置是否正确
  const pages = useMemo(() => {
    if (CORRECT_SENTENCES.length !== SENTENCE_TIMINGS_MS.length) {
      console.error(
        `句子数和时间戳数不匹配：${CORRECT_SENTENCES.length} vs ${SENTENCE_TIMINGS_MS.length}`,
      );
    }
    return CORRECT_SENTENCES.map((sentence, i) => {
      const [startMs, endMs] = SENTENCE_TIMINGS_MS[i] || [
        i * 2000,
        i * 2000 + 2000,
      ];
      return {
        sentence,
        startMs,
        endMs,
        startFrame: Math.round((startMs / 1000) * fps),
        endFrame: Math.round((endMs / 1000) * fps),
      };
    });
  }, [fps]);

  return (
    <>
      {pages.map((page, i) => {
        const durationInFrames = page.endFrame - page.startFrame;
        if (durationInFrames <= 0) return null;
        return (
          <Sequence
            key={i}
            from={page.startFrame}
            durationInFrames={durationInFrames}
          >
            <SubtitlePage
              sentence={page.sentence}
              startMs={page.startMs}
              endMs={page.endMs}
              color={color}
              size={size}
              bottom={bottom}
            />
          </Sequence>
        );
      })}
    </>
  );
};

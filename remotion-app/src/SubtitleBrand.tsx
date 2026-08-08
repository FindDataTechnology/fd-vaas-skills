// SubtitleBrand — 寻数科技 2026 品牌片字幕条
// 15 句句子级时间戳，基于 TTS 官方逐字时间戳聚合。
// 词组级高亮（逐字渐进），视觉风格同 SubtitleBar。

import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { useMemo } from "react";

// 配音文案（正确文本）
const SENTENCES = [
  "你相信吗？",
  "数据，正在成为这个时代最不公平的资源。",
  "大家好，这里是寻数科技。",
  "我们的使命，是让数据驱动决策，",
  "我们的愿景，是信息平权和机会公平。",
  "在 AI 时代，有人手握海量数据一骑绝尘，",
  "有人却连最基本的公开信息都找不到、用不起。",
  "我们想改变这件事。",
  "目前，寻数科技正在构建一套面向 AI 时代的开源项目矩阵。",
  "数据层，有 fd-open-data-mcp 和 fd-daas-mcp——",
  "连接全球主流数据源，从股票筛选到研究报告，一站式搞定。",
  "工具层，有 fd-paas-private 和 fd-paas-cloud——",
  "本地也好、云端也罢，每个人都能拥有自己的 AI 工作平台。",
  "内容层，有 fd-vaas-skills 和 fd-paper-trading——",
  "AI 帮你做内容、跑策略，把生产力直接拉满。",
  "我们还在做 fd-open-bench，",
  "用来评估 AI Agent 在各专业领域的真实能力。",
  "开源，不是口号，是我们的武器。",
  "我们要连接全球优质的数据、工具和知识，",
  "让每一个个人和微型组织，",
  "都能在 AI 时代更好地认识世界、把握机会、创造价值。",
  "这就是寻数科技。",
  "一个更开放、更公平的 AI 未来，",
  "我们一起探索。",
];

// 句级时间戳（ms），从 TTS captions.json 聚合而来
// [startMs, endMs]
const SENTENCE_TIMINGS_MS: [number, number][] = [
  [125, 955],
  [1720, 4875],
  [5800, 7685],
  [8380, 11400],
  [11400, 15355],
  [16780, 20400],
  [20400, 23745],
  [24620, 25555],
  [26480, 30995],
  [32951, 36800],
  [36800, 43381],
  [44646, 48800],
  [48800, 54372],
  [55527, 59800],
  [59800, 64469],
  [65414, 67800],
  [67800, 71139],
  [72734, 74719],
  [75494, 79800],
  [79800, 83200],
  [83200, 87209],
  [88194, 88979],
  [90059, 91800],
  [91800, 93644],
];

export type SubtitleBrandProps = {
  color?: string;
  size?: number;
  bottom?: number;
};

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
  const currentMs = (frame / fps) * 1000 - startMs;
  const sentenceDurMs = endMs - startMs;

  const chars = sentence.split("");
  const currentPct = Math.max(
    0,
    Math.min(1, (currentMs / sentenceDurMs) * 100),
  );

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
          lineHeight: 1.45,
          maxWidth: 1500,
          textShadow:
            "0 4px 24px rgba(0,0,0,0.95), 0 0 12px rgba(0,0,0,0.9)",
          fontFamily:
            "'PingFang SC', 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', sans-serif",
        }}
      >
        {chars.map((ch, i) => (
          <span
            key={i}
            style={{
              color: "rgba(255,255,255,0.95)",
            }}
          >
            {ch}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

export const SubtitleBrand: React.FC<SubtitleBrandProps> = ({
  color = "#3fb950",
  size = 52,
  bottom = 180,
}) => {
  const { fps } = useVideoConfig();

  const pages = useMemo(() => {
    return SENTENCES.map((sentence, i) => {
      const [startMs, endMs] = SENTENCE_TIMINGS_MS[i] || [i * 2000, i * 2000 + 2000];
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

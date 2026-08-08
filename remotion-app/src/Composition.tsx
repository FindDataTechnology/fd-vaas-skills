import { AbsoluteFill, Composition, Sequence, staticFile } from "remotion";
import { COLORS, FONT_SANS, VIDEO } from "./theme";
import { Background, Overlays } from "./ui";
import {
  HookVAAS,
  PlatformGrid,
  SkillCards,
  DownloadSection,
  CTAVAAS,
} from "./scenesVAAS";
import {
  ArchitectureVAAS,
  BrowserDemo,
  ComparisonTable,
  CodeBlockVAAS,
  FeatureGrid,
} from "./scenesVAASNew";
import { CTAGov, GovDeepDive, HookGov, PainGov } from "./scenesGov";
import {
  CTAReport,
  HookReport,
  PainReport,
  ReportDeepDive,
} from "./scenesReport";
import {
  CTABoth,
  HookBoth,
  Loop,
  PainBoth,
  Split,
} from "./scenesCombined";
import {
  CTAOrg,
  CoverOrg,
  HookOrg,
  ProjectsOrg,
  ThreeStepsOrg,
  ValueOrg,
} from "./scenesOrg";
import { SubtitleBar } from "./SubtitleBar";
import { SubtitleBrand } from "./SubtitleBrand";
import { VoiceOver } from "./voiceover";
import { VoiceoverVideo } from "./VoiceoverVideo";
import { CostRevolution } from "./CostRevolution";
import {
  CoverBrand,
  HookBrand,
  WhyBrand,
  DataLayerBrand,
  ToolLayerBrand,
  ContentLayerBrand,
  ValueBrand,
  CTABrand,
} from "./scenesBrand";
import { BrandCover, BrandCoverTitleOnly, BrandCoverGradient } from "./CoverBrand";

// ---------------------------------------------------------------------------
// IntroduceGov  -  960f / 32s  (hook 120 · pain 180 · deepdive 480 · cta 180)
// ---------------------------------------------------------------------------
const IntroduceGovMain: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: FONT_SANS, color: COLORS.text }}>
    <Background />
    <Overlays durationInFrames={960} accent={COLORS.green} />
    <Sequence from={0} durationInFrames={120} name="Hook">
      <HookGov />
    </Sequence>
    <Sequence from={120} durationInFrames={180} name="Pain">
      <PainGov />
    </Sequence>
    <Sequence from={300} durationInFrames={480} name="DeepDive">
      <GovDeepDive />
    </Sequence>
    <Sequence from={780} durationInFrames={180} name="CTA">
      <CTAGov />
    </Sequence>
  </AbsoluteFill>
);

// ---------------------------------------------------------------------------
// IntroduceReport  -  1050f / 35s  (hook 150 · pain 180 · deepdive 540 · cta 180)
// ---------------------------------------------------------------------------
const IntroduceReportMain: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: FONT_SANS, color: COLORS.text }}>
    <Background />
    <Overlays durationInFrames={1050} accent={COLORS.blue} />
    <Sequence from={0} durationInFrames={150} name="Hook">
      <HookReport />
    </Sequence>
    <Sequence from={150} durationInFrames={180} name="Pain">
      <PainReport />
    </Sequence>
    <Sequence from={330} durationInFrames={540} name="DeepDive">
      <ReportDeepDive />
    </Sequence>
    <Sequence from={870} durationInFrames={180} name="CTA">
      <CTAReport />
    </Sequence>
  </AbsoluteFill>
);

// ---------------------------------------------------------------------------
// IntroduceVideo  -  2070f / 69s
// (hook 150 · pain 240 · split 150 · gov 480 · report 540 · loop 210 · cta 300)
// ---------------------------------------------------------------------------
const IntroduceVideoMain: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: FONT_SANS, color: COLORS.text }}>
    <Background />
    <Overlays durationInFrames={2070} />
    <Sequence from={0} durationInFrames={150} name="Hook">
      <HookBoth />
    </Sequence>
    <Sequence from={150} durationInFrames={240} name="Pain">
      <PainBoth />
    </Sequence>
    <Sequence from={390} durationInFrames={150} name="Split">
      <Split />
    </Sequence>
    <Sequence from={540} durationInFrames={480} name="Gov">
      <GovDeepDive />
    </Sequence>
    <Sequence from={1020} durationInFrames={540} name="Report">
      <ReportDeepDive />
    </Sequence>
    <Sequence from={1560} durationInFrames={210} name="Loop">
      <Loop />
    </Sequence>
    <Sequence from={1770} durationInFrames={300} name="CTA">
      <CTABoth />
    </Sequence>
  </AbsoluteFill>
);

// ---------------------------------------------------------------------------
// IntroduceOrg  -  org brand video, 2461f / 82s @30fps  (16:9, narrated)
// Structure: Cover 60f (2s, silent) → Narration 2401f (79.5s, voice+subs)
// Voiceover: public/voiceover-1784450642653.mp3 (seed-tts-2.0 高冷御姐)
// SubtitleBar text + timings computed from TTS official captions-1784450642653.json.
// ---------------------------------------------------------------------------
type IntroduceOrgProps = {
  audioSrc: string;
  durationInFrames: number;
  subtitleColor?: string;
  subtitleSize?: number;
  subtitleBottom?: number;
};

const IntroduceOrgMain: React.FC<IntroduceOrgProps> = ({
  audioSrc,
  durationInFrames,
  subtitleColor,
  subtitleSize,
  subtitleBottom,
}) => (
  <AbsoluteFill style={{ fontFamily: FONT_SANS, color: COLORS.text }}>
    <Background />
    <Overlays durationInFrames={durationInFrames} accent={COLORS.green} />
    {/* Cover (2s brand card, no voice, no subtitles). */}
    <Sequence from={0} durationInFrames={60} name="Cover">
      <CoverOrg />
    </Sequence>
    {/* Narrated body — audio + subtitles share this Sequence so they stay in
        lockstep with the scenes, all shifted +60 frames by the cover. */}
    <Sequence from={60} name="Narration">
      <VoiceOver src={staticFile(audioSrc)} />
      <Sequence from={0} durationInFrames={510} name="Hook">
        <HookOrg />
      </Sequence>
      <Sequence from={510} durationInFrames={620} name="ThreeSteps">
        <ThreeStepsOrg />
      </Sequence>
      <Sequence from={1130} durationInFrames={730} name="Projects">
        <ProjectsOrg />
      </Sequence>
      <Sequence from={1860} durationInFrames={210} name="Value">
        <ValueOrg />
      </Sequence>
      <Sequence from={2070} durationInFrames={331} name="CTA">
        <CTAOrg />
      </Sequence>
      <SubtitleBar
        color={subtitleColor}
        size={subtitleSize}
        bottom={subtitleBottom}
      />
    </Sequence>
  </AbsoluteFill>
);

// ---------------------------------------------------------------------------
// VoiceOverDemo - Composition WITH real voice-over
// Audio: public/voiceover-doubao.mp3 (豆包 seed-tts-2.0 神经网络 TTS - 高冷御姐)
// Duration: 56.9s = 1707 frames @ 30fps
// ---------------------------------------------------------------------------
const VoiceOverDemo: React.FC = () => {
  return (
    <AbsoluteFill style={{ fontFamily: FONT_SANS, color: COLORS.text }}>
      <Background />
      <Overlays durationInFrames={1707} accent={COLORS.green} />

      {/* 🎤 豆包神经网络 TTS 配音（高冷御姐音色） */}
      <VoiceOver src={staticFile("voiceover-doubao.mp3")} />

      {/* Scenes aligned to the narration */}
      <Sequence from={0} durationInFrames={300} name="Hook">
        <HookGov />
      </Sequence>
      <Sequence from={300} durationInFrames={360} name="Pain">
        <PainGov />
      </Sequence>
      <Sequence from={660} durationInFrames={720} name="DeepDive">
        <GovDeepDive />
      </Sequence>
      <Sequence from={1380} durationInFrames={327} name="CTA">
        <CTAGov />
      </Sequence>
    </AbsoluteFill>
  );
};

export const MyComposition: React.FC = () => {
  return (
    <>
      {/* ============================================================
         FindDataBrand2026 — 寻数科技 2026 品牌片 (1920×1080, narrated)
         Cover(60f) → Hook → Why → DataLayer → ToolLayer
             → ContentLayer → Value → CTA
         ============================================================ */}
      <Composition
        id="FindDataBrand2026"
        component={
          ({
            audioSrc,
            durationInFrames,
            subtitleColor,
            subtitleSize,
            subtitleBottom,
          }: {
            audioSrc: string;
            durationInFrames: number;
            subtitleColor?: string;
            subtitleSize?: number;
            subtitleBottom?: number;
          }) => {
            const narrFrames = durationInFrames - 60;
            return (
              <AbsoluteFill
                style={{ fontFamily: FONT_SANS, color: COLORS.text }}
              >
                <Background />
                <Overlays
                  durationInFrames={durationInFrames}
                  accent={COLORS.green}
                />
                <Sequence from={0} durationInFrames={60} name="Cover">
                  <CoverBrand />
                </Sequence>
                <Sequence from={60} name="Narration">
                  <VoiceOver src={staticFile(audioSrc)} />
                  {/* Scene timings synced to TTS sentence timestamps (30fps) */}
                  <Sequence from={0} durationInFrames={174} name="Hook">
                    <HookBrand />
                  </Sequence>
                  <Sequence from={174} durationInFrames={620} name="Why">
                    <WhyBrand />
                  </Sequence>
                  <Sequence from={794} durationInFrames={545} name="DataLayer">
                    <DataLayerBrand />
                  </Sequence>
                  <Sequence from={1339} durationInFrames={327} name="ToolLayer">
                    <ToolLayerBrand />
                  </Sequence>
                  <Sequence
                    from={1666}
                    durationInFrames={516}
                    name="ContentLayer"
                  >
                    <ContentLayerBrand />
                  </Sequence>
                  <Sequence from={2182} durationInFrames={464} name="Value">
                    <ValueBrand />
                  </Sequence>
                  <Sequence
                    from={2646}
                    durationInFrames={narrFrames - 2646}
                    name="CTA"
                  >
                    <CTABrand />
                  </Sequence>
                  <SubtitleBrand
                    color={subtitleColor}
                    size={subtitleSize}
                    bottom={subtitleBottom}
                  />
                </Sequence>
              </AbsoluteFill>
            );
          }
        }
        durationInFrames={2870}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
        defaultProps={{
          audioSrc: "finddata-brand-2026-voiceover.mp3",
          durationInFrames: 2870,
          subtitleColor: "#3fb950",
          subtitleSize: 50,
          subtitleBottom: 160,
        }}
        calculateMetadata={({ props }) =>
          Promise.resolve({
            durationInFrames: props.durationInFrames,
            width: VIDEO.width,
            height: VIDEO.height,
          })
        }
      />

      <Composition
        id="IntroduceGov"
        component={IntroduceGovMain}
        durationInFrames={960}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />
      <Composition
        id="IntroduceReport"
        component={IntroduceReportMain}
        durationInFrames={1050}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />
      <Composition
        id="IntroduceVideo"
        component={IntroduceVideoMain}
        durationInFrames={2070}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />
      <Composition
        id="IntroduceOrg"
        component={IntroduceOrgMain}
        durationInFrames={2461}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
        defaultProps={{
          audioSrc: "voiceover-1784450642653.mp3",
          durationInFrames: 2461,
          subtitleColor: "#3fb950",
          subtitleSize: 48,
          subtitleBottom: 200,
        }}
        calculateMetadata={({ props }) =>
          Promise.resolve({
            durationInFrames: props.durationInFrames,
            width: VIDEO.width,
            height: VIDEO.height,
          })
        }
      />
      <Composition
        id="VoiceOverDemo"
        component={VoiceOverDemo}
        durationInFrames={1707}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />
      {/* ============================================================
         BrandCoverHorizontal — 寻数科技品牌封面 (横版 1920×1080)
         ============================================================ */}
      <Composition
        id="BrandCoverHorizontal"
        component={BrandCover}
        durationInFrames={1}
        fps={1}
        width={1920}
        height={1080}
        defaultProps={{
          title: "寻数科技",
          subtitle: "探索更开放更公平的 AI 未来",
          tags: "开源 · 数据 · AI",
          orientation: "horizontal",
          logo: "icon.png",
        }}
        calculateMetadata={({ props }) =>
          Promise.resolve({
            props,
            durationInFrames: 1,
            width: props.width ?? 1920,
            height: props.height ?? 1080,
          })
        }
      />

      {/* ============================================================
         BrandCoverVertical — 寻数科技品牌封面 (竖版 1080×1440, 3:4)
         ============================================================ */}
      <Composition
        id="BrandCoverVertical"
        component={BrandCover}
        durationInFrames={1}
        fps={1}
        width={1080}
        height={1440}
        defaultProps={{
          title: "寻数科技",
          subtitle: "探索更开放更公平的 AI 未来",
          tags: "开源 · 数据 · AI",
          orientation: "vertical",
          logo: "icon.png",
        }}
      />

      {/* ============================================================
         BrandCoverTitleOnly — 极简大字封面
         ============================================================ */}
      <Composition
        id="BrandCoverTitleOnly"
        component={BrandCoverTitleOnly}
        durationInFrames={1}
        fps={1}
        width={1920}
        height={1080}
        defaultProps={{
          title: "寻数科技",
          subtitle: "",
          orientation: "horizontal",
          logo: "icon.png",
        }}
      />

      {/* ============================================================
         BrandCoverGradient — 渐变冲击力封面
         ============================================================ */}
      <Composition
        id="BrandCoverGradient"
        component={BrandCoverGradient}
        durationInFrames={1}
        fps={1}
        width={1920}
        height={1080}
        defaultProps={{
          title: "寻数科技",
          subtitle: "探索更开放更公平的 AI 未来",
          tags: "开源 · 数据 · AI",
          orientation: "horizontal",
          logo: "icon.png",
        }}
      />

      {/* ============================================================
         VAASTutorial - 完整版 304秒 / 9个场景 10次切换（25-35秒/场）
         ============================================================ */}
      <Composition
        id="VAASTutorial"
        component={
          ({
            audioSrc,
            captionsSrc,
            durationInFrames,
          }: {
            audioSrc: string;
            captionsSrc: string;
            durationInFrames: number;
          }) => {
            return (
              <AbsoluteFill style={{ fontFamily: FONT_SANS }}>
                <Background />
                <Overlays durationInFrames={durationInFrames} accent={COLORS.blue} />
                <VoiceOver src={staticFile(audioSrc)} />

                {/* 🎬 场景时间轴（与口播内容精确对齐） */}
                {/* 0-10s: 开场 Hook - VAAS 介绍 */}
                <Sequence from={0} durationInFrames={300} name="Hook">
                  <HookVAAS />
                </Sequence>
                {/* 10-25s: 技术架构图 */}
                <Sequence from={300} durationInFrames={450} name="Architecture">
                  <ArchitectureVAAS />
                </Sequence>
                {/* 25-50s: 15个支持平台展示 */}
                <Sequence from={750} durationInFrames={750} name="Platforms">
                  <PlatformGrid />
                </Sequence>
                {/* 50-75s: 6大核心技能卡片 */}
                <Sequence from={1500} durationInFrames={750} name="Skills">
                  <SkillCards />
                </Sequence>
                {/* 75-100s: 功能特性网格 */}
                <Sequence from={2250} durationInFrames={750} name="Features">
                  <FeatureGrid />
                </Sequence>
                {/* 100-130s: 自然语言调用演示（复用平台场景） */}
                <Sequence from={3000} durationInFrames={900} name="Platforms2">
                  <PlatformGrid />
                </Sequence>
                {/* 130-160s: 浏览器自动化演示 */}
                <Sequence from={3900} durationInFrames={900} name="Browser">
                  <BrowserDemo />
                </Sequence>
                {/* 160-190s: Windows vs Mac 对比表格 */}
                <Sequence from={4800} durationInFrames={900} name="Comparison">
                  <ComparisonTable />
                </Sequence>
                {/* 190-220s: 技能卡片回顾 */}
                <Sequence from={5700} durationInFrames={900} name="Skills2">
                  <SkillCards />
                </Sequence>
                {/* 220-250s: 三行命令代码演示 */}
                <Sequence from={6600} durationInFrames={900} name="Code">
                  <CodeBlockVAAS />
                </Sequence>
                {/* 250-280s: 一键下载安装演示 */}
                <Sequence from={7500} durationInFrames={900} name="Download">
                  <DownloadSection />
                </Sequence>
                {/* 280s-结束: 总结 + CTA */}
                <Sequence from={8400} durationInFrames={durationInFrames - 8400} name="CTA">
                  <CTAVAAS />
                </Sequence>

              </AbsoluteFill>
            );
          }
        }
        durationInFrames={9140}
        fps={VIDEO.fps}
        width={1920}
        height={1080}
        defaultProps={{
          audioSrc: "voiceover.mp3",
          captionsSrc: "captions.json",
          durationInFrames: 9140,
        }}
      />

      {/* ============================================================
         VAASTutorialV7 - 2026-07-30 v7 口播（216s/6505f，9 场景按口播时间戳对齐）
         场景边界取自 captions.json 逐字时间戳，与 tmp-v6-script.md 8 段口播精确对齐。
         v7 修正：删 VAAS 全称、口播不念平台名（泛称）、curl 地址改对、字号放大。
         ============================================================ */}
      <Composition
        id="VAASTutorialV7"
        component={
          ({
            audioSrc,
            captionsSrc,
            durationInFrames,
          }: {
            audioSrc: string;
            captionsSrc: string;
            durationInFrames: number;
          }) => {
            return (
              <AbsoluteFill style={{ fontFamily: FONT_SANS }}>
                <Background />
                <Overlays durationInFrames={durationInFrames} accent={COLORS.blue} />
                <VoiceOver src={staticFile(audioSrc)} />

                {/* 🎬 场景时间轴（与 v7 口播精确对齐，总 6505f / 216.8s） */}
                {/* 0-19.6s: 开场 Hook */}
                <Sequence from={0} durationInFrames={589} name="Hook">
                  <HookVAAS />
                </Sequence>
                {/* 19.6-44.0s: 它是什么 - 架构图 + 两条主线总起 */}
                <Sequence from={589} durationInFrames={732} name="Architecture">
                  <ArchitectureVAAS />
                </Sequence>
                {/* 44.0-68.0s: 两条主线 - 核心技能卡片 */}
                <Sequence from={1321} durationInFrames={718} name="Skills">
                  <SkillCards />
                </Sequence>
                {/* 68.0-93.0s: 平台覆盖（泛称，不暴露平台名） */}
                <Sequence from={2039} durationInFrames={751} name="Platforms">
                  <PlatformGrid />
                </Sequence>
                {/* 93.0-124.5s: Mac vs Windows 双运行时 */}
                <Sequence from={2790} durationInFrames={945} name="Comparison">
                  <ComparisonTable />
                </Sequence>
                {/* 124.5-160.7s: 自然语言调用 + 不绑定基座 */}
                <Sequence from={3735} durationInFrames={1087} name="Code">
                  <CodeBlockVAAS />
                </Sequence>
                {/* 160.7-178.6s: 多模型可切换 */}
                <Sequence from={4822} durationInFrames={536} name="Features">
                  <FeatureGrid />
                </Sequence>
                {/* 178.6-197.0s: 一行安装（地址已修正） */}
                <Sequence from={5358} durationInFrames={552} name="Download">
                  <DownloadSection />
                </Sequence>
                {/* 197.0-216.8s: 总结 + CTA */}
                <Sequence from={5910} durationInFrames={durationInFrames - 5910} name="CTA">
                  <CTAVAAS />
                </Sequence>

              </AbsoluteFill>
            );
          }
        }
        durationInFrames={6505}
        fps={VIDEO.fps}
        width={1920}
        height={1080}
        defaultProps={{
          audioSrc: "voiceover.mp3",
          captionsSrc: "captions.json",
          durationInFrames: 6505,
        }}
      />

      {/* ============================================================
         VAASTutorialV8 - 2026-07-30 v8 口播（209s/6296f，9 场景按口播时间戳对齐）
         v8 修正：第②段「用户不用懂代码」（非「项目没代码」）；「寻数科技 FindData Technology」连读不断句。
         ============================================================ */}
      <Composition
        id="VAASTutorialV8"
        component={
          ({
            audioSrc,
            captionsSrc,
            durationInFrames,
          }: {
            audioSrc: string;
            captionsSrc: string;
            durationInFrames: number;
          }) => {
            return (
              <AbsoluteFill style={{ fontFamily: FONT_SANS }}>
                <Background />
                <Overlays durationInFrames={durationInFrames} accent={COLORS.blue} />
                <VoiceOver src={staticFile(audioSrc)} />

                {/* 🎬 场景时间轴（与 v8 口播精确对齐，总 6296f / 209.9s） */}
                {/* 0-19.0s: 开场 Hook */}
                <Sequence from={0} durationInFrames={569} name="Hook">
                  <HookVAAS />
                </Sequence>
                {/* 19.0-30.2s: 你不用懂代码 - 架构图 */}
                <Sequence from={569} durationInFrames={336} name="Architecture">
                  <ArchitectureVAAS />
                </Sequence>
                {/* 30.2-64.4s: 两条主线 - 核心技能卡片 */}
                <Sequence from={905} durationInFrames={1027} name="Skills">
                  <SkillCards />
                </Sequence>
                {/* 64.4-89.0s: 平台覆盖（泛称） */}
                <Sequence from={1932} durationInFrames={738} name="Platforms">
                  <PlatformGrid />
                </Sequence>
                {/* 89.0-119.9s: Mac vs Windows 双运行时 */}
                <Sequence from={2670} durationInFrames={926} name="Comparison">
                  <ComparisonTable />
                </Sequence>
                {/* 119.9-155.4s: 自然语言调用 + 不绑定基座 */}
                <Sequence from={3596} durationInFrames={1067} name="Code">
                  <CodeBlockVAAS />
                </Sequence>
                {/* 155.4-173.4s: 多模型可切换 */}
                <Sequence from={4663} durationInFrames={539} name="Features">
                  <FeatureGrid />
                </Sequence>
                {/* 173.4-191.0s: 一行安装（地址已修正） */}
                <Sequence from={5202} durationInFrames={527} name="Download">
                  <DownloadSection />
                </Sequence>
                {/* 191.0-209.9s: 总结 + CTA */}
                <Sequence from={5729} durationInFrames={durationInFrames - 5729} name="CTA">
                  <CTAVAAS />
                </Sequence>

              </AbsoluteFill>
            );
          }
        }
        durationInFrames={6296}
        fps={VIDEO.fps}
        width={1920}
        height={1080}
        defaultProps={{
          audioSrc: "voiceover.mp3",
          captionsSrc: "captions.json",
          durationInFrames: 6296,
        }}
      />

      <Composition
        id="VoiceoverVideo"
        component={VoiceoverVideo}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          audioSrc: "voiceover.mp3",
          captionsSrc: "captions.json",
          durationInFrames: 300,
        }}
        calculateMetadata={({ props }) =>
          Promise.resolve({
            durationInFrames: props.durationInFrames,
            width: props.width ?? 1080,
            height: props.height ?? 1920,
          })
        }
      />

      {/* ============================================================
    <>
      {/* ============================================================
         CostRevolution — AI 软件公司成本革命视频 (1920×1080, narrated)
         场景编排：Hook → 传统 SaaS 抛物线成本图 → AI 应用折线成本图 →
                 演进路径图 → 产品矩阵 → Agent 生态展望 → CTA
         ============================================================ */}
      <Composition
        id="CostRevolution"
        component={CostRevolution}
        durationInFrames={300}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
        defaultProps={{
          audioSrc: "ai-software-cost-revolution-voiceover.mp3",
          captionsSrc: "ai-software-cost-revolution-captions.json",
          durationInFrames: 10167,
          subtitleColor: "#3fb950",
          subtitleSize: 56,
        }}
        calculateMetadata={({ props }) =>
          Promise.resolve({
            durationInFrames: props.durationInFrames,
            width: VIDEO.width,
            height: VIDEO.height,
          })
        }
      />
    </>
  );
};

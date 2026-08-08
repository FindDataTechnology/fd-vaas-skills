import "./index.css";
import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { LogoAnimationMain, LOGO_DURATION_ZH, LOGO_DURATION_EN, LOGO_VIDEO } from "./LogoAnimation";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <Composition
        id="LogoAnimation-zh"
        component={LogoAnimationMain}
        durationInFrames={LOGO_DURATION_ZH}
        fps={LOGO_VIDEO.fps}
        width={LOGO_VIDEO.width}
        height={LOGO_VIDEO.height}
        defaultProps={{
          lang: "zh" as "zh" | "en",
          voiceStartFrame: 65,
          voiceDurationFrames: 96, // 3.2s
        }}
      />
      <Composition
        id="LogoAnimation-en"
        component={LogoAnimationMain}
        durationInFrames={LOGO_DURATION_EN}
        fps={LOGO_VIDEO.fps}
        width={LOGO_VIDEO.width}
        height={LOGO_VIDEO.height}
        defaultProps={{
          lang: "en" as "zh" | "en",
          voiceStartFrame: 65,
          voiceDurationFrames: 132, // 4.4s
        }}
      />
      <Composition
        id="LogoAnimation-zh-9x16"
        component={LogoAnimationMain}
        durationInFrames={LOGO_DURATION_ZH}
        fps={LOGO_VIDEO.fps}
        width={1080}
        height={1920}
        defaultProps={{
          lang: "zh" as "zh" | "en",
          voiceStartFrame: 65,
          voiceDurationFrames: 96,
        }}
      />
      <Composition
        id="LogoAnimation-en-9x16"
        component={LogoAnimationMain}
        durationInFrames={LOGO_DURATION_EN}
        fps={LOGO_VIDEO.fps}
        width={1080}
        height={1920}
        defaultProps={{
          lang: "en" as "zh" | "en",
          voiceStartFrame: 65,
          voiceDurationFrames: 132,
        }}
      />
    </>
  );
};

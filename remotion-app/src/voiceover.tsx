import { Audio, useCurrentFrame } from "remotion";

/**
 * VoiceOver Component
 *
 * Renders an audio track for video voice-over.
 * Auto-generates audio from text using the TTS skill (see scripts/generate-voiceover.mjs)
 *
 * Usage:
 *   1. Generate audio: node scripts/generate-voiceover.mjs "Your script text"
 *   2. Import in composition: <VoiceOver src={require("../public/voiceover.mp3")} />
 */

interface VoiceOverProps {
  /** Path to audio file (usually from public/ folder) */
  src: string;
  /** Start frame for the audio (default: 0) */
  startFrom?: number;
  /** Volume: 0-1 (default: 1) */
  volume?: number;
  /** Playback rate: 0.5-2 (default: 1) */
  playbackRate?: number;
  /** Allow audio to play even when tab is hidden (default: true) */
  allowAmplificationDuringRender?: boolean;
}

export const VoiceOver: React.FC<VoiceOverProps> = ({
  src,
  startFrom = 0,
  volume = 1,
  playbackRate = 1,
  allowAmplificationDuringRender = true,
}) => {
  return (
    <Audio
      src={src}
      startFrom={startFrom}
      volume={volume}
      playbackRate={playbackRate}
      allowAmplificationDuringRender={allowAmplificationDuringRender}
    />
  );
};

/**
 * Scene-level voiceover
 *
 * Use this when you want to sync specific voice lines with individual scenes.
 * Each scene gets its own audio clip that plays during that scene.
 */
interface SceneVoiceOverProps {
  src: string;
  sceneStartFrame: number;
  sceneDurationFrames: number;
  volume?: number;
  /** Add a small delay in frames before audio starts (default: 5) */
  delayFrames?: number;
}

export const SceneVoiceOver: React.FC<SceneVoiceOverProps> = ({
  src,
  sceneStartFrame,
  sceneDurationFrames,
  volume = 0.9,
  delayFrames = 5,
}) => {
  const frame = useCurrentFrame();
  const relativeFrame = frame - sceneStartFrame;

  // Don't render outside scene bounds
  if (relativeFrame < 0 || relativeFrame >= sceneDurationFrames) {
    return null;
  }

  return (
    <Audio
      src={src}
      startFrom={sceneStartFrame + delayFrames}
      volume={volume}
    />
  );
};

/**
 * Background Music Component
 *
 * Separate component for BGM, typically lower volume than voiceover.
 * Can be used alongside VoiceOver for layered audio.
 */
interface BackgroundMusicProps {
  src: string;
  /** Volume for BGM (usually lower than voice: 0.1-0.3) */
  volume?: number;
  /** Whether to loop the audio */
  loop?: boolean;
  startFrom?: number;
}

export const BackgroundMusic: React.FC<BackgroundMusicProps> = ({
  src,
  volume = 0.15,
  loop = true,
  startFrom = 0,
}) => {
  return (
    <Audio
      src={src}
      startFrom={startFrom}
      volume={volume}
      loop={loop}
    />
  );
};

/**
 * Helper: Calculate voiceover duration in frames
 *
 * Estimates how many frames a voice-over will take based on character count.
 * Useful for auto-sizing scene durations to match narration speed.
 *
 * @param charCount Number of characters in the script
 * @param fps Frames per second (default: 30)
 * @param charsPerSecond Typical reading speed (default: 4-5 chars/sec for Chinese)
 */
export const calculateVoiceOverFrames = (
  charCount: number,
  fps = 30,
  charsPerSecond = 4.5
): number => {
  return Math.ceil((charCount / charsPerSecond) * fps);
};

/**
 * Helper: Calculate speaking duration in seconds
 */
export const calculateSpeakingDuration = (
  charCount: number,
  charsPerSecond = 4.5
): number => {
  return charCount / charsPerSecond;
};

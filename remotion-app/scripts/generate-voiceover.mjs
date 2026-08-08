#!/usr/bin/env node

/**
 * Remotion Voice-over Generator
 *
 * Uses the voice-generator skill to generate voiceover audio from text.
 * Places the generated audio directly in Remotion's public/ folder for immediate use.
 *
 * Usage:
 *   node scripts/generate-voiceover.mjs --text "Your narration text here"
 *   node scripts/generate-voiceover.mjs --file script.txt --voice zh-CN-Yunfan
 *   node scripts/generate-voiceover.mjs --list-voices
 */

import { spawn, spawnSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = path.resolve(__dirname, "..");
const PUBLIC_DIR = path.join(PROJECT_ROOT, "public");
const TTS_WRAPPER = path.resolve(
  __dirname,
  "../../.agents/skills/fd-vaas-video-creator/scripts/generators/tts-wrapper.js"
);

// Ensure public dir exists
if (!fs.existsSync(PUBLIC_DIR)) {
  fs.mkdirSync(PUBLIC_DIR, { recursive: true });
}

// Parse args
const args = process.argv.slice(2);

function getArgValue(key, altKey) {
  const idx = args.indexOf(key);
  if (idx !== -1 && args[idx + 1] && !args[idx + 1].startsWith("--")) {
    return args[idx + 1];
  }
  if (altKey) return getArgValue(altKey);
  return null;
}

function hasArg(key) {
  return args.indexOf(key) !== -1;
}

// --list-voices shortcut
if (hasArg("--list-voices") || hasArg("--voices")) {
  spawnSync("node", [TTS_WRAPPER, "voices"], {
    stdio: "inherit",
    cwd: PROJECT_ROOT,
  });
  process.exit(0);
}

// Helper: Find the most recent audio file in Ark-TTS output dir
function findMostRecentAudio() {
  const home = process.env.HOME || process.env.USERPROFILE;
  const possibleDirs = [
    path.join(home, "Desktop", "Ark-TTS"),
    path.join(home, "Ark-TTS"),
    path.join(PROJECT_ROOT, "Ark-TTS"),
  ];

  let newestDir = null;
  let newestTime = 0;

  for (const baseDir of possibleDirs) {
    if (!fs.existsSync(baseDir)) continue;

    const dirs = fs.readdirSync(baseDir);
    for (const d of dirs) {
      const fullPath = path.join(baseDir, d);
      if (!fs.statSync(fullPath).isDirectory()) continue;
      const mtime = fs.statSync(fullPath).mtimeMs;
      if (mtime > newestTime) {
        newestTime = mtime;
        newestDir = fullPath;
      }
    }
  }

  if (!newestDir) return null;

  const files = fs.readdirSync(newestDir);
  const audioFile = files.find((f) => f.endsWith(".mp3") || f.endsWith(".wav"));
  return audioFile
    ? {
        audio: path.join(newestDir, audioFile),
        captions: files.includes("captions.json")
          ? path.join(newestDir, "captions.json")
          : null,
      }
    : null;
}

// Generate the voiceover
console.log("🎤 Generating voiceover...\n");

const ttsArgs = ["node", TTS_WRAPPER];

// Pass through all args
for (const arg of args) {
  ttsArgs.push(arg);
}

const result = spawnSync(ttsArgs[0], ttsArgs.slice(1), {
  stdio: "pipe",
  cwd: PROJECT_ROOT,
  encoding: "utf8",
});

if (result.status !== 0) {
  console.error("❌ Voiceover generation failed");
  console.error(result.stderr || result.stdout);
  process.exit(result.status || 1);
}

console.log(result.stdout);

// Find the generated audio and copy it to public/
const generated = findMostRecentAudio();
if (generated && generated.audio) {
  const ts = Date.now();
  const audioName = "voiceover-" + ts + path.extname(generated.audio);
  const audioDest = path.join(PUBLIC_DIR, audioName);
  fs.copyFileSync(generated.audio, audioDest);

  let captionsName = null;
  if (generated.captions) {
    captionsName = "captions-" + ts + ".json";
    fs.copyFileSync(generated.captions, path.join(PUBLIC_DIR, captionsName));
  }

  console.log("\n" + "=".repeat(60));
  console.log("✅ Voiceover copied to Remotion public folder!");
  console.log(`📁 Audio Source: ${generated.audio}`);
  console.log(`📁 Audio Dest:   ${audioDest}`);
  if (captionsName) {
    console.log(`📝 Captions Source: ${generated.captions}`);
    console.log(`📝 Captions Dest:   ${path.join(PUBLIC_DIR, captionsName)}`);
  } else {
    console.log(
      "⚠️  No captions.json produced by TTS (subtitle disabled or model unsupported)."
    );
  }
  console.log("\n🎬 Render with --props:");
  console.log(
    `   {"audioSrc":"${audioName}"${
      captionsName ? `,"captionsSrc":"${captionsName}"` : ""
    },"durationInFrames":<frames>,"videoSrc":"..."}`
  );
  console.log("=".repeat(60));
} else {
  console.log("\n⚠️  Could not auto-copy generated audio file.");
  console.log("   Please copy it manually to remotion-app/public/");
}

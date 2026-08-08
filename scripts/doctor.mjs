#!/usr/bin/env node
/**
 * doctor.mjs — VAAS 环境健康检查
 *
 * 用法: node scripts/doctor.mjs
 *
 * 检查项为数据驱动数组 {name, level, check(), fix}：
 *   level: "error" → 缺失会破坏核心管线（❌，退出码非 0）
 *          "warn"  → 可选能力缺失（⚠️，不影响退出码）
 * 输出每项 ✅/⚠️/❌ + 修复命令。绝不打印密钥值，只报「已配置/未配置」。
 */
import { execSync } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";

const VAAS = process.env.VAAS_ROOT ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const IS_MAC = process.platform === "darwin";
const IS_WIN = process.platform === "win32";

const which = (cmd) => {
  try {
    execSync(IS_WIN ? `where ${cmd}` : `command -v ${cmd}`, { stdio: "pipe" });
    return true;
  } catch {
    // ~/.local/bin 可能不在 PATH
    const local = path.join(os.homedir(), ".local/bin", cmd);
    return fs.existsSync(local);
  }
};
const ver = (cmd, args = "--version") => {
  try {
    return execSync(`${cmd} ${args} 2>&1`, { stdio: "pipe" }).toString().split("\n")[0].trim();
  } catch {
    return null;
  }
};

// .env 关键变量存在性（不读值）
const envKeys = () => {
  const p = path.join(VAAS, ".env");
  if (!fs.existsSync(p)) return { file: false, keys: new Set() };
  const keys = new Set();
  for (const line of fs.readFileSync(p, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(\S+)/);
    if (m && m[2] && !m[2].startsWith("#")) keys.add(m[1].toLowerCase());
  }
  return { file: true, keys };
};

const SKILL_LINKS = [
  "fd-browser-record", "fd-coding-wifi-tunnel", "fd-cover-image",
  "fd-vaas-brainstorm", "fd-vaas-dashboard", "fd-vaas-dashboard-sharing",
  "fd-vaas-publish-docs", "fd-vaas-publish-videos", "fd-vaas-video-creator",
];

const CHECKS = [
  {
    name: "Node.js ≥ 18",
    level: "error",
    check: () => {
      const v = ver("node");
      if (!v) return false;
      const major = Number(v.replace(/^v/i, "").split(".")[0]);
      return major >= 18 ? `v${v.replace(/^v/i, "")}` : false;
    },
    fix: "安装 Node 18+: macOS `brew install node`，其他见 https://nodejs.org",
  },
  {
    name: "git",
    level: "error",
    check: () => which("git") && ver("git"),
    fix: "macOS: `xcode-select --install`；Ubuntu: `sudo apt install git`",
  },
  {
    name: "ffmpeg + ffprobe",
    level: "warn",
    check: () => which("ffmpeg") && which("ffprobe"),
    fix: "封面合成/片头嵌入需要。macOS: `brew install ffmpeg`；Ubuntu: `sudo apt install ffmpeg`；Windows: `winget install ffmpeg`",
  },
  {
    name: "python3",
    level: "warn",
    check: () => which("python3") && ver("python3"),
    fix: "mcp-server 与部分脚本需要。macOS: `brew install python3`",
  },
  ...(IS_MAC
    ? ["ego-browser", "cap", "officecli"].map((t) => ({
        name: `${t}（macOS 浏览器发布/录屏/文档工具）`,
        level: "warn",
        check: () => which(t),
        fix: `安装方式见 README「依赖工具」节；装到 ~/.local/bin 亦可`,
      }))
    : []),
  ...(IS_WIN
    ? [{
        name: "uv + patchright（Windows 浏览器发布）",
        level: "warn",
        check: () => which("uv"),
        fix: `powershell: irm https://astral.sh/uv/install.ps1 | iex，然后 uv pip install patchright && patchright install chromium`,
      }]
    : []),
  {
    name: ".env 配置文件",
    level: "error",
    check: () => envKeys().file,
    fix: "cp .env.example .env，然后填入密钥",
  },
  {
    name: "火山引擎 Ark API Key（vol_agent_api_key）",
    level: "warn",
    check: () => {
      const { file, keys } = envKeys();
      if (!file) return false;
      return keys.has("vol_agent_api_key") || keys.has("ark_api_key");
    },
    fix: "编辑 .env 填入 vol_agent_api_key（https://console.volcengine.com/ark）；TTS/图像/视频生成都需要",
  },
  {
    name: "remotion-app 依赖（node_modules）",
    level: "error",
    check: () => fs.existsSync(path.join(VAAS, "remotion-app/node_modules")),
    fix: "npm install --prefix remotion-app",
  },
  {
    name: "VoiceoverVideo 合成已注册",
    level: "error",
    check: () => {
      const p = path.join(VAAS, "remotion-app/src/Composition.tsx");
      return fs.existsSync(p) && fs.readFileSync(p, "utf8").includes('id="VoiceoverVideo"');
    },
    fix: "按 .agents/skills/fd-vaas-video-creator/references/setup.md 完成一次性设置",
  },
  {
    name: ".claude/skills 技能链接完整",
    level: "warn",
    check: () => {
      const missing = SKILL_LINKS.filter((n) => !fs.existsSync(path.join(VAAS, ".claude/skills", n, "SKILL.md")));
      return missing.length === 0 ? true : `缺失: ${missing.join(", ")}`;
    },
    fix: "重跑 ./install.sh（幂等修复链接）",
  },
];

let hasError = false;
console.log(`🩺 VAAS doctor — ${VAAS}\n`);
for (const c of CHECKS) {
  let r;
  try {
    r = c.check();
  } catch {
    r = false;
  }
  const pass = r !== false && r !== undefined && r !== null;
  if (pass) {
    console.log(`✅ ${c.name}${typeof r === "string" ? ` — ${r}` : ""}`);
  } else if (c.level === "error") {
    hasError = true;
    console.log(`❌ ${c.name}\n   修复: ${c.fix}`);
  } else {
    console.log(`⚠️  ${c.name}\n   修复: ${c.fix}`);
  }
}
console.log(hasError ? "\n存在 ❌ 项，核心管线不可用，请先按上方修复。" : "\n核心管线就绪。⚠️ 项仅影响可选能力。");
process.exit(hasError ? 1 : 0);

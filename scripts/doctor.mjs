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

// .env 关键变量存在性（不读值；占位符视为未配置）
const PLACEHOLDER = /^(your[-_]|your_|changeme|xxx+|<.*>|\.\.\.)/i;
const envKeys = () => {
  const p = path.join(VAAS, ".env");
  if (!fs.existsSync(p)) return { file: false, keys: new Set() };
  const keys = new Set();
  for (const line of fs.readFileSync(p, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(\S+)/);
    if (m && m[2] && !m[2].startsWith("#") && !PLACEHOLDER.test(m[2])) keys.add(m[1].toLowerCase());
  }
  return { file: true, keys };
};

const SKILL_LINKS = [
  "fd-browser-record", "fd-coding-wifi-tunnel", "fd-cover-image",
  "fd-vaas-brainstorm", "fd-vaas-dashboard", "fd-vaas-dashboard-sharing",
  "fd-vaas-login", "fd-vaas-publish-docs", "fd-vaas-publish-videos",
  "fd-vaas-video-creator", "ppt-master",
];

// 平台感知的 Python 启动器（Windows 惯例 py/python，POSIX python3）
// 解释器解析顺序：VAAS_PYTHON 显式指定 > 仓内 .venv > 系统 python3。
// 背景：系统 python 被 homebrew 升到新 major 后依赖全空（doctor 与 ci-local
// 同时误判「核心管线不可用」），项目 venv 才是稳定口径。
function resolvePy() {
  if (process.env.VAAS_PYTHON) return process.env.VAAS_PYTHON;
  const venv = process.platform === "win32"
    ? path.join(VAAS, ".venv", "Scripts", "python.exe")
    : path.join(VAAS, ".venv", "bin", "python");
  if (fs.existsSync(venv)) return venv;
  return IS_WIN ? (which("py") ? "py" : "python") : "python3";
}
const pyCmd = resolvePy();

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
    level: "error",
    check: () => which("ffmpeg") && which("ffprobe"),
    fix: "渲染/分段合成/实测时长核心依赖。macOS: `brew install ffmpeg`；Ubuntu: `sudo apt install ffmpeg`；Windows: `winget install ffmpeg`",
  },
  {
    name: "python3",
    level: "error",
    check: () => which(pyCmd) && ver(pyCmd),
    fix: "mcp-server 平面与分发运行时必需。macOS: `brew install python@3.12`；Windows: `winget install python`",
  },
  ...(IS_MAC
    ? ["ego-browser", "cap", "officecli"].map((t) => ({
        name: `${t}（macOS 浏览器发布/录屏/文档工具）`,
        level: "warn",
        check: () => which(t),
        fix: `安装方式见 README「前置条件」节；装到 ~/.local/bin 亦可`,
      }))
    : []),
  {
    name: "uv + patchright（分发运行时，全平台）",
    level: "warn",
    check: () => {
      if (!which("uv")) return false;
      try {
        execSync(`${pyCmd} -c "import patchright"`, { stdio: "pipe" });
        return true;
      } catch {
        return which("patchright");
      }
    },
    fix: `安装 uv（macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh；Windows powershell: irm https://astral.sh/uv/install.ps1 | iex），然后 uv pip install patchright && patchright install chromium`,
  },
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
    // Remotion 已彻底退役（2026-11-09 adopt-hyperframes W6.5）：本地渲染改走
    // hyperframes 渲染面/chromium，不再要求 remotion-app 依赖。
    name: "渲染底座（chromium）",
    level: "warn",
    check: () => {
      const candidates = [
        "/usr/bin/chromium", "/usr/bin/chromium-browser",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      ];
      if (candidates.some((p) => fs.existsSync(p))) return true;
      try { execSync("chromium --version || chromium-browser --version", { stdio: "pipe" }); return true; } catch {}
      return which("chromium") || which("google-chrome") || which("chrome");
    },
    fix: "装 chromium/Chrome（托管镜像内已自带 /usr/bin/chromium；本机出片 render_video/render_still 需要）",
  },
  {
    name: "mcp-server 平面（stdio 工具面）",
    level: "error",
    check: () => {
      try {
        execSync(`${pyCmd} -c "import mcp_server.main"`, {
          cwd: path.join(VAAS, "mcp-server"), stdio: "pipe", timeout: 15000,
        });
      } catch {
        return false;
      }
      if (IS_WIN) return "可导入（拉活探针 Windows 跳跑，见 install.sh 验证路径）";
      const init = JSON.stringify({
        jsonrpc: "2.0", id: 1, method: "initialize",
        params: {
          protocolVersion: "2024-11-05", capabilities: {},
          clientInfo: { name: "vaas-doctor", version: "0" },
        },
      });
      try {
        const out = execSync(
          `printf '%s\\n' ${JSON.stringify(init)} | ${pyCmd} -m mcp_server.main 2>/dev/null | head -c 4000`,
          { cwd: path.join(VAAS, "mcp-server"), stdio: "pipe", timeout: 25000 },
        ).toString();
        return out.includes('"result"') ? "可导入 + stdio 可拉起" : false;
      } catch {
        return false;
      }
    },
    fix: "python3 -m pip install -e ./mcp-server（Windows: py -m pip install -e .\\mcp-server）；仍失败见 mcp-server/README.md",
  },
  {
    name: ".mcp.json（客户端接入配置）",
    level: "warn",
    check: () => fs.existsSync(path.join(VAAS, ".mcp.json")),
    fix: "重跑 ./install.sh（自动生成模板）或手写指向 python3 -m mcp_server.main",
  },
  {
    // 原「VoiceoverVideo 合成已注册」检查随 Remotion 退役失效：本地 node 渲染
    // 管线已下线，成片统一走 render_video（hyperframes 渲染面/托管 HTML）。
    name: "视频类型契约完整（types/*/type.json）",
    level: "warn",
    check: () => {
      const dir = path.join(VAAS, ".agents/skills/fd-vaas-video-creator/types");
      if (!fs.existsSync(dir)) return false;
      const types = fs.readdirSync(dir).filter((d) => fs.existsSync(path.join(dir, d, "type.json")));
      return types.length >= 5 ? `${types.length} 个类型` : false;
    },
    fix: "确认 .agents/skills/fd-vaas-video-creator/types/ 下五类型 type.json 齐全（renderer=hyperframes）",
  },
  {
    name: ".claude/skills 技能链接完整",
    level: "warn",
    check: () => {
      const missing = SKILL_LINKS.filter((n) => !fs.existsSync(path.join(VAAS, ".claude/skills", n, "SKILL.md")));
      return missing.length === 0 ? "全部就绪" : false;
    },
    fix: "重跑 ./install.sh（幂等修复链接；缺项见检查输出比对 SKILL_LINKS）",
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

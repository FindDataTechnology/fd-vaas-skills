/**
 * confirm-gate.mjs — 发布人工确认闸（哨兵文件形态）的共用纯逻辑。
 *
 * 与 Python 侧 `_shared/publish/browser_utils.confirm_gate` 同语义（enforce-publish-confirmation-gate
 * W1.1/W1.2/W5.1 要求三条链路同闸形态）：
 *   - 确认凭据 = 系统临时目录下的哨兵文件，人工复核后 `touch` 它即放行；
 *   - 凭据缺失 = 拒绝发布（fail closed），绝不超时自动放行；
 *   - 不读 stdin —— 非 TTY 环境天然走同一拒绝路径，不存在「EOF 静默放行」；
 *   - Windows 可移植：路径 = VAAS_GATE_DIR env 覆盖 ?? os.tmpdir()，MUST NOT 硬编码 POSIX /tmp。
 *
 * 消费语义与 Python wait_for_file 对齐：哨兵被消费即删除（一次确认只放行一次），
 * 防止上次遗留的哨兵静默放行下次发布。docs 自有平台的 patchright 路径例外：
 * 哨兵由 Python confirm_gate 消费（JS 只负责算路径，见 publish.mjs），故 consume=false。
 */
import fs from "fs";
import os from "os";
import path from "path";

// 与 Python 侧一致的命名前缀：图文 vaas-doc-*，视频 vaas-video-*
export const GATE_PREFIX_DOC = "vaas-doc";
export const GATE_PREFIX_VIDEO = "vaas-video";

/** 哨兵基目录：VAAS_GATE_DIR 优先（Windows 节点 /tmp 不可写的逃生口），否则系统临时目录。 */
export function resolveTempDir(env = process.env) {
  return env.VAAS_GATE_DIR || os.tmpdir();
}

/** 默认哨兵文件路径：<tempdir>/<prefix>-<platform>.go。platform 为空则报错（防「空凭据」挂死）。 */
export function defaultGateFile(platform, prefix = GATE_PREFIX_VIDEO, env = process.env) {
  if (!platform) {
    throw new Error("defaultGateFile 需要平台名（空平台名=无效凭据，必须拒绝而非挂等）");
  }
  return path.join(resolveTempDir(env), `${prefix}-${platform}.go`);
}

/**
 * 检查一个平台的确认凭据。纯同步：存在即消费放行，缺失即拒绝（不等待——视频链路是
 * 批次组装阶段一次性检查，缺失时打印补齐方法后 exit 非零，零 spawn）。
 *
 * @param {string} platform 平台名
 * @param {object} opts
 *   - confirmFile: 显式 `--confirm-file` 路径（覆盖默认哨兵名；空串=未给，用默认）
 *   - autoPublish: 显式 `--auto-publish` 旁路。返回 source="auto-publish"，调用方
 *     MUST 在回执/台账记录里标注 auto_publish: true（spec：旁路仅显式声明方可存在）
 *   - prefix: 哨兵命名前缀（默认 vaas-video；docs 路径用 vaas-doc）
 *   - consume: 放行时删除哨兵（默认 true；docs 侧交 Python 消费时传 false）
 * @returns {{ok: boolean, source: string, gateFile: string|null, reason: string}}
 *   source ∈ "auto-publish" | "sentinel" | "missing"
 */
export function checkGate(platform, opts = {}) {
  const { confirmFile = "", autoPublish = false, prefix = GATE_PREFIX_VIDEO, consume = true, env = process.env } = opts;
  if (autoPublish) {
    return { ok: true, source: "auto-publish", gateFile: null, reason: "--auto-publish 显式旁路（回执须标注）" };
  }
  const gateFile = String(confirmFile ?? "").trim() || defaultGateFile(platform, prefix, env);
  if (fs.existsSync(gateFile)) {
    if (consume) {
      try { fs.unlinkSync(gateFile); } catch { /* 删失败不阻塞放行（等价的 touch-rm 竞争） */ }
    }
    return { ok: true, source: "sentinel", gateFile, reason: `收到确认哨兵: ${gateFile}` };
  }
  return {
    ok: false,
    source: "missing",
    gateFile,
    reason: `缺人工确认：未找到哨兵文件 ${gateFile}（复核后 touch 它重跑，或显式 --auto-publish 旁路并标注）`,
  };
}

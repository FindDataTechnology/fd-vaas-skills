#!/usr/bin/env node
/**
 * registry.mjs — 视频类型注册表（schema + 发现 + 校验）
 *
 * 一个类型 = <skill>/types/<type-id>/type.json。注册即文件系统：
 * 新增类型只需新建目录 + type.json，不改任何核心脚本。
 *
 * type.json schema（v1）:
 *   {
 *     id:          string  kebab-case，必须与目录名一致
 *     name:        string  人类可读名称
 *     description: string
 *     version:     int ≥ 1
 *     status:      "experimental" | "stable"
 *     inputs:      { <key>: { required: bool, type: "file"|"json"|"text"|"enum",
 *                             desc: string, default?, enum? (type=enum 时必填) } }
 *     pipeline:    string[]  步骤名序列；含 "render" 时 composition 必填
 *     composition: string | null   （Remotion composition id；无 render 步骤可为 null）
 *     defaults:    object   （渲染/分段默认参数；透传到 render props，保留键见下）
 *     platforms:   string[] （适用发布平台）
 *   }
 *
 * defaults 保留键（被 pipeline 消费，不透传）:
 *   voice, tailPad, gapMs, minSegmentMs, padFrames
 *
 * API:
 *   validateType(def, source)      → 错误字符串数组（空 = 合法）
 *   loadRegistry({reload})         → { types: Map<id, def+{dir}>, errors: [{id,path,errors}] }
 *   getType(id)                    → def | null
 *   listTypes()                    → def[]
 *   registryErrors()               → 加载期错误（非法 type.json 不影响其他类型）
 *   loadTypeSteps(def)             → types/<id>/steps.mjs 的 default export（无则 {}）
 */
import fs from "fs";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

export const SKILL_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
export const TYPES_DIR = path.join(SKILL_ROOT, "types");

export const INPUT_TYPES = ["file", "json", "text", "enum"];
export const TYPE_STATUSES = ["experimental", "stable"];

const ID_RE = /^[a-z0-9][a-z0-9-]*$/;

export function validateType(def, source = "type.json") {
  const errors = [];
  const err = (m) => errors.push(`${source}: ${m}`);
  if (!def || typeof def !== "object" || Array.isArray(def)) {
    return [`${source}: must be a JSON object`];
  }

  if (typeof def.id !== "string" || !ID_RE.test(def.id)) {
    err(`field "id" must be a kebab-case string matching ${ID_RE}`);
  }
  for (const f of ["name", "description"]) {
    if (typeof def[f] !== "string" || !def[f].trim()) {
      err(`field "${f}" must be a non-empty string`);
    }
  }
  if (!Number.isInteger(def.version) || def.version < 1) {
    err(`field "version" must be an integer ≥ 1`);
  }
  if (!TYPE_STATUSES.includes(def.status)) {
    err(`field "status" must be one of: ${TYPE_STATUSES.join(" | ")}`);
  }

  if (def.inputs !== undefined) {
    if (typeof def.inputs !== "object" || def.inputs === null || Array.isArray(def.inputs)) {
      err(`field "inputs" must be an object keyed by input name`);
    } else {
      for (const [key, inp] of Object.entries(def.inputs)) {
        const p = `inputs."${key}"`;
        if (!inp || typeof inp !== "object" || Array.isArray(inp)) {
          err(`${p} must be an object {required, type, desc, ...}`);
          continue;
        }
        if (typeof inp.required !== "boolean") err(`${p}.required must be a boolean`);
        if (!INPUT_TYPES.includes(inp.type)) {
          err(`${p}.type must be one of: ${INPUT_TYPES.join(" | ")}`);
        }
        if (typeof inp.desc !== "string" || !inp.desc.trim()) {
          err(`${p}.desc must be a non-empty string`);
        }
        if (inp.type === "enum") {
          if (!Array.isArray(inp.enum) || inp.enum.length === 0) {
            err(`${p}.enum must be a non-empty array when type="enum"`);
          } else if (inp.default !== undefined && !inp.enum.includes(inp.default)) {
            err(`${p}.default must be one of its enum values`);
          }
        }
      }
    }
  }

  const pipelineOk =
    Array.isArray(def.pipeline) &&
    def.pipeline.length > 0 &&
    def.pipeline.every((s) => typeof s === "string" && s.trim());
  if (!pipelineOk) {
    err(`field "pipeline" must be a non-empty array of step names`);
  }

  const needsComposition = pipelineOk && def.pipeline.includes("render");
  if (needsComposition) {
    if (typeof def.composition !== "string" || !def.composition.trim()) {
      err(`field "composition" is required (pipeline contains "render")`);
    }
  } else if (
    def.composition !== undefined &&
    def.composition !== null &&
    typeof def.composition !== "string"
  ) {
    err(`field "composition" must be a string or null`);
  }

  if (
    def.defaults !== undefined &&
    (typeof def.defaults !== "object" || def.defaults === null || Array.isArray(def.defaults))
  ) {
    err(`field "defaults" must be an object`);
  }
  if (
    def.platforms !== undefined &&
    (!Array.isArray(def.platforms) || !def.platforms.every((p) => typeof p === "string"))
  ) {
    err(`field "platforms" must be a string array`);
  }

  return errors;
}

let _cache = null;

export function loadRegistry({ reload = false } = {}) {
  if (_cache && !reload) return _cache;
  const types = new Map();
  const errors = [];
  if (fs.existsSync(TYPES_DIR)) {
    for (const entry of fs.readdirSync(TYPES_DIR).sort()) {
      const dir = path.join(TYPES_DIR, entry);
      const file = path.join(dir, "type.json");
      if (!fs.statSync(dir).isDirectory() || !fs.existsSync(file)) continue;

      let def;
      try {
        def = JSON.parse(fs.readFileSync(file, "utf8"));
      } catch (e) {
        errors.push({ id: entry, path: file, errors: [`invalid JSON: ${e.message}`] });
        continue;
      }
      const errs = validateType(def, file);
      if (def?.id && def.id !== entry) {
        errs.push(`${file}: field "id" ("${def.id}") must match directory name "${entry}"`);
      }
      if (errs.length) {
        errors.push({ id: def?.id ?? entry, path: file, errors: errs });
        continue;
      }
      types.set(def.id, { ...def, dir });
    }
  }
  _cache = { types, errors };
  return _cache;
}

export function getType(id) {
  return loadRegistry().types.get(id) ?? null;
}

export function listTypes() {
  return [...loadRegistry().types.values()];
}

export function registryErrors() {
  return loadRegistry().errors;
}

/** 类型自带的 pipeline 步骤覆盖：types/<id>/steps.mjs default export {name: (ctx)=>ctx} */
export async function loadTypeSteps(def) {
  const p = path.join(def.dir, "steps.mjs");
  if (!fs.existsSync(p)) return {};
  const mod = await import(pathToFileURL(p).href);
  const steps = mod.default ?? {};
  if (typeof steps !== "object") {
    throw new Error(`${p}: default export must be an object {stepName: fn}`);
  }
  return steps;
}

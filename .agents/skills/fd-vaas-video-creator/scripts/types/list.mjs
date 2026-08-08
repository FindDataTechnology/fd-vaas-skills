#!/usr/bin/env node
/**
 * list.mjs — 打印已注册的视频类型清单
 *
 * 用法:
 *   node scripts/types/list.mjs [--json]
 *
 * 每个类型显示: id / 名称 / 状态 / pipeline / composition / 必填与可选输入 / 适用平台 / 简介。
 * 非法 type.json 不会中断列表，在末尾统一报告。
 */
import { listTypes, registryErrors } from "./registry.mjs";

const asJson = process.argv.includes("--json");
const types = listTypes();
const errors = registryErrors();

if (asJson) {
  console.log(
    JSON.stringify(
      {
        types: types.map(({ dir, ...t }) => t),
        errors,
      },
      null,
      2,
    ),
  );
  process.exit(errors.length ? 1 : 0);
}

if (!types.length) {
  console.log("（还没有注册任何视频类型 — 在 types/<id>/type.json 下新增）");
}

const fmtInput = (key, inp) => {
  let s = `  ${inp.required ? "必填" : "可选"}  --${key}`;
  s += `  (${inp.type}`;
  if (inp.type === "enum") s += `: ${inp.enum.join(" | ")}`;
  if (inp.default !== undefined) s += `, 默认 ${JSON.stringify(inp.default)}`;
  s += `)  ${inp.desc}`;
  return s;
};

for (const t of types) {
  const statusIcon = t.status === "stable" ? "✅" : "🧪";
  console.log(`\n${statusIcon} ${t.id} — ${t.name} [${t.status}] v${t.version}`);
  console.log(`   ${t.description}`);
  console.log(`   pipeline   : ${t.pipeline.join(" → ")}`);
  if (t.composition) console.log(`   composition: ${t.composition}（模板: remotion-app/src/types/${t.composition}.tsx）`);
  const inputs = Object.entries(t.inputs ?? {});
  if (inputs.length) {
    console.log(`   inputs:`);
    for (const [k, inp] of inputs) console.log(fmtInput(k, inp));
  }
  if (t.platforms?.length) console.log(`   platforms  : ${t.platforms.join(", ")}`);
}

if (errors.length) {
  console.log(`\n⚠️  ${errors.length} 个非法类型定义被跳过:`);
  for (const e of errors) {
    for (const msg of e.errors) console.log(`   - ${msg}`);
  }
  process.exitCode = 1;
} else if (types.length) {
  console.log("");
}

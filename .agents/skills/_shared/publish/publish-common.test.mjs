import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";

import {
  loadEnv,
  truncate,
  stripMd,
  mdToPlain,
  summarize,
  ensureSeconds,
  limitTags,
} from "./publish-common.mjs";

test("truncate: 中文不超长原样保留", () => {
  const s = "让公开信息真正可被计算";
  assert.equal(truncate(s, 100), s);
});

test("truncate: 超长按字数截断并加省略号", () => {
  const s = "一二三四五六七八九十";
  assert.equal(truncate(s, 6), "一二三四五…");
  assert.equal(truncate(s, 6).length, 6);
});

test("truncate: 含 emoji(按 JS 码元计数,现有行为)", () => {
  const s = "a🚀b🚀c🚀d"; // .length=10(🚀 是代理对,计 2 码元)
  // slice(0,4) 落在 'b' 之后,不切代理对 → "a🚀b" + "…"
  assert.equal(truncate(s, 5), "a🚀b" + "…");
});

test("truncate: max=0 不截断", () => {
  assert.equal(truncate("abcdef", 0), "abcdef");
});

test("mdToPlain: 保留代码块内容", () => {
  const md = "正文\n\n```bash\npip install patchright\n```\n\n收尾";
  const out = mdToPlain(md);
  assert.ok(out.includes("pip install patchright"), "代码块内容应保留");
  assert.ok(!out.includes("```"), "代码块围栏应去除");
});

test("mdToPlain: 去标题井号、行内代码、链接", () => {
  const md = "## 标题\n\n用 `npm` 安装 [Claude](https://claude.com)。";
  const out = mdToPlain(md);
  assert.ok(!out.includes("##"), "标题井号应去除");
  assert.ok(!out.includes("`"), "行内代码反引号应去除");
  assert.ok(out.includes("Claude"), "链接文本应保留");
  assert.ok(!out.includes("https://claude.com"), "链接 URL 应去除");
});

test("stripMd: 去 front matter 与链接", () => {
  const md = "---\ntitle: x\n---\n\n正文见 [链接](https://example.com)。";
  const out = stripMd(md);
  assert.ok(!out.includes("title:"), "front matter 应去除");
  assert.ok(out.includes("链接"), "链接文本应保留");
  assert.ok(!out.includes("example.com"), "链接 URL 应去除");
});

test("summarize: 超长截断加省略号", () => {
  const md = "a".repeat(200);
  const out = summarize(md, 50);
  assert.equal(out.length, 50);
  assert.ok(out.endsWith("…"));
});

test("limitTags: 限数、去空、trim", () => {
  assert.deepEqual(limitTags("a, b, , c,", 2), ["a", "b"]);
  assert.deepEqual(limitTags("开源, AI, 数据", 10), ["开源", "AI", "数据"]);
  assert.deepEqual(limitTags("a,b", 0), [], "max=0 应返回空");
  assert.deepEqual(limitTags("", 5), []);
});

test("ensureSeconds: 补秒 / 原样", () => {
  assert.equal(ensureSeconds("2026-07-20 21:30"), "2026-07-20 21:30:00");
  assert.equal(ensureSeconds("2026-07-20 21:30:45"), "2026-07-20 21:30:45");
});

test("loadEnv: 解析 key=value、跳注释、剥引号", () => {
  const tmp = path.join(os.tmpdir(), `publish-common-${process.pid}.env`);
  fs.writeFileSync(tmp, 'A=1\n# comment\nB="hello world"\n\nC=unquoted\n');
  try {
    const out = loadEnv(tmp);
    assert.deepEqual(out, { A: "1", B: "hello world", C: "unquoted" });
  } finally {
    fs.unlinkSync(tmp);
  }
});

test("loadEnv: 文件不存在返回空对象", () => {
  assert.deepEqual(loadEnv("/no/such/file.env"), {});
});

#!/usr/bin/env python3
"""Fix TTS timestamps: extend each token's endMs to the next token's startMs.
   The TTS API returns near-zero durations for Latin tokens; the gap-to-next
   is where the actual audio lives. Then aggregate to sentence timings.

   NOTE: one-off helper kept for reference; the reusable equivalent is
   .agents/skills/fd-vaas-video-creator/scripts/fix-tts-timings.mjs

   Usage: python3 compute-timings.py <captions.json> [fixed-out.json]
"""
import json
import sys
import os

inp = sys.argv[1] if len(sys.argv) > 1 else None
if not inp or not os.path.exists(inp):
    sys.exit(f"usage: {sys.argv[0]} <captions.json> [fixed-out.json]")
outp = sys.argv[2] if len(sys.argv) > 2 else inp.replace('.json', '-fixed.json')

with open(inp) as f:
    caps = json.load(f)

# Fix: extend endMs to next startMs (last token keeps its own endMs)
for i in range(len(caps) - 1):
    caps[i]['endMs'] = caps[i + 1]['startMs']

# Save fixed captions too
with open(outp, 'w') as f:
    json.dump(caps, f, ensure_ascii=False)

sentences = [
    '公开信息，本该人人可用。',
    '可它散落在部委公告、公司财报、统计数据里，',
    '锁在 PDF，没有统一字段。',
    'FindDataTechnology，',
    '要让世界上的公开信息，真正可被计算。',
    '我们做三件事。',
    '采集，把各国政府与统计栏目，目录化抓成干净记录。',
    '结构化，用规则把财报和公告，变成带 schema 的字段。',
    '服务，每个数据集都封装成 MCP 服务器，',
    '任何 AI 都能发现并调用。',
    '我们的开源工作，从中国开始。',
    'DAAS，六百七十三项金融函数，',
    '一个接口调全世界。',
    'fd-cn-gov，十一个部委公告，',
    '一键目录化采集。',
    'fd-cn-report，三十一个行业、两万多条规则，',
    '把年报 PDF 变成结构化指标。',
    '还有 Platform 和 coding，',
    '把这一切串起来。',
    '过去要几天的人工调研，',
    '现在一次查询。',
    '无论提问者是分析师，还是 AI。',
    'FindDataTechnology，',
    '让世界的信息，人人可用。',
    'github.com/FindDataOfficial，',
    '欢迎 Star、Issue、PR。',
]

token_texts = [t['text'] for t in caps]
combined = ''.join(token_texts)

def norm(s):
    return s.replace(' ', '').replace('\n', '')

combined_norm = norm(combined)

results = []
search_pos = 0
for sent in sentences:
    s_norm = norm(sent)
    idx = combined_norm.find(s_norm, search_pos)
    if idx == -1:
        s_norm2 = s_norm.rstrip('。，')
        idx = combined_norm.find(s_norm2, search_pos)
        if idx == -1:
            print(f"MISS: '{sent[:40]}'")
            continue
        char_after = combined_norm[idx + len(s_norm2):idx + len(s_norm2) + 1]
        if char_after in ('。', '，'):
            s_norm = s_norm2 + char_after
        else:
            s_norm = s_norm2

    cum = 0
    start_tok = 0
    for i, tt in enumerate(token_texts):
        lt = len(tt)
        if cum + lt > idx:
            start_tok = i
            break
        cum += lt

    end_pos = idx + len(s_norm)
    cum = 0
    end_tok = len(token_texts) - 1
    for i, tt in enumerate(token_texts):
        cum += len(tt)
        if cum >= end_pos:
            end_tok = i
            break

    start_ms = caps[start_tok]['startMs']
    end_ms = caps[end_tok]['endMs']
    results.append((sent, start_ms, end_ms))
    search_pos = idx + len(s_norm)

print(f"Matched {len(results)}/{len(sentences)} sentences\n")
print("const SENTENCE_TIMINGS_MS = [")
for i, (sent, start, end) in enumerate(results):
    print(f"  [{start}, {end}], // {i}: {sent[:40]}")
print("];")

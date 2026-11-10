---
name: remotion-captions
description: [legacy] Dealing with captions in Remotion
metadata:
  tags: subtitles, captions, remotion, json
---

> ⚠️ **legacy / 离线参考**：VAAS 出片链已切 HyperFrames，`remotion-app/` 已删除（2026-11-09）。
> 本文仅作通用 Remotion 知识参考，**不要**按它在本仓跑命令——本仓没有 Remotion 项目可跑。
> 退役台账：`docs/debt-ledger.md` DEBT-REMOTION-RESIDUE-01。

All captions must be processed in JSON. The captions must use the [`Caption`](https://www.remotion.dev/docs/captions/caption.md) type which is the following:

```ts
import type { Caption } from "@remotion/captions";
```

This is the definition:

```ts
type Caption = {
  text: string;
  startMs: number;
  endMs: number;
  timestampMs: number | null;
  confidence: number | null;
};
```

## Generating captions

To transcribe video and audio files to generate captions, load the [transcribe-captions.md](transcribe-captions.md) file for more instructions.

## Displaying captions

To display captions in your video, load the [display-captions.md](display-captions.md) file for more instructions.

## Importing captions

To import captions from a .srt file, load the [import-srt-captions.md](import-srt-captions.md) file for more instructions.

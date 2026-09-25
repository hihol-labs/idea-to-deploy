#!/usr/bin/env python3
"""Measure one unit window from Claude Code transcripts (PILOT-LOW-1).

Reads every *.jsonl under the given transcript roots (main sessions and their
subagents/), keeps assistant rows whose timestamp falls inside [start, end],
and prints JSON with:
  toolCalls      - tool_use blocks, main + subagents
  tokenUnits     - thousands of NEW tokens (input + cache creation + output),
                   each API message counted once; this goes to the ledger
  processedTokenUnits - the same plus cache reads (grows with context size,
                   so it is kept for the retro only)
  ioTokenUnits   - thousands of input + output tokens only; cache creation is
                   excluded because full-context cache re-creations scale with
                   context size, not with the work of the unit
  cacheCreationTokenUnits - thousands of cache-creation tokens
  wallMinutes    - end - start
  activeMinutes  - sum of gaps < GAP_MINUTES between consecutive rows
                   (idle stretches such as a night are dropped)
Read-only; stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

GAP_MINUTES = 15.0
FIELDS = ("input_tokens", "cache_creation_input_tokens",
          "cache_read_input_tokens", "output_tokens")


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("roots", nargs="+", type=Path)
    args = ap.parse_args()
    start, end = ts(args.start), ts(args.end)
    seen: dict[str, dict[str, int]] = {}
    tool_ids: set[str] = set()
    anonymous_tools = 0
    stamps: list[datetime] = []
    for root in args.roots:
        files = [root] if root.is_file() else sorted(root.rglob("*.jsonl"))
        for path in files:
            for line in path.open(encoding="utf-8", errors="replace"):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw = row.get("timestamp")
                if not raw:
                    continue
                at = ts(raw)
                if not start <= at <= end:
                    continue
                stamps.append(at)
                if row.get("type") != "assistant":
                    continue
                msg = row.get("message") or {}
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        # the same tool_use block can be logged on several rows
                        if block.get("id"):
                            tool_ids.add(block["id"])
                        else:
                            anonymous_tools += 1
                mid = msg.get("id")
                usage = msg.get("usage") or {}
                if mid:
                    # a message spans several rows; keep the largest value per field
                    best = seen.setdefault(mid, {})
                    for key in FIELDS:
                        best[key] = max(best.get(key, 0), int(usage.get(key) or 0))
    tokens = sum(u[k] for u in seen.values() for k in FIELDS
                 if k != "cache_read_input_tokens")
    cached = sum(u["cache_read_input_tokens"] for u in seen.values())
    created = sum(u["cache_creation_input_tokens"] for u in seen.values())
    io_tokens = sum(u["input_tokens"] + u["output_tokens"] for u in seen.values())
    stamps.sort()
    active = sum(
        gap for gap in ((b - a).total_seconds() / 60 for a, b in zip(stamps, stamps[1:]))
        if gap < GAP_MINUTES
    )
    json.dump({
        "toolCalls": len(tool_ids) + anonymous_tools,
        "tokenUnits": round(tokens / 1000, 1),
        "processedTokenUnits": round((tokens + cached) / 1000, 1),
        "ioTokenUnits": round(io_tokens / 1000, 1),
        "cacheCreationTokenUnits": round(created / 1000, 1),
        "apiMessages": len(seen),
        "wallMinutes": round((end - start).total_seconds() / 60, 2),
        "activeMinutes": round(active, 2),
    }, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

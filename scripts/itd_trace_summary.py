#!/usr/bin/env python3
"""Summarize execution-trace telemetry (v1.42.0).

`hooks/execution-trace.sh` writes one JSON line per tool call to
`.claude/traces/session-<id>.jsonl`. Until now nothing read that stream —
observability that nobody looks at is a write-only ritual. This reader turns a
trace into a 10-line digest fit for /session-save or debugging the harness:

  python3 scripts/itd_trace_summary.py [path/to/project | trace.jsonl]

With a directory argument (default: cwd) it picks the freshest trace under
`.claude/traces/`. Output: span, call count, per-tool breakdown, top targets,
and idle gaps > 60s (a gap usually marks a stall, a human pause, or a crash).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


def pick_trace(arg: str | None) -> Path | None:
    p = Path(arg) if arg else Path.cwd()
    if p.is_file():
        return p
    traces = sorted((p / ".claude" / "traces").glob("session-*.jsonl"),
                    key=lambda f: f.stat().st_mtime, reverse=True)
    return traces[0] if traces else None


def parse_ts(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def main() -> int:
    trace = pick_trace(sys.argv[1] if len(sys.argv) > 1 else None)
    if trace is None:
        print("no trace found (.claude/traces/session-*.jsonl)")
        return 0

    events = []
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    if not events:
        print(f"{trace}: empty trace")
        return 0

    tools = Counter(str(e.get("tool", "?")) for e in events)
    targets = Counter(str(e.get("target", ""))[:80] for e in events if e.get("target"))
    stamps = [t for t in (parse_ts(e.get("ts")) for e in events) if t]

    print(f"trace: {trace}")
    print(f"calls: {len(events)}")
    if stamps:
        span = max(stamps) - min(stamps)
        print(f"span:  {min(stamps).isoformat()} .. {max(stamps).isoformat()} ({span})")
        gaps = []
        for a, b in zip(stamps, stamps[1:]):
            d = (b - a).total_seconds()
            if d > 60:
                gaps.append((a.isoformat(), int(d)))
        if gaps:
            print(f"idle gaps >60s: {len(gaps)} (первые 5):")
            for ts, d in gaps[:5]:
                print(f"  {ts}  +{d}s")
    print("tools:", ", ".join(f"{t}×{n}" for t, n in tools.most_common(10)))
    print("top targets:")
    for t, n in targets.most_common(5):
        print(f"  {n:>4}  {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

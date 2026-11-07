#!/usr/bin/env python3
"""Run a list of pilot runs, at most 3 at a time, checking the budget ceilings (protocol section 9) before each start.

  batch.py K1:baseline:1 K1:baseline:2 ...
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
S13 = HERE.parent / "ITD-PLAN-S13" / "pilot"
MAX_RUNS, MAX_WALL, MAX_TOKENS, PAR = 30, 8 * 3600, 40_000_000, 3


def records():
    out = []
    for d in (S13, HERE / "runs"):
        for p in sorted(d.glob("run-*.json")):
            out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def tokens(r):
    if r.get("tokensTotal") is not None:
        return r["tokensTotal"]
    return sum(r.get(k) or 0 for k in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheCreationTokens"))


def totals():
    rs = records()
    return len(rs), sum(r.get("wallSeconds") or 0 for r in rs), sum(tokens(r) for r in rs)


def main(items):
    log = open(HERE / "batch.log", "a", encoding="utf-8")
    running: list = []
    queue = list(items)
    while queue or running:
        running = [(it, p) for it, p in running if p.poll() is None]
        if queue and len(running) < PAR:
            n, wall, tok = totals()
            n += len(running)
            if n >= MAX_RUNS or wall >= MAX_WALL or tok >= MAX_TOKENS:
                log.write(f"{time.strftime('%FT%TZ', time.gmtime())} STOP ceiling runs={n} wall={wall:.0f} "
                          f"tokens={tok}; not started: {queue}\n")
                log.flush()
                queue = []
                continue
            it = queue.pop(0)
            case, variant, rn = it.split(":")
            out = open(HERE / "runs" / f"stdout-{case}-{variant}-r{rn}.txt", "w", encoding="utf-8")
            p = subprocess.Popen([sys.executable, str(HERE / "pilot_run.py"), "run", case, variant, rn, "10", "1500"],
                                 stdout=out, stderr=subprocess.STDOUT)
            log.write(f"{time.strftime('%FT%TZ', time.gmtime())} START {it} pid={p.pid}\n")
            log.flush()
            running.append((it, p))
            time.sleep(5)
            continue
        time.sleep(10)
    n, wall, tok = totals()
    log.write(f"{time.strftime('%FT%TZ', time.gmtime())} DONE runs={n} wall={wall:.0f} tokens={tok}\n")


if __name__ == "__main__":
    main(sys.argv[1:])

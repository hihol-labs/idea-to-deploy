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
S13 = HERE / "s13"  # session 13 records (the pilot ran this tool next to them as ITD-PLAN-S13/pilot)
MAX_RUNS, MAX_WALL, MAX_TOKENS, PAR, LIMIT = 30, 8 * 3600, 40_000_000, 3, 1500


def records():
    out = []
    for d in (S13, HERE / "runs"):
        for p in sorted(d.glob("run-*.json")):
            out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


RECOUNTED = json.loads((S13 / "tokens-from-transcript.json").read_text(encoding="utf-8"))


def tokens(r):
    if r.get("tokensTotal") is not None:
        return r["tokensTotal"]
    if r.get("session") in RECOUNTED:
        return RECOUNTED[r["session"]]
    return sum(r.get(k) or 0 for k in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheCreationTokens"))


def totals():
    rs = records()
    return len(rs), sum(r.get("wallSeconds") or 0 for r in rs), sum(tokens(r) for r in rs)


def main(items):
    """Before each start the run and wall-time ceilings must hold with every running run and the new one at their
    worst case (the run limit). Tokens have no per-run limit in the CLI (only --max-budget-usd), so the token check is
    an estimate: the largest recorded run per running and new run. A finished runner without a record, or with a
    non-zero exit, is logged FAIL and counted as one run at the worst case. Duplicate items and items that already
    have a record are refused before anything starts. Exit 0 only when every item ran and none failed."""
    running: list = []
    failed: list = []
    queue = list(items)
    bad = sorted({it for it in queue if queue.count(it) > 1}) + [
        it for it in queue if len(it.split(":")) != 3 or (HERE / "runs" / "run-{}-{}-r{}.json".format(*it.split(":")))
        .exists()]
    if bad:
        print(f"refused: duplicate, malformed or already recorded items {bad}", file=sys.stderr)
        return 2
    stopped = False
    log = open(HERE / "batch.log", "a", encoding="utf-8")

    def stamp():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    while queue or running:
        still = []
        for it, p in running:
            rc = p.poll()
            if rc is None:
                still.append((it, p))
                continue
            case, variant, rn = it.split(":")
            has_record = (HERE / "runs" / f"run-{case}-{variant}-r{rn}.json").exists()
            if rc != 0 or not has_record:
                failed.append(it)
                log.write(f"{stamp()} FAIL {it} rc={rc} record={has_record}\n")
            log.flush()
        running = still
        if queue and len(running) < PAR:
            n, wall, tok = totals()
            worst_tok = max([tokens(r) for r in records()] or [0])
            lost = sum(1 for it in failed
                       if not (HERE / "runs" / f"run-{'-'.join(it.split(':')[:2])}-r{it.split(':')[2]}.json").exists())
            n, wall, tok = n + lost, wall + lost * LIMIT, tok + lost * worst_tok
            k = len(running) + 1
            if n + k > MAX_RUNS or wall + k * LIMIT > MAX_WALL or tok + k * worst_tok > MAX_TOKENS:
                log.write(f"{stamp()} STOP ceiling runs={n}+{k} wall={wall:.0f}+{k}x{LIMIT} "
                          f"tokens={tok}+{k}x{worst_tok}; not started: {queue}\n")
                log.flush()
                queue = []
                stopped = True
                continue
            it = queue.pop(0)
            case, variant, rn = it.split(":")
            out = open(HERE / "runs" / f"stdout-{case}-{variant}-r{rn}.txt", "w", encoding="utf-8")
            p = subprocess.Popen([sys.executable, str(HERE / "pilot_run.py"), "run", case, variant, rn, "10",
                                  str(LIMIT)], stdout=out, stderr=subprocess.STDOUT)
            log.write(f"{stamp()} START {it} pid={p.pid}\n")
            log.flush()
            running.append((it, p))
            time.sleep(5)
            continue
        time.sleep(10)
    n, wall, tok = totals()
    log.write(f"{stamp()} DONE runs={n} wall={wall:.0f} tokens={tok} failed={failed} stopped={stopped}\n")
    return 1 if failed or stopped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

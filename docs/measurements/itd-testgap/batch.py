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
    """Run records plus persisted charges of runners that failed without a record (worst case per failure)."""
    out = []
    for d in (S13, HERE / "runs"):
        for p in sorted(d.glob("run-*.json")) + sorted(d.glob("charge-*.json")):
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
    have a record are refused before anything starts. Exit 0 only when every item ran, none failed and the final
    totals stay within every ceiling."""
    running: list = []
    failed: list = []
    import fcntl
    lock = open(HERE / "batch.lock", "w")
    try:  # one batch at a time, taken before any item is checked: concurrency, the budget reservation and the
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # already-recorded refusal hold only under this lock
    except OSError:
        print("refused: another batch.py holds batch.lock", file=sys.stderr)
        return 2
    queue = list(items)
    bad = sorted({it for it in queue if queue.count(it) > 1}) + [
        it for it in queue if len(it.split(":")) != 3 or any(
            (HERE / "runs" / f"{kind}-{{}}-{{}}-r{{}}.json".format(*it.split(":"))).exists() for kind in ("run", "charge"))]
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
                if not has_record:  # persist the worst-case charge so later invocations still count it
                    worst = max([tokens(r) for r in records()] or [0])
                    (HERE / "runs" / f"charge-{case}-{variant}-r{rn}.json").write_text(json.dumps(
                        {"case": case, "variant": variant, "run": rn, "charge": "runner failed without a record",
                         "wallSeconds": LIMIT, "tokensTotal": worst}) + "\n", encoding="utf-8")
            log.flush()
        running = still
        if queue and len(running) < PAR:
            n, wall, tok = totals()  # includes the persisted charges of earlier failures
            worst_tok = max([tokens(r) for r in records()] or [0])
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
    exceeded = n > MAX_RUNS or wall > MAX_WALL or tok > MAX_TOKENS  # the token reservation is only an estimate
    log.write(f"{stamp()} DONE runs={n} wall={wall:.0f} tokens={tok} failed={failed} stopped={stopped} "
              f"exceeded={exceeded}\n")
    return 1 if failed or stopped or exceeded else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

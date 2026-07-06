#!/usr/bin/env python3
"""Regression test: the completion signal ledger is bounded (not append-only-forever).

Appends far more signals than the cap and asserts the file stays bounded while the
most-recent signals are retained and still readable. Self-contained, stdlib only.
Run: python3 tests/verify_completion_ledger.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import completion_lib as cl  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


# small caps so the prune fires quickly and deterministically
cl.LEDGER_SOFT_BYTES = 2000
cl.MAX_LEDGER_LINES = 40

with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp)
    N = 400
    for i in range(N):
        cl.append_signal(d, "sess", {"i": i, "kind": "test_run", "layer": 2, "outcome": "pass"})

    lines = cl.signals_path(d).read_text(encoding="utf-8").splitlines()
    # bounded: never the full N; stays near the cap (allow headroom until the size gate trips)
    check("ledger is bounded (not append-only)", len(lines) < N // 2,
          "have %d lines for %d appends" % (len(lines), N))
    check("ledger near the cap", len(lines) <= cl.MAX_LEDGER_LINES * 2,
          "have %d lines, cap %d" % (len(lines), cl.MAX_LEDGER_LINES))

    # recency retained: the last appended signal survives pruning
    import json
    last = json.loads(lines[-1])
    check("most-recent signal retained after prune", last.get("i") == N - 1,
          "last i=%r" % last.get("i"))

    # still readable by the normal path
    sigs = cl.read_signals(d, "sess")
    check("read_signals returns the bounded set", 0 < len(sigs) <= len(lines))

print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)

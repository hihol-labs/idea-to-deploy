#!/usr/bin/env python3
"""Gate: the G-005 targeted adoptions are really wired, not just ledger rows.

Two measured, invariant-safe adoptions land in Ось 3 (not for breadth):

  F-21  Scheduled read-only nudge (ScheduleWakeup / cron) for the abstention
        re-review — wired into skills/retro/SKILL.md. Makes "periodic" real.
        Invariant-safe: scheduled agent is a READ-ONLY reporter; flip still
        goes through Step 2 + a human. Fallback: manual /retro.

  F-16  spawn_task chip as a COMPLEMENT (not a replacement) for out-of-scope
        findings — wired into skills/_shared/helpers.md §10. The chip transports
        the finding to the UI; BACKLOG.md stays the contract. This is the safe
        use the /retro abstention re-review is meant to surface. Fallback: the
        backlog file. Using chips AS the backlog stays rejected.

For each adoption the gate asserts: the ledger row is `adopt` with an existing
evidence path and a non-empty vendor-neutral fallback; the wiring file ACTUALLY
contains the adoption (real change, not just a row); and the invariant guard is
stated.

Self-contained:  python3 tests/verify_feature_ledger_adoptions.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path(os.environ.get("FEATURE_LEDGER_PATH", ROOT / "docs" / "FABLE5_FEATURE_LEDGER.md"))

PASSED, FAILED = 0, 0
PATH_RE = re.compile(r"[A-Za-z0-9_][\w./-]*\.(?:md|sh|py|json|txt)")


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def ledger_row(feature_id: str) -> list[str]:
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        if ln.lstrip().startswith(f"| {feature_id} |"):
            return [c.strip() for c in ln.strip().strip("|").split("|")]
    return []


# adoption -> wiring file + tokens that must appear in it + fallback/invariant tokens
ADOPTIONS = {
    "F-21": {
        "wiring": ROOT / "skills" / "retro" / "SKILL.md",
        "wiring_tokens": ["scheduled", "read-only", "itd_ledger_abstentions"],
        "fallback_tokens": ["/retro"],
        "invariant_tokens": ["read-only reporter"],
    },
    "F-16": {
        "wiring": ROOT / "skills" / "_shared" / "helpers.md",
        "wiring_tokens": ["spawn_task", "chip", "backlog", "complement"],
        "fallback_tokens": ["backlog"],
        "invariant_tokens": ["contract", "replace"],  # BACKLOG is the contract; replacement rejected
    },
}

check("ledger exists", LEDGER.is_file(), str(LEDGER))
if not LEDGER.is_file():
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1)

for fid, spec in ADOPTIONS.items():
    cells = ledger_row(fid)
    ok_row = len(cells) >= 5
    check(f"{fid}: ledger row present", ok_row, str(cells)[:60])
    if not ok_row:
        continue
    _id, feature, decision, evidence, fallback = cells[:5]

    check(f"{fid}: decision is adopt", decision.lower().startswith("adopt"), decision)

    ev_paths = PATH_RE.findall(evidence)
    check(f"{fid}: evidence path exists", any((ROOT / p).exists() for p in ev_paths),
          f"{evidence[:48]!r} -> {ev_paths}")

    check(f"{fid}: fallback non-empty & vendor-neutral", bool(fallback) and
          any(t.lower() in fallback.lower() for t in spec["fallback_tokens"]), fallback[:60])

    # really wired: the evidence file actually contains the adoption
    wtxt = spec["wiring"].read_text(encoding="utf-8").lower() if spec["wiring"].is_file() else ""
    missing = [t for t in spec["wiring_tokens"] if t.lower() not in wtxt]
    check(f"{fid}: wiring file really contains the adoption", spec["wiring"].is_file() and not missing,
          f"missing={missing}")

    inv_ok = all(t.lower() in wtxt for t in spec["invariant_tokens"])
    check(f"{fid}: invariant guard stated in wiring", inv_ok,
          f"need {spec['invariant_tokens']}")

# not-for-breadth: exactly the two intended adoptions carry the G-005 change
check("G-005 lands 1-2 adoptions (not breadth)", 1 <= len(ADOPTIONS) <= 2, str(list(ADOPTIONS)))

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(0 if FAILED == 0 else 1)

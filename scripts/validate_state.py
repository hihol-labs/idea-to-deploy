#!/usr/bin/env python3
"""Validate .itd-memory/STATE.json and GOAL.json against the shipped schemas.

PFO plugin-native port (Wave 2, item 14). Structured session state is what makes
recovery-after-a-break machine-checkable instead of prose.

v1.75.0 (ACID-audit): the validation logic moved to hooks/validate_state_core.py
so the PostToolUse hook state-guard.sh enforces the SAME invariants immediately
after every Write/Edit of a state ledger — this file is the fail-closed CLI
wrapper (skills, CI). CLI contract is unchanged: prints "ERROR: ..." and exits 1
on the first failing file, prints "OK: validated N state file(s)" and exits 0
otherwise. New in v1.75.0: non-fatal reconciliation findings (STATE ↔
events.jsonl, absence-not-contradiction cases) are printed as "WARNING: ..."
lines and do NOT affect the exit code.

Fail-closed: empty required-non-empty fields (approvalStatus,
recommendedNextStep, nextAction), WIP=1 across both ledgers, and a STATE tail
that CONTRADICTS the events.jsonl tail are validation FAILURES, not passes.

Usage:
  python3 scripts/validate_state.py path/to/.itd-memory/STATE.json [more ...]
  python3 scripts/validate_state.py path/to/.itd-memory/GOAL.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

from validate_state_core import validate_path  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate idea-to-deploy .itd-memory/STATE.json and GOAL.json files.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    for path in args.paths:
        if not path.is_file():
            print(f"ERROR: missing state file: {path}")
            sys.exit(1)
        errors, warnings = validate_path(path)
        for w in warnings:
            print(f"WARNING: {w}")
        if errors:
            print(f"ERROR: {errors[0]}")
            sys.exit(1)

    print(f"OK: validated {len(args.paths)} state file(s)")


if __name__ == "__main__":
    main()

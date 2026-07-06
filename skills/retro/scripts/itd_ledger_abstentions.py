#!/usr/bin/env python3
"""Ledger abstention scanner — FACTS producer for the /retro abstention re-review.

Periodic re-review of the harness-native feature ledger's `abstain` rows: has a
SAFE use appeared for something we consciously declined? This script is the
deterministic FACTS half (same «харнес считает, агент интерпретирует, человек
мержит» split as itd_retro_scan.py): it lists the current abstentions and their
declared fallback, and prints the anti-Goodhart gate. It NEVER flips a decision —
a flip abstain->adopt is a /retro PROPOSAL that requires an EXTERNAL safe-use
signal, merged by a human.

Non-fatal by design: outside the methodology repo (no ledger) it reports the
ledger as absent and exits 0, exactly like the main retro scan treats a missing
source.

Usage:
  itd_ledger_abstentions.py [--ledger PATH] [--json]
Exit codes: 0 always (report or "absent"); 2 usage error.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GATE = ("re-check needs an EXTERNAL safe-use signal (a real safe adoption, a "
        "changed threat model, a vendor guarantee) — not 'might be nice'. "
        "No signal -> stays abstain (anti-Goodhart).")


def find_ledger() -> Path | None:
    """Resolve the ledger: explicit candidates from the script location, then cwd."""
    here = Path(__file__).resolve()
    candidates = [
        # repo layout: skills/retro/scripts/ -> repo root is parents[3]
        here.parents[3] / "docs" / "FABLE5_FEATURE_LEDGER.md",
        Path.cwd() / "docs" / "FABLE5_FEATURE_LEDGER.md",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def parse_abstentions(path: Path) -> list[dict]:
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.lstrip().startswith("|"):
            continue
        if re.fullmatch(r"[\s|:\-]+", ln.strip()):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        _id, feature, decision, evidence, fallback = cells[:5]
        if not re.match(r"^F-\d", _id):  # skip the header row
            continue
        if decision.lower().startswith("abstain"):
            rows.append({"id": _id, "feature": feature, "decision": decision,
                         "evidence": evidence, "fallback": fallback})
    return rows


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="List feature-ledger abstentions for /retro re-review.")
    ap.add_argument("--ledger", help="path to FABLE5_FEATURE_LEDGER.md")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    ledger = Path(args.ledger) if args.ledger else find_ledger()
    if ledger is None or not ledger.is_file():
        if args.json:
            print(json.dumps({"ledger": None, "abstentions": [], "gate": GATE}))
        else:
            print("# Ledger abstentions — SOURCE ABSENT (not the methodology repo) — skip")
        return 0

    rows = parse_abstentions(ledger)

    if args.json:
        print(json.dumps({"ledger": str(ledger), "count": len(rows),
                          "abstentions": rows, "gate": GATE}, ensure_ascii=False))
        return 0

    print("# Ledger abstentions — re-review candidates (FACTS)")
    print(f"# Source: {ledger}")
    print(f"# Gate: {GATE}")
    for r in rows:
        print(f"{r['id']}  {r['feature']}")
        print(f"      decision: {r['decision']}  | fallback: {r['fallback']}")
    print(f"abstentions: {len(rows)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:  # never fatal for a FACTS producer
        print(f"# Ledger abstentions — scan error (non-fatal): {e}")
        sys.exit(0)

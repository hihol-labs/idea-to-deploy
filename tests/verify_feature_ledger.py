#!/usr/bin/env python3
"""Structural gate for the Fable 5 / harness-native feature ledger (G-001).

Asserts docs/FABLE5_FEATURE_LEDGER.md is a *verifiably-complete* registry, not
prose: every frontier row carries all four columns, the decision is a real
adopt/abstain, every row's Evidence points at a file that ACTUALLY exists in the
repo, and the "~9, not 10" ceiling disclaimer is present.

Checks are structural — a row with an empty cell, a bogus decision word, or an
Evidence path that does not exist on disk must FAIL, not pass on mere presence.

Self-contained:  python3 tests/verify_feature_ledger.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Ledger path is overridable (FEATURE_LEDGER_PATH) so negative-control fixtures
# and G-003 can point the same structural checks at a mutated temp copy without
# touching the real file. Evidence-existence still resolves against ROOT.
LEDGER = Path(os.environ.get("FEATURE_LEDGER_PATH", ROOT / "docs" / "FABLE5_FEATURE_LEDGER.md"))

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


# ---------------------------------------------------------------- file exists
check("ledger file exists", LEDGER.is_file(), str(LEDGER))
if not LEDGER.is_file():
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1)

text = LEDGER.read_text(encoding="utf-8")

# ---------------------------------------------------------------- ceiling disclaimer
flat = re.sub(r"\s+", " ", text)
has_nine = "~9" in flat
has_not_ten = ("не цель" in flat) or ("не 10" in flat) or ("НЕ 10" in flat)
check("ceiling disclaimer present (~9 AND not-10)", has_nine and has_not_ten,
      f"~9={has_nine} not-10={has_not_ten}")

# ---------------------------------------------------------------- locate the table
lines = text.splitlines()
header_idx = None
for i, ln in enumerate(lines):
    low = ln.lower()
    if ln.lstrip().startswith("|") and ("фича" in low) and ("решение" in low) \
            and ("evidence" in low) and ("fallback" in low):
        header_idx = i
        break
check("ledger table header found", header_idx is not None,
      "expected | # | Фича | Решение | Evidence | Fallback |")
if header_idx is None:
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1)


def split_row(ln: str) -> list[str]:
    # markdown row: | a | b | c | ... |  -> [a, b, c, ...]
    return [c.strip() for c in ln.strip().strip("|").split("|")]


def is_separator(ln: str) -> bool:
    return bool(re.fullmatch(r"[\s|:\-]+", ln.strip()))


PATH_RE = re.compile(r"[A-Za-z0-9_][\w./-]*\.(?:md|sh|py|json|txt)")


rows: list[tuple[int, list[str]]] = []
for ln in lines[header_idx + 1:]:
    if not ln.lstrip().startswith("|"):
        break
    if is_separator(ln):
        continue
    rows.append((len(rows) + 1, split_row(ln)))

check("ledger has a substantial frontier (>= 15 rows)", len(rows) >= 15,
      f"{len(rows)} rows")

adopt_n = abstain_n = 0
bad_shape: list[str] = []
bad_decision: list[str] = []
bad_evidence: list[str] = []
empty_fallback: list[str] = []

for _, cells in rows:
    # expected: [#, Фича, Решение, Evidence, Fallback]
    if len(cells) < 5:
        bad_shape.append(" | ".join(cells)[:60])
        continue
    _id, feature, decision, evidence, fallback = cells[0], cells[1], cells[2], cells[3], cells[4]
    label = _id or feature[:24]

    if not (feature and decision and evidence and fallback):
        bad_shape.append(label)

    dl = decision.lower()
    if dl.startswith("adopt"):
        adopt_n += 1
    elif dl.startswith("abstain"):
        abstain_n += 1
        if not fallback:
            empty_fallback.append(label)
    else:
        bad_decision.append(f"{label}:{decision!r}")

    # every row's Evidence must cite >= 1 path that exists on disk
    paths = PATH_RE.findall(evidence)
    if not any((ROOT / p).exists() for p in paths):
        bad_evidence.append(f"{label}: {evidence[:48]!r} -> {paths}")

check("every row has all 4 non-empty columns", not bad_shape, "; ".join(bad_shape))
check("every decision is adopt/abstain", not bad_decision, "; ".join(bad_decision))
check("every row Evidence cites an existing repo file", not bad_evidence,
      " || ".join(bad_evidence))
check("every abstain row has a non-empty fallback", not empty_fallback,
      "; ".join(empty_fallback))
check("both adopt and abstain decisions present", adopt_n > 0 and abstain_n > 0,
      f"adopt={adopt_n} abstain={abstain_n}")

# ---------------------------------------------------------------- invariant frontier nouns
# The invariant block names five vendor features; the ledger must at least
# mention each (G-002 does the rigorous drift-guard; this is the light nod).
for noun in ["typed tool-call", "chips", "artifact", "background agent", "transcript"]:
    check(f"invariant noun present: {noun}", noun.lower() in text.lower())

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(0 if FAILED == 0 else 1)

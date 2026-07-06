#!/usr/bin/env python3
"""Drift-guard: the feature ledger COVERS the actual harness frontier (G-002).

Turns "scattered across CHANGELOG / invariant / DESIGN_SPACE" into "provably
consolidated": every harness-feature that is name-dropped in the source of truth
must have a row in docs/FABLE5_FEATURE_LEDGER.md.

Two mechanisms:

  A. Invariant nouns (LIVE-parsed drift-guard). The invariant block names the
     vendor frontier in one parenthetical — "(typed tool-calls, chips, artifacts,
     background agents, transcript search)". This test parses that sentence from
     the file and asserts (i) the parsed set exactly matches the keyword map
     (add a noun to the invariant → this FAILS until the ledger + map are
     updated), and (ii) each noun is represented by a ledger ROW. This is the
     concrete "new name-drop without a row -> FAIL" guarantee.

  B. Adopted CHANGELOG tokens (grounded coverage). A curated set of adopted
     Fable features; each token must (i) still appear in CHANGELOG.md (grounded —
     a stale token FAILS) and (ii) be covered by a ledger row.

Self-contained:  python3 tests/verify_feature_ledger_completeness.py
Override the ledger with FEATURE_LEDGER_PATH for negative-control fixtures.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# All three sources are overridable so negative-control fixtures can drift one
# of them (ledger / invariant sentence / CHANGELOG) and prove the guard catches it.
LEDGER = Path(os.environ.get("FEATURE_LEDGER_PATH", ROOT / "docs" / "FABLE5_FEATURE_LEDGER.md"))
INVARIANT = Path(os.environ.get("INVARIANT_PATH", ROOT / "docs" / "templates" / "global-claude-md.md"))
CHANGELOG = Path(os.environ.get("CHANGELOG_PATH", ROOT / "CHANGELOG.md"))

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def load_ledger_rows(path: Path) -> list[list[str]]:
    """Return the data rows (list of cells) of the ledger's feature table."""
    lines = path.read_text(encoding="utf-8").splitlines()
    header = None
    for i, ln in enumerate(lines):
        low = ln.lower()
        if ln.lstrip().startswith("|") and "фича" in low and "решение" in low \
                and "evidence" in low and "fallback" in low:
            header = i
            break
    if header is None:
        return []
    rows = []
    for ln in lines[header + 1:]:
        if not ln.lstrip().startswith("|"):
            break
        if re.fullmatch(r"[\s|:\-]+", ln.strip()):
            continue
        rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return rows


# ---------------------------------------------------------------- prerequisites
for label, p in [("ledger", LEDGER), ("invariant block", INVARIANT), ("CHANGELOG", CHANGELOG)]:
    check(f"{label} file exists", p.is_file(), str(p))
if not (LEDGER.is_file() and INVARIANT.is_file() and CHANGELOG.is_file()):
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1)

rows = load_ledger_rows(LEDGER)
check("ledger table parses", len(rows) >= 15, f"{len(rows)} rows")
ledger_text = LEDGER.read_text(encoding="utf-8").lower()
changelog_text = CHANGELOG.read_text(encoding="utf-8").lower()
invariant_text = INVARIANT.read_text(encoding="utf-8")


def row_contains(keyword: str) -> bool:
    kw = keyword.lower()
    return any(kw in " ".join(cells).lower() for cells in rows)


# ---------------------------------------------------------------- A: invariant nouns (live)
INVARIANT_NOUN_KEYWORD = {
    "typed tool-calls": ["typed", "tool-call"],
    "chips": ["chip"],
    "artifacts": ["artifact"],
    "background agents": ["background agent"],
    "transcript search": ["transcript"],
}

m = re.search(r"\(([^)]*typed tool-calls[^)]*)\)", invariant_text)
check("invariant frontier sentence found", m is not None,
      "expected '(typed tool-calls, ... )'")
parsed = []
if m:
    parsed = [n.strip().lower() for n in m.group(1).split(",") if n.strip()]

check("invariant nouns == keyword map (no drift either way)",
      set(parsed) == set(INVARIANT_NOUN_KEYWORD),
      f"parsed={set(parsed)} map={set(INVARIANT_NOUN_KEYWORD)}")

for noun in parsed:
    kws = INVARIANT_NOUN_KEYWORD.get(noun, [])
    covered = any(row_contains(kw) for kw in kws)
    check(f"invariant noun covered by a ledger row: {noun}", bool(kws) and covered,
          "no matching ledger row" if kws else "unmapped noun — add ledger row + keyword")

# ---------------------------------------------------------------- B: adopted CHANGELOG tokens
# source_token (must still be in CHANGELOG) -> ledger keyword (must be in a row)
CHANGELOG_ADOPTED = {
    "worktree": "worktree",
    "cross-review": "cross-vendor",
    "narration-final": "narration-final",
    "execution-trace": "execution-trace",
    "goal.json": "goal.json",
    "model-routing": "model-routing",
    "autoping": "autoping",
    "stall": "fresh narrow",
    "verification_contract": "verification_contract",
    "spawn_task": "spawn_task",
    "chips": "chip",
    "artifact": "artifact",
    "transcript": "transcript",
}

for src, kw in CHANGELOG_ADOPTED.items():
    grounded = src in changelog_text
    covered = row_contains(kw)  # must live in an actual table ROW, not incidental prose
    check(f"CHANGELOG token '{src}' grounded AND covered by ledger row", grounded and covered,
          f"grounded={grounded} covered={covered}")

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(0 if FAILED == 0 else 1)

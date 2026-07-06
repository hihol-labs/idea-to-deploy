#!/usr/bin/env python3
"""Gate: /retro periodically re-reviews ledger abstentions (G-004).

Asserts the abstention re-review is WIRED into /retro, not just intended:

  - skills/retro/SKILL.md has a step that runs the abstention FACTS helper,
    names the ledger, asks "has a safe use appeared?", and keeps the /retro
    anti-Goodhart gate (a flip needs an EXTERNAL signal).
  - skills/retro/scripts/itd_ledger_abstentions.py exists and is a faithful
    FACTS producer: its abstain set == an independent parse of the ledger
    (and is non-empty), and it is non-fatal when the ledger is absent.

Self-contained:  python3 tests/verify_retro_abstention_review.py
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "retro" / "SKILL.md"
HELPER = ROOT / "skills" / "retro" / "scripts" / "itd_ledger_abstentions.py"
LEDGER = ROOT / "docs" / "FABLE5_FEATURE_LEDGER.md"

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


# ---------------------------------------------------------------- prerequisites
for label, p in [("retro SKILL.md", SKILL), ("abstention helper", HELPER), ("ledger", LEDGER)]:
    check(f"{label} exists", p.is_file(), str(p))
if not (SKILL.is_file() and HELPER.is_file() and LEDGER.is_file()):
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1)

skill = SKILL.read_text(encoding="utf-8")
low = skill.lower()

# ---------------------------------------------------------------- SKILL.md wiring
check("SKILL.md invokes the abstention helper", "itd_ledger_abstentions.py" in skill)
check("SKILL.md names the feature ledger", "FABLE5_FEATURE_LEDGER" in skill or "реестр" in low)
check("SKILL.md frames it as re-review of abstentions",
      "абстенц" in low and ("ре-review" in low or "пересматрив" in low))
check("SKILL.md asks whether a safe use appeared",
      "безопасн" in low and ("юз" in low or "use" in low))
check("SKILL.md keeps the anti-Goodhart external-signal gate",
      ("внешн" in low) and ("safe-use" in low or "гудхарт" in low or "сигнал" in low))
check("SKILL.md ties the flip to abstain->adopt", "abstain" in low and "adopt" in low)

# ---------------------------------------------------------------- helper faithfulness
loader = importlib.machinery.SourceFileLoader("itd_ledger_abstentions", str(HELPER))
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

helper_abstentions = mod.parse_abstentions(LEDGER)
helper_ids = sorted(r["id"] for r in helper_abstentions)


# independent parse: count ledger rows whose decision cell starts with "abstain"
def independent_abstain_ids(path: Path) -> list[str]:
    ids = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.lstrip().startswith("| F-"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[2].lower().startswith("abstain"):
            ids.append(cells[0])
    return sorted(ids)


indep_ids = independent_abstain_ids(LEDGER)
check("helper finds a non-empty abstain set", len(helper_ids) > 0, f"{helper_ids}")
check("helper abstain set == independent ledger parse", helper_ids == indep_ids,
      f"helper={helper_ids} indep={indep_ids}")

# find_ledger() resolves the real ledger from the repo layout
check("helper find_ledger() resolves the real ledger", mod.find_ledger() is not None)

# ---------------------------------------------------------------- non-fatal when absent
r = subprocess.run([sys.executable, str(HELPER), "--ledger", "/no/such/ledger.md"],
                   capture_output=True, text=True)
check("helper is non-fatal on missing ledger (exit 0 + ABSENT)",
      r.returncode == 0 and "ABSENT" in r.stdout.upper(),
      f"rc={r.returncode} out={r.stdout[:60]!r}")

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(0 if FAILED == 0 else 1)

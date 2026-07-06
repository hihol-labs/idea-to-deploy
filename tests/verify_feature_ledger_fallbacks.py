#!/usr/bin/env python3
"""Fixture-proof of ledger fallbacks (G-003).

The harness best-effort invariant says: "a harness feature silently disappearing
must degrade to the neutral path, not to a false 'all green'." This test stops
that from being merely DECLARED — it SIMULATES the feature being absent and
asserts the exact vendor-neutral fallback the ledger claims actually engages,
for two adopted features:

  F-06 cross-review external CLI (Codex/Gemini) -> native `/cross-review` note.
       EXECUTABLE: import hooks/cross-review-precommit.sh, force both engines
       absent (resolve_engine -> None) and assert run_worker() writes the honest
       "UNAVAILABLE ... run /cross-review" degrade note and NOT a fabricated
       "Findings (engine: …)" green. A positive control (engine present) proves
       the absent-branch is not vacuous.

  F-05 git worktree isolation -> freeze.sh scope guard.
       EXECUTABLE precondition: in a non-git dir the worktree precondition
       (`git rev-parse --is-inside-work-tree`) genuinely fails, so the feature is
       really unavailable; assert the declared fallback (freeze.sh) is a real hook
       and the reference documents the "freeze fallback" route.

Each proven fallback is cross-checked against its ledger row (criterion:
"каждый проверенный fallback ссылается на строку реестра").

Self-contained:  python3 tests/verify_feature_ledger_fallbacks.py
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path(os.environ.get("FEATURE_LEDGER_PATH", ROOT / "docs" / "FABLE5_FEATURE_LEDGER.md"))
HOOK = ROOT / "hooks" / "cross-review-precommit.sh"
FREEZE = ROOT / "hooks" / "freeze.sh"
WT_REF = ROOT / "skills" / "refactor" / "references" / "worktree-isolation.md"

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def ledger_fallback_cell(feature_id: str) -> str:
    """Return the Fallback cell text of the ledger row with the given F-xx id."""
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        if ln.lstrip().startswith(f"| {feature_id} |"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 5:
                return cells[4]
    return ""


# ================================================================= F-06 cross-review
def load_hook_module():
    # .sh extension: importlib won't infer a loader, so force SourceFileLoader —
    # the file is python3 (shebang), __main__-guarded, top level is defs/imports.
    loader = importlib.machinery.SourceFileLoader("cross_review_precommit", str(HOOK))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


check("cross-review hook file exists", HOOK.is_file(), str(HOOK))
if HOOK.is_file():
    mod = load_hook_module()

    # --- simulate BOTH engines absent -----------------------------------------
    orig_resolve = mod.resolve_engine
    mod.resolve_engine = lambda name: None
    try:
        pf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        pf.write("dummy prompt")
        pf.close()
        notes_absent = pf.name + ".notes.md"
        mod.run_worker(pf.name, notes_absent)
        absent_txt = Path(notes_absent).read_text(encoding="utf-8") if Path(notes_absent).exists() else ""
    finally:
        mod.resolve_engine = orig_resolve

    check("engine-absent -> honest UNAVAILABLE degrade note",
          "UNAVAILABLE" in absent_txt and "not present" in absent_txt.lower(),
          absent_txt[:80])
    check("engine-absent -> routes to native /cross-review fallback",
          "/cross-review" in absent_txt, absent_txt[:80])
    check("engine-absent -> NO fabricated 'Findings (engine:' green",
          "Findings (engine:" not in absent_txt)

    # --- positive control: engine PRESENT -> the absent-branch is not vacuous --
    mod2 = load_hook_module()
    mod2.resolve_engine = lambda name: "/fake/codex" if name == "codex" else None
    mod2.run_engine = lambda argv, promptf: ("SIMULATED FINDINGS", True)
    pf2 = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    pf2.write("dummy")
    pf2.close()
    notes_present = pf2.name + ".notes.md"
    mod2.run_worker(pf2.name, notes_present)
    present_txt = Path(notes_present).read_text(encoding="utf-8") if Path(notes_present).exists() else ""
    check("positive control: engine present -> real Findings (absent-test not vacuous)",
          "Findings (engine: codex)" in present_txt and "UNAVAILABLE" not in present_txt,
          present_txt[:80])

    for p in [notes_absent, notes_present]:
        try:
            os.unlink(p)
        except OSError:
            pass

    # --- fallback is the one the ledger declares ------------------------------
    fb06 = ledger_fallback_cell("F-06").lower()
    check("ledger F-06 fallback names native self-review",
          ("native" in fb06) and ("self-review" in fb06 or "cross-review" in fb06), fb06)

# ================================================================= F-05 worktree
check("freeze.sh fallback hook exists", FREEZE.is_file(), str(FREEZE))
check("worktree-isolation reference exists", WT_REF.is_file(), str(WT_REF))

# feature genuinely unavailable in a non-git dir: the worktree precondition fails
tmpd = tempfile.mkdtemp()
try:
    r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                       cwd=tmpd, capture_output=True, text=True)
    worktree_unavailable = r.returncode != 0
    check("worktree precondition genuinely fails in a non-git dir (feature absent)",
          worktree_unavailable, f"rc={r.returncode}")
except FileNotFoundError:
    check("worktree precondition genuinely fails in a non-git dir (feature absent)",
          True, "git not installed — precondition trivially unmet")
finally:
    try:
        os.rmdir(tmpd)
    except OSError:
        pass

if FREEZE.is_file():
    ftxt = FREEZE.read_text(encoding="utf-8").lower()
    check("freeze.sh is a real scope-guard hook", "freeze" in ftxt and "scope" in ftxt)

if WT_REF.is_file():
    wtxt = WT_REF.read_text(encoding="utf-8").lower()
    check("worktree reference documents the freeze fallback route",
          "freeze fallback" in wtxt or "freeze path" in wtxt)

fb05 = ledger_fallback_cell("F-05").lower()
check("ledger F-05 fallback names freeze scope-guard", "freeze" in fb05, fb05)

print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(0 if FAILED == 0 else 1)

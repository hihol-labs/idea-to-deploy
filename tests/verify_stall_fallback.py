#!/usr/bin/env python3
"""Doc-contract test for the mechanical stall-resilience fallback (v1.60.0 —
Ось 2, agentic engineering, unit G-005).

A stalled subagent (watchdog timeout / autocompact death / empty return) used to
force a manual «resume or retry?» decision — itself a stall in the loop. v1.60.0
makes the recovery mechanical and AUTOMATIC: on a detected stall, spawn a fresh
narrow agent (thin context, smallest useful slice) — the default procedure, not
an option to weigh. Documented in skills/_shared/helpers.md §9 and referenced
from /review (the fork-thrash fallback is one instance) and /task.

Asserts (section-SCOPED, so a coincidental match elsewhere cannot false-pass):
  1. helpers.md §9 exists as a section;
  2. stall is detected by MECHANICAL signals (watchdog/no-progress/autocompact/
     empty), not judgement;
  3. the response is a FRESH agent, explicitly NOT a resume;
  4. the scope is NARROWED (smallest slice);
  5. it is AUTOMATIC — explicitly NOT a manual «resume or retry?» choice;
  6. bounded + escalate (a persistent stall becomes a visible blocker);
  7. /review references the shared stall fallback (helpers §9);
  8. /task references the shared stall fallback (helpers §9);
  9. the gate is wired into a CI workflow.

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_stall_fallback.py
Exits non-zero if a property is missing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "skills" / "_shared" / "helpers.md"
REVIEW = ROOT / "skills" / "review" / "SKILL.md"
TASK = ROOT / "skills" / "task" / "SKILL.md"
WORKFLOWS = ROOT / ".github" / "workflows"

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def has_all(hay: str, *needles: str) -> bool:
    low = hay.lower()
    return all(n.lower() in low for n in needles)


def has_any(hay: str, *needles: str) -> bool:
    low = hay.lower()
    return any(n.lower() in low for n in needles)


def slice_section(raw: str, start_pat: str, end_pat: str) -> str | None:
    m = re.search(start_pat, raw)
    if not m:
        return None
    rest = raw[m.start():]
    e = re.search(end_pat, rest[1:])
    return rest if not e else rest[: e.start() + 1]


def main() -> int:
    for p in (HELPERS, REVIEW, TASK):
        if not p.is_file():
            check("file exists: " + p.name, False, str(p))
            print("\n%d passed, %d failed" % (PASSED, FAILED))
            return 1

    # §9 is the last section; end anchor is a non-existent "## 10." → to EOF.
    sec = slice_section(HELPERS.read_text(encoding="utf-8"),
                        r"##\s+9\.\s+Stall-resilience", r"\n##\s+10\.")
    if sec is None:
        check("helpers.md §9 Stall-resilience section present", False,
              "no '## 9. Stall-resilience' heading")
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1
    s = norm(sec)

    check("§9: mechanical stall detection (not judgement)",
          has_any(s, "watchdog", "no-progress", "no progress")
          and has_any(s, "autocompact", "empty return", "truncated")
          and has_any(s, "mechanical", "signal"),
          "must detect a stall by mechanical signals")
    check("§9: response is a FRESH agent, explicitly not a resume",
          has_all(s, "fresh") and has_any(s, "not resume", "do not resume",
                                          "never resume", "not a resume"),
          "must spawn fresh, never resume the stalled transcript")
    check("§9: scope is narrowed to the smallest useful slice",
          has_any(s, "narrow", "smallest", "slice", "reduce"),
          "fresh agent must run on a narrowed scope")
    check("§9: AUTOMATIC — explicitly NOT a manual resume/retry choice",
          has_all(s, "automatic")
          and has_any(s, "not a manual", "do not ask", "not an option",
                      "not deliberate", "do not deliberate", "not a per-skill"),
          "the fallback must be automatic, not a manual decision")
    check("§9: bounded, then escalate to a visible blocker",
          has_any(s, "ITD_STALL_MAX_RESPAWNS", "bounded")
          and has_any(s, "escalate", "blocker"),
          "must bound respawns and escalate a persistent stall")

    # cross-references from /review and /task
    rv = norm(REVIEW.read_text(encoding="utf-8"))
    tk = norm(TASK.read_text(encoding="utf-8"))
    check("/review references the shared stall fallback (helpers §9)",
          has_any(rv, "helpers.md §9", "helpers §9", "§9")
          and has_all(rv, "stall"),
          "review must point at the shared stall-resilience rule")
    check("/task references the shared stall fallback (helpers §9)",
          has_any(tk, "helpers.md §9", "helpers §9", "§9")
          and has_all(tk, "stall"),
          "task must point at the shared stall-resilience rule")

    # CI wiring
    wired = False
    if WORKFLOWS.is_dir():
        for yml in WORKFLOWS.glob("*.yml"):
            if "verify_stall_fallback.py" in yml.read_text(encoding="utf-8"):
                wired = True
                break
    check("gate is wired into a CI workflow", wired,
          "add 'python3 tests/verify_stall_fallback.py' to a workflow")

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

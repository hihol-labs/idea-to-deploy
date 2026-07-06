#!/usr/bin/env python3
"""Doc-contract test for the caller-side auto-ping-for-verdict step (v1.60.0 —
Ось 2, agentic engineering, unit G-001).

The #1 agentic drag was a subagent ending its FINAL message on process
narration instead of a verdict, recovered only by the human pinging «выдай итог
одним сообщением» by hand (observed x4 in one session). v1.60.0 makes the
recovery mechanical AND caller-side: the /review conductor (and /cross-review)
must, on a subagent/reviewer return that carries NO verdict marker, auto-re-ping
ONCE without asking the user — detecting by the ABSENCE of the required marker,
NOT by regex-guessing whether the prose "looks like" a narration opener (which
is strictly the subagent-side hooks' job, and less reliable than checking for
the marker's presence).

This gate asserts the DOCUMENTED contract survives edits (the belt), independent
of the two SubagentStop hooks that enforce the same defect at the subagent
boundary (the suspenders). It checks invariant PROPERTIES via stable keywords,
not verbatim sentences, so rewording does not break it while a semantic removal
does. It also asserts the gate is wired into CI ("и в CI" clause of the unit).

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_review_autoping.py
Exits non-zero if any property is missing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "skills" / "review" / "SKILL.md"
CROSS = ROOT / "skills" / "cross-review" / "SKILL.md"
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
    """Collapse whitespace so line-wrapping never breaks a substring match."""
    return re.sub(r"\s+", " ", text)


def has_all(hay: str, *needles: str) -> bool:
    low = hay.lower()
    return all(n.lower() in low for n in needles)


def slice_section(raw: str, start_pat: str, end_pat: str) -> str | None:
    """Return the raw text from the start heading up to the next section
    boundary — so keyword checks are scoped to the RELEVANT section, not the
    whole 700+-line file (a coincidental match elsewhere must not false-pass
    the gate; review finding v1.60.0-G-001 #2). None if the section is absent
    (which is itself a failure — the documented step must exist as a heading)."""
    m = re.search(start_pat, raw)
    if not m:
        return None
    rest = raw[m.start():]
    e = re.search(end_pat, rest[1:])  # skip char 0 so start≠end on same anchor
    return rest if not e else rest[: e.start() + 1]


def main() -> int:
    if not REVIEW.is_file():
        check("skills/review/SKILL.md exists", False, str(REVIEW))
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1
    if not CROSS.is_file():
        check("skills/cross-review/SKILL.md exists", False, str(CROSS))
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1

    review_raw = REVIEW.read_text(encoding="utf-8")
    cross_raw = CROSS.read_text(encoding="utf-8")

    # Scope keyword checks to the RELEVANT section, not the whole file — a
    # coincidental match elsewhere must not false-pass the gate (review #2).
    rv_sec = slice_section(review_raw, r"###\s+Step\s+2\.7", r"###\s+Step\s+3\b")
    cx_sec = slice_section(cross_raw, r"\n3a\.", r"\n4\.\s+\*\*Fold\s+findings")
    if rv_sec is None:
        check("review: Step 2.7 section present as a heading", False,
              "no '### Step 2.7' heading found")
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1
    if cx_sec is None:
        check("cross-review: step 3a section present", False,
              "no '3a.' step found between step 3 and step 4")
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1
    rv = norm(rv_sec)
    cx = norm(cx_sec)

    # --- /review: caller-side auto-ping step exists and is correctly framed ---
    check("review: dedicated caller-side auto-ping step present",
          has_all(rv, "Step 2.7") and has_all(rv, "caller-side")
          and (has_all(rv, "auto-re-ping") or has_all(rv, "re-ping")),
          "no Step 2.7 / caller-side / re-ping keywords")

    check("review: detection is by ABSENCE of the verdict marker",
          has_all(rv, "absence") and has_all(rv, "marker"),
          "does not frame detection as 'absence of marker'")

    check("review: explicitly rejects regex-guessing the prose (load-bearing)",
          (has_all(rv, "not", "pattern-matching")
           or has_all(rv, "regex-guessing"))
          and has_all(rv, "narration"),
          "must say detection is NOT regex/pattern-matching the narration")

    check("review: recovery proceeds without asking the user",
          has_all(rv, "without asking the user"),
          "auto-ping must be automatic, not «Хочешь, переспрошу?»")

    check("review: re-ping is bounded (ping cap)",
          has_all(rv, "ITD_AUTOPING_MAX")
          or (has_all(rv, "bounded") and has_all(rv, "re-ping")),
          "no cap on re-pings")

    check("review: names both SubagentStop hooks as suspenders",
          has_all(rv, "narration-final.sh")
          and has_all(rv, "verdict-contract.sh"),
          "both hooks must be named as the suspenders to this belt")

    check("review: belt/suspenders degrade independently (best-effort)",
          has_all(rv, "belt") and has_all(rv, "suspenders")
          and (has_all(rv, "best-effort") or has_all(rv, "degrade")),
          "must state the two layers degrade independently")

    # --- /cross-review: symmetric verdict-completeness instruction ------------
    check("cross-review: symmetric auto-re-ping on verdict-less return",
          (has_all(cx, "auto-re-ping") or has_all(cx, "re-ping"))
          and has_all(cx, "caller-side"),
          "cross-review must carry the same caller-side auto-re-ping")

    check("cross-review: detect by ABSENCE, not prose pattern-matching",
          has_all(cx, "absence")
          and (has_all(cx, "not", "pattern-matching")
               or has_all(cx, "marker")),
          "cross-review must detect by absence of the conclusion marker")

    check("cross-review: references /review Step 2.7",
          has_all(cx, "Step 2.7"),
          "should point at the /review caller-side step")

    check("cross-review: stays fail-open, never treats empty as clean",
          has_all(cx, "fail-open")
          and (has_all(cx, "never silently treat")
               or has_all(cx, "empty return as clean")
               or has_all(cx, "empty as clean")),
          "must not silently treat an empty return as clean")

    # --- CI wiring: the gate itself is run in CI ("и в CI" clause) -----------
    wired = False
    if WORKFLOWS.is_dir():
        for yml in WORKFLOWS.glob("*.yml"):
            if "verify_review_autoping.py" in yml.read_text(encoding="utf-8"):
                wired = True
                break
    check("gate is wired into a CI workflow",
          wired,
          "add 'python3 tests/verify_review_autoping.py' to a workflow")

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

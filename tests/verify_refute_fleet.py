#!/usr/bin/env python3
"""Doc-contract test for the refute pass across the whole verify fleet (v1.60.0
— Ось 2, agentic engineering, unit G-002).

/review Step 2.6 already adversarially refutes each surfaced finding before it
gates. v1.60.0 extends the SAME discipline to the rest of the verify fleet so a
plausible-but-wrong finding never survives to any gate:

  * /security-audit Step 2.5 — refute EXPLOITABILITY of each Critical/Important
    vuln (fresh-context; security tie-break: vague doubt is not a refutation);
  * /perf Step 2.5 — refute each HIGH/MEDIUM bottleneck (must be measured on the
    hot path; default-refuted under uncertainty);
  * /test Step 5.5 — mutation-check each behavior-asserting test (green under a
    mutation = vacuous coverage, refuted; default-refuted under uncertainty).

Shared invariants asserted per section (section-SCOPED so a coincidental match
elsewhere in the file cannot false-pass — same hardening as
verify_review_autoping.py): the section exists; it is an adversarial refute pass;
fresh/independent context; minor/low findings are NOT refuted (cost); the pass
can only REMOVE findings, never invent one; it references the /review Step 2.6
pattern. Uncertainty handling is checked per domain (perf/test: default-refuted;
security: the documented vague-doubt-drops-nothing tie-break). Plus the gate is
wired into CI ("и в CI" clause of the unit).

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_refute_fleet.py
Exits non-zero if any property is missing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "skills" / "security-audit" / "SKILL.md"
PERF = ROOT / "skills" / "perf" / "SKILL.md"
TEST = ROOT / "skills" / "test" / "SKILL.md"
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


def shared_invariants(label: str, sec: str) -> None:
    """The invariants every fleet refute pass must carry."""
    check(label + ": adversarial refute framing",
          has_all(sec, "refute") and has_any(sec, "adversari", "REFUTE"),
          "no adversarial-refute language")
    check(label + ": fresh / independent context",
          has_all(sec, "fresh")
          and has_any(sec, "Agent(", "subagent", "separate", "independent"),
          "refuter must not inherit the finder's reasoning")
    check(label + ": minor/low findings are NOT refuted (cost)",
          has_all(sec, "not justified")
          and has_any(sec, "not refuted", "not mutation-checked",
                      "never gate", "not mutation"),
          "must exempt minor/low findings from the refute cost")
    check(label + ": pass can only REMOVE, never invent a finding",
          has_all(sec, "only remove")
          and has_any(sec, "never invent", "never fabricat", "never manufactur"),
          "refute must not fabricate new findings or verdicts")
    check(label + ": references the /review Step 2.6 pattern",
          has_all(sec, "Step 2.6"),
          "should tie back to the canonical refute pass")


def main() -> int:
    for p in (SEC, PERF, TEST):
        if not p.is_file():
            check("skill file exists: " + p.name, False, str(p))
            print("\n%d passed, %d failed" % (PASSED, FAILED))
            return 1

    sec = slice_section(SEC.read_text(encoding="utf-8"),
                        r"###\s+Step\s+2\.5", r"###\s+Step\s+3\b")
    perf = slice_section(PERF.read_text(encoding="utf-8"),
                         r"###\s+Step\s+2\.5", r"###\s+Step\s+3\b")
    test = slice_section(TEST.read_text(encoding="utf-8"),
                         r"###\s+Step\s+5\.5", r"###\s+Step\s+6\b")

    if sec is None:
        check("security-audit: Step 2.5 refute section present", False,
              "no '### Step 2.5' heading")
    if perf is None:
        check("perf: Step 2.5 refute section present", False,
              "no '### Step 2.5' heading")
    if test is None:
        check("test: Step 5.5 refute section present", False,
              "no '### Step 5.5' heading")
    if None in (sec, perf, test):
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1

    sec_n, perf_n, test_n = norm(sec), norm(perf), norm(test)

    # --- shared invariants across the whole fleet ---------------------------
    shared_invariants("security-audit", sec_n)
    shared_invariants("perf", perf_n)
    shared_invariants("test", test_n)

    # --- domain-specific uncertainty handling -------------------------------
    check("security-audit: security tie-break (vague doubt is not a refutation)",
          has_any(sec_n, "vague doubt", "not a refutation",
                  "false-negative"),
          "security must NOT drop an unrefuted finding on vague doubt")
    check("perf: default-refuted under uncertainty + measured-on-hot-path teeth",
          has_all(perf_n, "default") and has_all(perf_n, "refuted")
          and has_all(perf_n, "uncertainty") and has_all(perf_n, "hot path"),
          "perf refutation must lean on measurement / hot-path")
    check("test: mutation-based refutation, default-refuted under uncertainty",
          has_all(test_n, "mutation")
          and has_all(test_n, "default") and has_all(test_n, "refuted")
          and has_all(test_n, "uncertainty"),
          "test refutation must be mutation-based")

    # --- CI wiring ----------------------------------------------------------
    wired = False
    if WORKFLOWS.is_dir():
        for yml in WORKFLOWS.glob("*.yml"):
            if "verify_refute_fleet.py" in yml.read_text(encoding="utf-8"):
                wired = True
                break
    check("gate is wired into a CI workflow", wired,
          "add 'python3 tests/verify_refute_fleet.py' to a workflow")

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

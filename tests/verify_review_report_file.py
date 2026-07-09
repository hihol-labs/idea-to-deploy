#!/usr/bin/env python3
"""Doc-contract gate: review report-file + finish-line interruption class
(v1.72.0 — root cause 2026-07-09, «пустые финалы ревью-агентов»).

Three long (9-15 min) review runs in one day were killed mid-stream by the
harness watchdog and reported as «completed» with an empty final — the finished
report lived only in the transcript. v1.72.0 closes both recovery layers:

  1. finish-line interruption class (helpers §9 + /review Step 2.7): empty
     final after a long «completed» run → cheap resume re-ping FIRST (3/3
     recovered live), fresh narrow agent only for TRUE stalls;
  2. report file (agents/code-reviewer.md + /review dispatch): findings are
     appended to a claude-review-*.md file DURING the review, so a killed run
     leaves the work on disk (file = contract, final message = transport);
     Write is allowed for that single path only.

Keyword-property checks (rewording survives, semantic removal fails).
Self-contained:  python3 tests/verify_review_report_file.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agents" / "code-reviewer.md"
REVIEW = ROOT / "skills" / "review" / "SKILL.md"
HELPERS = ROOT / "skills" / "_shared" / "helpers.md"
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


def norm(p: Path) -> str:
    return re.sub(r"\s+", " ", p.read_text(encoding="utf-8")).lower()


def has_all(hay: str, *needles: str) -> bool:
    return all(n.lower() in hay for n in needles)


def main() -> int:
    for p in (AGENT, REVIEW, HELPERS):
        if not p.is_file():
            check("file exists: " + p.name, False, str(p))
            print(f"\n{PASSED} passed, {FAILED} failed")
            return 1

    a, r, h = norm(AGENT), norm(REVIEW), norm(HELPERS)

    # --- agent: report file contract ---
    check("agent: Write is in allowed-tools",
          re.search(r"allowed-tools:.*\bwrite\b", AGENT.read_text(encoding="utf-8"),
                    re.IGNORECASE) is not None)
    check("agent: report file created at start, path from caller or default",
          has_all(a, "claude-review-", "report file"))
    check("agent: findings appended DURING the review, not only at the end",
          has_all(a, "append") and has_all(a, "dimension"))
    check("agent: final message still the full deliverable + report path line",
          has_all(a, "report file: <path>"))
    check("agent: Write restricted to the report file only (review stays read-only)",
          has_all(a, "report file only") and has_all(a, "must not"))

    # --- /review: dispatch passes the path; recovery order file -> ping -> fresh ---
    check("/review: dispatch passes a report-file path in the thin prompt",
          has_all(r, "claude-review-", "report"))
    check("/review: on empty/interrupted final read the report file FIRST",
          has_all(r, "report") and ("сначала прочитай report-файл" in r
                                    or "read the report file" in r))
    check("/review Step 2.7: empty return treated as mislabeled mid-stream kill",
          has_all(r, "empty", "mislabel"))

    # --- helpers §9: finish-line class before the fresh-narrow response ---
    check("helpers §9: finish-line interruption class is distinguished",
          has_all(h, "finish-line", "true stall"))
    check("helpers §9: cheap resume re-ping is the first move for that class",
          has_all(h, "re-ping", "sendmessage"))
    check("helpers §9: fresh-narrow no-resume rule survives for TRUE stalls",
          has_all(h, "do not resume") or has_all(h, "never resume"))
    check("helpers §9: root-cause evidence is cited",
          has_all(h, "root_cause-empty-review-finals") or has_all(h, "2026-07-09"))

    # --- wired into CI ---
    wired = any("verify_review_report_file" in p.read_text(encoding="utf-8")
                for p in WORKFLOWS.glob("*.yml"))
    check("gate is wired into a CI workflow", wired)

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

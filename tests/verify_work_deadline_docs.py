#!/usr/bin/env python3
"""PE5-015 documentation oracle for bounded model/effort routing."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEADLINE_POLICY = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
MODEL_DOC = ROOT / "docs" / "MODEL-ROUTING-POLICY.md"
DEADLINE_DOC = ROOT / "docs" / "WORKING_DEADLINE_MODE.md"
EFFORT_DOC = ROOT / "docs" / "AGENT_EFFORT_TIERS.md"

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + ((" -- " + detail) if detail else ""))


def main() -> int:
    try:
        contract = json.loads(DEADLINE_POLICY.read_text(encoding="utf-8"))
        routing = contract["modelRouting"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("FAIL  model-routing contract is unreadable -- %s" % exc)
        return 1

    model = MODEL_DOC.read_text(encoding="utf-8") if MODEL_DOC.is_file() else ""
    deadline = DEADLINE_DOC.read_text(encoding="utf-8") if DEADLINE_DOC.is_file() else ""
    effort = EFFORT_DOC.read_text(encoding="utf-8") if EFFORT_DOC.is_file() else ""
    joined = "\n".join((model, deadline, effort))
    low = joined.lower()

    check("policy allowlist is exactly bounded low/medium mechanical",
          set(routing.get("lowEffortAllowedFor") or []) == {
              "bounded-low-mechanical", "bounded-medium-mechanical"})
    check("docs require working_deadline plus known low/medium risk",
          "working_deadline" in low and "low/medium" in low
          and "[itd:mechanical]" in low)
    check("docs preserve protected quality-floor phases",
          all(token in low for token in
              ("review", "security", "root-cause", "architecture")))
    check("docs preserve mandatory evidence contours",
          routing.get("modelChoiceMayRemoveEvidenceContour") is False
          and "evidence" in low and "contour" in low)
    check("speed/credit multipliers are explicitly non-contractual",
          routing.get("speedOrCreditMultipliersAreContractual") is False
          and "not a methodology contract" in low)
    check("routing economics use observed telemetry and frozen A/B",
          "host-observed" in low and "frozen a/b" in low)

    unstable_patterns = (
        r"\b\d+(?:[.,]\d+)?\s*[x×]\s*(?:faster|speed|credits?)",
        r"\b(?:speed|credits?).{0,32}\b\d+(?:[.,]\d+)?\s*[x×]",
        r"\b\d+(?:[.,]\d+)?\s*(?:-|–|—|to)\s*\d+(?:[.,]\d+)?\s*[x×]",
    )
    unstable = [pattern for pattern in unstable_patterns
                if re.search(pattern, joined, flags=re.I)]
    check("docs contain no unstable numeric speed/credit multipliers",
          not unstable, repr(unstable))
    check("docs do not pin dated vendor model IDs",
          re.search(r"claude-(?:opus|sonnet|haiku)-\d", joined, flags=re.I) is None)

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

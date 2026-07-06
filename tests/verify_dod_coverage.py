#!/usr/bin/env python3
"""Coverage test for the machine-readable skill Definition-of-Done (v1.60.0 —
Ось 2, agentic engineering, unit G-004).

Before v1.60.0 a skill's DoD lived only as a prose "Self-validation" checklist
plus a per-unit VERIFICATION_CONTRACT with an empty commands[]. v1.60.0 extends
VERIFICATION_CONTRACT.json with a `skillDefinitionOfDone` registry: each
verify/impl skill's "done" is expressed as >=1 STRUCTURED done-signal (sentinel /
command / artifact / json_field / evidence), not a vibe. This gate enforces that
the registry covers the required set, every entry is machine-readable, and — the
anti-fabrication check — every `sentinel` done-signal actually names a sentinel
the corresponding skill really writes (grep of skills/<skill>/SKILL.md).

Asserts:
  1. the schema block + `skillDefinitionOfDone` exist and parse;
  2. coverage of `requiredCoverageSkills` == 100% (every required skill has an
     entry with roleClass in {verify,impl} and >=1 done-signal);
  3. every done-signal `type` is in `allowedDoneSignalTypes` (machine-readable,
     never a prose-only entry);
  4. every `sentinel` ref is grounded: it appears in skills/<skill>/SKILL.md
     (the registry cannot cite a done-signal the skill does not emit);
  5. the gate is wired into a CI workflow.

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_dod_coverage.py
Exits non-zero if coverage drops or a done-signal is fabricated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "templates" / "itd" / "VERIFICATION_CONTRACT.json"
SKILLS = ROOT / "skills"
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


def main() -> int:
    if not CONTRACT.is_file():
        check("VERIFICATION_CONTRACT.json exists", False, str(CONTRACT))
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1
    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except Exception as e:
        check("VERIFICATION_CONTRACT.json parses", False, str(e))
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1

    schema = contract.get("skillDoneSignalSchema", {})
    allowed = schema.get("allowedDoneSignalTypes", [])
    required = schema.get("requiredCoverageSkills", [])
    dod = contract.get("skillDefinitionOfDone", {})

    check("schema block present (allowedDoneSignalTypes + requiredCoverageSkills)",
          bool(allowed) and bool(required),
          "skillDoneSignalSchema is missing or empty")
    check("skillDefinitionOfDone registry present",
          isinstance(dod, dict) and bool(dod), "registry missing/empty")
    if not (allowed and required and isinstance(dod, dict) and dod):
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1

    allowed_set = set(allowed)

    # 2 + 3: coverage of the required set, each entry machine-readable
    covered = 0
    for skill in required:
        entry = dod.get(skill)
        ok = (isinstance(entry, dict)
              and entry.get("roleClass") in {"verify", "impl"}
              and isinstance(entry.get("doneSignals"), list)
              and len(entry["doneSignals"]) >= 1
              and all(isinstance(s, dict) and s.get("type") in allowed_set
                      for s in entry["doneSignals"]))
        check("DoD entry for required skill '%s' (machine-readable)" % skill, ok,
              "missing / wrong roleClass / no structured done-signal")
        if ok:
            covered += 1

    coverage = covered / len(required) if required else 0.0
    check("coverage of required verify/impl skills == 100%%",
          covered == len(required),
          "coverage %.0f%% (%d/%d)" % (coverage * 100, covered, len(required)))

    # 4: anti-fabrication — every sentinel done-signal is grounded in its skill
    for skill, entry in dod.items():
        if not isinstance(entry, dict):
            continue
        for sig in entry.get("doneSignals", []):
            if not (isinstance(sig, dict) and sig.get("type") == "sentinel"):
                continue
            ref = sig.get("ref", "")
            skill_md = SKILLS / skill / "SKILL.md"
            # Anti-fabrication: the ref must appear on a line that actually
            # WRITES the sentinel (a redirection / tee), not merely mention it
            # in prose — otherwise a done-signal could be gamed by naming a
            # sentinel the skill never emits (review G-004 #2).
            grounded = False
            if skill_md.is_file():
                for ln in skill_md.read_text(encoding="utf-8").splitlines():
                    if ref in ln and (">" in ln or "tee " in ln):
                        grounded = True
                        break
            check("sentinel done-signal '%s' written (not just mentioned) in "
                  "skills/%s/SKILL.md" % (ref, skill), grounded,
                  "the skill must actually write this sentinel, not name it in prose")

    # 5: CI wiring
    wired = False
    if WORKFLOWS.is_dir():
        for yml in WORKFLOWS.glob("*.yml"):
            if "verify_dod_coverage.py" in yml.read_text(encoding="utf-8"):
                wired = True
                break
    check("gate is wired into a CI workflow", wired,
          "add 'python3 tests/verify_dod_coverage.py' to a workflow")

    print("\ncoverage: %d/%d required verify/impl skills have machine-readable DoD"
          % (covered, len(required)))
    print("%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

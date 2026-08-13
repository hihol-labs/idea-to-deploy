#!/usr/bin/env python3
"""GPG-004 U17: the /blueprint design-provenance reviewer stays advisory.

Proves the sealed unit criterion on fixtures: an opt-in advisory provenance
reviewer exists on top of the Devil's Advocate step, it produces an advisory
report, and the gate outcome is unchanged - the reviewer never blocks,
its absence never blocks, and its output can never pass as review or
acceptance evidence (cannotWeaken).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "blueprint" / "scripts" / "itd_design_provenance.py"
SKILL = ROOT / "skills" / "blueprint" / "SKILL.md"
FIXTURES = ROOT / "tests" / "fixtures" / "blueprint-provenance"
ACCEPTANCE_TOKEN = "PASS" + "ED"  # never appear verbatim in this oracle's own source

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS  " if ok else "FAIL  ") + name + (f" ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=60,
    )


def advisory_output(proc: subprocess.CompletedProcess, label: str) -> dict:
    check(f"{label}: exit 0 (advisory never blocks)", proc.returncode == 0,
          f"rc={proc.returncode} stderr={proc.stderr[:200]}")
    check(f"{label}: no acceptance token in output",
          ACCEPTANCE_TOKEN not in proc.stdout and ACCEPTANCE_TOKEN not in proc.stderr)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        check(f"{label}: output is one JSON object", False, str(exc))
        return {}
    check(f"{label}: advisory flag set", payload.get("advisory") is True)
    check(f"{label}: no verdict-shaped field",
          not any("verdict" in key.casefold() for key in payload))
    for entry in payload.get("notes", []):
        check(f"{label}: note is actionable (path+line+why+fix)",
              isinstance(entry, dict)
              and set(entry) == {"path", "line", "why", "fix"}
              and entry["why"] and entry["fix"])
    return payload


def main() -> int:
    check("advisory validator exists", SCRIPT.is_file())
    check("fixtures exist", all(
        (FIXTURES / name).is_file()
        for name in ("sourced.md", "unsourced.md", "malformed.md")))
    if failures:
        print(f"FAILED {len(failures)} checks")
        return 1

    # The opt-in advisory step is documented on top of the Devil's Advocate
    # debate, with the non-gate invariants stated in the skill itself.
    skill_text = SKILL.read_text(encoding="utf-8")
    step = skill_text[skill_text.find("Design Provenance Review"):]
    check("SKILL.md documents the provenance step",
          "Design Provenance Review" in skill_text)
    debate_at = skill_text.find("Adversarial Architecture Debate")
    step_at = skill_text.find("Design Provenance Review")
    check("provenance step sits inside the adversarial debate protocol",
          0 <= debate_at < step_at)
    for marker in (
        "opt-in", "ITD_DESIGN_PROVENANCE", "DESIGN_PROVENANCE.md",
        "NOT a gate", "absence never blocks",
        "never turn into a " + ACCEPTANCE_TOKEN + " verdict",
        "itd_design_provenance.py",
    ):
        check(f"SKILL.md states invariant: {marker!r}", marker in step)

    # Fixture run 1: fully sourced report -> advisory, zero findings.
    clean = advisory_output(run("--report", str(FIXTURES / "sourced.md")), "sourced")
    check("sourced: all claims counted", clean.get("claims") == 4)
    check("sourced: no unsourced claims", clean.get("unsourced") == 0)
    check("sourced: advisory-only notes absent", clean.get("notes") == [])

    # Fixture run 2: unsourced/unknown/assumption claims -> advisory findings,
    # exit still 0. This IS the "advisory report + unchanged gate outcome" run.
    before = sorted(
        (p.name, p.read_bytes()) for p in FIXTURES.iterdir() if p.is_file())
    findings = advisory_output(run("--report", str(FIXTURES / "unsourced.md")), "unsourced")
    check("unsourced: all claims counted", findings.get("claims") == 4)
    check("unsourced: findings surfaced advisorily", findings.get("unsourced") == 2)
    check("unsourced: assumption without reference noted",
          any("model-assumption" in entry["why"] for entry in findings.get("notes", [])))
    after = sorted(
        (p.name, p.read_bytes()) for p in FIXTURES.iterdir() if p.is_file())
    check("reviewer is read-only (fixtures untouched)", before == after)

    # Fixture run 3: absence never blocks.
    advisory_output(run("--report", str(FIXTURES / "does-not-exist.md")), "absent")
    # Fixture run 4: malformed input never blocks.
    advisory_output(run("--report", str(FIXTURES / "malformed.md")), "malformed")
    # Fixture run 5: no arguments -> quiet no-op.
    noop = run()
    check("no-args: quiet no-op", noop.returncode == 0 and noop.stdout == "" and noop.stderr == "")

    # Unchanged gate outcome, structurally: no hook and no gate machinery may
    # reference the reviewer or its report - it cannot influence any gate.
    gate_surfaces = sorted((ROOT / "hooks").glob("*.sh")) + [
        ROOT / "skills" / "review" / "scripts" / "itd_review_cache.py",
        ROOT / "skills" / "_shared" / "itd_verification_loop.py",
        ROOT / "skills" / "_shared" / "itd_free_reviewer_producer.py",
    ]
    pattern = re.compile(r"design_provenance|DESIGN_PROVENANCE", re.IGNORECASE)
    for surface in gate_surfaces:
        check(f"gate surface free of provenance coupling: {surface.name}",
              not pattern.search(surface.read_text(encoding="utf-8", errors="replace")))

    # The validator's own source can never mint the acceptance token.
    check("validator source never emits the acceptance token",
          ACCEPTANCE_TOKEN not in SCRIPT.read_text(encoding="utf-8"))

    if failures:
        print(f"FAILED {len(failures)} checks")
        return 1
    print("ALL CHECKS COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

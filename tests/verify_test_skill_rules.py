#!/usr/bin/env python3
"""Doc-contract test for two /test Step 5.5 rules (TEST-RULES-1, route traps of
STOPRULE-STUB-1 and TIER-WORDING-2, BACKLOG P2 2026-10-01).

  * Unique mutation marker: the string a mutation replaces must occur exactly
    once in the mutated file, and the mutation helper checks `count == 1`
    before applying the mutant. A repeated marker made a mutant land nowhere
    (refusal instead of evidence) on STOPRULE-STUB-1.
  * Escaped fixtures: fixtures with non-ASCII or invisible characters are
    written as escape sequences by a script, because the file-write tool
    decodes escape sequences into the characters themselves (U+00A0, U+3164
    and curly quotes had to be restored by a script on TIER-WORDING-2).

Bullet-SCOPED: each rule is looked up in the one Step 5.5 bullet that names it
(the marker bullet, the fixture bullet), so a coincidental phrase elsewhere in
the section or the file cannot false-pass. Plus the gate is wired into
tests/run-all.sh and a CI workflow.

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_test_skill_rules.py
Exits non-zero if any property is missing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "skills" / "test" / "SKILL.md"
RUN_ALL = ROOT / "tests" / "run-all.sh"
WORKFLOWS = ROOT / ".github" / "workflows"
ORACLE = "verify_test_skill_rules"

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


def bullets(section: str) -> list[str]:
    """Top-level '- ' items of the section; an item ends at the next item or
    at a blank line (the paragraph after the list is not part of the item)."""
    out = []
    for chunk in re.split(r"\n(?=- )", "\n" + section)[1:]:
        if chunk.startswith("- "):
            out.append(norm(chunk.split("\n\n", 1)[0]))
    return out


def bullet_with(items: list[str], needle: str) -> str:
    found = [b for b in items if needle.lower() in b.lower()]
    return found[0] if len(found) == 1 else ""


def main() -> int:
    if not TEST.is_file():
        check("skill file exists: skills/test/SKILL.md", False, str(TEST))
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1

    section = slice_section(TEST.read_text(encoding="utf-8"),
                            r"###\s+Step\s+5\.5", r"###\s+Step\s+6\b")
    if section is None:
        check("test: Step 5.5 section present", False, "no '### Step 5.5' heading")
        print("\n%d passed, %d failed" % (PASSED, FAILED))
        return 1
    items = bullets(section)

    # --- rule 1: unique mutation marker ------------------------------------
    marker = bullet_with(items, "marker")
    check("marker rule: exactly one Step 5.5 bullet names the mutation marker",
          bool(marker) and has_all(marker, "mutation"),
          "add one bullet about the mutation marker to Step 5.5")
    check("marker rule: the marker occurs exactly once in the mutated file",
          has_all(marker, "exactly once", "mutated file"),
          "state that the marker must occur exactly once in the mutated file")
    check("marker rule: the helper checks count == 1 before applying the mutant",
          bool(re.search(r"count\([^)]*\)\s*==\s*1", marker))
          and has_all(marker, "helper", "before applying"),
          "state that the mutation helper checks count(marker) == 1 before applying")

    # --- rule 2: escaped fixtures ------------------------------------------
    fixture = bullet_with(items, "fixture")
    check("fixture rule: exactly one Step 5.5 bullet covers non-ASCII / invisible fixtures",
          bool(fixture) and has_all(fixture, "non-ascii", "invisible"),
          "add one bullet about fixtures with non-ASCII or invisible characters")
    check("fixture rule: such fixtures are written as escape sequences by a script",
          has_all(fixture, "escape sequence", "script"),
          "state that the fixture is written as escape sequences by a script")
    check("fixture rule: names the cause - the file-write tool decodes escapes",
          has_all(fixture, "file-write tool", "decode"),
          "state that the file-write tool decodes escape sequences")

    # --- wiring ------------------------------------------------------------
    check("gate is wired into tests/run-all.sh",
          RUN_ALL.is_file() and ORACLE in RUN_ALL.read_text(encoding="utf-8"),
          "add verify_test_skill_rules to tests/run-all.sh")
    wired = False
    if WORKFLOWS.is_dir():
        for yml in WORKFLOWS.glob("*.yml"):
            if ORACLE + ".py" in yml.read_text(encoding="utf-8"):
                wired = True
                break
    check("gate is wired into a CI workflow", wired,
          "add 'python3 tests/verify_test_skill_rules.py' to a workflow")

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

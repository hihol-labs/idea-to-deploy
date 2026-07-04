#!/usr/bin/env python3
"""Generate Phase-2 contract snapshots for pending fixtures (v1.48.0).

For every fixture whose expected-snapshot.json is `status: pending`, derive a
`status: contract` snapshot that pins the fixture's DOCUMENTED guarantees
against the live SKILL.md:

  - anchors  — backtick-quoted tokens and **bold** phrases harvested from the
    fixture's notes.md (the manual half of the contract), kept ONLY if they
    appear VERBATIM in skills/<name>/SKILL.md. Green at generation time by
    construction — this is a DRIFT GUARD: it fails when a future SKILL.md edit
    drops a guarantee the fixture still documents.
  - required_sections — the canonical SKILL.md sections that exist today.
  - harness_suite — for skills with harness scripts (goal, retro), the
    functional suite that must exist and stay wired into CI.

Fixtures yielding fewer than MIN_ANCHORS usable anchors are left `pending`
(manual curation needed) and reported.

Deterministic and idempotent: rerunning after SKILL.md/notes.md changes
regenerates the same structure. Run from anywhere:
  python3 tests/gen_phase2_contracts.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

MIN_ANCHORS = 3
MAX_ANCHORS = 12
MIN_ANCHOR_LEN = 4   # skip trivia like `-v`
MAX_ANCHOR_LEN = 80

CANONICAL_SECTIONS = [
    "Trigger phrases", "Recommended model", "Instructions",
    "Examples", "Self-validation", "Troubleshooting", "Rules",
]

HARNESS_SUITES = {
    "goal": "tests/verify_goal_tools.py",
    "retro": "tests/verify_retro_scan.py",
}

BACKTICK_RE = re.compile(r"`([^`\n]{%d,%d})`" % (MIN_ANCHOR_LEN, MAX_ANCHOR_LEN))
BOLD_RE = re.compile(r"\*\*([^*\n]{%d,%d})\*\*" % (MIN_ANCHOR_LEN, MAX_ANCHOR_LEN))
SECTION_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def harvest_anchors(notes: str, skill_md: str) -> list[str]:
    """Anchors documented in notes.md that literally exist in SKILL.md."""
    seen: list[str] = []
    for rx in (BACKTICK_RE, BOLD_RE):
        for m in rx.finditer(notes):
            a = m.group(1).strip()
            if not a or a in seen:
                continue
            # generic file names / pure paths of the fixture itself are noise
            if a.startswith(("tests/fixtures", "notes.md", "expected-")):
                continue
            if a in skill_md:
                seen.append(a)
            if len(seen) >= MAX_ANCHORS:
                return seen
    return seen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    converted, left_pending, skipped = [], [], []
    for fdir in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        snap_path = fdir / "expected-snapshot.json"
        if not snap_path.is_file():
            continue
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        if snap.get("status") != "pending":
            skipped.append(fdir.name)
            continue
        skill = (snap.get("skill_under_test") or "").lstrip("/")
        skill_md_path = ROOT / "skills" / skill / "SKILL.md"
        notes_path = fdir / "notes.md"
        if not skill_md_path.is_file() or not notes_path.is_file():
            left_pending.append((fdir.name, "no SKILL.md or notes.md"))
            continue
        skill_md = skill_md_path.read_text(encoding="utf-8", errors="replace")
        notes = notes_path.read_text(encoding="utf-8", errors="replace")

        anchors = harvest_anchors(notes, skill_md)
        if len(anchors) < MIN_ANCHORS:
            left_pending.append((fdir.name, f"only {len(anchors)} usable anchors"))
            continue

        headings = [h.strip() for h in SECTION_RE.findall(skill_md)]
        sections = [s for s in CANONICAL_SECTIONS
                    if any(s.lower() in h.lower() for h in headings)]

        contract = {
            "skill": skill,
            "required_sections": sections,
            "must_contain": anchors,
        }
        if skill in HARNESS_SUITES:
            contract["harness_suite"] = HARNESS_SUITES[skill]

        snap["$schema_version"] = "2.0"
        snap["status"] = "contract"
        snap["skill_contract"] = contract
        snap["description"] = (snap.get("description") or "").rstrip() + (
            " [v1.48.0: Phase-2 CONTRACT validation is active for this fixture —"
            " the guarantees quoted in notes.md are machine-pinned against"
            " SKILL.md by verify_snapshot.py (drift guard); live behaviour is"
            " still validated by battle/headless runs.]"
        )
        if not args.dry_run:
            snap_path.write_text(
                json.dumps(snap, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        converted.append((fdir.name, len(anchors), len(sections)))

    print(f"converted: {len(converted)}")
    for name, na, ns in converted:
        print(f"  ✅ {name}: {na} anchors, {ns} sections")
    print(f"left pending: {len(left_pending)}")
    for name, why in left_pending:
        print(f"  ⏸️  {name}: {why}")
    print(f"untouched (not pending): {len(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

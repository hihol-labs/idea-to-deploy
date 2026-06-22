#!/usr/bin/env python3
"""Verify every skill declares a machine-checkable contract profile.

PFO plugin-native port (Wave 1, item 13). Each skills/<name>/SKILL.md must carry
three frontmatter fields under `metadata:` so routing and safety are explicit and
validatable, instead of re-derived per skill:

  effort:              low | medium | high
  side_effect:         one of ALLOWED_SIDE_EFFECTS
  explicit_invocation: true | false   (true = must be asked for, never auto-routed)

Exit 0 if all skills conform, 1 otherwise. Intended for CI (see docs/CI.md) and
local runs. Read-only — never edits skills.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ALLOWED_EFFORT = {"low", "medium", "high"}
ALLOWED_SIDE_EFFECTS = {
    "read-only",
    "local-write",
    "command-execution",
    "memory-write",
    "external-write",
    "production-mutation",
    "local-browser",
    "methodology-write",
}
REQUIRED = ("effort", "side_effect", "explicit_invocation")

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"


def frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    return m.group(1) if m else ""


def field(fm: str, key: str) -> str | None:
    m = re.search(rf"^\s+{re.escape(key)}:\s*(.+?)\s*$", fm, re.MULTILINE)
    return m.group(1).strip().strip("'\"") if m else None


def main() -> int:
    failures: list[str] = []
    skills = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_"))
    for skill in skills:
        sk = skill / "SKILL.md"
        if not sk.exists():
            failures.append(f"{skill.name}: missing SKILL.md")
            continue
        fm = frontmatter(sk.read_text(encoding="utf-8"))
        for key in REQUIRED:
            val = field(fm, key)
            if val is None:
                failures.append(f"{skill.name}: missing metadata.{key}")
            elif key == "effort" and val not in ALLOWED_EFFORT:
                failures.append(f"{skill.name}: effort '{val}' not in {sorted(ALLOWED_EFFORT)}")
            elif key == "side_effect" and val not in ALLOWED_SIDE_EFFECTS:
                failures.append(f"{skill.name}: side_effect '{val}' not in {sorted(ALLOWED_SIDE_EFFECTS)}")
            elif key == "explicit_invocation" and val not in ("true", "false"):
                failures.append(f"{skill.name}: explicit_invocation '{val}' must be true|false")

    print(f"verify_skill_profiles: checked {len(skills)} skills")
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: all skills declare a valid contract profile")
    return 0


if __name__ == "__main__":
    sys.exit(main())

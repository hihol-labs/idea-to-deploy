#!/usr/bin/env python3
"""
Trigger drift verifier — for each skill in `skills/*/SKILL.md`, extract
the canonical list of trigger phrases from the `## Trigger phrases`
section of the body, then verify that every canonical phrase:

  1. Matches at least one regex in `hooks/check-skills.sh`'s TRIGGERS list
  2. The matched hint text mentions `/<skill-name>`

Any canonical phrase that is NOT matched, OR that is matched by a regex
whose hint routes to the wrong skill, is reported as drift.

This closes the v1.4.0 class of bug where a phrase lived in the SKILL.md
body but never made it into the hook regex (or vice versa). Example from
the v1.4.0 audit: `/infra` had "provision ec2 instance" in its body but
the hook only matched "create ec2" — that drift was invisible until a
smoke-test caught it by accident.

Used by `tests/meta_review.py` as rubric check M-C11 (added in v1.7.0).

Usage:
    python3 tests/verify_triggers.py              # verify, print drift report
    python3 tests/verify_triggers.py --json       # machine-readable output

Exit codes:
    0 — no drift
    1 — drift detected
    2 — internal error

Parsing rules:
- The `## Trigger phrases` section is the content between that heading
  and the next `## ` heading.
- Only bullet lines (starting with `- `) are extracted.
- Each bullet may contain multiple phrases separated by commas.
- Phrases that look like documentation (URLs, notes) are skipped.
- Phrases shorter than 3 characters are skipped as too ambiguous.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Phrases that should be skipped even if they appear in the list
# (they're meta-descriptions or conditions, not literal user phrases).
NOISE_PREFIX_RE = re.compile(
    r"^("
    r"any\b|любой\b|любая\b|любое\b|любые\b|"
    r"автоматически\b|перед\s+любым\b|"
    r"не\s+о\s+|не\s+понимаю\b|"
    r"есть\s+документац|нужны\s+готов|"
    r"передать\s+другом|"
    r"только\s+планиров|"
    r"набор\s+документ|"
    r"работало\s+вчера|"
    r"задеплоить\s+нов|"
    r"сделай\s+сервис|"
    r"see\b|full\s+list|keep\s+.*\s+sync|"
    r"multi-file|multi-module"
    r")",
    re.IGNORECASE,
)

# Phrases matching these patterns anywhere are also skipped as descriptions
NOISE_ANY_RE = re.compile(
    r"(любой\s+запрос|любая\s+вставка|любой\s+жалобный|любой\s+вопрос\s+о|"
    r"/multi-|любой\s+запрос\s+на\s+создание)",
    re.IGNORECASE,
)

# Minimum/maximum phrase word count for a phrase to be a real trigger
MIN_PHRASE_LEN = 3
MAX_PHRASE_WORDS = 6


def find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".claude-plugin" / "plugin.json").exists():
            return parent
    raise SystemExit("error: not inside an idea-to-deploy repo")


def extract_trigger_phrases(skill_md: Path) -> list[str]:
    """Parse `## Trigger phrases` section and return a flat list of
    canonical phrases."""
    if not skill_md.exists():
        return []
    text = skill_md.read_text(encoding="utf-8", errors="replace")

    # Find the section
    start_match = re.search(r"^##\s+Trigger\s+phrases\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not start_match:
        return []
    start = start_match.end()
    end_match = re.search(r"^##\s+", text[start:], re.MULTILINE)
    section = text[start : start + end_match.start()] if end_match else text[start:]

    phrases: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        bullet = stripped[2:].strip()
        # Split on commas, treating each as a separate phrase
        for phrase in bullet.split(","):
            p = phrase.strip()
            if len(p) < MIN_PHRASE_LEN:
                continue
            # Skip phrases that are just backtick code spans or URLs
            if p.startswith("`") and p.endswith("`"):
                continue
            if p.startswith("http"):
                continue
            # Skip meta-descriptions
            if NOISE_PREFIX_RE.match(p) or NOISE_ANY_RE.search(p):
                continue
            # Skip phrases longer than MAX_PHRASE_WORDS (they are
            # descriptions, not literal user input)
            if len(p.split()) > MAX_PHRASE_WORDS:
                continue
            phrases.append(p)
    return phrases


def load_hook_triggers(hook_path: Path) -> list[tuple[str, str]]:
    """Load the TRIGGERS list from hooks/check-skills.sh by importing it
    as Python (it is Python despite the .sh extension)."""
    import importlib.util
    import shutil

    tmp = Path("/tmp") / "_check_skills_import.py"
    shutil.copy(hook_path, tmp)
    spec = importlib.util.spec_from_file_location("_check_skills_import", tmp)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {hook_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(getattr(module, "TRIGGERS", []))


def check_phrase_routes(phrase: str, triggers: list[tuple[str, str]], expected_skill: str) -> tuple[bool, bool]:
    """Return (matched_any, routes_to_expected). `matched_any` is True
    if any regex matches the phrase. `routes_to_expected` is True if the
    matched hint text mentions `/<expected_skill>`."""
    lp = phrase.lower()
    matched_any = False
    routes_to_expected = False
    for pattern, hint in triggers:
        try:
            if re.search(pattern, lp):
                matched_any = True
                if f"/{expected_skill}" in hint:
                    routes_to_expected = True
        except re.error:
            continue
    return matched_any, routes_to_expected


def skill_is_disabled(skill_md: Path) -> bool:
    """Return True if the skill's frontmatter sets
    `disable-model-invocation: true` — such skills don't need hook
    triggers (they're invoked explicitly)."""
    if not skill_md.exists():
        return False
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---\n", 4)
    if end < 0:
        return False
    return bool(re.search(r"disable-model-invocation\s*:\s*true", text[4:end], re.IGNORECASE))


def verify(repo: Path) -> list[dict]:
    """Run the verification and return a list of drift findings.
    Each finding is a dict with: skill, phrase, kind (unmatched|wrong-route)."""
    findings: list[dict] = []
    hook = repo / "hooks" / "check-skills.sh"
    triggers = load_hook_triggers(hook)

    skills_dir = repo / "skills"
    for sd in sorted(skills_dir.iterdir()):
        if not sd.is_dir() or sd.name.startswith("_"):
            continue
        skill = sd.name
        skill_md = sd / "SKILL.md"
        if skill_is_disabled(skill_md):
            continue  # exempt from trigger checks
        phrases = extract_trigger_phrases(skill_md)
        if not phrases:
            findings.append({
                "skill": skill,
                "phrase": None,
                "kind": "no-trigger-section",
                "detail": "SKILL.md has no '## Trigger phrases' section or it is empty",
            })
            continue
        for phrase in phrases:
            matched, routes = check_phrase_routes(phrase, triggers, skill)
            if not matched:
                findings.append({
                    "skill": skill,
                    "phrase": phrase,
                    "kind": "unmatched",
                    "detail": f"phrase '{phrase}' from /{skill} SKILL.md has no matching regex in hooks/check-skills.sh",
                })
            elif not routes:
                findings.append({
                    "skill": skill,
                    "phrase": phrase,
                    "kind": "wrong-route",
                    "detail": f"phrase '{phrase}' matches a regex, but the hint does not mention /{skill}",
                })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify hook triggers against SKILL.md canonical phrases")
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    try:
        repo = find_repo_root(here)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    try:
        findings = verify(repo)
    except Exception as e:
        print(f"error running verify_triggers: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"drift_count": len(findings), "findings": findings}, ensure_ascii=False, indent=2))
    else:
        print(f"=== TRIGGER DRIFT VERIFIER ({repo.name}) ===")
        if not findings:
            print("No drift detected — every canonical phrase in SKILL.md bodies")
            print("matches a regex in hooks/check-skills.sh AND routes to the right skill.")
            return 0
        by_skill: dict[str, list[dict]] = {}
        for f in findings:
            by_skill.setdefault(f["skill"], []).append(f)
        total = sum(len(v) for v in by_skill.values())
        print(f"{total} drift finding(s) across {len(by_skill)} skill(s):\n")
        for skill, items in sorted(by_skill.items()):
            print(f"  /{skill}:")
            for f in items:
                print(f"    ❌ [{f['kind']}] {f['detail']}")
        print()
        print("Action: either add the missing phrase to hooks/check-skills.sh")
        print("OR remove it from the SKILL.md Trigger phrases section.")
        print("The SKILL.md body is the canonical source of truth.")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

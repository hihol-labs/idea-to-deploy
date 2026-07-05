#!/usr/bin/env python3
"""
Routing-accuracy benchmark — for a curated set of REALISTIC, paraphrased
user prompts (benchmarks/routing-prompts.json), verify that the hook router
(`hooks/check-skills.sh` TRIGGERS) routes each prompt to its expected skill.

Why this exists (and how it differs from verify_triggers.py):

- `verify_triggers.py` checks that every CANONICAL trigger phrase that lives
  inside a `SKILL.md` body matches a regex in the hook and routes to the
  right skill. It guards against phrase/regex DRIFT — but it only ever tests
  the verbatim phrases the authors already wrote into the hook.
- `verify_routing.py` (this file) tests ROBUSTNESS: it feeds prompts that are
  deliberately NOT the verbatim trigger phrases — real-world paraphrases in
  Russian and English — and measures how many still route correctly. A drop
  here means the router is brittle to phrasing the authors didn't anticipate.

Ported in spirit from product-factory-os `benchmarks/prompts.json` (which
measures product-type classification accuracy). The canon has no product-type
classifier as a deterministic artifact — its deterministic classifier IS the
hook's regex→skill map — so the benchmark is adapted to skill routing.

Routing model (precise, not naive substring):
  - Each TRIGGER is (regex, hint). A trigger's PRIMARY skill is the FIRST
    `/<slug>` token in its hint text. Hints legitimately mention several
    skills (e.g. the /task hint lists every daily-work skill in parentheses,
    the /advisor hint lists /grill-me and /discover) — only the first is the
    skill the trigger is ABOUT.
  - A prompt's routed set = { primary(trigger) for each trigger whose regex
    matches the prompt }.
  - The prompt routes correctly iff expectedSkill is in that routed set.
  - This also avoids the `/migrate` ⊂ `/migrate-prod` substring trap that a
    naive `f"/{expected}" in hint` test (verify_triggers' check_phrase_routes)
    would fall into.

Usage:
    python3 tests/verify_routing.py                 # human-readable report
    python3 tests/verify_routing.py --json          # machine-readable output
    python3 tests/verify_routing.py --min-accuracy 0.95

Exit codes:
    0 — accuracy >= threshold (default 1.0)
    1 — accuracy below threshold (misroutes found)
    2 — internal error (data/hook missing, etc.)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Reuse the hook loader from the sibling drift verifier (DRY — single source
# of truth for how `check-skills.sh` is imported as a Python module).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_triggers import load_hook_triggers  # noqa: E402

# First `/<slug>` token in a hint = the skill the trigger is about.
PRIMARY_SKILL_RE = re.compile(r"/([a-z][a-z0-9-]+)")


def find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".claude-plugin" / "plugin.json").exists():
            return parent
    raise SystemExit("error: not inside an idea-to-deploy repo")


def primary_skill(hint: str, skills: set[str]) -> str | None:
    """Return the first /<slug> in a hint that is a REAL skill. Slashes also
    appear inside quoted category labels like 'auth/payments' or 'UI/frontend'
    and in references to external plugins — restricting to known skills skips
    those. Returns None if the hint routes to no skill (external plugin only)."""
    for m in PRIMARY_SKILL_RE.finditer(hint):
        if m.group(1) in skills:
            return m.group(1)
    return None


def route(prompt: str, triggers: list[tuple[str, str]], skills: set[str]) -> list[str]:
    """Return the ordered, de-duplicated list of primary skills the prompt
    routes to (one per matched trigger)."""
    lp = prompt.lower()
    routed: list[str] = []
    for pattern, hint in triggers:
        try:
            if re.search(pattern, lp):
                skill = primary_skill(hint, skills)
                if skill and skill not in routed:
                    routed.append(skill)
        except re.error:
            continue
    return routed


def known_skills(repo: Path) -> set[str]:
    skills_dir = repo / "skills"
    return {
        p.name
        for p in skills_dir.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    }


def run(repo: Path) -> dict:
    data_path = repo / "benchmarks" / "routing-prompts.json"
    if not data_path.exists():
        raise SystemExit(f"error: benchmark data not found at {data_path}")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    prompts = data.get("prompts", [])

    triggers = load_hook_triggers(repo / "hooks" / "check-skills.sh")
    skills = known_skills(repo)

    results = []
    for p in prompts:
        pid = p.get("id", "?")
        text = p.get("text", "")
        expected = p.get("expectedSkill", "")
        # `exclusive` prompts (v1.57.0, Release D2 eval): the router must reach
        # the expected skill AND nothing else. This is a regression guard for
        # skills whose over-broad triggers were de-prescribed in D1 — without it
        # a re-broadened trigger keeps 100% accuracy (expected still in routed)
        # while silently re-introducing the ambiguity the de-prescription removed.
        exclusive = bool(p.get("exclusive"))
        routed = route(text, triggers, skills)
        bad_expected = expected not in skills
        if exclusive:
            correct = (not bad_expected) and routed == [expected]
        else:
            correct = (not bad_expected) and (expected in routed)
        results.append(
            {
                "id": pid,
                "text": text,
                "expected": expected,
                "routed": routed,
                "correct": correct,
                "ambiguous": len(routed) > 1,
                "exclusive": exclusive,
                "expected_is_unknown_skill": bad_expected,
            }
        )

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = (correct / total) if total else 1.0
    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "failures": [r for r in results if not r["correct"]],
        "ambiguous": [r for r in results if r["ambiguous"] and r["correct"]],
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Routing-accuracy benchmark for the hook router")
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=1.0,
        help="minimum routing accuracy to pass (default 1.0)",
    )
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    try:
        repo = find_repo_root(here)
        report = run(repo)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error running verify_routing: {e}", file=sys.stderr)
        return 2

    passed = report["accuracy"] >= args.min_accuracy

    if args.json:
        out = dict(report)
        out["min_accuracy"] = args.min_accuracy
        out["passed"] = passed
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if passed else 1

    print("=== ROUTING-ACCURACY BENCHMARK ===")
    print(
        f"{report['correct']}/{report['total']} prompts routed correctly "
        f"— accuracy {report['accuracy'] * 100:.1f}% "
        f"(threshold {args.min_accuracy * 100:.1f}%)"
    )
    if report["failures"]:
        print(f"\n{len(report['failures'])} misroute(s):")
        for f in report["failures"]:
            if f["expected_is_unknown_skill"]:
                detail = f"expectedSkill '{f['expected']}' is not a real skill under skills/"
            elif f.get("exclusive") and f["expected"] in f["routed"]:
                others = ", ".join(s for s in f["routed"] if s != f["expected"])
                detail = (
                    f"/{f['expected']} must route EXCLUSIVELY, but also co-fired: "
                    f"{others} — a de-prescription regression (D1/D2 exclusivity eval); "
                    f"re-narrow the over-broad trigger in hooks/check-skills.sh"
                )
            else:
                got = ", ".join(f["routed"]) if f["routed"] else "(no skill matched)"
                detail = f"expected /{f['expected']}, routed to: {got}"
            print(f"  ❌ [{f['id']}] {detail}")
            print(f"       prompt: {f['text']}")
        print("\nAction: either tighten/extend the regex in hooks/check-skills.sh")
        print("so the prompt routes to the expected skill, OR (if the prompt is")
        print("genuinely ambiguous) reclassify or remove it from")
        print("benchmarks/routing-prompts.json.")
    else:
        print("\nNo misroutes — every benchmark prompt reaches its expected skill.")

    if report["ambiguous"]:
        print(f"\nℹ️  {len(report['ambiguous'])} prompt(s) routed correctly but to >1 skill (ambiguous):")
        for a in report["ambiguous"]:
            print(f"     [{a['id']}] /{a['expected']} among {{{', '.join(a['routed'])}}}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

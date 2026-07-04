#!/usr/bin/env python3
"""
verify_snapshot.py — deterministic structural validation of fixture output.

Given a fixture directory (`tests/fixtures/fixture-XX-name/`) and an output
directory (typically `tests/fixtures/fixture-XX-name/output/`), validates
that the output matches the fixture's `expected-snapshot.json` contract.

This is the **Phase 1** of v1.15.0 behavioural automation — deterministic
*structural* validation of already-generated output. Phase 2 (v1.16.0
candidate) will add **actual non-interactive execution** via
`claude -p --output-format json --input-format stream-json` so the
output can be produced automatically instead of manually.

Why structural validation is not just a "grep":
- **Required files** — catches the "forgot to generate CLAUDE.md" regression
- **Required sections per file** — catches the "renamed ## Budget to ##
  Финансы" regression that passes grep-for-existence but breaks
  downstream skills relying on section headings
- **Content markers** — catches the "generated generic text that doesn't
  mention the fixture's subject" regression (a common LLM failure mode:
  writing plausible text that ignores the user's actual domain)
- **Count constraints** (min_api_endpoints, min_user_story_count, etc.)
  — catches "generated 3 endpoints for a 6-table SaaS" regression

Usage:
    python3 tests/verify_snapshot.py <fixture_dir> [--output <dir>] [--json]

Exit codes:
    0 — PASSED
    1 — FAILED (at least one check failed)
    2 — invalid arguments / missing snapshot file / internal error

Schema format (expected-snapshot.json):

    {
      "$schema_version": "1.0",
      "fixture_type": "kickstart-full",
      "skill_under_test": "/kickstart",
      "mode": "full",                  // optional
      "status": "active",              // active | pending (pending = not
                                       //   yet bootstrapped, gate skips)
      "description": "...",

      "files": {
        "required": ["STRATEGIC_PLAN.md", ...],
        "optional": [".gitignore"],
        "min_count": 7
      },

      "content_contracts": {
        "FILENAME.md": {
          "required_sections": ["Competitors|Конкуренты", ...],
          "min_length_chars": 800,
          "must_contain": ["literal1", "literal2"],
          "must_contain_any_of": {
            "label": ["alt1", "alt2", "alt3"]
          },
          "min_api_endpoints": 15,      // counts ^(GET|POST|PUT|DELETE|PATCH)
          "min_user_story_count": 8,    // counts "- as a " / "- As a "
          "min_step_count": 8,          // counts "^## Step \\d+" or "^\\d+\\."
          "max_step_count": 12
        }
      },

      "rubric_status": {
        "expected": ["PASSED", "PASSED_WITH_WARNINGS"],
        "forbidden": ["BLOCKED"]
      }
    }

All fields are optional except `$schema_version`, `fixture_type`, and
`status`. A snapshot with `status: pending` returns PASSED immediately
(no validation performed), so contributors can stage schema files before
bootstrapping the actual expectations.

Phase 2 (v1.48.0) — `status: "contract"`. For stdout/dialog/orchestrator
skills whose behaviour cannot be asserted file-shaped, the snapshot pins the
SKILL CONTRACT instead: machine-checks that the guarantees documented in the
fixture's notes.md still exist verbatim in skills/<name>/SKILL.md. This is a
DRIFT GUARD (green at adoption time, fails when a later SKILL.md edit drops a
documented guarantee), not a live-behaviour test — live behaviour stays with
battle runs / headless runs. Schema addition:

    {
      "$schema_version": "2.0",
      "status": "contract",
      "skill_contract": {
        "skill": "goal",                        // skills/<skill>/SKILL.md
        "required_sections": ["Trigger phrases", ...],   // section_matches()
        "must_contain": ["literal anchor", ...],          // verbatim in SKILL.md
        "must_contain_any_of": {"label": ["alt1", "alt2"]},
        "harness_suite": "tests/verify_goal_tools.py"     // optional: must exist
                                                          // and be wired into CI
      }
    }

`--all` iterates every tests/fixtures/fixture-*/: contract fixtures are
validated, pending are counted, active (Phase-1) are validated only when an
output/ dir exists locally (outputs are not in git — absent output is SKIP,
not failure). Exit 1 if any validated fixture fails.

Regeneration helper: tests/gen_phase2_contracts.py (extracts anchors from
notes.md that literally appear in SKILL.md; fixtures with too few anchors
stay pending for manual curation).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    fixture: str
    snapshot_path: str
    output_path: str
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(CheckResult(name, passed, detail))

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def to_json(self) -> dict:
        return {
            "fixture": self.fixture,
            "snapshot": self.snapshot_path,
            "output": self.output_path,
            "status": "PASSED" if self.passed else "FAILED",
            "checks_run": len(self.checks),
            "checks_failed": len(self.failed_checks),
            "failures": [
                {"check": c.name, "detail": c.detail} for c in self.failed_checks
            ],
        }


# --------------------------------------------------------------------------
# Content-probe helpers
# --------------------------------------------------------------------------


_SECTION_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)
_API_ENDPOINT_RE = re.compile(
    r"^\s*(?:"
    # v1.43.1: the path must START with /, : or { — bare `METHOD word` is prose
    # («GET requests are cached»), not an endpoint (regression: verify_endpoint_regex.py)
    r"[`*]?\s*(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+[`]?[/:{][/:\w{}\-]*"
    r"|\|\s*\d+\s*\|\s*(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s*\|"
    r"|\|\s*(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+[`]?[/:{][/:\w{}\-]*\s*\|"
    # v1.43.1: method in its OWN table cell, path in the NEXT cell —
    # `| GET | /api/v1/auth/login | ... |` (live fixture-01 headless run
    # 2026-07-03 generated exactly this shape and scored 0/15 endpoints)
    r"|\|\s*[`*]?(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)[`*]?\s*\|\s*[`]?[/:{]"
    r")",
    re.MULTILINE | re.IGNORECASE,
)
# User story markers — matches any of the common LLM-generated formats:
#   1. "As a X, I want ..." / "Как X, я хочу ..." in a bullet list
#      (the original pattern — still valid)
#   2. "### US-N: Title" numbered user story headings (v1.16.0 POC
#      calibration: observed in blueprint output for fixture-02)
#   3. "> As a X, ..." / "> Как X, ..." in a blockquote (also observed
#      in the POC output — model puts the actual story in a quote below
#      the heading)
# Each match is one unique user story. The heading and the blockquote
# for the same story would double-count, so patterns 2 and 3 are
# mutually exclusive in practice because /blueprint uses one of the
# two conventions per document, not both.
_USER_STORY_RE = re.compile(
    r"^\s*(?:"
    r"(?:[-*]|\d+\.)\s+(?:as\s+a|как\s+\w+)\s+"        # bullet-list form
    r"|#{2,4}\s+US[-\s]?\d+[:\s]"                        # "### US-1:" heading
    r"|>\s*(?:as\s+a|как\s+\w+)\b"                      # "> Как X, ..."
    r")",
    re.MULTILINE | re.IGNORECASE,
)
# Implementation plan steps — strict match on "## Step N" / "## Шаг N" /
# "## Этап N" headings ONLY. Earlier versions also matched "\d+\.\s+\w"
# at line start, but that alternative double-counted numbered list items
# INSIDE each step section, inflating the count by an order of magnitude
# (v1.16.0 POC observed 83 "steps" in a 13-step document).
_STEP_HEADING_RE = re.compile(
    r"^\s*#{1,4}\s+(?:step|шаг|этап)\s*\d+",
    re.MULTILINE | re.IGNORECASE,
)


def count_sections(text: str) -> list[str]:
    """Return every section heading (stripped of #) in document order."""
    return [m.group(1).strip() for m in _SECTION_HEADING_RE.finditer(text)]


def count_api_endpoints(text: str) -> int:
    return len(_API_ENDPOINT_RE.findall(text))


def count_user_stories(text: str) -> int:
    return len(_USER_STORY_RE.findall(text))


def count_implementation_steps(text: str) -> int:
    return len(_STEP_HEADING_RE.findall(text))


def section_matches(sections: list[str], pattern: str) -> bool:
    """Match a required_sections pattern against actual section headings.

    The pattern is a pipe-separated list of alternatives — any alternative
    (case-insensitive substring match) counts as a hit. Allows bilingual
    sections: "Competitors|Конкуренты" matches either English or Russian.
    """
    alternatives = [alt.strip().lower() for alt in pattern.split("|") if alt.strip()]
    for heading in sections:
        hl = heading.lower()
        if any(alt in hl for alt in alternatives):
            return True
    return False


def read_rubric_status(output_dir: Path) -> str | None:
    """Look for a rubric status recorded during manual review.

    If the output directory contains a `.rubric-status` file (written by
    the maintainer after running `/review` on the generated output),
    return its contents stripped. Otherwise return None — the snapshot
    check will then be skipped with a note rather than failing.
    """
    status_file = output_dir / ".rubric-status"
    if status_file.is_file():
        return status_file.read_text(encoding="utf-8").strip()
    return None


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate(snapshot: dict, output_dir: Path, report: Report) -> None:
    """Populate `report.checks` from the snapshot contract."""

    # --- files section ---
    files_spec = snapshot.get("files", {})
    required_files = files_spec.get("required", [])
    optional_files = files_spec.get("optional", [])
    min_count = files_spec.get("min_count")

    present_files = {p.name for p in output_dir.iterdir() if p.is_file()}

    for required in required_files:
        if required in present_files:
            report.add(f"files.required[{required}]", True)
        else:
            report.add(
                f"files.required[{required}]",
                False,
                f"required file missing from output",
            )

    if min_count is not None:
        total_present = len(present_files)
        report.add(
            "files.min_count",
            total_present >= min_count,
            f"found {total_present} files, need at least {min_count}",
        )

    # --- content_contracts section ---
    for filename, contract in snapshot.get("content_contracts", {}).items():
        file_path = output_dir / filename
        if not file_path.is_file():
            # Already reported as missing above, skip deep checks.
            report.add(
                f"content_contracts[{filename}].file_exists",
                False,
                "file not in output — cannot validate content",
            )
            continue

        text = file_path.read_text(encoding="utf-8", errors="replace")
        sections = count_sections(text)

        for section_pattern in contract.get("required_sections", []):
            matched = section_matches(sections, section_pattern)
            report.add(
                f"content_contracts[{filename}].section[{section_pattern}]",
                matched,
                "" if matched else f"no section heading matches '{section_pattern}'",
            )

        min_len = contract.get("min_length_chars")
        if min_len is not None:
            actual_len = len(text)
            report.add(
                f"content_contracts[{filename}].min_length_chars",
                actual_len >= min_len,
                f"length={actual_len}, need >= {min_len}",
            )

        for literal in contract.get("must_contain", []):
            present = literal in text
            report.add(
                f"content_contracts[{filename}].must_contain[{literal}]",
                present,
                "" if present else f"literal '{literal}' not found in file",
            )

        for label, alternatives in contract.get("must_contain_any_of", {}).items():
            matched_alt = next((alt for alt in alternatives if alt in text), None)
            report.add(
                f"content_contracts[{filename}].must_contain_any_of[{label}]",
                matched_alt is not None,
                ""
                if matched_alt
                else f"none of {alternatives} found in file",
            )

        min_endpoints = contract.get("min_api_endpoints")
        if min_endpoints is not None:
            actual = count_api_endpoints(text)
            report.add(
                f"content_contracts[{filename}].min_api_endpoints",
                actual >= min_endpoints,
                f"found {actual} endpoint-like lines, need >= {min_endpoints}",
            )

        min_stories = contract.get("min_user_story_count")
        if min_stories is not None:
            actual = count_user_stories(text)
            report.add(
                f"content_contracts[{filename}].min_user_story_count",
                actual >= min_stories,
                f"found {actual} user stories, need >= {min_stories}",
            )

        min_steps = contract.get("min_step_count")
        max_steps = contract.get("max_step_count")
        if min_steps is not None or max_steps is not None:
            actual = count_implementation_steps(text)
            if min_steps is not None:
                report.add(
                    f"content_contracts[{filename}].min_step_count",
                    actual >= min_steps,
                    f"found {actual} steps, need >= {min_steps}",
                )
            if max_steps is not None:
                report.add(
                    f"content_contracts[{filename}].max_step_count",
                    actual <= max_steps,
                    f"found {actual} steps, need <= {max_steps}",
                )

    # --- rubric_status section ---
    rubric_spec = snapshot.get("rubric_status", {})
    expected = rubric_spec.get("expected", [])
    forbidden = rubric_spec.get("forbidden", [])
    if expected or forbidden:
        recorded = read_rubric_status(output_dir)
        if recorded is None:
            report.add(
                "rubric_status",
                True,
                "skipped — no .rubric-status file in output_dir "
                "(run `/review` manually and write the status to "
                "`output/.rubric-status` to enable this check)",
            )
        else:
            if expected:
                report.add(
                    "rubric_status.expected",
                    recorded in expected,
                    f"recorded status '{recorded}' not in expected {expected}",
                )
            if forbidden:
                report.add(
                    "rubric_status.forbidden",
                    recorded not in forbidden,
                    f"recorded status '{recorded}' is in forbidden {forbidden}",
                )


def validate_contract(snapshot: dict, fixture_dir: Path, repo_root: Path,
                      report: Report) -> None:
    """Phase-2: pin the documented skill contract against SKILL.md (drift guard)."""
    spec = snapshot.get("skill_contract") or {}
    # Single skill ("skill") or a scenario fixture spanning several ("skills",
    # e.g. fixture-07-daily-work-skills → bugfix/refactor/perf): anchors are
    # checked against the concatenation, each SKILL.md must exist.
    skills = spec.get("skills") or [
        spec.get("skill") or (snapshot.get("skill_under_test") or "").lstrip("/")]
    texts = []
    for skill in skills:
        skill_md = repo_root / "skills" / skill / "SKILL.md"
        if not skill_md.is_file():
            report.add(f"contract.skill_md_exists[{skill}]", False,
                       f"missing {skill_md}")
            return
        report.add(f"contract.skill_md_exists[{skill}]", True)
        texts.append(skill_md.read_text(encoding="utf-8", errors="replace"))
    text = "\n".join(texts)
    sections = count_sections(text)

    for pattern in spec.get("required_sections", []):
        ok = section_matches(sections, pattern)
        report.add(f"contract.section[{pattern}]", ok,
                   "" if ok else f"no SKILL.md heading matches '{pattern}'")

    for literal in spec.get("must_contain", []):
        ok = literal in text
        report.add(f"contract.must_contain[{literal[:60]}]", ok,
                   "" if ok else "documented guarantee no longer present in SKILL.md")

    for label, alts in (spec.get("must_contain_any_of") or {}).items():
        ok = any(a in text for a in alts)
        report.add(f"contract.any_of[{label}]", ok,
                   "" if ok else f"none of {alts} found in SKILL.md")

    suite = spec.get("harness_suite")
    if suite:
        suite_path = repo_root / suite
        report.add("contract.harness_suite_exists", suite_path.is_file(),
                   "" if suite_path.is_file() else f"missing {suite}")
        ci = repo_root / ".github" / "workflows" / "windows-verify.yml"
        wired = ci.is_file() and Path(suite).name in ci.read_text(
            encoding="utf-8", errors="replace")
        report.add("contract.harness_suite_in_ci", wired,
                   "" if wired else f"{Path(suite).name} not wired into windows-verify.yml")

    notes = fixture_dir / "notes.md"
    report.add("contract.notes_exist", notes.is_file(),
               "" if notes.is_file() else "notes.md (manual half of the contract) missing")


def run_all(fixtures_root: Path, as_json: bool) -> int:
    """--all mode: validate every fixture by its status. Absent Phase-1 output
    dirs are SKIP (outputs are not committed), never a failure."""
    repo_root = fixtures_root.parents[1]
    totals = {"contract_pass": 0, "contract_fail": 0, "pending": 0,
              "active_pass": 0, "active_fail": 0, "active_skip": 0,
              "load_fail": 0}
    failures: list[str] = []
    for fixture_dir in sorted(p for p in fixtures_root.iterdir() if p.is_dir()):
        try:
            snapshot = load_snapshot(fixture_dir)
        except (FileNotFoundError, ValueError) as e:
            # neutral bucket (review N2): a missing/broken snapshot is a load
            # problem, not a failed contract — but it still fails the run
            totals["load_fail"] += 1
            failures.append(f"{fixture_dir.name}: {e}")
            continue
        status = snapshot.get("status")
        if status == "pending":
            totals["pending"] += 1
            continue
        report = Report(fixture=fixture_dir.name,
                        snapshot_path=str(fixture_dir / "expected-snapshot.json"),
                        output_path="-")
        if status == "contract":
            validate_contract(snapshot, fixture_dir, repo_root, report)
            key = "contract_pass" if report.passed else "contract_fail"
            totals[key] += 1
        else:  # Phase-1 active
            output_dir = fixture_dir / "output"
            if not output_dir.is_dir():
                totals["active_skip"] += 1
                continue
            report.output_path = str(output_dir)
            validate(snapshot, output_dir, report)
            key = "active_pass" if report.passed else "active_fail"
            totals[key] += 1
        if not report.passed:
            for c in report.failed_checks:
                failures.append(f"{fixture_dir.name}: {c.name} — {c.detail}")
    result = {"totals": totals, "failures": failures}
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print("verify_snapshot --all:", ", ".join(f"{k}={v}" for k, v in totals.items()))
        for f in failures:
            print("  ❌ " + f)
    return 1 if (totals["contract_fail"] or totals["active_fail"]
                 or totals["load_fail"]) else 0


def load_snapshot(fixture_dir: Path) -> dict:
    snapshot_path = fixture_dir / "expected-snapshot.json"
    if not snapshot_path.is_file():
        raise FileNotFoundError(
            f"no expected-snapshot.json in {fixture_dir} — create one or "
            f"add `\"status\": \"pending\"` stub to skip validation"
        )
    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {snapshot_path}: {e}") from e


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate fixture output against expected-snapshot.json",
    )
    parser.add_argument(
        "fixture_dir",
        type=Path,
        nargs="?",
        default=None,
        help="Path to fixture directory (tests/fixtures/fixture-XX-name/)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate every fixture under tests/fixtures/ by its status "
        "(contract fixtures validated, pending counted, Phase-1 active "
        "validated only when output/ exists locally)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to output directory (default: <fixture_dir>/output/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable output",
    )
    args = parser.parse_args()

    if args.all:
        fixtures_root = Path(__file__).resolve().parent / "fixtures"
        return run_all(fixtures_root, args.json)

    if args.fixture_dir is None:
        parser.error("fixture_dir is required unless --all is given")

    fixture_dir = args.fixture_dir.resolve()
    if not fixture_dir.is_dir():
        print(f"error: fixture dir not found: {fixture_dir}", file=sys.stderr)
        return 2

    output_dir = args.output or (fixture_dir / "output")
    output_dir = output_dir.resolve()

    try:
        snapshot = load_snapshot(fixture_dir)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    # Phase-2 contract snapshots validate SKILL.md, no output dir involved.
    if snapshot.get("status") == "contract":
        report = Report(
            fixture=fixture_dir.name,
            snapshot_path=str(fixture_dir / "expected-snapshot.json"),
            output_path="- (contract mode)",
        )
        # fixture-XX -> fixtures -> tests -> REPO ROOT
        validate_contract(snapshot, fixture_dir, fixture_dir.parents[2], report)
        if args.json:
            print(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
        else:
            icon = "✅" if report.passed else "❌"
            print(f"{icon} {fixture_dir.name}: "
                  f"{'PASSED' if report.passed else 'FAILED'} (contract mode, "
                  f"{len(report.checks)} checks, {len(report.failed_checks)} failed)")
            for c in report.failed_checks:
                print(f"  ❌ {c.name}: {c.detail}")
        return 0 if report.passed else 1

    # Pending snapshots auto-pass without touching the output dir.
    if snapshot.get("status") == "pending":
        result = {
            "fixture": fixture_dir.name,
            "snapshot": str(fixture_dir / "expected-snapshot.json"),
            "status": "PENDING",
            "note": "snapshot marked as pending — bootstrap it before flipping to active",
        }
        if args.json:
            print(json.dumps(result))
        else:
            print(f"⏸️  {fixture_dir.name}: PENDING (snapshot not yet bootstrapped)")
        return 0

    if not output_dir.is_dir():
        print(
            f"error: output dir not found: {output_dir}\n"
            f"  run the fixture manually, then point --output at the result",
            file=sys.stderr,
        )
        return 2

    report = Report(
        fixture=fixture_dir.name,
        snapshot_path=str(fixture_dir / "expected-snapshot.json"),
        output_path=str(output_dir),
    )
    validate(snapshot, output_dir, report)

    if args.json:
        print(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
    else:
        status = "PASSED" if report.passed else "FAILED"
        icon = "✅" if report.passed else "❌"
        print(f"{icon} {fixture_dir.name}: {status}")
        print(f"  Snapshot: {report.snapshot_path}")
        print(f"  Output:   {report.output_path}")
        print(f"  Checks:   {len(report.checks)} run, {len(report.failed_checks)} failed")
        if report.failed_checks:
            print("\nFailures:")
            for c in report.failed_checks:
                print(f"  ❌ {c.name}")
                if c.detail:
                    print(f"       {c.detail}")

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())

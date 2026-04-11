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
    r"^\s*[`*]?\s*(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+[/:\w{}\-]+",
    re.MULTILINE | re.IGNORECASE,
)
# User story markers: "As a X", "Как X", numbered list starting with "As"
_USER_STORY_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+(?:as\s+a|как\s+\w+)\s+",
    re.MULTILINE | re.IGNORECASE,
)
# Implementation plan steps — either "## Step N" or "N." at start of line
_STEP_HEADING_RE = re.compile(
    r"^\s*(?:#{1,3}\s+(?:step|шаг|этап)\s+\d+|\d+\.\s+\w)",
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
        help="Path to fixture directory (tests/fixtures/fixture-XX-name/)",
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

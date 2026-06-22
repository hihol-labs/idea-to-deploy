#!/usr/bin/env python3
"""Validate .itd-memory/STATE.json against the session-state schema.

PFO plugin-native port (Wave 2, item 14). Structured session state is what makes
recovery-after-a-break machine-checkable instead of prose. Ported and adapted from
product-factory-os `scripts/validate_state.py` (`.codex-memory`/`.pfo` -> `.itd-memory`/`.itd`).

Fail-closed: empty required-non-empty fields (approvalStatus, recommendedNextStep,
nextAction) are a validation FAILURE, not a pass — the same principle as the
verification gates. Exit 0 if all state files are valid, 1 otherwise.

Usage:
  python3 scripts/validate_state.py path/to/.itd-memory/STATE.json [more ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "docs" / "templates" / "itd-memory" / "session-state.schema.json"

_OBJECT_FIELDS = ("classification", "architecture", "existingProject", "currentUnit",
                  "gateResults", "humanSteering", "eventLog")
_LIST_FIELDS = ("verificationHistory", "decisionLog", "artifacts",
                "completedModules", "failedValidations", "blockers")


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def validate_state(path: Path) -> None:
    schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    state = json.loads(path.read_text(encoding="utf-8"))

    for field in schema.get("requiredFields", []):
        if field not in state:
            fail(f"{path}: missing required state field '{field}'")

    for field in _OBJECT_FIELDS:
        if not isinstance(state.get(field), dict):
            fail(f"{path}: '{field}' must be an object")
    for field in _LIST_FIELDS:
        if not isinstance(state.get(field), list):
            fail(f"{path}: '{field}' must be a list")

    steering = state.get("humanSteering", {})
    if not steering.get("approvalStatus"):
        fail(f"{path}: humanSteering.approvalStatus must not be empty (fail-closed)")
    if not steering.get("recommendedNextStep"):
        fail(f"{path}: humanSteering.recommendedNextStep must not be empty (fail-closed)")
    if "nextStepApproval" not in state.get("gateResults", {}):
        fail(f"{path}: gateResults.nextStepApproval must be present")
    if not state.get("nextAction"):
        fail(f"{path}: nextAction must not be empty (fail-closed)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate idea-to-deploy .itd-memory/STATE.json files.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    for path in args.paths:
        if not path.is_file():
            fail(f"missing state file: {path}")
        validate_state(path)

    print(f"OK: validated {len(args.paths)} state file(s)")


if __name__ == "__main__":
    main()

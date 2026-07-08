#!/usr/bin/env python3
"""Validate .itd-memory/STATE.json against the session-state schema.

PFO plugin-native port (Wave 2, item 14). Structured session state is what makes
recovery-after-a-break machine-checkable instead of prose. Ported and adapted from
product-factory-os `scripts/validate_state.py` (`.codex-memory`/`.pfo` -> `.itd-memory`/`.itd`).

Fail-closed: empty required-non-empty fields (approvalStatus, recommendedNextStep,
nextAction) are a validation FAILURE, not a pass — the same principle as the
verification gates. Exit 0 if all state files are valid, 1 otherwise.

v1.44.0 (/goal layer): also validates .itd-memory/GOAL.json — the persistent
long-goal unit ledger — against docs/templates/itd-memory/goal.schema.json.
Dispatch is by filename: any path whose basename starts with "GOAL" is validated
as a goal ledger, everything else as session state. Same fail-closed principle:
an empty goal, an empty criterion or verificationCommand, or a skipped unit
without a skippedReason is a FAILURE, not a pass.

Usage:
  python3 scripts/validate_state.py path/to/.itd-memory/STATE.json [more ...]
  python3 scripts/validate_state.py path/to/.itd-memory/GOAL.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "docs" / "templates" / "itd-memory" / "session-state.schema.json"
GOAL_SCHEMA = ROOT / "docs" / "templates" / "itd-memory" / "goal.schema.json"

_OBJECT_FIELDS = ("classification", "architecture", "existingProject", "currentUnit",
                  "gateResults", "humanSteering", "eventLog")
_LIST_FIELDS = ("verificationHistory", "decisionLog", "artifacts",
                "completedModules", "failedValidations", "blockers")

_ACTIVE_UNIT_STATUSES = {"in_progress", "verifying", "recovery_required"}


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def _check_single_wip(path: Path, state: dict) -> None:
    """WIP=1 across both state ledgers. Removes the dual source of "current
    unit": STATE.currentUnit (ad-hoc /task unit) and GOAL.json (long goal) must
    not be active simultaneously -- otherwise it is ambiguous what is in flight.
    GOAL.json owns long-goal units; STATE.currentUnit owns /task units.
    """
    cu = state.get("currentUnit") or {}
    state_active = str(cu.get("status", "")).strip() in _ACTIVE_UNIT_STATUSES
    goal_path = path.parent / "GOAL.json"
    goal_active, goal_unit = False, ""
    if goal_path.is_file():
        try:
            goal = json.loads(goal_path.read_text(encoding="utf-8"))
            goal_unit = str(goal.get("currentUnitId", "")).strip()
            goal_active = str(goal.get("status", "")).strip() != "done" and bool(goal_unit)
        except Exception:
            goal_active = False
    if state_active and goal_active:
        fail(f"{path}: WIP=1 violated -- both STATE.currentUnit "
             f"('{cu.get('id', '')}') and GOAL.json ('{goal_unit}') are active. "
             f"Finish/close one before activating the other.")


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

    _check_single_wip(path, state)


def validate_goal(path: Path) -> None:
    """Validate a .itd-memory/GOAL.json long-goal unit ledger (v1.44.0)."""
    schema = json.loads(GOAL_SCHEMA.read_text(encoding="utf-8"))
    goal = json.loads(path.read_text(encoding="utf-8"))

    for field in schema.get("requiredFields", []):
        if field not in goal:
            fail(f"{path}: missing required goal field '{field}'")

    if not str(goal.get("goal") or "").strip():
        fail(f"{path}: 'goal' must not be empty (fail-closed)")

    goal_statuses = schema.get("goalStatuses", [])
    if goal.get("status") not in goal_statuses:
        fail(f"{path}: status '{goal.get('status')}' not in {goal_statuses}")

    units = goal.get("units")
    if not isinstance(units, list) or not units:
        fail(f"{path}: 'units' must be a non-empty list (fail-closed)")

    unit_statuses = schema.get("unitStatuses", [])
    unit_required = schema.get("unitRequiredFields", [])
    seen_ids: set[str] = set()
    for i, unit in enumerate(units):
        where = f"{path}: units[{i}]"
        if not isinstance(unit, dict):
            fail(f"{where} must be an object")
        for field in unit_required:
            if not str(unit.get(field) or "").strip():
                fail(f"{where}: '{field}' must not be empty (fail-closed)")
        uid = str(unit.get("id"))
        if uid in seen_ids:
            fail(f"{where}: duplicate unit id '{uid}'")
        seen_ids.add(uid)
        if unit.get("status") not in unit_statuses:
            fail(f"{where}: status '{unit.get('status')}' not in {unit_statuses}")
        if unit.get("status") == "skipped" and not str(unit.get("skippedReason") or "").strip():
            fail(f"{where}: skipped unit must carry a non-empty skippedReason (fail-closed)")
        if unit.get("status") == "blocked" and not str(unit.get("blockedReason") or "").strip():
            fail(f"{where}: blocked unit must carry a non-empty blockedReason (fail-closed)")

    current = str(goal.get("currentUnitId") or "").strip()
    if current and current not in seen_ids:
        fail(f"{path}: currentUnitId '{current}' does not match any unit id")

    if goal.get("status") == "done":
        open_units = [u.get("id") for u in units
                      if u.get("status") in ("pending", "in_progress", "blocked")]
        if open_units:
            fail(f"{path}: goal is 'done' but units {open_units} are still open")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate idea-to-deploy .itd-memory/STATE.json and GOAL.json files.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    for path in args.paths:
        if not path.is_file():
            fail(f"missing state file: {path}")
        if path.name.startswith("GOAL"):
            validate_goal(path)
        else:
            validate_state(path)

    print(f"OK: validated {len(args.paths)} state file(s)")


if __name__ == "__main__":
    main()

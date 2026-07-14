#!/usr/bin/env python3
"""Shared validation core for .itd-memory/STATE.json and GOAL.json (v1.75.0).

Extracted from scripts/validate_state.py so the SAME invariants are enforced
from two call sites without drift:

  - scripts/validate_state.py  — the CLI (skills, CI) — thin wrapper;
  - hooks/state-guard.sh       — PostToolUse hook that validates immediately
    after every Write/Edit of a state ledger (ACID-audit fix #4: consistency
    moves from "checked on next session boot" to "checked after each mutation").

Functions here return error/warning LISTS instead of sys.exit'ing, so a hook
can degrade softly (additionalContext) while the CLI stays fail-closed.

Schema resolution is multi-path because this file lives in two layouts:
  repo checkout:   <repo>/hooks/validate_state_core.py
                   schemas at <repo>/docs/templates/itd-memory/
  active install:  ~/.claude/hooks/validate_state_core.py
                   schemas at ~/.claude/templates/itd-memory/  (sync Step 4/6)
If no schema file is found, a built-in minimal required-field list keeps the
core checks alive (best-effort invariant: a missing artifact degrades to the
neutral path, never to a false "all green").

v1.75.0 also adds the reconciliation invariant (ACID-audit fix #5): when
events.jsonl exists next to STATE.json, the STATE tail must not CONTRADICT the
event-log tail. Contradiction (STATE says the unit is active but the log says
it was already verified) is an ERROR; mere absence of an event (unit never
logged) is a WARNING — projects predating the events convention stay valid.

Stdlib only. Never raises out of validate_* entry points on malformed input —
malformed JSON is itself reported as an error.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent

# repo layout first, then active-install layout (~/.claude/templates/...)
_SCHEMA_DIRS = (
    _LIB_DIR.parent / "docs" / "templates" / "itd-memory",
    _LIB_DIR.parent / "templates" / "itd-memory",
)

# Built-in fallback when no schema file is resolvable (fresh machine, partial
# install). Mirrors requiredFields of the shipped schemas — keep in sync.
_FALLBACK_STATE_REQUIRED = [
    "classification", "architecture", "existingProject", "currentUnit",
    "gateResults", "humanSteering", "eventLog", "verificationHistory",
    "decisionLog", "artifacts", "completedModules", "failedValidations",
    "blockers", "nextAction",
]
_FALLBACK_GOAL = {
    "requiredFields": ["goal", "status", "units"],
    "goalStatuses": ["active", "done", "abandoned"],
    "unitStatuses": ["pending", "in_progress", "verified", "skipped", "blocked"],
    "unitRequiredFields": ["id", "criterion", "verificationCommand", "status"],
    "runPolicyModes": ["bounded_autonomous"],
    "runPolicyRequiredFields": [
        "mode", "maxAttemptsPerUnit", "maxWallClockSecondsPerUnit",
        "maxTokensPerSession", "freezeVerification", "requireApproach",
        "requireIndependentReview",
    ],
    "attemptKinds": ["verification", "recheck"],
    "attemptOutcomes": ["verified", "failed", "regressed"],
    "stopReasons": ["", "verified", "blocked", "budget_exhausted"],
}

_OBJECT_FIELDS = ("classification", "architecture", "existingProject", "currentUnit",
                  "gateResults", "humanSteering", "eventLog")
_LIST_FIELDS = ("verificationHistory", "decisionLog", "artifacts",
                "completedModules", "failedValidations", "blockers")

ACTIVE_UNIT_STATUSES = {"in_progress", "verifying", "recovery_required"}

# Unit-event decisions that mean "this unit is finished" in events.jsonl.
_TERMINAL_DECISIONS = {"verified", "closed", "skipped", "abandoned"}


def _load_schema(name: str) -> dict | None:
    for d in _SCHEMA_DIRS:
        p = d / name
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def _load_json(path: Path, errors: list[str]) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path}: missing state file")
        return None
    except Exception as exc:
        errors.append(f"{path}: not valid JSON ({exc})")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path}: top-level value must be an object")
        return None
    return data


def _check_single_wip(path: Path, state: dict, errors: list[str]) -> None:
    """WIP=1 across both state ledgers (STATE.currentUnit vs GOAL.json)."""
    cu = state.get("currentUnit") or {}
    if not isinstance(cu, dict):
        return  # already reported as a type error
    state_active = str(cu.get("status", "")).strip() in ACTIVE_UNIT_STATUSES
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
        errors.append(
            f"{path}: WIP=1 violated -- both STATE.currentUnit "
            f"('{cu.get('id', '')}') and GOAL.json ('{goal_unit}') are active. "
            f"Finish/close one before activating the other.")


def _last_unit_event(events_path: Path, unit_id: str) -> dict | None:
    """Last {"type":"unit","name":<unit_id>,...} record in events.jsonl."""
    return _last_unit_events(events_path).get(unit_id)


EVENTS_TAIL_BYTES = 512 * 1024  # реконсиляция читает не больше этого хвоста


def _last_unit_events(events_path: Path) -> dict:
    """One pass over events.jsonl → {unit_name: last unit-event record}.

    v1.76.0: shared by STATE and GOAL reconciliation — GOAL ledgers hold many
    units, per-unit rescans would be O(units × log).

    v1.80.1 (RUNBOOK-кандидат): чтение ограничено ХВОСТОМ EVENTS_TAIL_BYTES.
    Очень большой журнал + hook-timeout 5с → валидация молча скипалась бы
    целиком; хвост — безопасная деградация: «последнее решение по юниту»
    tail-biased по построению, а юнит, чьи события целиком старше окна,
    выглядит как «нет события» → это WARNING-ветка (absence), не ложный fail.
    """
    last: dict = {}
    try:
        size = events_path.stat().st_size
        with events_path.open("rb") as fb:
            if size > EVENTS_TAIL_BYTES:
                fb.seek(size - EVENTS_TAIL_BYTES)
                fb.readline()  # отбрасываем, скорее всего, неполную первую строку
            payload = fb.read().decode("utf-8", errors="replace")
        for line in payload.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict) or rec.get("type") != "unit":
                continue
            name = str(rec.get("name", "") or "").strip()
            if name:
                last[name] = rec
    except Exception:
        return {}
    return last


def _events_ledger(path: Path) -> Path | None:
    """events.jsonl next to the ledger, or None when there is nothing to
    reconcile against (missing/empty — legacy projects stay valid)."""
    events_path = path.parent / "events.jsonl"
    if not events_path.is_file():
        return None
    try:
        if events_path.stat().st_size == 0:
            return None
    except Exception:
        return None
    return events_path


def reconcile_goal_with_events(path: Path, goal: dict) -> tuple[list[str], list[str]]:
    """v1.76.0 — the reconciliation invariant GOAL.json ↔ events.jsonl.

    Same semantics as the STATE check (contradiction fails, absence warns),
    applied per unit of the long-goal ledger:
      - a unit still OPEN in GOAL (pending/in_progress/verifying/blocked)
        while the log already recorded a terminal decision for it → ERROR;
      - a unit VERIFIED in GOAL with no terminal decision in a non-empty
        log → WARNING (capped at 3 to keep the CLI readable).
    """
    errors: list[str] = []
    warnings: list[str] = []
    events_path = _events_ledger(path)
    if events_path is None:
        return errors, warnings
    last_by_unit = _last_unit_events(events_path)

    units = goal.get("units")
    if not isinstance(units, list):
        return errors, warnings
    open_statuses = {"pending", "in_progress", "verifying", "blocked"}
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id", "") or "").strip()
        status = str(unit.get("status", "") or "").strip()
        if not uid or not status:
            continue
        last = last_by_unit.get(uid)
        last_decision = str((last or {}).get("decision", "") or "").strip().lower()
        if status in open_statuses and last_decision in _TERMINAL_DECISIONS:
            errors.append(
                f"{path}: reconciliation violated -- unit '{uid}' is "
                f"'{status}' in GOAL.json, but events.jsonl already recorded "
                f"'{last_decision}' for it. Goal ledger tail is stale: update "
                f"the unit status or append the missing unit event.")
        elif status == "verified" and last_decision not in _TERMINAL_DECISIONS:
            if len(warnings) < 3:
                seen = ("no unit event at all" if last is None
                        else f"last decision '{last_decision}'")
                warnings.append(
                    f"{path}: unit '{uid}' is 'verified' in GOAL.json, but "
                    f"events.jsonl has {seen} for it -- append the 'verified' "
                    f"unit event so the ledger stays the source of truth.")
    return errors, warnings


def reconcile_with_events(path: Path, state: dict) -> tuple[list[str], list[str]]:
    """ACID-audit fix #5 — the reconciliation invariant STATE ↔ events.jsonl.

    Returns (errors, warnings). Only CONTRADICTION fails; absence warns:
      - STATE unit active, but the log's last decision for it is terminal
        (verified/closed/...) → ERROR: STATE tail is stale vs the event log.
      - STATE unit verified, but the log never saw a terminal decision for it
        (activated-only, or no record at all in a non-empty log) → WARNING:
        the "verified" claim has no event-sourced trace.
    No events.jsonl (or empty) → nothing to reconcile against, silent.
    """
    errors: list[str] = []
    warnings: list[str] = []
    events_path = path.parent / "events.jsonl"
    if not events_path.is_file():
        return errors, warnings
    try:
        if events_path.stat().st_size == 0:
            return errors, warnings
    except Exception:
        return errors, warnings

    cu = state.get("currentUnit") or {}
    if not isinstance(cu, dict):
        return errors, warnings
    unit_id = str(cu.get("id", "") or "").strip()
    status = str(cu.get("status", "") or "").strip()
    if not unit_id or not status:
        return errors, warnings

    last = _last_unit_event(events_path, unit_id)
    last_decision = str((last or {}).get("decision", "") or "").strip().lower()

    if status in ACTIVE_UNIT_STATUSES and last_decision in _TERMINAL_DECISIONS:
        errors.append(
            f"{path}: reconciliation violated -- currentUnit '{unit_id}' is "
            f"'{status}' in STATE, but events.jsonl already recorded "
            f"'{last_decision}' for it. STATE tail is stale: update "
            f"currentUnit.status or append the missing unit event.")
    elif status == "verified" and last_decision not in _TERMINAL_DECISIONS:
        seen = "no unit event at all" if last is None else f"last decision '{last_decision}'"
        warnings.append(
            f"{path}: currentUnit '{unit_id}' is 'verified' in STATE, but "
            f"events.jsonl has {seen} for it -- append the 'verified' unit "
            f"event so the ledger stays the source of truth.")
    return errors, warnings


def validate_state_file(path: Path) -> tuple[list[str], list[str]]:
    """Validate a STATE.json session-state file. Returns (errors, warnings)."""
    errors: list[str] = []
    state = _load_json(path, errors)
    if state is None:
        return errors, []

    schema = _load_schema("session-state.schema.json")
    required = (schema or {}).get("requiredFields") or _FALLBACK_STATE_REQUIRED
    for field in required:
        if field not in state:
            errors.append(f"{path}: missing required state field '{field}'")

    for field in _OBJECT_FIELDS:
        if field in state and not isinstance(state.get(field), dict):
            errors.append(f"{path}: '{field}' must be an object")
    for field in _LIST_FIELDS:
        if field in state and not isinstance(state.get(field), list):
            errors.append(f"{path}: '{field}' must be a list")
    if errors:
        return errors, []

    steering = state.get("humanSteering", {})
    if not steering.get("approvalStatus"):
        errors.append(f"{path}: humanSteering.approvalStatus must not be empty (fail-closed)")
    if not steering.get("recommendedNextStep"):
        errors.append(f"{path}: humanSteering.recommendedNextStep must not be empty (fail-closed)")
    if "nextStepApproval" not in state.get("gateResults", {}):
        errors.append(f"{path}: gateResults.nextStepApproval must be present")
    if not state.get("nextAction"):
        errors.append(f"{path}: nextAction must not be empty (fail-closed)")

    _check_single_wip(path, state, errors)
    rec_errors, warnings = reconcile_with_events(path, state)
    errors.extend(rec_errors)
    return errors, warnings


def _bounded_policy_snapshot(policy: dict) -> dict:
    return {
        key: policy.get(key)
        for key in ("mode", "maxAttemptsPerUnit",
                    "maxWallClockSecondsPerUnit", "maxTokensPerSession",
                    "freezeVerification", "requireApproach",
                    "requireIndependentReview")
    }


def _bounded_snapshot_fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _bounded_policy_fingerprint(policy: dict) -> str:
    return _bounded_snapshot_fingerprint(_bounded_policy_snapshot(policy))


def _bounded_unit_fingerprint(unit: dict) -> str:
    payload = {
        "criterion": str(unit.get("criterion") or ""),
        "verificationCommand": str(unit.get("verificationCommand") or ""),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def validate_goal_file(path: Path) -> tuple[list[str], list[str]]:
    """Validate a GOAL.json long-goal unit ledger. Returns (errors, warnings)."""
    errors: list[str] = []
    goal = _load_json(path, errors)
    if goal is None:
        return errors, []

    schema = _load_schema("goal.schema.json") or _FALLBACK_GOAL

    for field in schema.get("requiredFields", []):
        if field not in goal:
            errors.append(f"{path}: missing required goal field '{field}'")

    if not str(goal.get("goal") or "").strip():
        errors.append(f"{path}: 'goal' must not be empty (fail-closed)")

    goal_statuses = schema.get("goalStatuses", [])
    if goal_statuses and goal.get("status") not in goal_statuses:
        errors.append(f"{path}: status '{goal.get('status')}' not in {goal_statuses}")

    units = goal.get("units")
    if not isinstance(units, list) or not units:
        errors.append(f"{path}: 'units' must be a non-empty list (fail-closed)")
        return errors, []

    policy = goal.get("runPolicy")
    bounded = policy is not None
    policy_sealed = False
    if bounded:
        if not isinstance(policy, dict):
            errors.append(f"{path}: runPolicy must be an object")
            policy = {}
        for field in schema.get("runPolicyRequiredFields", []):
            if field not in policy:
                errors.append(f"{path}: runPolicy missing required field '{field}'")
        modes = schema.get("runPolicyModes", [])
        if modes and policy.get("mode") not in modes:
            errors.append(f"{path}: runPolicy.mode '{policy.get('mode')}' not in {modes}")
        for field in ("maxAttemptsPerUnit", "maxWallClockSecondsPerUnit",
                      "maxTokensPerSession"):
            value = policy.get(field)
            if type(value) is not int or value <= 0:
                errors.append(f"{path}: runPolicy.{field} must be a positive integer")
        for field in ("freezeVerification", "requireApproach",
                      "requireIndependentReview"):
            if type(policy.get(field)) is not bool:
                errors.append(f"{path}: runPolicy.{field} must be boolean")
        if policy.get("freezeVerification") is not True:
            errors.append(f"{path}: bounded run requires freezeVerification=true")
        if policy.get("requireApproach") is not True:
            errors.append(f"{path}: bounded run requires requireApproach=true")
        sealed = str(policy.get("sealedFingerprint") or "")
        policy_sealed = bool(sealed)
        if sealed:
            sealed_policy = policy.get("sealedPolicy")
            if not isinstance(sealed_policy, dict):
                errors.append(f"{path}: sealed runPolicy requires sealedPolicy snapshot")
            elif sealed != _bounded_snapshot_fingerprint(sealed_policy):
                errors.append(f"{path}: sealedPolicy does not match sealedFingerprint")
            elif sealed_policy != _bounded_policy_snapshot(policy):
                errors.append(f"{path}: runPolicy changed after approval seal")

    unit_statuses = schema.get("unitStatuses", [])
    unit_required = schema.get("unitRequiredFields", [])
    seen_ids: set[str] = set()
    for i, unit in enumerate(units):
        where = f"{path}: units[{i}]"
        if not isinstance(unit, dict):
            errors.append(f"{where} must be an object")
            continue
        for field in unit_required:
            if not str(unit.get(field) or "").strip():
                errors.append(f"{where}: '{field}' must not be empty (fail-closed)")
        uid = str(unit.get("id"))
        if uid in seen_ids:
            errors.append(f"{where}: duplicate unit id '{uid}'")
        seen_ids.add(uid)
        if unit_statuses and unit.get("status") not in unit_statuses:
            errors.append(f"{where}: status '{unit.get('status')}' not in {unit_statuses}")
        if unit.get("status") == "skipped" and not str(unit.get("skippedReason") or "").strip():
            errors.append(f"{where}: skipped unit must carry a non-empty skippedReason (fail-closed)")
        if unit.get("status") == "blocked" and not str(unit.get("blockedReason") or "").strip():
            errors.append(f"{where}: blocked unit must carry a non-empty blockedReason (fail-closed)")

        attempts = unit.get("attempts")
        if attempts is not None and not isinstance(attempts, list):
            errors.append(f"{where}: attempts must be an array")
            attempts = []
        if isinstance(attempts, list):
            kinds = schema.get("attemptKinds", [])
            outcomes = schema.get("attemptOutcomes", [])
            for j, attempt in enumerate(attempts):
                awhere = f"{where}.attempts[{j}]"
                if not isinstance(attempt, dict):
                    errors.append(f"{awhere} must be an object")
                    continue
                if attempt.get("number") != j + 1:
                    errors.append(f"{awhere}: number must be sequential ({j + 1})")
                for field in ("at", "approach", "verificationCommand", "evidence"):
                    if not str(attempt.get(field) or "").strip():
                        errors.append(f"{awhere}: '{field}' must not be empty")
                if kinds and attempt.get("kind") not in kinds:
                    errors.append(f"{awhere}: kind '{attempt.get('kind')}' not in {kinds}")
                if outcomes and attempt.get("outcome") not in outcomes:
                    errors.append(f"{awhere}: outcome '{attempt.get('outcome')}' not in {outcomes}")
                if (isinstance(policy, dict)
                        and policy.get("requireIndependentReview")
                        and not str(attempt.get("reviewEvidence") or "").strip()):
                    errors.append(f"{awhere}: independent review evidence is required")
            if (isinstance(policy, dict)
                    and type(policy.get("maxAttemptsPerUnit")) is int
                    and len(attempts) > policy["maxAttemptsPerUnit"]):
                errors.append(f"{where}: attempt count exceeds approved budget")

        run_state = unit.get("runState")
        if run_state is not None and not isinstance(run_state, dict):
            errors.append(f"{where}: runState must be an object")
            run_state = {}
        if bounded and policy_sealed:
            if not isinstance(attempts, list):
                errors.append(f"{where}: sealed bounded unit requires attempts[]")
            if not isinstance(run_state, dict):
                errors.append(f"{where}: sealed bounded unit requires runState")
            else:
                fp = str(run_state.get("verificationFingerprint") or "")
                if not fp:
                    errors.append(f"{where}: approved verification fingerprint is missing")
                elif fp != _bounded_unit_fingerprint(unit):
                    errors.append(f"{where}: criterion/verificationCommand changed after approval")
                stop = str(run_state.get("stopReason") or "")
                allowed_stops = schema.get("stopReasons", [])
                if allowed_stops and stop not in allowed_stops:
                    errors.append(f"{where}: stopReason '{stop}' not in {allowed_stops}")
                if unit.get("status") in ("in_progress", "verified") \
                        and not str(run_state.get("startedAt") or "").strip():
                    errors.append(f"{where}: active/completed bounded unit lacks startedAt")
                if unit.get("status") == "verified" and stop != "verified":
                    errors.append(f"{where}: verified bounded unit requires stopReason=verified")
                if unit.get("status") == "blocked" and not stop:
                    errors.append(f"{where}: blocked bounded unit requires typed stopReason")
                if stop == "budget_exhausted":
                    exhausted = run_state.get("exhaustedBudget")
                    if (not isinstance(exhausted, dict)
                            or exhausted.get("kind") not in
                            ("attempts", "wall_clock", "tokens")
                            or type(exhausted.get("limit")) is not int):
                        errors.append(f"{where}: budget_exhausted requires exhaustedBudget evidence")

    current = str(goal.get("currentUnitId") or "").strip()
    if current and current not in seen_ids:
        errors.append(f"{path}: currentUnitId '{current}' does not match any unit id")

    if goal.get("status") == "done":
        open_units = [u.get("id") for u in units if isinstance(u, dict)
                      and u.get("status") in ("pending", "in_progress", "blocked")]
        if open_units:
            errors.append(f"{path}: goal is 'done' but units {open_units} are still open")

    rec_errors, warnings = reconcile_goal_with_events(path, goal)
    errors.extend(rec_errors)
    return errors, warnings


def validate_path(path: Path) -> tuple[list[str], list[str]]:
    """Dispatch by filename (GOAL* → goal ledger, else session state)."""
    if path.name.startswith("GOAL"):
        return validate_goal_file(path)
    return validate_state_file(path)

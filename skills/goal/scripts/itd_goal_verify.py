#!/usr/bin/env python3
"""Goal-unit verifier — the harness-side "ОТК" for .itd-memory/GOAL.json (v1.45.0).

Closes the walkinglabs feature-list divergence «переходами управляет harness, а
не агент»: the AGENT may only REQUEST a transition; THIS SCRIPT executes the
unit's verificationCommand and is the only party that writes `verified`. The
agent never edits unit states by hand when this tool is available.

State machine it enforces (goal.schema.json unitStatuses):

    pending ──activate──▶ in_progress ──verify(exit 0)──▶ verified
       ▲                    │  ▲  │
       └────unblock─────────┘  │  └──block <reason>──▶ blocked
                               └──verify(exit≠0): stays in_progress
    in_progress ──working deadline 45m──▶ recovery_required
    recovery_required ──activate --reason──▶ in_progress (fresh observed cycle)
    verified ──recheck(exit≠0)──▶ in_progress   (ledger reflects VERIFIED
                                                 reality, not bureaucracy)

Guarantees:
  - WIP=1: --activate refuses while another unit is in_progress.
  - verify only from in_progress (activate first) — course's «gate on passing».
  - verified only with evidence from an ACTUAL command run (never hand-set).
  - every transition appends a unit event to events.jsonl with actor "harness"
    (VCR in itd_metrics.py counts them automatically).
  - blocked requires a non-empty reason (fail-closed, mirrors skippedReason).

Ships inside the skill (skills/goal/scripts/) so both sync-to-active and the
plugin install deliver it to ~/.claude/skills/goal/scripts/. Stdlib only.

Trust model: verificationCommand is executed via ["sh", "-c", command]. It is
TRUSTED, user-approved content — the user explicitly approves every unit (incl.
its command) at /goal Step 1 before the ledger is written; same trust boundary
as hook commands in .claude/settings.json. If a future caller feeds this tool a
ledger from an external/synced source, that assumption no longer holds — add
sandboxing there, not here.

Shell contract (v1.87.0): verificationCommand is POSIX sh. Раньше стояло
shell=True — на Windows это cmd.exe, который не снимает одинарные кавычки и не
раскрывает $VAR; деградировавшая команда могла вернуть exit 0 → ТИХИЙ ложный
verified (live-репро retro 2026-07-11 сет-3 упр.1: evidence '"HOME=$HOME"'').
Теперь всегда ["sh","-c",…]; sh недоступен (нет Git Bash) — громкий отказ
rc=127, НЕ тихая деградация в cmd.exe.

Asymmetry note: verify/--activate/--block resolve a default unit when UNIT_ID
is omitted (currentUnitId → first in_progress → first pending); --recheck
targets `verified` units, which that chain never returns — always pass an
explicit UNIT_ID with --recheck.

Usage:
  itd_goal_verify.py [--goal PATH] --seal
  itd_goal_verify.py [--goal PATH] --activate [UNIT_ID]
  itd_goal_verify.py [--goal PATH] [UNIT_ID]              # verify (default cmd)
  itd_goal_verify.py [--goal PATH] --recheck UNIT_ID      # re-run a verified unit
  itd_goal_verify.py [--goal PATH] --block UNIT_ID --reason "..."
  itd_goal_verify.py [--goal PATH] --budget-exhausted UNIT_ID \
      --budget-kind tokens --reason "host token ceiling reached"
  itd_goal_verify.py [--goal PATH] --activate UNIT_ID \
      --work-profile working_deadline
  itd_goal_verify.py [--goal PATH] --deadline-check UNIT_ID \
      --elapsed-seconds 1800 --checkpoint-ready "..." \
      --checkpoint-blocker "..." --checkpoint-remainder "..." \
      --checkpoint-estimate "..."
  itd_goal_verify.py [--goal PATH] --ack-handoff UNIT_ID --reason "new user turn"
  itd_goal_verify.py [--goal PATH] --timeout 600

Exit codes: 0 transition applied (or recheck still green), 1 verification
failed / invalid transition, 2 usage or ledger error, 3 typed bounded stop
(`runState.stopReason` explains `blocked` vs `budget_exhausted`).
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from itd_safe_atomic import atomic_replace_bytes, durable_append_bytes, durable_unlink, ledger_events, read_ledger_snapshot, read_regular_snapshot  # noqa: E402

GOAL_DEFAULT = Path(".itd-memory") / "GOAL.json"
UNIT_STATUSES = (
    "pending", "in_progress", "recovery_required", "verified", "skipped", "blocked",
)
# A unit in ANY of these states keeps the goal open (backpressure > 0). Must
# stay identical to OPEN_STATUSES in itd_goal_report.py.
OPEN_STATUSES = ("pending", "in_progress", "recovery_required", "blocked")
EVIDENCE_MAX = 200
BOUNDED_MODE = "bounded_autonomous"
BOUNDED_STOP_EXIT = 3
POLICY_KEYS = (
    "mode", "maxAttemptsPerUnit", "maxWallClockSecondsPerUnit",
    "maxTokensPerSession", "freezeVerification", "requireApproach",
    "requireIndependentReview",
)
OPTIONAL_POLICY_KEYS = (
    "enforceObservedTokens", "verificationStrategy", "maxCheckpointBytes",
)
RISK_TIERS = ("low", "medium", "high")
JSON_SNAPSHOT_MAX_BYTES = 4 * 1024 * 1024
WORKING_DEADLINE_PROFILE = "working_deadline"
WORKING_DEADLINE_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "_shared" / "WORKING_DEADLINE_POLICY.json"
)
VERIFICATION_LOOP_PATH = (
    Path(__file__).resolve().parents[2] / "_shared" / "itd_verification_loop.py"
)
UNIT_LOG_PATH = Path(__file__).resolve().parents[2] / "task" / "scripts" / "itd_unit_log.py"
CHECKPOINT_FIELDS = ("ready", "blocker", "remainder", "estimate")


class VerificationReceiptError(ValueError):
    pass


def strict_json_equal(left: object, right: object) -> bool:
    """Compare JSON values without Python's bool/int or int/float coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(strict_json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(strict_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def contained_project_path(project_root: Path, raw: str | Path, label: str) -> Path:
    """Bind a receipt path lexically inside the project without following links.

    The path is never resolved: ``resolve()`` would follow a symlink or
    junction first and let a later no-link check inspect only the target
    (Sol-a7). Containment is decided on the unresolved components; the
    anchored snapshot then refuses any link on the way to the leaf.
    """
    path = Path(raw)
    if ".." in path.parts or not path.name:
        raise VerificationReceiptError(f"{label} must stay inside the project")
    if not path.is_absolute():
        path = project_root / path
    try:
        relative = path.relative_to(project_root)
    except ValueError as exc:
        raise VerificationReceiptError(f"{label} must stay inside the project") from exc
    if not relative.parts:
        raise VerificationReceiptError(f"{label} must stay inside the project")
    return path


def stable_json_snapshot(path: Path, label: str) -> tuple[bytes, dict]:
    """Read one bounded anchored no-follow regular JSON snapshot without blocking on FIFOs."""
    try:
        before = path.lstat()
        reparse = bool(getattr(before, "st_file_attributes", 0) & 0x400)
        if stat.S_ISLNK(before.st_mode) or reparse or not stat.S_ISREG(before.st_mode):
            raise VerificationReceiptError(f"{label} is not a regular no-link file")
        if before.st_size > JSON_SNAPSHOT_MAX_BYTES:
            raise VerificationReceiptError(f"{label} exceeds the snapshot size limit")
        # Every directory on the way and the leaf are opened without following
        # links from a held parent (POSIX dir_fd chain / Windows relative
        # NtCreateFile), so a link swapped in after validation is refused
        # rather than read through; the read is bounded and non-blocking.
        payload = read_regular_snapshot(path.absolute(), JSON_SNAPSHOT_MAX_BYTES)
        current = path.lstat()
        if ((current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
                or stat.S_ISLNK(current.st_mode) or current.st_size != len(payload)):
            raise VerificationReceiptError(f"{label} changed or exceeded its bound while reading")
        value = json.loads(payload.decode("utf-8"))
    except VerificationReceiptError:
        raise
    except Exception as exc:
        raise VerificationReceiptError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise VerificationReceiptError(f"{label} is not a JSON object")
    return payload, value


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}")
    sys.exit(code)


def validate_verification_receipt(goal_path: Path, receipt_path: str,
                                  risk_tier: str, unit_id: str) -> dict:
    """Consume an adjudicated exact-candidate receipt from the shared harness."""
    spec = importlib.util.spec_from_file_location(
        "itd_goal_verification_loop", VERIFICATION_LOOP_PATH)
    if spec is None or spec.loader is None:
        raise VerificationReceiptError(
            "Verification Loop producer is unavailable; cannot trust checker evidence")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project_root = goal_path.resolve().parent.parent
    path = contained_project_path(project_root, receipt_path, "Verification Loop receipt")
    relative = path.relative_to(project_root).as_posix()
    try:
        receipt = module.validate_adjudication(
            project_root, path, risk_tier, unit_id)
    except module.LoopError as exc:
        raise VerificationReceiptError(
            f"Verification Loop receipt UNVERIFIED: {exc.why}; FIX: {exc.fix}") from exc
    adjudication_bytes, stable_receipt = stable_json_snapshot(path, "Verification Loop adjudication receipt")
    if not strict_json_equal(stable_receipt, receipt):
        raise VerificationReceiptError("Verification Loop adjudication receipt changed after validation")
    machine_ref = receipt.get("dependencies", {}).get("machine", {})
    machine_path = contained_project_path(
        project_root, str(machine_ref.get("path") or ""), "Verification Loop machine receipt")
    machine_bytes, machine = stable_json_snapshot(machine_path, "Verification Loop machine receipt")
    if hashlib.sha256(machine_bytes).hexdigest() != str(machine_ref.get("sha256") or ""):
        raise VerificationReceiptError("Verification Loop machine receipt changed after adjudication validation")
    return {
        "path": relative,
        "sha256": hashlib.sha256(adjudication_bytes).hexdigest(),
        "receiptSha256": str(receipt.get("receiptSha256") or ""),
        "outcome": str(receipt.get("outcome") or ""),
        "machinePath": str(machine_ref.get("path") or ""),
        "machineSha256": str(machine_ref.get("sha256") or ""),
        "machine": machine,
    }


def write_verify_signal(goal_path: Path, unit_id: str, rc: int,
                        command: str, evidence: str) -> None:
    """Записать runtime-сигнал верификации (v1.89.0, GO-003).

    Раньше ОТК исполнял verificationCommand subprocess-ом мимо PostToolUse —
    completion-gate этих прогонов НЕ видел (44 verified / 0 сигналов, сет-4:
    «верифицирован ↔ ничего не проверялось» неразличимы). Теперь каждый прогон
    оставляет сигнал kind `verify` (L2, class verification) с атрибуцией к юниту.
    Вендор-нейтрально: пишем JSONL напрямую, без импорта hooks-пакета.
    Best-effort — сбой записи НИКОГДА не ломает верификацию.
    """
    try:
        project_root = goal_path.resolve().parent.parent
        d = project_root / ".claude" / "completion"
        d.mkdir(parents=True, exist_ok=True)
        sig = {
            "ts": now_iso(),
            "kind": "verify",
            "layer": 2,
            "class": "verification",
            "command": ("otk: " + command)[:300],
            "outcome": "pass" if rc == 0 else "fail",
            "evidence": evidence[:200],
            "unit": unit_id,
            "session": "otk",
        }
        with (d / "signals.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(sig, ensure_ascii=False) + "\n")
    except Exception:
        pass


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_working_deadline_policy() -> tuple[dict, str]:
    """Load the canonical cadence policy and reject an unsafe runtime shape."""
    try:
        raw = WORKING_DEADLINE_POLICY_PATH.read_bytes()
        policy = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        die(f"working_deadline policy is unavailable: {exc}", 1)
    activation = policy.get("activation") or {}
    timebox = policy.get("timebox") or {}
    cadence = policy.get("unitCadence") or {}
    if (policy.get("id") != "working-deadline-v1"
            or activation.get("profile") != WORKING_DEADLINE_PROFILE
            or activation.get("explicitOptInRequired") is not True
            or activation.get("defaultEnabled") is not False
            or activation.get("allowedRiskTiers") != ["low", "medium"]
            or timebox.get("measurement") != "host-observed-unit-elapsed"
            or timebox.get("softCheckpointSeconds") != 1800
            or timebox.get("hardPauseSeconds") != 2700
            or timebox.get("partialCompletionIsVerified") is not False
            or cadence.get("maxOpenUnits") != 1
            or cadence.get("handoffAfterVerifiedUnit") is not True
            or cadence.get("maxVerifiedUnitsPerHandoff") != 1):
        die("working_deadline policy is malformed or weakened", 1)
    return policy, hashlib.sha256(raw).hexdigest()


def deadline_state(unit: dict) -> dict | None:
    state = unit.get("deadlineState")
    if state is None:
        return None
    if not isinstance(state, dict):
        die(f"{unit.get('id')}: deadlineState must be an object", 1)
    return state


def is_working_deadline_unit(unit: dict) -> bool:
    state = deadline_state(unit)
    return bool(state and state.get("profile") == WORKING_DEADLINE_PROFILE)


def assert_deadline_policy_binding(unit: dict) -> tuple[dict, dict]:
    state = deadline_state(unit)
    if not state or state.get("profile") != WORKING_DEADLINE_PROFILE:
        die(f"{unit.get('id')}: working_deadline is not active", 1)
    policy, digest = load_working_deadline_policy()
    if (state.get("policyId") != policy.get("id")
            or state.get("policySha256") != digest):
        die(f"{unit.get('id')}: working_deadline policy changed after activation; "
            "pause and start a new observed cycle", 1)
    allowed = set((policy.get("activation") or {}).get("allowedRiskTiers") or [])
    risk = str(unit.get("riskTier") or "")
    if risk not in allowed:
        die(f"{unit.get('id')}: current riskTier '{risk or 'unknown'}' no longer "
            "permits working_deadline; route to strict release", 1)
    return state, policy


def new_deadline_state(unit: dict) -> dict:
    policy, digest = load_working_deadline_policy()
    allowed = set((policy.get("activation") or {}).get("allowedRiskTiers") or [])
    risk = str(unit.get("riskTier") or "")
    if risk not in allowed:
        die(f"{unit.get('id')}: riskTier '{risk or 'unknown'}' cannot enter "
            "working_deadline; route to strict release", 1)
    return {
        "profile": WORKING_DEADLINE_PROFILE,
        "policyId": policy["id"],
        "policySha256": digest,
        "cycle": 1,
        "startedAt": now_iso(),
        "hostObservedElapsedSeconds": 0,
        "softCheckpointAt": "",
        "checkpoint": {},
        "hardPausedAt": "",
        "stopReason": "",
        "pauses": [],
    }


def reset_deadline_cycle(unit: dict) -> None:
    state, _ = assert_deadline_policy_binding(unit)
    state["cycle"] = int(state.get("cycle") or 0) + 1
    state["startedAt"] = now_iso()
    state["hostObservedElapsedSeconds"] = 0
    state["softCheckpointAt"] = ""
    state["checkpoint"] = {}
    state["hardPausedAt"] = ""
    state["stopReason"] = ""
    state.pop("exhaustedBudget", None)


def handoff_state(goal: dict) -> dict | None:
    state = goal.get("handoffState")
    if state is None:
        return None
    if not isinstance(state, dict):
        die("handoffState must be an object", 1)
    return state


def require_result_handoff(goal: dict, unit: dict) -> None:
    goal["handoffState"] = {
        "required": True,
        "unitId": unit["id"],
        "requiredAt": now_iso(),
        "acknowledgedAt": "",
        "acknowledgement": "",
    }


def bounded_policy(goal: dict) -> dict | None:
    """Return and fail-closed validate the optional bounded run envelope."""
    policy = goal.get("runPolicy")
    if policy is None:
        return None
    if not isinstance(policy, dict):
        die("runPolicy must be an object when present (fail-closed)")
    if policy.get("mode") != BOUNDED_MODE:
        die(f"runPolicy.mode must be '{BOUNDED_MODE}'")
    for field in ("maxAttemptsPerUnit", "maxWallClockSecondsPerUnit",
                  "maxTokensPerSession"):
        value = policy.get(field)
        if type(value) is not int or value <= 0:
            die(f"runPolicy.{field} must be a positive integer")
    for field in ("freezeVerification", "requireApproach",
                  "requireIndependentReview"):
        if type(policy.get(field)) is not bool:
            die(f"runPolicy.{field} must be boolean")
    if policy.get("freezeVerification") is not True:
        die("bounded autonomy requires runPolicy.freezeVerification=true")
    if policy.get("requireApproach") is not True:
        die("bounded autonomy requires runPolicy.requireApproach=true")
    if ("enforceObservedTokens" in policy
            and type(policy.get("enforceObservedTokens")) is not bool):
        die("runPolicy.enforceObservedTokens must be boolean when present")
    strategy = policy.get("verificationStrategy")
    if strategy not in (None, "adaptive"):
        die("runPolicy.verificationStrategy must be 'adaptive' when present")
    if "maxCheckpointBytes" in policy:
        size = policy.get("maxCheckpointBytes")
        if type(size) is not int or not 1024 <= size <= 4096:
            die("runPolicy.maxCheckpointBytes must be an integer in 1024..4096")
    return policy


def verification_fingerprint(unit: dict) -> str:
    payload = {
        "criterion": str(unit.get("criterion") or ""),
        "verificationCommand": str(unit.get("verificationCommand") or ""),
    }
    if "riskTier" in unit:
        payload["riskTier"] = str(unit.get("riskTier") or "")
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def policy_snapshot(policy: dict) -> dict:
    keys = POLICY_KEYS + tuple(key for key in OPTIONAL_POLICY_KEYS if key in policy)
    return {key: policy.get(key) for key in keys}


def snapshot_fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def policy_fingerprint(policy: dict) -> str:
    return snapshot_fingerprint(policy_snapshot(policy))


def unit_run_state(unit: dict) -> dict:
    state = unit.setdefault("runState", {})
    if not isinstance(state, dict):
        die(f"{unit.get('id')}: runState must be an object")
    return state


def unit_attempts(unit: dict) -> list[dict]:
    attempts = unit.setdefault("attempts", [])
    if not isinstance(attempts, list):
        die(f"{unit.get('id')}: attempts must be an array")
    if any(not isinstance(a, dict) for a in attempts):
        die(f"{unit.get('id')}: every attempt must be an object")
    return attempts


def budgeted_attempt_count(unit: dict) -> int:
    return len([a for a in unit_attempts(unit)
                if a.get("kind") in ("verification", "recheck")])


def checker_mode(policy: dict, unit: dict) -> str:
    """Return the sealed verification cost for this unit."""
    if policy.get("requireIndependentReview"):
        return "full"
    if policy.get("verificationStrategy") != "adaptive":
        return "machine_only"
    risk = str(unit.get("riskTier") or "")
    if risk not in RISK_TIERS:
        die(f"{unit.get('id')}: adaptive verification requires riskTier "
            f"in {RISK_TIERS}")
    return {"low": "machine_only", "medium": "targeted", "high": "full"}[risk]


def parse_iso_epoch(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def elapsed_seconds(unit: dict) -> float | None:
    state = unit.get("runState") or {}
    started = parse_iso_epoch(str(state.get("startedAt") or ""))
    return None if started is None else max(0.0, time.time() - started)


def set_stop_reason(unit: dict, reason: str) -> None:
    if isinstance(unit.get("runState"), dict):
        unit["runState"]["stopReason"] = reason


def bounded_stop(goal: dict, goal_path: Path, unit: dict,
                 stop_reason: str, detail: str,
                 budget_kind: str = "", observed: int | None = None) -> int:
    """Persist a typed stop without inventing a new open-unit status."""
    projection = state_projection(goal_path, unit, "blocked")
    unit["status"] = "blocked"
    unit["blockedReason"] = f"{stop_reason}: {detail}"
    set_stop_reason(unit, stop_reason)
    if is_working_deadline_unit(unit):
        # The deadline and bounded envelopes are orthogonal. A bounded stop
        # materialises as GOAL.status=blocked, so the deadline sub-state must
        # agree with that outer state even when the bounded reason is budget.
        (deadline_state(unit) or {})["stopReason"] = "blocked"
    if stop_reason == "budget_exhausted":
        fields = {
            "attempts": "maxAttemptsPerUnit",
            "wall_clock": "maxWallClockSecondsPerUnit",
            "tokens": "maxTokensPerSession",
        }
        if budget_kind not in fields:
            die("budget_exhausted stop requires budget kind")
        policy = bounded_policy(goal)
        state = unit_run_state(unit)
        state["exhaustedBudget"] = {
            "kind": budget_kind,
            "limit": policy[fields[budget_kind]],
            "at": now_iso(),
        }
        if observed is not None:
            state["exhaustedBudget"]["observed"] = observed
    if goal.get("currentUnitId") == unit.get("id"):
        goal["currentUnitId"] = ""
    if not commit_goal_transition(goal, goal_path, unit, stop_reason, detail,
                                  projection, state_decision="blocked"):
        return 1
    print(f"STOPPED {unit['id']} [{stop_reason}] — {detail}")
    return BOUNDED_STOP_EXIT


def record_attempt(unit: dict, approach: str, command: str, outcome: str,
                   evidence: str, verification_receipt: dict | None, recheck: bool,
                   tokens_used: int | None = None,
                   checker: str = "machine_only") -> None:
    attempts = unit_attempts(unit)
    attempt = {
        "number": len(attempts) + 1,
        "at": now_iso(),
        "kind": "recheck" if recheck else "verification",
        "approach": approach.strip(),
        "verificationCommand": command,
        "outcome": outcome,
        "evidence": evidence,
        "reviewEvidence": (
            "adjudicated:" + str(
                (verification_receipt or {}).get("receiptSha256") or "")
            if verification_receipt else ""
        ),
        "verificationReceipt": verification_receipt or {},
        "checkerMode": checker,
    }
    if tokens_used is not None:
        attempt["observedTokens"] = tokens_used
    attempts.append(attempt)


def cmd_seal(goal: dict, goal_path: Path) -> int:
    """Freeze the user-approved oracle and run policy before first activation."""
    policy = bounded_policy(goal)
    if policy is None:
        die("--seal requires an opt-in runPolicy", 1)
    non_pending = [u.get("id") for u in goal["units"]
                   if u.get("status") != "pending"]
    if non_pending:
        die(f"--seal is only valid before execution; non-pending units: "
            f"{', '.join(str(x) for x in non_pending)}", 1)

    already_sealed = bool(policy.get("sealedFingerprint"))
    expected_policy = policy_fingerprint(policy)
    if already_sealed:
        approved = policy.get("sealedPolicy")
        if (not isinstance(approved, dict)
                or snapshot_fingerprint(approved) != policy.get("sealedFingerprint")
                or approved != policy_snapshot(policy)):
            die("runPolicy changed after approval; do not reseal an edited policy", 1)

    for unit in goal["units"]:
        checker_mode(policy, unit)
        state = unit_run_state(unit)
        current = verification_fingerprint(unit)
        baseline = str(state.get("verificationFingerprint") or "")
        if baseline and baseline != current:
            die(f"{unit.get('id')}: approved verification contract changed; "
                "create a new user-approved unit instead of resealing", 1)
        state["verificationFingerprint"] = current
        state.setdefault("approvedAt", now_iso())
        state.setdefault("startedAt", "")
        state.setdefault("stopReason", "")
        unit_attempts(unit)

    if already_sealed:
        print("bounded goal is already sealed — nothing to do")
        return 0
    policy["sealedPolicy"] = policy_snapshot(policy)
    policy["sealedFingerprint"] = expected_policy
    policy["sealedAt"] = now_iso()
    save_goal(goal_path, goal)
    for unit in goal["units"]:
        append_event(goal_path, unit["id"], "verification_sealed",
                     unit["runState"]["verificationFingerprint"])
    print(f"SEALED bounded goal: {len(goal['units'])} unit oracle(s) frozen")
    return 0


def load_goal(path: Path) -> dict:
    if not path.is_file():
        die(f"goal ledger not found: {path}")
    try:
        raw = read_ledger_snapshot(path)
        if raw is None:
            die(f"goal ledger not found: {path}")
        goal = json.loads(raw.decode("utf-8"))
    except Exception as e:
        die(f"{path}: not valid JSON ({e})")
    if not isinstance(goal.get("units"), list) or not goal["units"]:
        die(f"{path}: 'units' must be a non-empty list")
    return goal


def save_goal(path: Path, goal: dict) -> None:
    goal["updatedAt"] = now_iso()
    save_goal_bytes(path, goal_document_bytes(goal))


def goal_document_bytes(goal: dict) -> bytes:
    return (json.dumps(goal, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def save_goal_bytes(path: Path, content: bytes) -> None:
    """Atomically replace a Goal document with already-bound bytes."""
    atomic_replace_bytes(path, content)


def unit_log_module():
    """Load the task ledger's atomic STATE writer; do not duplicate it here."""
    spec = importlib.util.spec_from_file_location("itd_goal_unit_log", UNIT_LOG_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("task STATE writer is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state_projection(goal_path: Path, unit: dict, decision: str,
                     *, writer: object | None = None) -> tuple[object, dict, str] | None:
    """Preflight the STATE mirror without changing it or the goal ledger.

    A missing STATE is a supported standalone/legacy goal ledger.  A live
    foreign STATE is never overwritten by a GOAL transition.
    """
    mem = goal_path.parent
    path = mem / "STATE.json"
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        die(f"cannot read STATE mirror: {exc}", 1)
    writer = writer or unit_log_module()
    # The mirror that authorizes a Goal transition is read like a receipt:
    # no-follow, anchored and bounded, so a STATE link swapped in from
    # outside the project cannot steer WIP or projection decisions (Sol-a10).
    try:
        raw, state = stable_json_snapshot(path, "STATE mirror")
    except VerificationReceiptError as exc:
        die(f"cannot read STATE mirror: {exc}", 1)
    cur = state.get("currentUnit") or {}
    active = cur.get("status") in ("in_progress", "verifying", "recovery_required")
    foreign = (cur.get("id") and
               (cur.get("id") != unit.get("id")
                or cur.get("ledger") not in ("", None, goal_path.name)))
    if foreign and (decision != "activated" or active):
        die("WIP=1: STATE has a foreign current unit; refusing to change GOAL", 1)
    if decision == "activated":
        files = state.get("ledgerFiles")
        if files is not None and (not isinstance(files, list)
                                  or not all(isinstance(v, str) for v in files)):
            die("STATE.ledgerFiles is malformed; refusing GOAL activation", 1)
    return writer, state, hashlib.sha256(raw).hexdigest()


def write_state_projection(projection: tuple[object, dict, str] | None, goal_path: Path,
                           unit: dict, decision: str, event_at: str = "",
                           *, lock_held: bool = False) -> None:
    if projection is None:
        return
    writer, state, before_sha256 = projection
    path = goal_path.parent / "STATE.json"
    lock = contextlib.nullcontext() if lock_held else writer.state_write_lock(goal_path.parent)
    with lock:
        # The re-read under the lock uses the same anchored no-follow
        # snapshot as the preflight: a STATE link swapped in after the first
        # read would otherwise pass the hash check and the writer would then
        # operate on the swapped namespace (Sol-a11).
        try:
            current_raw, _current_state = stable_json_snapshot(path, "STATE mirror")
        except VerificationReceiptError as exc:
            raise RuntimeError(f"cannot re-read STATE mirror for projection: {exc}") from exc
        current_sha256 = hashlib.sha256(current_raw).hexdigest()
        if current_sha256 != before_sha256:
            raise RuntimeError("STATE mirror changed after projection; refusing overwrite")
        cur = dict(state.get("currentUnit") or {})
        if decision in ("activated", "regressed"):
            cur.update({"id": unit["id"], "goal": unit.get("criterion") or "",
                        "status": "in_progress", "ledger": goal_path.name,
                        "riskTier": unit.get("riskTier") or "unknown"})
            if not cur.get("startedAt") or decision == "activated":
                cur["startedAt"] = event_at or now_iso()
            cur.pop("completedAt", None)
        else:
            cur.update({"id": unit["id"], "goal": unit.get("criterion") or "",
                        "status": decision, "ledger": goal_path.name,
                        "riskTier": unit.get("riskTier") or "unknown",
                        "completedAt": event_at or now_iso()})
        state["currentUnit"] = cur
        if decision == "activated":
            files = state.get("ledgerFiles")
            if files is None:
                files = []
            if not isinstance(files, list) or not all(isinstance(v, str) for v in files):
                die("STATE.ledgerFiles is malformed; refusing GOAL activation", 1)
            try:
                canonical = goal_path.resolve().relative_to(goal_path.parent.parent.resolve()).as_posix()
            except ValueError:
                canonical = f"{goal_path.parent.name}/{goal_path.name}"
            if canonical not in files:
                files.append(canonical)
            state["ledgerFiles"] = files
        writer.save_state_locked(goal_path.parent, state)


def receipt_binds_command(binding: dict, command: str) -> bool:
    """The adjudicated machine evidence must contain this exact goal oracle."""
    return any(run.get("command") == command
               for run in binding.get("machine", {}).get("runs", [])
               if isinstance(run, dict))


GOAL_TRANSITION_RECOVERY = ".goal-transition-recovery.json"


def transition_recovery_path(goal_path: Path) -> Path:
    return goal_path.parent / GOAL_TRANSITION_RECOVERY


def event_line(event: dict) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


def transition_event(goal_path: Path, unit_id: str, decision: str,
                     evidence: str, transaction: str) -> dict:
    return {
        "id": f"evt-goal-{int(time.time())}-{transaction}",
        "at": now_iso(),
        "actor": "harness",
        "type": "unit",
        "name": unit_id,
        "decision": decision,
        "evidence": evidence[:EVIDENCE_MAX],
        "ledger": goal_path.name,
        # Binds a recovery record to this one append.  It is deliberately not
        # an alternate authority for transitions: the JSONL event remains the
        # canonical history and the record is removed once all three writes
        # have completed.
        "transaction": transaction,
    }


def save_transition_recovery(goal_path: Path, recovery: dict) -> None:
    path = transition_recovery_path(goal_path)
    atomic_replace_bytes(path, (json.dumps(recovery, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def clear_transition_recovery(goal_path: Path) -> None:
    durable_unlink(transition_recovery_path(goal_path))


def load_transition_recovery(goal_path: Path) -> dict | None:
    path = transition_recovery_path(goal_path)
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError(f"Goal transition recovery record is unreadable: {exc}") from exc
    # Recovery instructions drive rollback or STATE projection, so they are
    # read like a receipt: no-follow, anchored and bounded (Sol-a11).
    try:
        _raw, recovery = stable_json_snapshot(path, "Goal transition recovery record")
    except VerificationReceiptError as exc:
        raise RuntimeError(f"Goal transition recovery record is unreadable: {exc}") from exc
    required = {"version", "transaction", "goalBefore", "goalBeforeSha256",
                "goalAfter", "goalAfterSha256", "eventsBeforeSha256",
                "eventsBeforeBytes", "event", "unitId", "decision", "stateDecision"}
    if not isinstance(recovery, dict) or set(recovery) != required:
        raise RuntimeError("Goal transition recovery record is malformed")
    if (type(recovery["version"]) is not int or recovery["version"] != 1
            or type(recovery["eventsBeforeBytes"]) is not int or recovery["eventsBeforeBytes"] < 0
            or not all(isinstance(recovery[key], str) for key in required - {"version", "event", "eventsBeforeBytes"})
            or not isinstance(recovery["event"], dict)):
        raise RuntimeError("Goal transition recovery record has an unsupported version")
    try:
        if uuid.UUID(hex=recovery["transaction"]).hex != recovery["transaction"]:
            raise ValueError("transaction")
    except ValueError as exc:
        raise RuntimeError("Goal transition recovery transaction is malformed") from exc
    event = recovery["event"]
    expected_event = {"id", "at", "actor", "type", "name", "decision",
                      "evidence", "ledger", "transaction"}
    if (set(event) != expected_event or event.get("transaction") != recovery["transaction"]
            or event.get("name") != recovery["unitId"]
            or event.get("ledger") != goal_path.name
            or event.get("decision") != recovery["decision"]
            or event.get("actor") != "harness" or event.get("type") != "unit"
            or not all(isinstance(event[key], str) for key in expected_event)):
        raise RuntimeError("Goal transition recovery event is malformed or unbound")
    if recovery["stateDecision"] not in ("activated", "regressed", "verified", "blocked"):
        raise RuntimeError("Goal transition recovery STATE decision is invalid")
    decision = recovery["decision"]
    if decision in ("activated", "regressed", "verified", "blocked"):
        if recovery["stateDecision"] != decision:
            raise RuntimeError("Goal transition recovery event/state decisions are inconsistent")
    elif decision == "budget_exhausted":
        if recovery["stateDecision"] != "blocked":
            raise RuntimeError("Goal transition recovery budget stop must project blocked")
    elif decision == "verification_unverified":
        if recovery["stateDecision"] != "regressed":
            raise RuntimeError("Goal transition recovery checker failure must project regressed")
    else:
        raise RuntimeError("Goal transition recovery decision is unsupported")
    return recovery


def event_with_transaction(goal_path: Path, transaction: str) -> dict | None:
    # Recovery authority: anchored no-follow, fail-closed on malformed records.
    for event in ledger_events(goal_path.parent / "events.jsonl"):
        if event.get("transaction") == transaction:
            return event
    return None


def recovery_goal(recovery: dict) -> tuple[bytes, bytes, dict, dict]:
    try:
        before = base64.b64decode(recovery["goalBefore"], validate=True)
        after = base64.b64decode(recovery["goalAfter"], validate=True)
        goal = json.loads(after.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("Goal transition recovery bytes are malformed") from exc
    if (hashlib.sha256(before).hexdigest() != recovery["goalBeforeSha256"]
            or hashlib.sha256(after).hexdigest() != recovery["goalAfterSha256"]):
        raise RuntimeError("Goal transition recovery record hash mismatch")
    unit = next((item for item in goal.get("units", [])
                 if item.get("id") == recovery["unitId"]), None)
    expected = "in_progress" if recovery["stateDecision"] in ("activated", "regressed") else recovery["stateDecision"]
    if not isinstance(unit, dict) or unit.get("status") != expected:
        raise RuntimeError("Goal transition recovery unit/status is not bound to the target state")
    return before, after, goal, unit


def recover_goal_transition(goal_path: Path, receipt_path: str = "",
                            *, verified_context: bool = False,
                            expected_unit_id: str | None = None,
                            writer: object | None = None,
                            lock_held: bool = False) -> str | None:
    """Finish or roll back one interrupted Goal/event/STATE transaction.

    A verified projection needs the existing current-candidate receipt unless
    the same invocation just produced the verified transition.  The recovery
    record is crash metadata, never independent verification authority.
    """
    recovery = load_transition_recovery(goal_path)
    if recovery is None:
        return None
    before, after, goal, unit = recovery_goal(recovery)
    if expected_unit_id is not None and unit["id"] != expected_unit_id:
        raise RuntimeError("Goal transition recovery belongs to a different unit")
    event = recovery["event"]
    landed = event_with_transaction(goal_path, str(recovery["transaction"]))
    current = read_ledger_snapshot(goal_path) or b""
    if landed is None:
        events = goal_path.parent / "events.jsonl"
        current_events = read_ledger_snapshot(events) or b""
        if (len(current_events) != recovery["eventsBeforeBytes"]
                or hashlib.sha256(current_events).hexdigest() != recovery["eventsBeforeSha256"]):
            raise RuntimeError("Goal event log changed after interrupted append; preserving append-only evidence")
        # Preflight before rewriting Goal, even for rollback.
        state_projection(goal_path, unit, str(recovery["stateDecision"]), writer=writer)
        if current == after:
            save_goal_bytes(goal_path, before)
        elif current != before:
            raise RuntimeError("Goal changed during an interrupted transition; refusing rollback")
        clear_transition_recovery(goal_path)
        return "rolled_back"
    if landed != event:
        raise RuntimeError("Goal event transaction does not match the recovery record")
    # A parseable transaction is not proof that the append completed: a durable
    # append can fail after writing the whole object without its newline, and a
    # projection built on that would clear recovery while refuse_partial_tail
    # then blocks every later append (Sol-a9). Prove the log is exactly the
    # recorded pre-append bytes plus the one newline-terminated event line.
    events = goal_path.parent / "events.jsonl"
    current_events = read_ledger_snapshot(events) or b""
    before_bytes = int(recovery["eventsBeforeBytes"])
    line = event_line(event)
    if (hashlib.sha256(current_events[:before_bytes]).hexdigest() != recovery["eventsBeforeSha256"]
            or current_events[before_bytes:] != line):
        if current_events[before_bytes:] == line[:-1]:
            raise RuntimeError(
                "Goal event append left a partial final record without its newline; "
                "recovery evidence preserved, repair the event log before any projection")
        raise RuntimeError("Goal event log does not end at the recorded append boundary; preserving recovery evidence")
    if current_canonical_event(goal_path, unit["id"], recovery["decision"]) != event:
        raise RuntimeError("Goal event is no longer the latest canonical transition")
    if recovery["stateDecision"] == "verified" and not verified_context:
        if not receipt_path.strip():
            raise RuntimeError("verified transition recovery requires a fresh --verification-receipt")
        try:
            checked = validate_verification_receipt(goal_path, receipt_path,
                                                    str(unit.get("riskTier") or "unknown"),
                                                    str(unit["id"]))
        except VerificationReceiptError as exc:
            raise RuntimeError(f"verified transition recovery receipt is unverified: {exc}") from exc
        if not receipt_binds_command(checked, str(unit.get("verificationCommand") or "")):
            raise RuntimeError("verified transition recovery receipt lacks Goal verificationCommand")
    projection = state_projection(goal_path, unit, str(recovery["stateDecision"]), writer=writer)
    if current == before:
        save_goal_bytes(goal_path, after)
    elif current != after:
        raise RuntimeError("Goal changed after a canonical event; refusing projection repair")
    write_state_projection(projection, goal_path, unit,
                           str(recovery["stateDecision"]), str(event.get("at") or ""),
                           lock_held=lock_held)
    clear_transition_recovery(goal_path)
    return "projected"


def commit_goal_transition(goal: dict, goal_path: Path, unit: dict, decision: str,
                           evidence: str, projection: tuple[object, dict, str] | None,
                           *, state_decision: str = "", verified_context: bool = False) -> bool:
    """Commit Goal, canonical event, and STATE with bounded crash recovery."""
    writer = unit_log_module()
    with writer.state_write_lock(goal_path.parent):
        # The initial preflight can be separated from this commit by a test or
        # checker. Re-read under the same lock used by ordinary task lifecycle
        # writes before creating any durable Goal/event recovery record.
        fresh_projection = state_projection(goal_path, unit, state_decision or decision, writer=writer)
        requested_state = None if projection is None else projection[2]
        current_state = None if fresh_projection is None else fresh_projection[2]
        if requested_state != current_state:
            print("ERROR: STATE mirror changed after transition preflight; refusing stale Goal commit")
            return False
        projection = fresh_projection
        if transition_recovery_path(goal_path).exists():
            print("ERROR: unresolved Goal transition recovery; use --reconcile with current evidence")
            return False
        before = read_ledger_snapshot(goal_path) or b""
        events_path = goal_path.parent / "events.jsonl"
        events_before = read_ledger_snapshot(events_path) or b""
        goal["updatedAt"] = now_iso()
        after = goal_document_bytes(goal)
        transaction = uuid.uuid4().hex
        event = transition_event(goal_path, unit["id"], decision, evidence, transaction)
        recovery = {
            "version": 1,
            "transaction": transaction,
            "goalBefore": base64.b64encode(before).decode("ascii"),
            "goalBeforeSha256": hashlib.sha256(before).hexdigest(),
            "goalAfter": base64.b64encode(after).decode("ascii"),
            "goalAfterSha256": hashlib.sha256(after).hexdigest(),
            "eventsBeforeSha256": hashlib.sha256(events_before).hexdigest(),
            "eventsBeforeBytes": len(events_before),
            "event": event,
            "unitId": unit["id"],
            "decision": decision,
            "stateDecision": state_decision or decision,
        }
        save_transition_recovery(goal_path, recovery)
        try:
            save_goal_bytes(goal_path, after)
        except Exception as exc:
            print(f"ERROR: Goal transition was not written: {exc}")
            return False
        try:
            append_event(goal_path, unit["id"], decision, evidence, event=event)
        except Exception as exc:
            try:
                recovered = recover_goal_transition(goal_path, verified_context=verified_context,
                                                    writer=writer, lock_held=True)
            except Exception as recovery_exc:
                print(f"ERROR: canonical {decision} event append interrupted: {exc}; "
                      f"recovery pending: {recovery_exc}")
                return False
            if recovered == "projected" and event_with_transaction(goal_path, transaction) == event:
                print(f"recovered canonical {decision} event after append interruption")
                return True
            print(f"ERROR: canonical {decision} event append interrupted; Goal rolled back: {exc}")
            return False
        try:
            write_state_projection(projection, goal_path, unit, state_decision or decision,
                                   event["at"], lock_held=True)
        except Exception as exc:
            print(f"ERROR: STATE projection interrupted after canonical {decision} event: {exc}")
            print("Use --reconcile with current verification evidence; recovery will not append another event.")
            return False
        clear_transition_recovery(goal_path)
        return True


def append_event(goal_path: Path, unit_id: str, decision: str, evidence: str,
                 *, event: dict | None = None) -> dict:
    """Append the canonical event. Failure is fatal; callers must repair, not retry."""
    events = goal_path.parent / "events.jsonl"
    evt = event or {
        "id": f"evt-goal-{int(time.time())}",
        "at": now_iso(),
        "actor": "harness",
        "type": "unit",
        "name": unit_id,
        "decision": decision,
        "evidence": evidence[:EVIDENCE_MAX],
        # Имя юнита не уникально между леджерами (live: `G-001` — пять разных
        # юнитов), поэтому событие несёт СВОЙ леджер (S10-LEDGER).
        "ledger": goal_path.name,
    }
    refuse_partial_tail(events)
    durable_append_bytes(events, event_line(evt))
    return evt


def refuse_partial_tail(events: Path) -> None:
    """Refuse to append after an interrupted record (same rule as the task ledger).

    A failed append can leave a JSON fragment without its newline. Appending
    the next event would concatenate both records, the durable append would
    still succeed and the transition could advance STATE while neither record
    parses (Sol-a8). The tail is inspected through the shared anchored
    no-follow ledger reader, so a link, junction or FIFO swapped in at this
    path can neither redirect nor stall the preflight (Sol-a11/a12).
    """
    try:
        payload = read_ledger_snapshot(events)
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(f"events.jsonl tail cannot be safely read: {exc}") from exc
    if payload and not payload.endswith(b"\n"):
        raise RuntimeError("events.jsonl has a partial final record; preserved without append")


def observe_working_deadline(
        goal: dict, goal_path: Path, unit: dict, elapsed: int | None,
        checkpoint_ready: str = "", checkpoint_blocker: str = "",
        checkpoint_remainder: str = "", checkpoint_estimate: str = "") -> int:
    """Persist a host observation and enforce the 30/45-minute boundaries."""
    if elapsed is None:
        die(f"{unit.get('id')}: working_deadline requires --elapsed-seconds "
            "from the host clock", 1)
    if elapsed < 0:
        die("--elapsed-seconds must be non-negative", 1)
    if unit.get("status") not in ("in_progress", "recovery_required"):
        die(f"cannot observe deadline for {unit.get('id')} from status "
            f"'{unit.get('status')}'", 1)

    state, policy = assert_deadline_policy_binding(unit)
    previous = state.get("hostObservedElapsedSeconds")
    if type(previous) is not int or previous < 0:
        die(f"{unit.get('id')}: invalid hostObservedElapsedSeconds", 1)
    if elapsed < previous:
        die(f"{unit.get('id')}: non-monotonic host observation "
            f"{elapsed} < {previous}", 1)

    timebox = policy["timebox"]
    soft = timebox["softCheckpointSeconds"]
    hard = timebox["hardPauseSeconds"]
    values = {
        "ready": checkpoint_ready.strip(),
        "blocker": checkpoint_blocker.strip(),
        "remainder": checkpoint_remainder.strip(),
        "estimate": checkpoint_estimate.strip(),
    }

    # A hard pause must still allow the cheap checkpoint promised by policy.
    # Capturing it never resumes work and always preserves the typed stop.
    if unit.get("status") == "recovery_required":
        if not state.get("softCheckpointAt"):
            missing = [field for field in CHECKPOINT_FIELDS if not values[field]]
            if missing:
                die(f"{unit.get('id')}: recovery checkpoint requires ready, "
                    f"blocker, remainder, estimate; missing {', '.join(missing)}", 1)
            state["softCheckpointAt"] = now_iso()
            state["checkpoint"] = values
            append_event(goal_path, unit["id"], "working_deadline_checkpoint",
                         "; ".join(f"{key}={values[key]}" for key in CHECKPOINT_FIELDS))
        state["hostObservedElapsedSeconds"] = elapsed
        save_goal(goal_path, goal)
        checkpoint = state.get("checkpoint") or {}
        print(f"CHECKPOINT {unit['id']} — ready={checkpoint.get('ready')}; "
              f"blocker={checkpoint.get('blocker')}; "
              f"remainder={checkpoint.get('remainder')}; "
              f"estimate={checkpoint.get('estimate')}")
        print(f"STILL STOPPED {unit['id']} [budget_exhausted/recovery_required]")
        return BOUNDED_STOP_EXIT

    # Safety wins over reporting completeness: a host that missed the soft
    # boundary still gets a hard pause instead of another expensive attempt.
    if elapsed >= hard:
        if not state.get("softCheckpointAt") and all(values.values()):
            state["softCheckpointAt"] = now_iso()
            state["checkpoint"] = values
        state["hostObservedElapsedSeconds"] = elapsed
        state["hardPausedAt"] = now_iso()
        state["stopReason"] = "budget_exhausted"
        exhausted = {
            "kind": "wall_clock",
            "limit": hard,
            "observed": elapsed,
            "at": now_iso(),
        }
        state["exhaustedBudget"] = exhausted
        pauses = state.setdefault("pauses", [])
        if not isinstance(pauses, list):
            die(f"{unit.get('id')}: deadlineState.pauses must be an array", 1)
        pauses.append({"cycle": state.get("cycle"), **exhausted})
        unit["status"] = "recovery_required"
        unit["recoveryReason"] = (
            f"budget_exhausted: host-observed working deadline reached "
            f"({elapsed}/{hard}s)"
        )
        # Keep currentUnitId: recovery_required is active backpressure and must
        # prevent the next unit from opening under WIP=1.
        goal["currentUnitId"] = unit["id"]
        save_goal(goal_path, goal)
        append_event(goal_path, unit["id"], "budget_exhausted",
                     unit["recoveryReason"])
        print(f"STOPPED {unit['id']} [budget_exhausted/recovery_required] — "
              f"host elapsed {elapsed}s reached {hard}s; partial work is not verified")
        if not state.get("softCheckpointAt"):
            print("CHECKPOINT REQUIRED — provide ready, blocker, remainder, estimate "
                  "through --deadline-check before recovery resume")
        return BOUNDED_STOP_EXIT

    if elapsed >= soft and not state.get("softCheckpointAt"):
        missing = [field for field in CHECKPOINT_FIELDS if not values[field]]
        if missing:
            die(f"{unit.get('id')}: 30-minute checkpoint requires ready, blocker, "
                f"remainder, estimate; missing {', '.join(missing)}", 1)
        state["softCheckpointAt"] = now_iso()
        state["checkpoint"] = values
        append_event(goal_path, unit["id"], "working_deadline_checkpoint",
                     "; ".join(f"{key}={values[key]}" for key in CHECKPOINT_FIELDS))
        print(f"CHECKPOINT {unit['id']} — ready={values['ready']}; "
              f"blocker={values['blocker']}; remainder={values['remainder']}; "
              f"estimate={values['estimate']}")
    else:
        print(f"DEADLINE OK {unit['id']} — host elapsed {elapsed}s/{hard}s")

    state["hostObservedElapsedSeconds"] = elapsed
    save_goal(goal_path, goal)
    return 0


def cmd_ack_handoff(goal: dict, goal_path: Path, unit: dict, reason: str) -> int:
    state = handoff_state(goal)
    if not state or state.get("required") is not True:
        die("no verified-unit handoff is awaiting acknowledgement", 1)
    if state.get("unitId") != unit.get("id"):
        die(f"handoff belongs to {state.get('unitId')}, not {unit.get('id')}", 1)
    if unit.get("status") != "verified":
        die(f"handoff unit {unit.get('id')} is not verified", 1)
    if not reason.strip():
        die("--ack-handoff requires --reason with host/user-turn provenance", 1)
    state["required"] = False
    state["acknowledgedAt"] = now_iso()
    state["acknowledgement"] = reason.strip()
    save_goal(goal_path, goal)
    append_event(goal_path, unit["id"], "handoff_acknowledged", reason.strip())
    print(f"HANDOFF ACKNOWLEDGED {unit['id']} — {reason.strip()}")
    return 0


def has_activation_event(goal_path: Path, unit_id: str) -> bool:
    """True если в events.jsonl уже есть activation-событие юнита."""
    for evt in ledger_events(goal_path.parent / "events.jsonl"):
        if (evt.get("type") == "unit" and evt.get("name") == unit_id
                and str(evt.get("decision")).lower() == "activated"):
            return True
    return False


def current_canonical_event(goal_path: Path, unit_id: str, decision: str) -> dict | None:
    # Transition authority: anchored no-follow read that refuses a malformed
    # or partial record instead of skipping it (Sol-a12).
    cycle: list[dict] = []
    for evt in ledger_events(goal_path.parent / "events.jsonl"):
        if not (evt.get("type") == "unit" and evt.get("actor") == "harness"
                and evt.get("name") == unit_id and evt.get("ledger") == goal_path.name):
            continue
        if evt.get("decision") == "activated":
            cycle = [evt]
        elif cycle:
            cycle.append(evt)
    transitions = {"activated", "verified", "regressed", "blocked", "skipped",
                   "budget_exhausted", "recovery_required", "goal_complete",
                   "needs_reclassification", "verification_unverified"}
    for evt in reversed(cycle):
        if evt.get("decision") in transitions:
            return evt if evt.get("decision") == decision else None
    return None


def cmd_reconcile(goal: dict, goal_path: Path, unit: dict, receipt_path: str) -> int:
    """Recover the selected interrupted transition or repair its STATE mirror.

    Reconciliation never creates canonical events or accepts prose as evidence.
    """
    if transition_recovery_path(goal_path).exists():
        try:
            outcome = recover_goal_transition(goal_path, receipt_path,
                                              expected_unit_id=str(unit.get("id") or ""))
        except Exception as exc:
            die(f"reconcile cannot recover interrupted transition: {exc}", 1)
        if outcome == "projected":
            print(f"reconciled STATE from current canonical Goal event for {unit['id']}")
            return 0
        die("interrupted transition rolled back because no canonical event landed", 1)
    event = current_canonical_event(goal_path, unit.get("id", ""), "verified")
    if unit.get("status") != "verified" or event is None:
        die("reconcile requires a verified Goal unit and its canonical verified event", 1)
    if not receipt_path.strip():
        die("reconcile requires a fresh --verification-receipt for the current candidate", 1)
    try:
        checked = validate_verification_receipt(
            goal_path, receipt_path, str(unit.get("riskTier") or "unknown"),
            str(unit["id"]))
        if not receipt_binds_command(checked, str(unit.get("verificationCommand") or "")):
            die("reconcile receipt lacks Goal verificationCommand", 1)
    except VerificationReceiptError as exc:
        die(f"reconcile receipt is unverified: {exc}", 1)
    writer = unit_log_module()
    with writer.state_write_lock(goal_path.parent):
        event = current_canonical_event(goal_path, unit.get("id", ""), "verified")
        if event is None:
            die("reconcile requires the current canonical verified Goal event", 1)
        projection = state_projection(goal_path, unit, "verified", writer=writer)
        if projection is None:
            print("NOOP reconcile: STATE.json is absent (standalone legacy Goal)")
            return 0
        _, state, _ = projection
        cur = state.get("currentUnit") or {}
        if (cur.get("id") == unit["id"] and cur.get("ledger") == goal_path.name
                and cur.get("status") == "verified"):
            print("NOOP reconcile: STATE already matches canonical verified Goal event")
            return 0
        try:
            write_state_projection(projection, goal_path, unit, "verified",
                                   str(event.get("at") or ""), lock_held=True)
        except Exception as exc:
            die(f"reconcile could not atomically repair STATE: {exc}", 1)
    print(f"reconciled STATE from canonical verified Goal event for {unit['id']}")
    return 0


def find_unit(goal: dict, unit_id: str | None) -> dict:
    units = goal["units"]
    if unit_id:
        for u in units:
            if u.get("id") == unit_id:
                return u
        die(f"unit '{unit_id}' not found in ledger")
    # default: currentUnitId, else first active unit, else first pending
    cur = goal.get("currentUnitId") or ""
    if cur:
        for u in units:
            if u.get("id") == cur:
                return u
    for status in ("in_progress", "recovery_required", "pending"):
        for u in units:
            if u.get("status") == status:
                return u
    die("no unit to act on (no in_progress or pending units)")
    raise AssertionError  # unreachable


def open_units_summary(goal: dict) -> str:
    """One line about what still keeps the goal open — blocked-aware.

    blocked units COUNT as open (they are exactly why the goal cannot be
    closed); saying "no open units" while a unit awaits unblock would invert
    the ledger's meaning.
    """
    pending_handoff = handoff_state(goal)
    if pending_handoff and pending_handoff.get("required") is True:
        return (f"result handoff required for {pending_handoff.get('unitId')} — "
                "acknowledge it before next activation or goal close")
    actionable = [u for u in goal["units"]
                  if u.get("status") in ("in_progress", "recovery_required", "pending")]
    blocked = [u for u in goal["units"] if u.get("status") == "blocked"]
    if actionable:
        return f"next unit: {actionable[0].get('id')}"
    if blocked:
        reasons = "; ".join(
            f"{u.get('id')}: {u.get('blockedReason') or '(no reason)'}"
            for u in blocked)
        return (f"{len(blocked)} unit(s) still BLOCKED ({reasons}) — unblock "
                "via --activate before closing the goal")
    return "no open units left — goal can be closed (status: done)"


def decisive_line(output: str) -> str:
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    return lines[-1] if lines else "(no output)"


def cmd_activate(goal: dict, goal_path: Path, unit: dict,
                 resume_reason: str = "", work_profile: str = "") -> int:
    projection = state_projection(goal_path, unit, "activated")
    pending_handoff = handoff_state(goal)
    if pending_handoff and pending_handoff.get("required") is True:
        die(f"verified unit {pending_handoff.get('unitId')} requires result handoff "
            "before another activation; use --ack-handoff with host/user-turn provenance", 1)
    if unit["status"] == "in_progress":
        if work_profile and not is_working_deadline_unit(unit):
            die(f"{unit['id']}: cannot opt into working_deadline after legacy "
                "activation; finish/reclassify the unit first", 1)
        writer = unit_log_module()
        with writer.state_write_lock(goal_path.parent):
            event = current_canonical_event(goal_path, unit["id"], "activated")
            projection = state_projection(goal_path, unit, "activated", writer=writer)
            if projection is not None and event is not None:
                _, state, _ = projection
                cur = state.get("currentUnit") or {}
                if not (cur.get("id") == unit["id"] and cur.get("ledger") == goal_path.name
                        and cur.get("status") == "in_progress"):
                    try:
                        write_state_projection(projection, goal_path, unit, "activated",
                                               str(event.get("at") or ""), lock_held=True)
                    except Exception as exc:
                        die(f"could not repair STATE from canonical activation event: {exc}", 1)
                    print(f"repaired STATE from canonical activation event for {unit['id']}")
                    return 0
        print(f"{unit['id']} is already in_progress — nothing to do")
        return 0
    if unit["status"] not in ("pending", "blocked", "recovery_required"):
        die(f"cannot activate {unit['id']} from status '{unit['status']}'", 1)
    busy = [u["id"] for u in goal["units"]
            if u.get("status") in ("in_progress", "recovery_required") and u is not unit]
    if busy:
        die(f"WIP=1: unit {busy[0]} is still active — verify, recover, block or skip "
            "it before activating the next one", 1)
    was_blocked = unit["status"] == "blocked"
    was_recovery = unit["status"] == "recovery_required"

    if work_profile and work_profile != WORKING_DEADLINE_PROFILE:
        die(f"unknown work profile '{work_profile}'", 1)
    if was_recovery:
        if not is_working_deadline_unit(unit):
            die(f"{unit['id']}: recovery_required unit lacks deadline state", 1)
        if not resume_reason.strip():
            die(f"{unit['id']}: recovery_required resume needs --reason", 1)
        state = deadline_state(unit) or {}
        checkpoint = state.get("checkpoint") or {}
        if (not state.get("softCheckpointAt")
                or any(not str(checkpoint.get(field) or "").strip()
                       for field in CHECKPOINT_FIELDS)):
            die(f"{unit['id']}: capture the complete recovery checkpoint before resume", 1)
        if work_profile and work_profile != (deadline_state(unit) or {}).get("profile"):
            die(f"{unit['id']}: cannot change work profile during recovery", 1)
        reset_deadline_cycle(unit)
    elif work_profile:
        if deadline_state(unit) is not None:
            die(f"{unit['id']}: deadlineState already exists before activation", 1)
        unit["deadlineState"] = new_deadline_state(unit)
    elif unit.get("status") == "pending" and deadline_state(unit) is not None:
        die(f"{unit['id']}: pending deadlineState cannot replace explicit "
            "--work-profile opt-in", 1)
    elif was_blocked and is_working_deadline_unit(unit):
        if not resume_reason.strip():
            die(f"{unit['id']}: blocked working_deadline resume needs --reason", 1)
        reset_deadline_cycle(unit)

    policy = bounded_policy(goal)
    bounded_resumed = False
    if policy is not None:
        state = unit_run_state(unit)
        unit_attempts(unit)
        previous_stop = str(state.get("stopReason") or "")
        approved_policy = policy.get("sealedPolicy")
        if (not isinstance(approved_policy, dict)
                or snapshot_fingerprint(approved_policy)
                != policy.get("sealedFingerprint")):
            die("runPolicy approval snapshot/seal is missing or inconsistent", 1)
        if previous_stop == "budget_exhausted":
            if not resume_reason.strip():
                die(f"{unit['id']} stopped on budget_exhausted — increasing the "
                    "approved budget and --activate requires --reason", 1)
            exhausted = state.get("exhaustedBudget")
            fields = {
                "attempts": "maxAttemptsPerUnit",
                "wall_clock": "maxWallClockSecondsPerUnit",
                "tokens": "maxTokensPerSession",
            }
            if not isinstance(exhausted, dict) or exhausted.get("kind") not in fields:
                die(f"{unit['id']}: missing exhaustedBudget evidence", 1)
            field = fields[exhausted["kind"]]
            previous_limit = exhausted.get("limit")
            if (type(previous_limit) is not int
                    or policy[field] <= previous_limit):
                die(f"{unit['id']}: increase runPolicy.{field} above "
                    f"{previous_limit} before budget resume", 1)
            current_policy = policy_snapshot(policy)
            changed = [key for key in current_policy
                       if current_policy.get(key) != approved_policy.get(key)]
            if changed != [field] or approved_policy.get(field) != previous_limit:
                die(f"{unit['id']}: budget resume may change only {field}; "
                    f"observed changes: {changed or ['none']}", 1)
            if exhausted["kind"] == "attempts":
                used = budgeted_attempt_count(unit)
                if used >= policy["maxAttemptsPerUnit"]:
                    die(f"{unit['id']}: {used} attempts already used; increase "
                        "runPolicy.maxAttemptsPerUnit further", 1)
            if exhausted["kind"] == "wall_clock":
                elapsed = elapsed_seconds(unit)
                if (elapsed is None
                        or elapsed >= policy["maxWallClockSecondsPerUnit"]):
                    die(f"{unit['id']}: wall-clock budget is still exhausted; "
                        "increase runPolicy.maxWallClockSecondsPerUnit further", 1)
            policy["sealedPolicy"] = current_policy
            policy["sealedFingerprint"] = snapshot_fingerprint(current_policy)
            policy["reapprovedAt"] = now_iso()
            bounded_resumed = True
        elif (approved_policy != policy_snapshot(policy)
              or policy.get("sealedFingerprint") != policy_fingerprint(policy)):
            die("runPolicy is missing its approval seal or changed after approval; "
                "run --seal before execution", 1)
        current_fp = verification_fingerprint(unit)
        baseline = str(state.get("verificationFingerprint") or "")
        if not baseline:
            die(f"{unit['id']}: missing approved verification fingerprint; "
                "run --seal after user approval", 1)
        if baseline != current_fp:
            return bounded_stop(
                goal, goal_path, unit, "blocked",
                "criterion or verificationCommand changed after approval")
        if not str(state.get("startedAt") or ""):
            state["startedAt"] = now_iso()
        state["stopReason"] = ""
    unit["status"] = "in_progress"
    if was_blocked:
        unit["blockedReason"] = ""
    if was_recovery:
        unit["recoveryReason"] = ""
    goal["currentUnitId"] = unit["id"]
    if not commit_goal_transition(goal, goal_path, unit, "activated",
                                  unit.get("criterion") or "", projection):
        return 1
    if bounded_resumed:
        append_event(goal_path, unit["id"], "budget_resumed",
                     resume_reason.strip())
    if was_recovery:
        append_event(goal_path, unit["id"], "working_deadline_resumed",
                     resume_reason.strip())
    print(f"activated {unit['id']}: {unit.get('criterion')}")
    return 0


def cmd_block(goal: dict, goal_path: Path, unit: dict, reason: str) -> int:
    if not reason.strip():
        die("--block requires a non-empty --reason (fail-closed)", 1)
    if unit["status"] not in ("in_progress", "recovery_required", "pending"):
        die(f"cannot block {unit['id']} from status '{unit['status']}'", 1)
    projection = state_projection(goal_path, unit, "blocked")
    unit["status"] = "blocked"
    unit["blockedReason"] = reason.strip()
    if bounded_policy(goal) is not None:
        set_stop_reason(unit, "blocked")
    if is_working_deadline_unit(unit):
        (deadline_state(unit) or {})["stopReason"] = "blocked"
    if goal.get("currentUnitId") == unit["id"]:
        goal["currentUnitId"] = ""
    if not commit_goal_transition(goal, goal_path, unit, "blocked", reason.strip(), projection):
        return 1
    print(f"blocked {unit['id']}: {reason.strip()}")
    return 0


def cmd_budget_exhausted(goal: dict, goal_path: Path, unit: dict,
                         reason: str, budget_kind: str,
                         budget_observed: int | None) -> int:
    policy = bounded_policy(goal)
    if policy is None:
        die("--budget-exhausted requires an opt-in runPolicy", 1)
    if not reason.strip():
        die("--budget-exhausted requires a non-empty --reason", 1)
    if budget_kind not in ("attempts", "wall_clock", "tokens"):
        die("--budget-exhausted requires --budget-kind "
            "attempts|wall_clock|tokens", 1)
    if unit.get("status") != "in_progress":
        die(f"cannot stop {unit['id']} on budget from status "
            f"'{unit.get('status')}'", 1)
    fields = {
        "attempts": "maxAttemptsPerUnit",
        "wall_clock": "maxWallClockSecondsPerUnit",
        "tokens": "maxTokensPerSession",
    }
    if budget_kind == "attempts":
        observed = budgeted_attempt_count(unit)
    elif budget_kind == "wall_clock":
        elapsed = elapsed_seconds(unit)
        if elapsed is None:
            die(f"{unit['id']}: invalid runState.startedAt", 1)
        observed = int(elapsed)
    else:
        if budget_observed is None:
            die("token budget stop requires --budget-observed from the host meter", 1)
        observed = budget_observed
    if observed < 0:
        die("--budget-observed must be non-negative", 1)
    limit = policy[fields[budget_kind]]
    if observed < limit:
        die(f"{unit['id']}: refusing unproved {budget_kind} exhaustion; "
            f"observed {observed} < sealed limit {limit}", 1)
    return bounded_stop(goal, goal_path, unit, "budget_exhausted",
                        reason.strip(), budget_kind, observed)


def cmd_verify(goal: dict, goal_path: Path, unit: dict,
               recheck: bool, timeout: int, approach: str,
               review_evidence: str, verification_receipt_path: str,
               tokens_used: int | None,
               elapsed_seconds_observed: int | None,
               checkpoint_ready: str, checkpoint_blocker: str,
               checkpoint_remainder: str, checkpoint_estimate: str) -> int:
    if recheck:
        if unit["status"] != "verified":
            die(f"--recheck applies to verified units; {unit['id']} is "
                f"'{unit['status']}'", 1)
        if is_working_deadline_unit(unit):
            pending_handoff = handoff_state(goal)
            if pending_handoff and pending_handoff.get("required") is True:
                die(f"{unit['id']}: hand off the verified result before another "
                    "expensive recheck", 1)
            # Rechecks do not consume a new observed work window, but they
            # still must fail before the command when their policy binding is stale.
            assert_deadline_policy_binding(unit)
    elif unit["status"] == "pending":
        die(f"{unit['id']} is pending — activate it first "
            f"(--activate {unit['id']}); verify runs only from in_progress "
            "(gate on passing)", 1)
    elif unit["status"] == "recovery_required":
        die(f"cannot verify {unit['id']} while recovery_required; resume it "
            "through --activate --reason first", 1)
    elif unit["status"] != "in_progress":
        die(f"cannot verify {unit['id']} from status '{unit['status']}'", 1)

    command = (unit.get("verificationCommand") or "").strip()
    if not command:
        die(f"{unit['id']} has an empty verificationCommand (fail-closed)", 1)
    projection = state_projection(goal_path, unit, "regressed" if recheck else "verified")

    if is_working_deadline_unit(unit) and not recheck:
        deadline_rc = observe_working_deadline(
            goal, goal_path, unit, elapsed_seconds_observed,
            checkpoint_ready, checkpoint_blocker,
            checkpoint_remainder, checkpoint_estimate,
        )
        if deadline_rc != 0:
            return deadline_rc

    policy = bounded_policy(goal)
    verification_receipt: dict | None = None
    required_checker_mode = "machine_only"
    explicit_risk = str(unit.get("riskTier") or "").lower()
    if explicit_risk == "medium":
        required_checker_mode = "targeted"
    elif explicit_risk == "high":
        required_checker_mode = "full"
    if policy is not None:
        approved_policy = policy.get("sealedPolicy")
        if (not isinstance(approved_policy, dict)
                or approved_policy != policy_snapshot(policy)
                or policy.get("sealedFingerprint")
                != snapshot_fingerprint(approved_policy)):
            return bounded_stop(goal, goal_path, unit, "blocked",
                                "runPolicy changed after approval")
        state = unit.get("runState")
        if (not isinstance(state, dict)
                or not str(state.get("startedAt") or "")
                or not str(state.get("verificationFingerprint") or "")):
            return bounded_stop(
                goal, goal_path, unit, "blocked",
                "bounded unit lacks activation baseline; activate through the harness")
        if state["verificationFingerprint"] != verification_fingerprint(unit):
            return bounded_stop(
                goal, goal_path, unit, "blocked",
                "criterion or verificationCommand changed after approval")
        if tokens_used is not None and tokens_used < 0:
            die("--tokens-used must be non-negative", 1)
        if policy.get("enforceObservedTokens") and tokens_used is None:
            die(f"{unit['id']}: runPolicy.enforceObservedTokens requires "
                "--tokens-used from the host meter", 1)
        if tokens_used is not None and tokens_used >= policy["maxTokensPerSession"]:
            return bounded_stop(
                goal, goal_path, unit, "budget_exhausted",
                f"token limit reached ({tokens_used}/"
                f"{policy['maxTokensPerSession']})", "tokens", tokens_used)
        if policy["requireApproach"] and not approach.strip():
            die(f"{unit['id']}: bounded verification requires --approach", 1)
        required_checker_mode = checker_mode(policy, unit)
        if required_checker_mode in ("targeted", "full"):
            if review_evidence.strip():
                die(f"{unit['id']}: plain --review-evidence is not trusted; "
                    "use --verification-receipt from the harness adjudicator", 1)
        used = budgeted_attempt_count(unit)
        if used >= policy["maxAttemptsPerUnit"]:
            return bounded_stop(
                goal, goal_path, unit, "budget_exhausted",
                f"attempt limit reached ({used}/{policy['maxAttemptsPerUnit']})",
                "attempts", used)
        elapsed = elapsed_seconds(unit)
        if elapsed is None:
            return bounded_stop(goal, goal_path, unit, "blocked",
                                "invalid runState.startedAt")
        remaining = policy["maxWallClockSecondsPerUnit"] - elapsed
        if remaining <= 0:
            return bounded_stop(
                goal, goal_path, unit, "budget_exhausted",
                f"wall-clock limit reached ({int(elapsed)}s/"
                f"{policy['maxWallClockSecondsPerUnit']}s)", "wall_clock",
                int(elapsed))
        # subprocess accepts a float timeout. Preserve the exact remainder:
        # rounding a sub-second budget up to one second would violate the
        # approved wall-clock ceiling.
        timeout = min(float(timeout), remaining)

    print(f"verifying {unit['id']}: {command}")
    sh = shutil.which("sh")
    if sh is None and os.name == "nt":
        # The native adapter deliberately never falls back to cmd.exe. Git
        # Bash is the supported POSIX interpreter, but Codex's isolated Python
        # launch does not necessarily inherit its bin directory on PATH.
        git_bash = Path(r"C:\Program Files\Git\bin\sh.exe")
        if git_bash.is_file() and not git_bash.is_symlink():
            sh = str(git_bash)
    if sh is None:
        # POSIX-контракт (v1.87.0): без sh НЕ деградируем в cmd.exe тихо —
        # cmd.exe даёт ложные verified (см. Shell contract в шапке).
        output, rc = ("no POSIX sh on PATH — verificationCommand contract "
                      "requires sh (Git Bash / WSL); refusing cmd.exe fallback"), 127
    else:
        try:
            # encoding pinned + errors replaced: an arbitrary verificationCommand on
            # Windows may emit cp1251/cp1252 bytes — never let decoding kill the ОТК.
            proc = subprocess.run([sh, "-c", command], capture_output=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
            output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            output, rc = f"timeout after {timeout}s", 124

    evidence = f"exit {rc}: {decisive_line(output)}"[:EVIDENCE_MAX]
    receipt_error = ""
    if rc == 0 and verification_receipt_path.strip():
        try:
            verification_receipt = validate_verification_receipt(
                goal_path, verification_receipt_path,
                str(unit.get("riskTier") or "unknown"), str(unit["id"]))
            if not receipt_binds_command(verification_receipt, command):
                receipt_error = "receipt machine evidence does not contain Goal verificationCommand"
        except VerificationReceiptError as exc:
            receipt_error = str(exc)

    if policy is not None:
        # A checker is a second-stage gate over a machine-green candidate.  A
        # machine-red attempt must still be journalled so the bounded repair
        # loop can learn, spend its attempt budget, and continue.  Requiring a
        # PASSED adjudication before running the oracle would make failed
        # attempts unobservable and deadlock the repair loop.
        checker_error = receipt_error
        if rc == 0 and required_checker_mode in ("targeted", "full"):
            if not verification_receipt_path.strip():
                checker_error = f"{required_checker_mode} checker receipt is missing"
        if checker_error:
            evidence = (evidence + "; checker UNVERIFIED: " + checker_error)[:EVIDENCE_MAX]
            record_attempt(unit, approach, command, "unverified", evidence,
                           None, recheck, tokens_used, required_checker_mode)
            write_verify_signal(goal_path, unit["id"], 1, command, evidence)
            if recheck:
                unit["evidence"] = ""
                unit["verifiedAt"] = ""
                unit["status"] = "in_progress"
                goal["currentUnitId"] = unit["id"]
            set_stop_reason(unit, "")
            if recheck:
                if not commit_goal_transition(
                        goal, goal_path, unit, "verification_unverified", evidence,
                        projection, state_decision="regressed"):
                    return 1
            else:
                save_goal(goal_path, goal)
                append_event(goal_path, unit["id"], "verification_unverified", evidence)
            used = budgeted_attempt_count(unit)
            if used >= policy["maxAttemptsPerUnit"]:
                return bounded_stop(
                    goal, goal_path, unit, "budget_exhausted",
                    f"attempt limit reached ({used}/{policy['maxAttemptsPerUnit']}); "
                    f"last result {evidence}", "attempts", used)
            print(f"UNVERIFIED {unit['id']} stays in_progress — {evidence}")
            return 1
        outcome = "verified" if rc == 0 else ("regressed" if recheck else "failed")
        record_attempt(unit, approach, command, outcome, evidence,
                       verification_receipt, recheck, tokens_used,
                       required_checker_mode)

    # A supplied receipt is never decorative: validate it outside bounded mode
    # too, and require it for explicitly classified medium/high legacy units.
    if policy is None and rc == 0 and (verification_receipt_path.strip()
                                       or required_checker_mode != "machine_only"):
        if not verification_receipt_path.strip():
            receipt_error = f"{required_checker_mode} checker receipt is missing"
        if receipt_error:
            if recheck:
                unit["evidence"] = ""
                unit["verifiedAt"] = ""
                unit["status"] = "in_progress"
                goal["currentUnitId"] = unit["id"]
                if not commit_goal_transition(goal, goal_path, unit, "regressed",
                                              evidence + "; checker UNVERIFIED", projection):
                    return 1
            print(f"UNVERIFIED {unit['id']} — {receipt_error}")
            return 1

    # Runtime-сигнал верификации (GO-003): прогон становится наблюдаемым для
    # completion-gate независимо от исхода (pass/fail).
    write_verify_signal(goal_path, unit["id"], rc, command, evidence)

    if rc == 0:
        unit["status"] = "verified"
        unit["verifiedAt"] = now_iso()
        unit["evidence"] = evidence
        if verification_receipt is not None:
            unit["verificationReceipt"] = {
                key: value for key, value in verification_receipt.items() if key != "machine"
            }
        if policy is not None:
            set_stop_reason(unit, "verified")
        if is_working_deadline_unit(unit):
            (deadline_state(unit) or {})["stopReason"] = "verified"
            require_result_handoff(goal, unit)
        goal["currentUnitId"] = ""
        # Инвариант леджера verified ⊆ activated: если activation-событие
        # потеряно (activated руками/другим путём), бэкфиллим его ДО verified —
        # иначе VCR-учёт видит юнит verified без активации (retro 2026-07-11 P3,
        # live: OneOfS U-2..U-5).
        if not has_activation_event(goal_path, unit["id"]):
            # Historical hand-edited goals have no STATE lifecycle to mirror.
            append_event(goal_path, unit["id"], "activated",
                         "backfill при verify: activation-событие отсутствовало")
        if not commit_goal_transition(goal, goal_path, unit, "verified", evidence, projection,
                                      verified_context=True):
            return 1
        print(f"VERIFIED {unit['id']} — {evidence}")
        print(open_units_summary(goal))
        return 0

    if recheck:
        unit["evidence"] = ""
        unit["verifiedAt"] = ""
        if policy is not None:
            set_stop_reason(unit, "")
            used = budgeted_attempt_count(unit)
            if used >= policy["maxAttemptsPerUnit"]:
                return bounded_stop(
                    goal, goal_path, unit, "budget_exhausted",
                    f"attempt limit reached ({used}/{policy['maxAttemptsPerUnit']}); "
                    f"last recheck result {evidence}", "attempts", used)
            elapsed = elapsed_seconds(unit)
            if (elapsed is not None
                    and elapsed >= policy["maxWallClockSecondsPerUnit"]):
                return bounded_stop(
                    goal, goal_path, unit, "budget_exhausted",
                    f"wall-clock limit reached after recheck ({int(elapsed)}s/"
                    f"{policy['maxWallClockSecondsPerUnit']}s)", "wall_clock",
                    int(elapsed))
        if is_working_deadline_unit(unit):
            reset_deadline_cycle(unit)
            pending_handoff = handoff_state(goal)
            if pending_handoff and pending_handoff.get("unitId") == unit.get("id"):
                goal.pop("handoffState", None)
        unit["status"] = "in_progress"
        goal["currentUnitId"] = unit["id"]
        if not commit_goal_transition(goal, goal_path, unit, "regressed", evidence, projection):
            return 1
        print(f"REGRESSED {unit['id']} back to in_progress — {evidence}")
        return 1

    if policy is not None:
        set_stop_reason(unit, "")
        save_goal(goal_path, goal)
        used = budgeted_attempt_count(unit)
        if used >= policy["maxAttemptsPerUnit"]:
            return bounded_stop(
                goal, goal_path, unit, "budget_exhausted",
                f"attempt limit reached ({used}/{policy['maxAttemptsPerUnit']}); "
                f"last result {evidence}", "attempts", used)
        elapsed = elapsed_seconds(unit)
        if (elapsed is not None
                and elapsed >= policy["maxWallClockSecondsPerUnit"]):
            return bounded_stop(
                goal, goal_path, unit, "budget_exhausted",
                f"wall-clock limit reached after failure ({int(elapsed)}s/"
                f"{policy['maxWallClockSecondsPerUnit']}s)", "wall_clock",
                int(elapsed))
    append_event(goal_path, unit["id"], "verification_failed", evidence)
    print(f"FAILED {unit['id']} stays in_progress — {evidence}")
    print(decisive_line(output))
    return 1


def main() -> int:
    # Windows consoles default to cp125x — reconfigure so em-dashes and Russian
    # in our own messages never raise UnicodeEncodeError (platform symmetry).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(
        description="Harness-side verifier for .itd-memory/GOAL.json unit transitions")
    p.add_argument("unit_id", nargs="?", default=None)
    p.add_argument("--goal", type=Path, default=GOAL_DEFAULT)
    p.add_argument("--seal", action="store_true",
                   help="freeze approved runPolicy + unit verification oracles")
    p.add_argument("--activate", action="store_true",
                   help="pending/blocked -> in_progress (WIP=1 enforced)")
    p.add_argument("--block", action="store_true",
                   help="in_progress/pending -> blocked (requires --reason)")
    p.add_argument("--budget-exhausted", action="store_true",
                   help="typed bounded stop reported by the host budget gate")
    p.add_argument("--deadline-check", action="store_true",
                   help="observe/enforce the working_deadline timebox")
    p.add_argument("--ack-handoff", action="store_true",
                   help="acknowledge that a verified-unit result was handed off")
    p.add_argument("--reconcile", action="store_true",
                   help="recover the selected interrupted transition, or repair STATE from a canonical verified Goal event")
    p.add_argument("--reason", default="",
                   help="reason for --block/--budget-exhausted/budget resume")
    p.add_argument("--budget-kind", default="",
                   choices=("", "attempts", "wall_clock", "tokens"),
                   help="which approved budget was exhausted")
    p.add_argument("--budget-observed", type=int, default=None,
                   help="host-observed usage for a typed budget stop")
    p.add_argument("--tokens-used", type=int, default=None,
                   help="cumulative host-session tokens observed before verify")
    p.add_argument("--work-profile", default="", choices=("", WORKING_DEADLINE_PROFILE),
                   help="explicit per-unit daily-work profile (valid with --activate)")
    p.add_argument("--elapsed-seconds", type=int, default=None,
                   help="host-observed elapsed unit time for deadline check/verify")
    p.add_argument("--checkpoint-ready", default="")
    p.add_argument("--checkpoint-blocker", default="")
    p.add_argument("--checkpoint-remainder", default="")
    p.add_argument("--checkpoint-estimate", default="")
    p.add_argument("--recheck", action="store_true",
                   help="re-run a verified unit; regression demotes it")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--approach", default="",
                   help="hypothesis/approach recorded for a bounded attempt")
    p.add_argument("--review-evidence", default="",
                   help="deprecated plain text; rejected when a checker is required")
    p.add_argument("--verification-receipt", default="",
                   help="adjudicated exact-candidate Verification Loop receipt")
    args = p.parse_args()

    actions = sum(bool(x) for x in
                  (args.seal, args.activate, args.block,
                   args.budget_exhausted, args.deadline_check,
                   args.ack_handoff, args.recheck, args.reconcile))
    if actions > 1:
        die("--seal, --activate, --block, --budget-exhausted, --deadline-check, "
            "--ack-handoff, --recheck and --reconcile are mutually exclusive")
    if args.work_profile and not args.activate:
        die("--work-profile is valid only with --activate")

    if transition_recovery_path(args.goal).exists() and not args.reconcile:
        die("interrupted Goal transition is pending; use --reconcile with current verification evidence", 1)
    goal = load_goal(args.goal)
    for u in goal["units"]:
        if u.get("status") not in UNIT_STATUSES:
            die(f"unit {u.get('id')}: unknown status '{u.get('status')}'")
    if args.seal:
        if args.unit_id:
            die("--seal applies to the whole approved goal; omit UNIT_ID")
        return cmd_seal(goal, args.goal)
    unit = find_unit(goal, args.unit_id)
    # WIP=1 is enforced going forward by --activate; also DETECT a ledger that
    # was hand-corrupted into >1 in_progress and say so instead of silently
    # working on one of them.
    in_progress = [u.get("id") for u in goal["units"]
                   if u.get("status") in ("in_progress", "recovery_required")]
    if len(in_progress) > 1:
        print(f"warning: WIP=1 violated in ledger — {len(in_progress)} units "
              f"in_progress ({', '.join(in_progress)}); fix the ledger "
              "(only one may be open)")

    if args.activate:
        return cmd_activate(goal, args.goal, unit, args.reason, args.work_profile)
    if args.block:
        return cmd_block(goal, args.goal, unit, args.reason)
    if args.budget_exhausted:
        return cmd_budget_exhausted(goal, args.goal, unit, args.reason,
                                    args.budget_kind, args.budget_observed)
    if args.deadline_check:
        return observe_working_deadline(
            goal, args.goal, unit, args.elapsed_seconds,
            args.checkpoint_ready, args.checkpoint_blocker,
            args.checkpoint_remainder, args.checkpoint_estimate,
        )
    if args.ack_handoff:
        return cmd_ack_handoff(goal, args.goal, unit, args.reason)
    if args.reconcile:
        return cmd_reconcile(goal, args.goal, unit, args.verification_receipt)
    return cmd_verify(goal, args.goal, unit, args.recheck, args.timeout,
                      args.approach, args.review_evidence,
                      args.verification_receipt, args.tokens_used,
                      args.elapsed_seconds, args.checkpoint_ready,
                      args.checkpoint_blocker, args.checkpoint_remainder,
                      args.checkpoint_estimate)


if __name__ == "__main__":
    sys.exit(main())

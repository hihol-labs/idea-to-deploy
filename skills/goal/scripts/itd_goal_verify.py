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
  itd_goal_verify.py [--goal PATH] --timeout 600

Exit codes: 0 transition applied (or recheck still green), 1 verification
failed / invalid transition, 2 usage or ledger error, 3 typed bounded stop
(`runState.stopReason` explains `blocked` vs `budget_exhausted`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

GOAL_DEFAULT = Path(".itd-memory") / "GOAL.json"
UNIT_STATUSES = ("pending", "in_progress", "verified", "skipped", "blocked")
# A unit in ANY of these states keeps the goal open (backpressure > 0). Must
# stay identical to OPEN_STATUSES in itd_goal_report.py.
OPEN_STATUSES = ("pending", "in_progress", "blocked")
EVIDENCE_MAX = 200
BOUNDED_MODE = "bounded_autonomous"
BOUNDED_STOP_EXIT = 3


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}")
    sys.exit(code)


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
    return policy


def verification_fingerprint(unit: dict) -> str:
    payload = {
        "criterion": str(unit.get("criterion") or ""),
        "verificationCommand": str(unit.get("verificationCommand") or ""),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def policy_snapshot(policy: dict) -> dict:
    return {
        key: policy.get(key)
        for key in ("mode", "maxAttemptsPerUnit",
                    "maxWallClockSecondsPerUnit", "maxTokensPerSession",
                    "freezeVerification", "requireApproach",
                    "requireIndependentReview")
    }


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
                 budget_kind: str = "") -> int:
    """Persist a typed stop without inventing a new open-unit status."""
    unit["status"] = "blocked"
    unit["blockedReason"] = f"{stop_reason}: {detail}"
    set_stop_reason(unit, stop_reason)
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
    if goal.get("currentUnitId") == unit.get("id"):
        goal["currentUnitId"] = ""
    save_goal(goal_path, goal)
    append_event(goal_path, unit["id"], stop_reason, detail)
    print(f"STOPPED {unit['id']} [{stop_reason}] — {detail}")
    return BOUNDED_STOP_EXIT


def record_attempt(unit: dict, approach: str, command: str, outcome: str,
                   evidence: str, review_evidence: str, recheck: bool) -> None:
    attempts = unit_attempts(unit)
    attempts.append({
        "number": len(attempts) + 1,
        "at": now_iso(),
        "kind": "recheck" if recheck else "verification",
        "approach": approach.strip(),
        "verificationCommand": command,
        "outcome": outcome,
        "evidence": evidence,
        "reviewEvidence": review_evidence.strip(),
    })


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
        goal = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        die(f"{path}: not valid JSON ({e})")
    if not isinstance(goal.get("units"), list) or not goal["units"]:
        die(f"{path}: 'units' must be a non-empty list")
    return goal


def save_goal(path: Path, goal: dict) -> None:
    goal["updatedAt"] = now_iso()
    path.write_text(json.dumps(goal, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def append_event(goal_path: Path, unit_id: str, decision: str, evidence: str) -> None:
    """Append a unit event (actor: harness) next to the ledger. Best-effort."""
    events = goal_path.parent / "events.jsonl"
    evt = {
        "id": f"evt-goal-{int(time.time())}",
        "at": now_iso(),
        "actor": "harness",
        "type": "unit",
        "name": unit_id,
        "decision": decision,
        "evidence": evidence[:EVIDENCE_MAX],
    }
    try:
        with events.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"warning: could not append event to {events}: {e}")


def has_activation_event(goal_path: Path, unit_id: str) -> bool:
    """True если в events.jsonl уже есть activation-событие юнита."""
    events = goal_path.parent / "events.jsonl"
    try:
        for line in events.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except Exception:
                continue
            if (evt.get("type") == "unit" and evt.get("name") == unit_id
                    and str(evt.get("decision")).lower() == "activated"):
                return True
    except OSError:
        pass
    return False


def find_unit(goal: dict, unit_id: str | None) -> dict:
    units = goal["units"]
    if unit_id:
        for u in units:
            if u.get("id") == unit_id:
                return u
        die(f"unit '{unit_id}' not found in ledger")
    # default: currentUnitId, else first in_progress, else first pending
    cur = goal.get("currentUnitId") or ""
    if cur:
        for u in units:
            if u.get("id") == cur:
                return u
    for status in ("in_progress", "pending"):
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
    actionable = [u for u in goal["units"]
                  if u.get("status") in ("in_progress", "pending")]
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
                 resume_reason: str = "") -> int:
    if unit["status"] == "in_progress":
        print(f"{unit['id']} is already in_progress — nothing to do")
        return 0
    if unit["status"] not in ("pending", "blocked"):
        die(f"cannot activate {unit['id']} from status '{unit['status']}'", 1)
    busy = [u["id"] for u in goal["units"]
            if u.get("status") == "in_progress" and u is not unit]
    if busy:
        die(f"WIP=1: unit {busy[0]} is still in_progress — verify, block or skip "
            "it before activating the next one", 1)
    was_blocked = unit["status"] == "blocked"
    policy = bounded_policy(goal)
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
    goal["currentUnitId"] = unit["id"]
    save_goal(goal_path, goal)
    append_event(goal_path, unit["id"],
                 "activated", unit.get("criterion") or "")
    if policy is not None and resume_reason.strip():
        append_event(goal_path, unit["id"], "budget_resumed",
                     resume_reason.strip())
    print(f"activated {unit['id']}: {unit.get('criterion')}")
    return 0


def cmd_block(goal: dict, goal_path: Path, unit: dict, reason: str) -> int:
    if not reason.strip():
        die("--block requires a non-empty --reason (fail-closed)", 1)
    if unit["status"] not in ("in_progress", "pending"):
        die(f"cannot block {unit['id']} from status '{unit['status']}'", 1)
    unit["status"] = "blocked"
    unit["blockedReason"] = reason.strip()
    if bounded_policy(goal) is not None:
        set_stop_reason(unit, "blocked")
    if goal.get("currentUnitId") == unit["id"]:
        goal["currentUnitId"] = ""
    save_goal(goal_path, goal)
    append_event(goal_path, unit["id"], "blocked", reason.strip())
    print(f"blocked {unit['id']}: {reason.strip()}")
    return 0


def cmd_budget_exhausted(goal: dict, goal_path: Path, unit: dict,
                         reason: str, budget_kind: str) -> int:
    if bounded_policy(goal) is None:
        die("--budget-exhausted requires an opt-in runPolicy", 1)
    if not reason.strip():
        die("--budget-exhausted requires a non-empty --reason", 1)
    if budget_kind not in ("attempts", "wall_clock", "tokens"):
        die("--budget-exhausted requires --budget-kind "
            "attempts|wall_clock|tokens", 1)
    if unit.get("status") != "in_progress":
        die(f"cannot stop {unit['id']} on budget from status "
            f"'{unit.get('status')}'", 1)
    return bounded_stop(goal, goal_path, unit, "budget_exhausted",
                        reason.strip(), budget_kind)


def cmd_verify(goal: dict, goal_path: Path, unit: dict,
               recheck: bool, timeout: int, approach: str,
               review_evidence: str) -> int:
    if recheck:
        if unit["status"] != "verified":
            die(f"--recheck applies to verified units; {unit['id']} is "
                f"'{unit['status']}'", 1)
    elif unit["status"] == "pending":
        die(f"{unit['id']} is pending — activate it first "
            f"(--activate {unit['id']}); verify runs only from in_progress "
            "(gate on passing)", 1)
    elif unit["status"] != "in_progress":
        die(f"cannot verify {unit['id']} from status '{unit['status']}'", 1)

    command = (unit.get("verificationCommand") or "").strip()
    if not command:
        die(f"{unit['id']} has an empty verificationCommand (fail-closed)", 1)

    policy = bounded_policy(goal)
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
        if policy["requireApproach"] and not approach.strip():
            die(f"{unit['id']}: bounded verification requires --approach", 1)
        if (policy["requireIndependentReview"]
                and not review_evidence.strip()):
            die(f"{unit['id']}: independent checker evidence required "
                "(--review-evidence)", 1)
        used = budgeted_attempt_count(unit)
        if used >= policy["maxAttemptsPerUnit"]:
            return bounded_stop(
                goal, goal_path, unit, "budget_exhausted",
                f"attempt limit reached ({used}/{policy['maxAttemptsPerUnit']})",
                "attempts")
        elapsed = elapsed_seconds(unit)
        if elapsed is None:
            return bounded_stop(goal, goal_path, unit, "blocked",
                                "invalid runState.startedAt")
        remaining = policy["maxWallClockSecondsPerUnit"] - elapsed
        if remaining <= 0:
            return bounded_stop(
                goal, goal_path, unit, "budget_exhausted",
                f"wall-clock limit reached ({int(elapsed)}s/"
                f"{policy['maxWallClockSecondsPerUnit']}s)", "wall_clock")
        # subprocess accepts a float timeout. Preserve the exact remainder:
        # rounding a sub-second budget up to one second would violate the
        # approved wall-clock ceiling.
        timeout = min(float(timeout), remaining)

    print(f"verifying {unit['id']}: {command}")
    sh = shutil.which("sh")
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

    if policy is not None:
        outcome = "verified" if rc == 0 else ("regressed" if recheck else "failed")
        record_attempt(unit, approach, command, outcome, evidence,
                       review_evidence, recheck)

    # Runtime-сигнал верификации (GO-003): прогон становится наблюдаемым для
    # completion-gate независимо от исхода (pass/fail).
    write_verify_signal(goal_path, unit["id"], rc, command, evidence)

    if rc == 0:
        unit["status"] = "verified"
        unit["verifiedAt"] = now_iso()
        unit["evidence"] = evidence
        if policy is not None:
            set_stop_reason(unit, "verified")
        goal["currentUnitId"] = ""
        save_goal(goal_path, goal)
        # Инвариант леджера verified ⊆ activated: если activation-событие
        # потеряно (activated руками/другим путём), бэкфиллим его ДО verified —
        # иначе VCR-учёт видит юнит verified без активации (retro 2026-07-11 P3,
        # live: OneOfS U-2..U-5).
        if not has_activation_event(goal_path, unit["id"]):
            append_event(goal_path, unit["id"], "activated",
                         "backfill при verify: activation-событие отсутствовало")
        append_event(goal_path, unit["id"], "verified", evidence)
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
                    f"last recheck result {evidence}", "attempts")
            elapsed = elapsed_seconds(unit)
            if (elapsed is not None
                    and elapsed >= policy["maxWallClockSecondsPerUnit"]):
                return bounded_stop(
                    goal, goal_path, unit, "budget_exhausted",
                    f"wall-clock limit reached after recheck ({int(elapsed)}s/"
                    f"{policy['maxWallClockSecondsPerUnit']}s)", "wall_clock")
        unit["status"] = "in_progress"
        goal["currentUnitId"] = unit["id"]
        save_goal(goal_path, goal)
        append_event(goal_path, unit["id"], "regressed", evidence)
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
                f"last result {evidence}", "attempts")
        elapsed = elapsed_seconds(unit)
        if (elapsed is not None
                and elapsed >= policy["maxWallClockSecondsPerUnit"]):
            return bounded_stop(
                goal, goal_path, unit, "budget_exhausted",
                f"wall-clock limit reached after failure ({int(elapsed)}s/"
                f"{policy['maxWallClockSecondsPerUnit']}s)", "wall_clock")
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
    p.add_argument("--reason", default="",
                   help="reason for --block/--budget-exhausted/budget resume")
    p.add_argument("--budget-kind", default="",
                   choices=("", "attempts", "wall_clock", "tokens"),
                   help="which approved budget was exhausted")
    p.add_argument("--recheck", action="store_true",
                   help="re-run a verified unit; regression demotes it")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--approach", default="",
                   help="hypothesis/approach recorded for a bounded attempt")
    p.add_argument("--review-evidence", default="",
                   help="fresh checker verdict/evidence when policy requires it")
    args = p.parse_args()

    actions = sum(bool(x) for x in
                  (args.seal, args.activate, args.block,
                   args.budget_exhausted, args.recheck))
    if actions > 1:
        die("--seal, --activate, --block, --budget-exhausted and --recheck are "
            "mutually exclusive")

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
                   if u.get("status") == "in_progress"]
    if len(in_progress) > 1:
        print(f"warning: WIP=1 violated in ledger — {len(in_progress)} units "
              f"in_progress ({', '.join(in_progress)}); fix the ledger "
              "(only one may be open)")

    if args.activate:
        return cmd_activate(goal, args.goal, unit, args.reason)
    if args.block:
        return cmd_block(goal, args.goal, unit, args.reason)
    if args.budget_exhausted:
        return cmd_budget_exhausted(goal, args.goal, unit, args.reason,
                                    args.budget_kind)
    return cmd_verify(goal, args.goal, unit, args.recheck, args.timeout,
                      args.approach, args.review_evidence)


if __name__ == "__main__":
    sys.exit(main())

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

Trust model: verificationCommand is executed with shell=True. It is TRUSTED,
user-approved content — the user explicitly approves every unit (incl. its
command) at /goal Step 1 before the ledger is written; same trust boundary as
hook commands in .claude/settings.json. If a future caller feeds this tool a
ledger from an external/synced source, that assumption no longer holds — add
sandboxing there, not here.

Asymmetry note: verify/--activate/--block resolve a default unit when UNIT_ID
is omitted (currentUnitId → first in_progress → first pending); --recheck
targets `verified` units, which that chain never returns — always pass an
explicit UNIT_ID with --recheck.

Usage:
  itd_goal_verify.py [--goal PATH] --activate [UNIT_ID]
  itd_goal_verify.py [--goal PATH] [UNIT_ID]              # verify (default cmd)
  itd_goal_verify.py [--goal PATH] --recheck UNIT_ID      # re-run a verified unit
  itd_goal_verify.py [--goal PATH] --block UNIT_ID --reason "..."
  itd_goal_verify.py [--goal PATH] --timeout 600

Exit codes: 0 transition applied (or recheck still green), 1 verification
failed / invalid transition, 2 usage or ledger error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

GOAL_DEFAULT = Path(".itd-memory") / "GOAL.json"
UNIT_STATUSES = ("pending", "in_progress", "verified", "skipped", "blocked")
# A unit in ANY of these states keeps the goal open (backpressure > 0). Must
# stay identical to OPEN_STATUSES in itd_goal_report.py.
OPEN_STATUSES = ("pending", "in_progress", "blocked")
EVIDENCE_MAX = 200


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}")
    sys.exit(code)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def cmd_activate(goal: dict, goal_path: Path, unit: dict) -> int:
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
    unit["status"] = "in_progress"
    if was_blocked:
        unit["blockedReason"] = ""
    goal["currentUnitId"] = unit["id"]
    save_goal(goal_path, goal)
    append_event(goal_path, unit["id"],
                 "activated", unit.get("criterion") or "")
    print(f"activated {unit['id']}: {unit.get('criterion')}")
    return 0


def cmd_block(goal: dict, goal_path: Path, unit: dict, reason: str) -> int:
    if not reason.strip():
        die("--block requires a non-empty --reason (fail-closed)", 1)
    if unit["status"] not in ("in_progress", "pending"):
        die(f"cannot block {unit['id']} from status '{unit['status']}'", 1)
    unit["status"] = "blocked"
    unit["blockedReason"] = reason.strip()
    if goal.get("currentUnitId") == unit["id"]:
        goal["currentUnitId"] = ""
    save_goal(goal_path, goal)
    append_event(goal_path, unit["id"], "blocked", reason.strip())
    print(f"blocked {unit['id']}: {reason.strip()}")
    return 0


def cmd_verify(goal: dict, goal_path: Path, unit: dict,
               recheck: bool, timeout: int) -> int:
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

    print(f"verifying {unit['id']}: {command}")
    try:
        # encoding pinned + errors replaced: an arbitrary verificationCommand on
        # Windows may emit cp1251/cp1252 bytes — never let decoding kill the ОТК.
        proc = subprocess.run(command, shell=True, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        output, rc = f"timeout after {timeout}s", 124

    evidence = f"exit {rc}: {decisive_line(output)}"[:EVIDENCE_MAX]

    if rc == 0:
        unit["status"] = "verified"
        unit["verifiedAt"] = now_iso()
        unit["evidence"] = evidence
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
        unit["status"] = "in_progress"
        unit["evidence"] = ""
        unit["verifiedAt"] = ""
        goal["currentUnitId"] = unit["id"]
        save_goal(goal_path, goal)
        append_event(goal_path, unit["id"], "regressed", evidence)
        print(f"REGRESSED {unit['id']} back to in_progress — {evidence}")
        return 1

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
    p.add_argument("--activate", action="store_true",
                   help="pending/blocked -> in_progress (WIP=1 enforced)")
    p.add_argument("--block", action="store_true",
                   help="in_progress/pending -> blocked (requires --reason)")
    p.add_argument("--reason", default="", help="blockedReason for --block")
    p.add_argument("--recheck", action="store_true",
                   help="re-run a verified unit; regression demotes it")
    p.add_argument("--timeout", type=int, default=600)
    args = p.parse_args()

    if args.activate and args.block:
        die("--activate and --block are mutually exclusive")

    goal = load_goal(args.goal)
    unit = find_unit(goal, args.unit_id)
    for u in goal["units"]:
        if u.get("status") not in UNIT_STATUSES:
            die(f"unit {u.get('id')}: unknown status '{u.get('status')}'")
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
        return cmd_activate(goal, args.goal, unit)
    if args.block:
        return cmd_block(goal, args.goal, unit, args.reason)
    return cmd_verify(goal, args.goal, unit, args.recheck, args.timeout)


if __name__ == "__main__":
    sys.exit(main())

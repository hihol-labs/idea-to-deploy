#!/usr/bin/env python3
"""Behavioural oracle for the opt-in working_deadline goal runtime."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
REPORT = ROOT / "skills" / "goal" / "scripts" / "itd_goal_report.py"
VALIDATE = ROOT / "scripts" / "validate_state.py"
PY = sys.executable
PROFILE = "working_deadline"
REL_GOAL = os.path.join(".itd-memory", "GOAL.json")

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run(
        [PY, str(script), *args], cwd=str(cwd), capture_output=True,
        encoding="utf-8", errors="replace", env=env, timeout=60,
    )


def command(marker: str) -> str:
    return f'printf executed > "{marker}"'


def make_goal(root: Path, risks: tuple[str | None, ...] = ("low", "medium")) -> Path:
    mem = root / ".itd-memory"
    mem.mkdir(parents=True)
    units = []
    for number, risk in enumerate(risks, 1):
        unit = {
            "id": f"G-{number:03d}",
            "criterion": f"unit {number} passes",
            "verificationCommand": command(f"executed-{number}.txt"),
            "status": "pending",
            "verifiedAt": "",
            "evidence": "",
            "skippedReason": "",
            "blockedReason": "",
        }
        if risk is not None:
            unit["riskTier"] = risk
        units.append(unit)
    goal = {
        "version": 1,
        "goal": "working deadline fixture",
        "status": "active",
        "createdAt": "2026-07-16T00:00:00Z",
        "updatedAt": "2026-07-16T00:00:00Z",
        "currentUnitId": "",
        "units": units,
    }
    path = mem / "GOAL.json"
    path.write_text(json.dumps(goal, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def unit(path: Path, index: int = 0) -> dict:
    return load(path)["units"][index]


def checkpoint_args(elapsed: int) -> tuple[str, ...]:
    return (
        "--elapsed-seconds", str(elapsed),
        "--checkpoint-ready", "runtime and schema drafted",
        "--checkpoint-blocker", "none",
        "--checkpoint-remainder", "review and focused tests",
        "--checkpoint-estimate", "15 minutes",
    )


# The profile is explicit, low/medium only, and legacy activation stays unchanged.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, ("low",))
    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001", cwd=root)
    check("legacy activation remains profile-free",
          r.returncode == 0 and "deadlineState" not in unit(path), r.stdout + r.stderr)
    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
            "--work-profile", PROFILE, cwd=root)
    check("late opt-in cannot mutate an already-active legacy unit",
          r.returncode == 1 and "deadlineState" not in unit(path), r.stdout + r.stderr)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, ("high",))
    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
            "--work-profile", PROFILE, cwd=root)
    check("high risk cannot enter the daily deadline profile",
          r.returncode == 1 and unit(path)["status"] == "pending",
          r.stdout + r.stderr)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, (None,))
    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
            "--work-profile", PROFILE, cwd=root)
    check("unknown risk fails closed instead of entering the profile",
          r.returncode == 1 and unit(path)["status"] == "pending",
          r.stdout + r.stderr)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, ("low",))
    run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
        "--work-profile", PROFILE, cwd=root)
    data = load(path)
    data["units"][0]["riskTier"] = "high"
    data["units"][0]["verificationCommand"] = (
        'printf risk-bypass > "risk-bypass.txt"')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VERIFY, "--goal", REL_GOAL, "G-001", "--elapsed-seconds", "100",
            cwd=root)
    check("post-activation high-risk signal exits before command execution",
          r.returncode == 1 and unit(path)["status"] == "in_progress"
          and not (root / "risk-bypass.txt").exists(), r.stdout + r.stderr)


# Soft checkpoint, monotonic host time, verified handoff, hard pause and resume.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root)
    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
            "--work-profile", PROFILE, cwd=root)
    state = unit(path).get("deadlineState") or {}
    check("explicit opt-in starts host-observed deadline state",
          r.returncode == 0 and state.get("profile") == PROFILE
          and state.get("hostObservedElapsedSeconds") == 0
          and state.get("cycle") == 1, r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-001",
            "--elapsed-seconds", "1799", cwd=root)
    check("before 30 minutes no checkpoint is invented",
          r.returncode == 0
          and not (unit(path).get("deadlineState") or {}).get("softCheckpointAt"),
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-001",
            "--elapsed-seconds", "1800", cwd=root)
    check("30-minute checkpoint requires all four report fields",
          r.returncode == 1 and all(name in (r.stdout + r.stderr) for name in
                                    ("ready", "blocker", "remainder", "estimate")),
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-001",
            *checkpoint_args(1800), cwd=root)
    state = unit(path).get("deadlineState") or {}
    checkpoint = state.get("checkpoint") or {}
    check("30-minute checkpoint is complete and persisted",
          r.returncode == 0 and bool(state.get("softCheckpointAt"))
          and set(checkpoint) == {"ready", "blocker", "remainder", "estimate"}
          and checkpoint["estimate"] == "15 minutes", r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-001",
            "--elapsed-seconds", "1799", cwd=root)
    check("host-observed elapsed time is monotonic",
          r.returncode == 1
          and (unit(path).get("deadlineState") or {}).get(
              "hostObservedElapsedSeconds") == 1800,
          r.stdout + r.stderr)

    r = run(VALIDATE, str(path), cwd=root)
    check("active working-deadline ledger validates", r.returncode == 0,
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "G-001",
            "--elapsed-seconds", "2699", cwd=root)
    data = load(path)
    handoff = data.get("handoffState") or {}
    check("verified unit creates a handoff barrier",
          r.returncode == 0 and data["units"][0]["status"] == "verified"
          and handoff.get("required") is True
          and handoff.get("unitId") == "G-001", r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-002",
            "--work-profile", PROFILE, cwd=root)
    check("next unit cannot activate before result handoff",
          r.returncode == 1 and unit(path, 1)["status"] == "pending"
          and "handoff" in (r.stdout + r.stderr).lower(), r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--ack-handoff", "G-001", cwd=root)
    check("handoff acknowledgement requires provenance",
          r.returncode == 1 and (load(path).get("handoffState") or {}).get("required") is True,
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--ack-handoff", "G-001",
            "--reason", "new user message continued the approved goal", cwd=root)
    check("explicit handoff acknowledgement releases the barrier",
          r.returncode == 0 and (load(path).get("handoffState") or {}).get("required") is False,
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-002",
            "--work-profile", PROFILE, cwd=root)
    check("next unit starts only after acknowledged handoff",
          r.returncode == 0 and unit(path, 1)["status"] == "in_progress",
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-002",
            "--elapsed-seconds", "2700", cwd=root)
    data = load(path)
    second = data["units"][1]
    state = second.get("deadlineState") or {}
    exhausted = state.get("exhaustedBudget") or {}
    check("45-minute observation creates typed recovery pause",
          r.returncode == 3 and second["status"] == "recovery_required"
          and state.get("stopReason") == "budget_exhausted"
          and exhausted.get("kind") == "wall_clock"
          and exhausted.get("limit") == 2700 and exhausted.get("observed") == 2700
          and data["currentUnitId"] == "G-002", r.stdout + r.stderr)
    check("hard pause never executes or verifies partial work",
          not (root / "executed-2.txt").exists()
          and not second.get("verifiedAt") and not second.get("evidence"))

    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-002",
            "--reason", "attempt resume without checkpoint", cwd=root)
    check("hard pause cannot resume before cheap checkpoint capture",
          r.returncode == 1 and unit(path, 1)["status"] == "recovery_required",
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-002",
            *checkpoint_args(2700), cwd=root)
    state = unit(path, 1).get("deadlineState") or {}
    check("cheap checkpoint remains available while hard-paused",
          r.returncode == 3 and unit(path, 1)["status"] == "recovery_required"
          and state.get("checkpoint", {}).get("ready") == "runtime and schema drafted",
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "G-002",
            "--elapsed-seconds", "2700", cwd=root)
    check("verification is refused while recovery is required",
          r.returncode == 1 and unit(path, 1)["status"] == "recovery_required"
          and not (root / "executed-2.txt").exists(), r.stdout + r.stderr)

    r = run(VALIDATE, str(path), cwd=root)
    check("typed recovery ledger validates", r.returncode == 0,
          r.stdout + r.stderr)

    r = run(REPORT, "--goal", REL_GOAL, "--json", cwd=root)
    report = json.loads(r.stdout) if r.returncode == 0 else {}
    report_unit = next((u for u in report.get("units", [])
                        if u.get("id") == "G-002"), {})
    check("report exposes recovery and handoff state",
          r.returncode == 0 and report_unit.get("status") == "recovery_required"
          and report_unit.get("deadlineStopReason") == "budget_exhausted"
          and report_unit.get("deadlineCheckpoint", {}).get("blocker") == "none"
          and (report.get("handoffState") or {}).get("required") is False,
          r.stdout + r.stderr)

    r = run(REPORT, "--goal", REL_GOAL, "--compact", cwd=root)
    check("compact recovery handoff carries all checkpoint fields",
          r.returncode == 0 and all(field in r.stdout for field in
                                    ("ready=", "blocker=", "remainder=", "estimate=")),
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-002", cwd=root)
    check("recovery cannot resume without an explicit reason",
          r.returncode == 1 and unit(path, 1)["status"] == "recovery_required",
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-002",
            "--reason", "new bounded work window approved", cwd=root)
    state = unit(path, 1).get("deadlineState") or {}
    check("explicit recovery starts a fresh observed cycle",
          r.returncode == 0 and unit(path, 1)["status"] == "in_progress"
          and state.get("cycle") == 2
          and state.get("hostObservedElapsedSeconds") == 0
          and not state.get("softCheckpointAt"), r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "G-002", cwd=root)
    check("profile verification requires current host observation",
          r.returncode == 1 and not (root / "executed-2.txt").exists(),
          r.stdout + r.stderr)

    r = run(VERIFY, "--goal", REL_GOAL, "G-002",
            "--elapsed-seconds", "2700", cwd=root)
    check("verify path hard-pauses before an expensive command",
          r.returncode == 3 and unit(path, 1)["status"] == "recovery_required"
          and not (root / "executed-2.txt").exists(), r.stdout + r.stderr)


# A final verified unit cannot close or recheck around the handoff barrier.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, ("low",))
    run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
        "--work-profile", PROFILE, cwd=root)
    r = run(VERIFY, "--goal", REL_GOAL, "G-001", "--elapsed-seconds", "100",
            cwd=root)
    check("last-unit verify output requires handoff instead of goal close",
          r.returncode == 0 and "result handoff required" in r.stdout.lower()
          and "goal can be closed" not in r.stdout.lower(), r.stdout + r.stderr)
    r = run(REPORT, "--goal", REL_GOAL, cwd=root)
    check("full report blocks last-unit close until acknowledgement",
          r.returncode == 0 and "--ack-handoff G-001" in r.stdout
          and "Открытых юнитов нет" not in r.stdout, r.stdout + r.stderr)
    r = run(REPORT, "--goal", REL_GOAL, "--compact", cwd=root)
    check("compact report blocks last-unit close until acknowledgement",
          r.returncode == 0 and "acknowledge handoff" in r.stdout.lower()
          and "close goal; no open unit" not in r.stdout.lower(), r.stdout + r.stderr)
    r = run(VERIFY, "--goal", REL_GOAL, "--recheck", "G-001", cwd=root)
    check("recheck cannot postpone a pending result handoff",
          r.returncode == 1 and unit(path)["status"] == "verified",
          r.stdout + r.stderr)
    data = load(path)
    data["status"] = "done"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VALIDATE, str(path), cwd=root)
    check("validator rejects goal close before handoff acknowledgement",
          r.returncode == 1 and "handoff" in (r.stdout + r.stderr).lower(),
          r.stdout + r.stderr)
    data["status"] = "active"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    run(VERIFY, "--goal", REL_GOAL, "--ack-handoff", "G-001",
        "--reason", "new user turn", cwd=root)
    data = load(path)
    policy_digest = data["units"][0]["deadlineState"]["policySha256"]
    data["units"][0]["deadlineState"]["policySha256"] = "0" * 64
    data["units"][0]["verificationCommand"] = (
        'printf stale-policy-ran > "stale-recheck.txt"')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VERIFY, "--goal", REL_GOAL, "--recheck", "G-001", cwd=root)
    check("stale policy binding blocks recheck before command execution",
          r.returncode == 1 and unit(path)["status"] == "verified"
          and not (root / "stale-recheck.txt").exists(), r.stdout + r.stderr)
    data = load(path)
    data["units"][0]["deadlineState"]["policySha256"] = policy_digest
    data["units"][0]["verificationCommand"] = "exit 1"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(VERIFY, "--goal", REL_GOAL, "--recheck", "G-001", cwd=root)
    data = load(path)
    check("failed post-handoff recheck opens a fresh cycle without stale handoff",
          r.returncode == 1 and data["units"][0]["status"] == "in_progress"
          and data["units"][0]["deadlineState"]["cycle"] == 2
          and "handoffState" not in data, r.stdout + r.stderr)
    r = run(VALIDATE, str(path), cwd=root)
    check("regressed working-deadline ledger validates", r.returncode == 0,
          r.stdout + r.stderr)


# A bounded-autonomy stop must keep the orthogonal deadline state consistent.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    path = make_goal(root, ("medium",))
    data = load(path)
    data["units"][0]["verificationCommand"] = "exit 1"
    data["runPolicy"] = {
        "mode": "bounded_autonomous",
        "maxAttemptsPerUnit": 1,
        "maxWallClockSecondsPerUnit": 3600,
        "maxTokensPerSession": 1000,
        "freezeVerification": True,
        "requireApproach": True,
        "requireIndependentReview": False,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    run(VERIFY, "--goal", REL_GOAL, "--seal", cwd=root)
    run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
        "--work-profile", PROFILE, cwd=root)
    r = run(VERIFY, "--goal", REL_GOAL, "G-001", "--elapsed-seconds", "100",
            "--approach", "bounded failure", cwd=root)
    state = unit(path).get("deadlineState") or {}
    check("bounded stop synchronizes the deadline sub-state",
          r.returncode == 3 and unit(path)["status"] == "blocked"
          and state.get("stopReason") == "blocked", r.stdout + r.stderr)
    r = run(VALIDATE, str(path), cwd=root)
    check("combined bounded/deadline stopped ledger validates", r.returncode == 0,
          r.stdout + r.stderr)


print(f"\n{passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
print("ALL PASS")

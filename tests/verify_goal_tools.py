#!/usr/bin/env python3
"""Functional pipe-tests for the /goal harness tools (v1.45.0).

Covers the walkinglabs feature-list contract the tools implement:
  - transitions are made by the HARNESS (itd_goal_verify.py), not by hand;
  - gate on passing: verify only from in_progress, pending must be activated;
  - WIP=1: a second activation is refused while one unit is in_progress;
  - verified only via an actual verificationCommand run, with evidence;
  - failure keeps in_progress; --recheck demotes a regressed verified unit;
  - blocked is fail-closed (needs --reason) and unblocks via --activate;
  - every transition lands in events.jsonl with actor "harness";
  - itd_goal_report.py renders progress/backpressure/first-action from the
    ledger and stays consistent with it;
  - the resulting ledger stays valid for scripts/validate_state.py.

Cross-platform by construction: verification commands are built from
sys.executable, tmp dirs via tempfile. Self-contained. Run:
  python3 tests/verify_goal_tools.py

Консолидация LPD003-4: сюда же перенесён поведенческий оракул бывшего
verify_work_deadline_runtime (тот же предмет — itd_goal_verify/itd_goal_report/
validate_state): opt-in working_deadline профиль — явный вход low/medium only,
монотонное host-время, soft checkpoint 30 мин (все четыре поля), hard pause 45
мин с typed budget_exhausted, handoff barrier и возобновление только явной
командой, связка с bounded-autonomy stop.
"""
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
PASS_CMD = f'"{PY}" -c "import sys; print(2, chr(112)+chr(97)+chr(115)+chr(115)+chr(101)+chr(100)); sys.exit(0)"'
FAIL_CMD = f'"{PY}" -c "import sys; print(chr(98)+chr(111)+chr(111)+chr(109)); sys.exit(1)"'

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    # PYTHONUTF8 + pinned decode: on Windows the child would otherwise write
    # cp125x bytes (em-dash 0x97) that kill a utf-8 reader thread.
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run([PY, str(script), *args], cwd=str(cwd),
                          capture_output=True, encoding="utf-8",
                          errors="replace", env=env, timeout=120)


def make_ledger(mem: Path) -> Path:
    ledger = {
        "version": 1,
        "goal": "Fixture goal for harness tools",
        "status": "active",
        "createdAt": "2026-07-03T00:00:00Z",
        "updatedAt": "2026-07-03T00:00:00Z",
        "currentUnitId": "",
        "units": [
            {"id": "G-001", "criterion": "unit one passes", "verificationCommand": PASS_CMD,
             "status": "pending", "verifiedAt": "", "evidence": "", "skippedReason": "", "blockedReason": ""},
            {"id": "G-002", "criterion": "unit two passes", "verificationCommand": FAIL_CMD,
             "status": "pending", "verifiedAt": "", "evidence": "", "skippedReason": "", "blockedReason": ""},
            {"id": "G-003", "criterion": "unit three passes", "verificationCommand": PASS_CMD,
             "status": "pending", "verifiedAt": "", "evidence": "", "skippedReason": "", "blockedReason": ""},
        ],
    }
    path = mem / "GOAL.json"
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def unit(goal: dict, uid: str) -> dict:
    return next(u for u in goal["units"] if u["id"] == uid)


def events(mem: Path) -> list[dict]:
    p = mem / "events.jsonl"
    if not p.is_file():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        mem = proj / ".itd-memory"
        mem.mkdir()
        goal_path = make_ledger(mem)
        rel = os.path.join(".itd-memory", "GOAL.json")

        # 1) verify a pending unit is refused (gate on passing)
        r = run(VERIFY, "--goal", rel, "G-001", cwd=proj)
        check("verify refuses pending unit (activate first)", r.returncode == 1
              and "activate" in (r.stdout + r.stderr).lower(), r.stdout + r.stderr)

        # 2) activate G-001
        r = run(VERIFY, "--goal", rel, "--activate", "G-001", cwd=proj)
        g = load(goal_path)
        check("activate flips pending -> in_progress + currentUnitId",
              r.returncode == 0 and unit(g, "G-001")["status"] == "in_progress"
              and g["currentUnitId"] == "G-001", r.stdout + r.stderr)

        # 3) WIP=1: activating G-002 while G-001 is open is refused
        r = run(VERIFY, "--goal", rel, "--activate", "G-002", cwd=proj)
        g = load(goal_path)
        check("WIP=1: second activation refused", r.returncode == 1
              and unit(g, "G-002")["status"] == "pending", r.stdout + r.stderr)

        # 4) verify G-001 (passing command) -> verified with evidence
        r = run(VERIFY, "--goal", rel, "G-001", cwd=proj)
        g = load(goal_path)
        u1 = unit(g, "G-001")
        check("harness verifies passing unit", r.returncode == 0
              and u1["status"] == "verified" and "exit 0" in u1["evidence"]
              and u1["verifiedAt"] != "", r.stdout + r.stderr)

        # 5) events carry actor=harness for activated+verified
        evs = events(mem)
        kinds = {(e.get("name"), e.get("decision")) for e in evs}
        check("events.jsonl has activated+verified with actor harness",
              ("G-001", "activated") in kinds and ("G-001", "verified") in kinds
              and all(e.get("actor") == "harness" for e in evs), str(evs))

        # 6) failing verification keeps in_progress
        run(VERIFY, "--goal", rel, "--activate", "G-002", cwd=proj)
        r = run(VERIFY, "--goal", rel, "G-002", cwd=proj)
        g = load(goal_path)
        check("failing command keeps unit in_progress", r.returncode == 1
              and unit(g, "G-002")["status"] == "in_progress", r.stdout + r.stderr)

        # 6.5) verified ⊆ activated (v1.83.0, retro 2026-07-11 P3): юнит,
        # активированный МИМО скрипта (потерянное activation-событие), при
        # verify получает activated-бэкфилл ДО verified — VCR-учёт не видит
        # verified без активации. Изолированная фикстура: reconciliation-чек
        # validate_state не должен видеть эти события в основном леджере.
        proj_bf = Path(td) / "backfill"
        mem_bf = proj_bf / ".itd-memory"
        mem_bf.mkdir(parents=True)
        goal_bf = make_ledger(mem_bf)
        g_bf = load(goal_bf)
        unit(g_bf, "G-001")["status"] = "in_progress"   # «ручная» активация без события
        g_bf["currentUnitId"] = "G-001"
        goal_bf.write_text(json.dumps(g_bf, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        r = run(VERIFY, "--goal", rel, "G-001", cwd=proj_bf)
        evs_bf = [(e.get("decision"), e.get("evidence", ""))
                  for e in events(mem_bf) if e.get("name") == "G-001"]
        decisions_bf = [d for d, _ in evs_bf]
        check("verify backfills missing activation before verified",
              r.returncode == 0 and decisions_bf == ["activated", "verified"]
              and "backfill" in evs_bf[0][1],
              str(evs_bf) + (r.stdout + r.stderr)[:200])

        # 7) block is fail-closed and unblocks via --activate
        r = run(VERIFY, "--goal", rel, "--block", "G-002", cwd=proj)
        check("block without reason refused", r.returncode == 1, r.stdout + r.stderr)
        r = run(VERIFY, "--goal", rel, "--block", "G-002", "--reason", "waiting for key", cwd=proj)
        g = load(goal_path)
        check("block with reason -> blocked + blockedReason", r.returncode == 0
              and unit(g, "G-002")["status"] == "blocked"
              and unit(g, "G-002")["blockedReason"] == "waiting for key", r.stdout + r.stderr)
        rv = subprocess.run([PY, str(VALIDATE), str(goal_path)],
                            capture_output=True, text=True)
        check("validate_state accepts blocked-with-reason ledger", rv.returncode == 0,
              rv.stdout + rv.stderr)
        r = run(VERIFY, "--goal", rel, "--activate", "G-002", cwd=proj)
        g = load(goal_path)
        check("activate unblocks (blocked -> in_progress, reason cleared)",
              r.returncode == 0 and unit(g, "G-002")["status"] == "in_progress"
              and unit(g, "G-002")["blockedReason"] == "", r.stdout + r.stderr)

        # 8) fix the command -> verified; then recheck regression demotes
        g = load(goal_path)
        unit(g, "G-002")["verificationCommand"] = PASS_CMD
        goal_path.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
        r = run(VERIFY, "--goal", rel, "G-002", cwd=proj)
        g = load(goal_path)
        check("fixed command verifies", r.returncode == 0
              and unit(g, "G-002")["status"] == "verified", r.stdout + r.stderr)
        g = load(goal_path)
        unit(g, "G-002")["verificationCommand"] = FAIL_CMD
        goal_path.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
        r = run(VERIFY, "--goal", rel, "--recheck", "G-002", cwd=proj)
        g = load(goal_path)
        check("recheck demotes regressed unit to in_progress", r.returncode == 1
              and unit(g, "G-002")["status"] == "in_progress"
              and ("G-002", "regressed") in {(e.get("name"), e.get("decision"))
                                             for e in events(mem)}, r.stdout + r.stderr)

        # 9) reporter renders ledger-derived numbers and first action
        r = run(REPORT, "--goal", rel, cwd=proj)
        out = r.stdout
        check("report renders N/M verified and backpressure", r.returncode == 0
              and "1/3" in out and "Обратное давление" in out, out[:300])
        check("report names current unit and its command",
              "G-002" in out and "Первое действие" in out, out[:300])
        r = run(REPORT, "--goal", rel, "--json", cwd=proj)
        try:
            data = json.loads(r.stdout)
            ok = data["unitsVerified"] == 1 and data["unitsTotal"] == 3 and data["backpressure"] == 2
        except Exception:
            ok = False
        check("report --json is machine-readable and consistent", ok, r.stdout[:300])

        # 10) final ledger still valid
        rv = subprocess.run([PY, str(VALIDATE), str(goal_path)],
                            capture_output=True, text=True)
        check("final ledger passes validate_state.py", rv.returncode == 0,
              rv.stdout + rv.stderr)

    # 11) blocked-only scenario: tools must NOT claim the goal is closeable
    with tempfile.TemporaryDirectory() as td2:
        proj = Path(td2)
        mem = proj / ".itd-memory"
        mem.mkdir()
        goal_path = make_ledger(mem)
        rel = os.path.join(".itd-memory", "GOAL.json")
        g = load(goal_path)
        g["units"] = g["units"][:2]  # G-001 (pass cmd), G-002
        unit(g, "G-001")["criterion"] = "unit one | with pipe"
        goal_path.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")

        run(VERIFY, "--goal", rel, "--activate", "G-002", cwd=proj)
        run(VERIFY, "--goal", rel, "--block", "G-002", "--reason", "external key", cwd=proj)
        run(VERIFY, "--goal", rel, "--activate", "G-001", cwd=proj)
        r = run(VERIFY, "--goal", rel, "G-001", cwd=proj)
        check("verifier is blocked-aware after last actionable unit",
              r.returncode == 0 and "BLOCKED" in r.stdout
              and "can be closed" not in r.stdout, r.stdout + r.stderr)

        r = run(REPORT, "--goal", rel, cwd=proj)
        check("report does not suggest closing with a blocked unit open",
              "Открытых юнитов нет" not in r.stdout
              and "заблокирован" in r.stdout and "external key" in r.stdout,
              r.stdout[:400])
        check("report escapes pipes in table cells",
              "unit one \\| with pipe" in r.stdout, r.stdout[:400])
        r = run(REPORT, "--goal", rel, "--json", cwd=proj)
        try:
            data = json.loads(r.stdout)
            ok = data["backpressure"] == 1 and data["unitsVerified"] == 1
        except Exception:
            ok = False
        check("report --json backpressure counts blocked as open", ok, r.stdout[:300])

    work_deadline_runtime_checks()

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


# --- Перенесено из verify_work_deadline_runtime (LPD003-4) ------------------
# Behavioural oracle for the opt-in working_deadline goal runtime.
# Переименование от коллизии: хелпер донора unit(path, index) здесь называется
# unit_at (у keeper-сьюта unit(goal, uid) с другой сигнатурой).

PROFILE = "working_deadline"
REL_GOAL = os.path.join(".itd-memory", "GOAL.json")


def command(marker: str) -> str:
    return f'printf executed > "{marker}"'


def make_goal(root: Path, risks: tuple[str | None, ...] = ("low", "medium")) -> Path:
    mem = root / ".itd-memory"
    mem.mkdir(parents=True)
    units = []
    for number, risk in enumerate(risks, 1):
        u = {
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
            u["riskTier"] = risk
        units.append(u)
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


def unit_at(path: Path, index: int = 0) -> dict:
    return load(path)["units"][index]


def checkpoint_args(elapsed: int) -> tuple[str, ...]:
    return (
        "--elapsed-seconds", str(elapsed),
        "--checkpoint-ready", "runtime and schema drafted",
        "--checkpoint-blocker", "none",
        "--checkpoint-remainder", "review and focused tests",
        "--checkpoint-estimate", "15 minutes",
    )


def work_deadline_runtime_checks() -> None:
    # The profile is explicit, low/medium only, and legacy activation stays unchanged.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        path = make_goal(root, ("low",))
        r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001", cwd=root)
        check("legacy activation remains profile-free",
              r.returncode == 0 and "deadlineState" not in unit_at(path), r.stdout + r.stderr)
        r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
                "--work-profile", PROFILE, cwd=root)
        check("late opt-in cannot mutate an already-active legacy unit",
              r.returncode == 1 and "deadlineState" not in unit_at(path), r.stdout + r.stderr)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        path = make_goal(root, ("high",))
        r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
                "--work-profile", PROFILE, cwd=root)
        check("high risk cannot enter the daily deadline profile",
              r.returncode == 1 and unit_at(path)["status"] == "pending",
              r.stdout + r.stderr)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        path = make_goal(root, (None,))
        r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
                "--work-profile", PROFILE, cwd=root)
        check("unknown risk fails closed instead of entering the profile",
              r.returncode == 1 and unit_at(path)["status"] == "pending",
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
              r.returncode == 1 and unit_at(path)["status"] == "in_progress"
              and not (root / "risk-bypass.txt").exists(), r.stdout + r.stderr)

    # Soft checkpoint, monotonic host time, verified handoff, hard pause and resume.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        path = make_goal(root)
        r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-001",
                "--work-profile", PROFILE, cwd=root)
        state = unit_at(path).get("deadlineState") or {}
        check("explicit opt-in starts host-observed deadline state",
              r.returncode == 0 and state.get("profile") == PROFILE
              and state.get("hostObservedElapsedSeconds") == 0
              and state.get("cycle") == 1, r.stdout + r.stderr)

        r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-001",
                "--elapsed-seconds", "1799", cwd=root)
        check("before 30 minutes no checkpoint is invented",
              r.returncode == 0
              and not (unit_at(path).get("deadlineState") or {}).get("softCheckpointAt"),
              r.stdout + r.stderr)

        r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-001",
                "--elapsed-seconds", "1800", cwd=root)
        check("30-minute checkpoint requires all four report fields",
              r.returncode == 1 and all(name in (r.stdout + r.stderr) for name in
                                        ("ready", "blocker", "remainder", "estimate")),
              r.stdout + r.stderr)

        r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-001",
                *checkpoint_args(1800), cwd=root)
        state = unit_at(path).get("deadlineState") or {}
        checkpoint = state.get("checkpoint") or {}
        check("30-minute checkpoint is complete and persisted",
              r.returncode == 0 and bool(state.get("softCheckpointAt"))
              and set(checkpoint) == {"ready", "blocker", "remainder", "estimate"}
              and checkpoint["estimate"] == "15 minutes", r.stdout + r.stderr)

        r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-001",
                "--elapsed-seconds", "1799", cwd=root)
        check("host-observed elapsed time is monotonic",
              r.returncode == 1
              and (unit_at(path).get("deadlineState") or {}).get(
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
              r.returncode == 1 and unit_at(path, 1)["status"] == "pending"
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
              r.returncode == 0 and unit_at(path, 1)["status"] == "in_progress",
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
              r.returncode == 1 and unit_at(path, 1)["status"] == "recovery_required",
              r.stdout + r.stderr)

        r = run(VERIFY, "--goal", REL_GOAL, "--deadline-check", "G-002",
                *checkpoint_args(2700), cwd=root)
        state = unit_at(path, 1).get("deadlineState") or {}
        check("cheap checkpoint remains available while hard-paused",
              r.returncode == 3 and unit_at(path, 1)["status"] == "recovery_required"
              and state.get("checkpoint", {}).get("ready") == "runtime and schema drafted",
              r.stdout + r.stderr)

        r = run(VERIFY, "--goal", REL_GOAL, "G-002",
                "--elapsed-seconds", "2700", cwd=root)
        check("verification is refused while recovery is required",
              r.returncode == 1 and unit_at(path, 1)["status"] == "recovery_required"
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
              r.returncode == 1 and unit_at(path, 1)["status"] == "recovery_required",
              r.stdout + r.stderr)

        r = run(VERIFY, "--goal", REL_GOAL, "--activate", "G-002",
                "--reason", "new bounded work window approved", cwd=root)
        state = unit_at(path, 1).get("deadlineState") or {}
        check("explicit recovery starts a fresh observed cycle",
              r.returncode == 0 and unit_at(path, 1)["status"] == "in_progress"
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
              r.returncode == 3 and unit_at(path, 1)["status"] == "recovery_required"
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
              r.returncode == 1 and unit_at(path)["status"] == "verified",
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
              r.returncode == 1 and unit_at(path)["status"] == "verified"
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
        state = unit_at(path).get("deadlineState") or {}
        check("bounded stop synchronizes the deadline sub-state",
              r.returncode == 3 and unit_at(path)["status"] == "blocked"
              and state.get("stopReason") == "blocked", r.stdout + r.stderr)
        r = run(VALIDATE, str(path), cwd=root)
        check("combined bounded/deadline stopped ledger validates", r.returncode == 0,
              r.stdout + r.stderr)


if __name__ == "__main__":
    sys.exit(main())

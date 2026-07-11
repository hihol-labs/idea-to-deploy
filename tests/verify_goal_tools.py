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

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

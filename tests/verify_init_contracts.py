#!/usr/bin/env python3
"""Functional tests for the v1.67.0 init-hardening set (init-audit 2026-07-08).

Covers all five closed gaps:
  1. itd_init_validate.py — selftest (isolated-clone bootstrap+test, positive
     and negative paths exercised by a real git repo, no mocks);
  2. check_contract_drift.py — selftest (drift compare + filled_status logic);
  3. --filled functional: a scaffolded-from-templates .itd/ is reported as NOT
     filled (template prose is not a contract); a filled one passes;
  4. crash-recovery + pre-flight consumer pipe-test: a significant tool call
     leaves clean_exit=false with cwd; a DIFFERENT session's pre-flight in the
     same cwd surfaces the crash section exactly once (consumed after); a Stop
     event marks clean_exit=true and nothing is surfaced;
  5. GOAL.json built per goal.schema.json goalTemplate (the /kickstart step 7.5
     mirror shape) validates via scripts/validate_state.py.

Cross-platform by construction: sys.executable, tempfile, no shell. Run:
  python3 tests/verify_init_contracts.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "docs" / "templates" / "itd"
INIT_VALIDATE = TEMPLATES / "itd_init_validate.py"
DRIFT = TEMPLATES / "check_contract_drift.py"
CRASH_HOOK = ROOT / "hooks" / "crash-recovery.sh"
PREFLIGHT = ROOT / "hooks" / "pre-flight-check.sh"
VALIDATE_STATE = ROOT / "scripts" / "validate_state.py"

PY = sys.executable or "python3"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(args: list[str], cwd: Path | None = None, stdin_text: str | None = None,
        env_extra: dict | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    res = subprocess.run(args, cwd=str(cwd) if cwd else None, input=stdin_text,
                         capture_output=True, text=True, timeout=300, env=env)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


def t1_init_validate_selftest() -> None:
    rc, out = run([PY, str(INIT_VALIDATE), "--selftest"])
    check("itd_init_validate --selftest exits 0", rc == 0, out[-300:])
    check("itd_init_validate selftest ALL PASS", "SELFTEST: ALL PASS" in out)


def t2_drift_selftest() -> None:
    rc, out = run([PY, str(DRIFT), "--selftest"])
    check("check_contract_drift --selftest exits 0", rc == 0, out[-300:])
    check("check_contract_drift selftest ALL PASS", "SELFTEST: ALL PASS" in out)


def t3_filled_functional() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-filled-") as td:
        proj = Path(td)
        itd = proj / ".itd"
        itd.mkdir()
        for name in ("FORBIDDEN_CHANGES.md", "SCOPE_LOCK.md", "VERIFICATION_CONTRACT.json"):
            (itd / name).write_text((TEMPLATES / name).read_text(encoding="utf-8"),
                                    encoding="utf-8")
        script = itd / "check_contract_drift.py"
        script.write_text(DRIFT.read_text(encoding="utf-8"), encoding="utf-8")

        rc, out = run([PY, str(script), "--filled", "--strict"], cwd=proj)
        check("--filled --strict red on template scaffold", rc == 1, out[-300:])
        check("--filled names the unfilled contracts", "НЕ ЗАПОЛНЕНО" in out)

        (itd / "FORBIDDEN_CHANGES.md").write_text(
            "# Forbidden Changes\n- Никогда не трогать платёжные пути.\n", encoding="utf-8")
        (itd / "SCOPE_LOCK.md").write_text(
            "## Current Task\n- Закрыть init-дыры.\n", encoding="utf-8")
        (itd / "VERIFICATION_CONTRACT.json").write_text(
            json.dumps({"version": 1, "commands": [
                {"id": "t", "command": "make test", "timeoutSeconds": 600,
                 "expectedOutput": "", "passFailParser": "exit_code_zero"}]}),
            encoding="utf-8")
        rc, out = run([PY, str(script), "--filled", "--strict"], cwd=proj)
        check("--filled --strict green on filled contracts", rc == 0, out[-300:])


def t4_crash_pipeline() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-crashproj-") as td:
        proj = Path(td)
        sid = "vtest-" + uuid.uuid4().hex[:8]
        cp_file = Path(tempfile.gettempdir()) / f"claude-checkpoint-{sid}.json"
        try:
            # significant tool call -> checkpoint with cwd + clean_exit=false
            rc, out = run([PY, str(CRASH_HOOK)], cwd=proj,
                          stdin_text=json.dumps({"tool_name": "Edit",
                                                 "tool_input": {"file_path": "a.py"}}),
                          env_extra={"CLAUDE_SESSION_ID": sid})
            data = json.loads(cp_file.read_text(encoding="utf-8"))
            check("checkpoint records cwd", data.get("cwd") == str(proj.resolve()),
                  str(data.get("cwd")))
            check("checkpoint clean_exit=false mid-work", data.get("clean_exit") is False)

            # a DIFFERENT session's pre-flight in the same cwd surfaces it once
            rc, out = run([PY, str(PREFLIGHT)], cwd=proj, stdin_text="{}",
                          env_extra={"CLAUDE_SESSION_ID": sid + "-next"})
            check("pre-flight surfaces crash section", "Crash recovery" in out, out[-300:])
            rc, out = run([PY, str(PREFLIGHT)], cwd=proj, stdin_text="{}",
                          env_extra={"CLAUDE_SESSION_ID": sid + "-next"})
            check("crash section consumed (not repeated)", "Crash recovery" not in out)

            # Stop marks clean_exit=true; a clean checkpoint never surfaces
            cp_file.unlink()
            run([PY, str(CRASH_HOOK)], cwd=proj,
                stdin_text=json.dumps({"tool_name": "Edit", "tool_input": {}}),
                env_extra={"CLAUDE_SESSION_ID": sid})
            run([PY, str(CRASH_HOOK)], cwd=proj,
                stdin_text=json.dumps({"hook_event_name": "Stop"}),
                env_extra={"CLAUDE_SESSION_ID": sid})
            data = json.loads(cp_file.read_text(encoding="utf-8"))
            check("Stop flips clean_exit=true", data.get("clean_exit") is True)
            rc, out = run([PY, str(PREFLIGHT)], cwd=proj, stdin_text="{}",
                          env_extra={"CLAUDE_SESSION_ID": sid + "-again"})
            check("clean exit not surfaced as crash", "Crash recovery" not in out)
        finally:
            try:
                cp_file.unlink()
            except OSError:
                pass


def t5_goal_mirror_shape() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-goal-") as td:
        goal = Path(td) / "GOAL.json"
        goal.write_text(json.dumps({
            "version": 1, "goal": "Kickstarted project", "status": "active",
            "createdAt": "2026-07-08T00:00:00Z", "updatedAt": "2026-07-08T00:00:00Z",
            "currentUnitId": "U-1",
            "units": [
                {"id": "U-1", "criterion": "pytest tests/test_auth.py all passing",
                 "verificationCommand": "pytest tests/test_auth.py", "status": "pending"},
                {"id": "U-2", "criterion": "profile CRUD passing",
                 "verificationCommand": "pytest tests/test_profile.py", "status": "pending"},
            ],
        }), encoding="utf-8")
        rc, out = run([PY, str(VALIDATE_STATE), str(goal)])
        check("kickstart GOAL.json mirror validates", rc == 0, out[-300:])


def main() -> int:
    for t in (t1_init_validate_selftest, t2_drift_selftest, t3_filled_functional,
              t4_crash_pipeline, t5_goal_mirror_shape):
        t()
    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

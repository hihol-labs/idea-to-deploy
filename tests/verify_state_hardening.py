#!/usr/bin/env python3
"""verify_state_hardening.py — v1.75.0 ACID-audit state-hardening tests.

Covers the five audit fixes:
  #1 atomic writes (tmp + os.replace) for verdict / ledger trim / checkpoint;
  #2 append+trim serialized through a dedicated lock file;
  #3 persist failures logged to a bounded errors.log instead of swallowed;
  #4 state-guard.sh — immediate post-Write validation of .itd-memory ledgers
     + .active-session.lock heartbeat that never overwrites a foreign fresh lock;
  #5 reconciliation invariant STATE <-> events.jsonl (contradiction fails,
     absence warns) in validate_state_core / the CLI wrapper.

Stdlib-only, cross-platform (runs in windows-verify.yml too).
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))

import completion_lib as cl                      # noqa: E402
import validate_state_core as core               # noqa: E402

passed = 0
failed = 0


def check(name: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}")


def load_hook_module(filename: str, modname: str):
    loader = importlib.machinery.SourceFileLoader(modname, str(HOOKS / filename))
    spec = importlib.util.spec_from_loader(modname, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def make_valid_state(mem_dir: Path, unit_status: str = "in_progress") -> Path:
    schema = json.loads(
        (ROOT / "docs" / "templates" / "itd-memory" / "session-state.schema.json")
        .read_text(encoding="utf-8"))
    state: dict = {}
    for f in schema.get("requiredFields", []):
        if f in core._OBJECT_FIELDS:
            state[f] = {}
        elif f in core._LIST_FIELDS:
            state[f] = []
        else:
            state[f] = "x"
    for f in core._OBJECT_FIELDS:
        state.setdefault(f, {})
    for f in core._LIST_FIELDS:
        state.setdefault(f, [])
    state["humanSteering"] = {"approvalStatus": "approved",
                              "recommendedNextStep": "continue"}
    state["gateResults"] = {"nextStepApproval": "granted"}
    state["nextAction"] = "continue work"
    state["currentUnit"] = {"id": "U-1", "status": unit_status}
    p = mem_dir / "STATE.json"
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="itd-hardening-"))

    # ---- fix #1: atomic_write_text -------------------------------------
    target = tmp / "x.json"
    cl.atomic_write_text(target, '{"a": 1}')
    check("atomic_write_text writes readable content",
          json.loads(target.read_text(encoding="utf-8")) == {"a": 1})
    check("atomic_write_text leaves no tmp files", not list(tmp.glob("*.tmp-*")))

    # ---- fix #1+#2: append_signal trim is bounded, atomic, locked ------
    proj = tmp / "proj"
    proj.mkdir()
    old_soft, old_max = cl.LEDGER_SOFT_BYTES, cl.MAX_LEDGER_LINES
    cl.LEDGER_SOFT_BYTES, cl.MAX_LEDGER_LINES = 200, 5
    try:
        for i in range(30):
            cl.append_signal(proj, "sess-1",
                             {"kind": "static", "layer": 1, "outcome": "pass", "n": i})
    finally:
        cl.LEDGER_SOFT_BYTES, cl.MAX_LEDGER_LINES = old_soft, old_max
    ledger = cl.signals_path(proj)
    raw = ledger.read_text(encoding="utf-8")
    lines = raw.splitlines()
    check("ledger trimmed to MAX_LEDGER_LINES", 0 < len(lines) <= 5)
    ok_json = all(json.loads(l) is not None for l in lines if l.strip())
    check("every surviving ledger line is valid JSON", ok_json)
    check("ledger ends with newline (no torn tail)", raw.endswith("\n"))
    check("latest append survives the trim",
          json.loads(lines[-1]).get("n") == 29)
    check("dedicated lock file exists next to the ledger",
          (ledger.parent / (cl.SIGNALS_FILE + ".lock")).is_file())
    check("no tmp leftovers after trims",
          not list(ledger.parent.glob("*.tmp-*")))

    # ---- fix #3: persist errors observable + bounded --------------------
    cl.log_persist_error(proj, "unit-test", ValueError("boom-42"))
    errlog = cl.completion_dir(proj) / cl.ERRORS_FILE
    txt = errlog.read_text(encoding="utf-8")
    check("errors.log records where + what", "unit-test" in txt and "boom-42" in txt)
    old_b = cl.ERRORS_SOFT_BYTES
    cl.ERRORS_SOFT_BYTES = 500
    try:
        errlog.write_text("x" * 2000 + "\n", encoding="utf-8")
        cl.log_persist_error(proj, "bound-test", RuntimeError("tail"))
    finally:
        cl.ERRORS_SOFT_BYTES = old_b
    check("errors.log is bounded (tail kept)", errlog.stat().st_size <= 1100)

    # ---- fix #1: write_verdict atomic -----------------------------------
    cl.write_verdict(proj, {"ok": True, "ts": cl.now_iso()})
    check("verdict is readable JSON after atomic write",
          json.loads(cl.verdict_path(proj).read_text(encoding="utf-8")).get("ok") is True)

    # ---- fix #1: crash-recovery checkpoint atomic -----------------------
    cr = load_hook_module("crash-recovery.sh", "crash_recovery_ht")
    sid = f"hardening-{os.getpid()}"
    cp = {"session_id": sid, "tool_history": [], "call_count": 1, "clean_exit": False}
    cr.write_checkpoint(cp, sid)
    cp_path = Path(cr.checkpoint_file(sid))
    check("checkpoint written atomically and readable",
          json.loads(cp_path.read_text(encoding="utf-8")).get("call_count") == 1)
    check("no checkpoint tmp leftovers",
          not list(cp_path.parent.glob(cp_path.name + ".tmp-*")))
    try:
        cp_path.unlink()
    except OSError:
        pass

    # ---- fix #5: reconciliation STATE <-> events.jsonl --------------------
    mem = tmp / "ledger" / ".itd-memory"
    mem.mkdir(parents=True)
    state_p = make_valid_state(mem, unit_status="in_progress")
    errors, warnings = core.validate_path(state_p)
    check("valid STATE without events.jsonl -> no errors", errors == [])

    events = mem / "events.jsonl"
    events.write_text(
        json.dumps({"type": "unit", "name": "U-1", "decision": "activated"}) + "\n"
        + json.dumps({"type": "unit", "name": "U-1", "decision": "verified"}) + "\n",
        encoding="utf-8")
    errors, warnings = core.validate_path(state_p)
    check("active STATE vs verified event log -> reconciliation ERROR",
          any("reconciliation" in e for e in errors))

    make_valid_state(mem, unit_status="verified")
    events.write_text(
        json.dumps({"type": "unit", "name": "U-1", "decision": "activated"}) + "\n",
        encoding="utf-8")
    errors, warnings = core.validate_path(state_p)
    check("verified STATE with activated-only log -> WARNING, not error",
          errors == [] and len(warnings) == 1)

    # ---- fix #5: CLI wrapper contract ------------------------------------
    cli = ROOT / "scripts" / "validate_state.py"
    res = subprocess.run([sys.executable, str(cli), str(state_p)],
                         capture_output=True, text=True, timeout=30)
    check("CLI: warning case still exits 0 with OK",
          res.returncode == 0 and "OK:" in res.stdout and "WARNING:" in res.stdout)

    make_valid_state(mem, unit_status="in_progress")
    events.write_text(
        json.dumps({"type": "unit", "name": "U-1", "decision": "verified"}) + "\n",
        encoding="utf-8")
    res = subprocess.run([sys.executable, str(cli), str(state_p)],
                         capture_output=True, text=True, timeout=30)
    check("CLI: contradiction exits 1 with ERROR",
          res.returncode == 1 and "ERROR:" in res.stdout)
    events.unlink()

    # ---- fix #4: state-guard hook ----------------------------------------
    sg = load_hook_module("state-guard.sh", "state_guard_ht")
    check("is_state_ledger matches .itd-memory/STATE.json",
          sg.is_state_ledger("/w/repo/.itd-memory/STATE.json"))
    check("is_state_ledger matches windows GOAL path",
          sg.is_state_ledger(r"C:\w\repo\.itd-memory\GOAL.json"))
    check("is_state_ledger ignores ordinary files",
          not sg.is_state_ledger("/w/repo/src/state.json"))

    # heartbeat: create / refresh own, never clobber a foreign fresh lock
    memdir = tmp / "clmem"
    memdir.mkdir()
    sg.find_project_memory_dir = lambda cwd: memdir  # type: ignore[assignment]
    lock = memdir / ".active-session.lock"

    sg.heartbeat_lock(tmp, "sess-A")
    data = json.loads(lock.read_text(encoding="utf-8"))
    check("heartbeat creates the lock with our session", data.get("session") == "sess-A")

    lock.write_text(json.dumps({"timestamp": time.time(), "session": "sess-B",
                                "pid": 1, "branch": "b", "project": "p",
                                "note": "n"}), encoding="utf-8")
    sg.heartbeat_lock(tmp, "sess-A")
    data = json.loads(lock.read_text(encoding="utf-8"))
    check("heartbeat never overwrites a FOREIGN fresh lock",
          data.get("session") == "sess-B")

    lock.write_text(json.dumps({"timestamp": time.time() - 3600,
                                "session": "sess-B", "pid": 1, "branch": "b",
                                "project": "p", "note": "n"}), encoding="utf-8")
    sg.heartbeat_lock(tmp, "sess-A")
    data = json.loads(lock.read_text(encoding="utf-8"))
    check("heartbeat takes over a STALE foreign lock",
          data.get("session") == "sess-A")

    # end-to-end: hook subprocess flags an invalid ledger via additionalContext
    bad = mem / "STATE.json"
    bad_state = json.loads(bad.read_text(encoding="utf-8"))
    bad_state["nextAction"] = ""
    bad.write_text(json.dumps(bad_state), encoding="utf-8")
    payload = {"session_id": "t", "cwd": str(tmp), "tool_name": "Write",
               "tool_input": {"file_path": str(bad)}}
    env = dict(os.environ)
    env["HOME"] = str(tmp / "nohome")          # heartbeat no-ops: no ~/.claude
    env["USERPROFILE"] = str(tmp / "nohome")
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(payload), capture_output=True,
                         text=True, timeout=30, env=env)
    check("state-guard subprocess exits 0", res.returncode == 0)
    out = res.stdout or ""
    check("state-guard red-marks the invalid ledger",
          "additionalContext" in out and "FAILED" in out and "nextAction" in out)

    payload["tool_input"]["file_path"] = str(tmp / "src" / "app.py")
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(payload), capture_output=True,
                         text=True, timeout=30, env=env)
    check("state-guard stays silent on non-ledger files",
          res.returncode == 0 and "FAILED" not in (res.stdout or ""))

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

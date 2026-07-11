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
import re
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

    # v1.80.1: reconciliation reads only the TAIL of a huge events.jsonl
    # (bounded work under the 5s hook timeout); a recent decision in the
    # tail is still found, and the whole pass stays fast.
    big = mem / "events.jsonl"
    junk = json.dumps({"type": "unit", "name": "U-other", "decision": "activated"})
    with big.open("w", encoding="utf-8") as f:
        need = core.EVENTS_TAIL_BYTES * 2 // (len(junk) + 1)
        for _ in range(need):
            f.write(junk + "\n")
        f.write(json.dumps({"type": "unit", "name": "U-1",
                            "decision": "verified"}) + "\n")
    make_valid_state(mem, unit_status="in_progress")
    t0 = time.time()
    errors, warnings = core.validate_path(mem / "STATE.json")
    took = time.time() - t0
    check("huge events.jsonl: recent decision in tail still reconciles",
          any("reconciliation" in e for e in errors))
    check("huge events.jsonl: bounded pass is fast (< 3s)", took < 3)
    # восстановить состояние, ожидаемое следующим CLI-блоком:
    # STATE=verified + events c одним activated (warning-кейс)
    big.write_text(
        json.dumps({"type": "unit", "name": "U-1", "decision": "activated"}) + "\n",
        encoding="utf-8")
    make_valid_state(mem, unit_status="verified")

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
    sg.find_project_memory_dir = lambda cwd, deep=True: memdir  # type: ignore[assignment]
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

    # ================= v1.76.0 — ACID to 9 =================

    # ---- fix A2: orphan tmp removed when the WRITE itself fails ----------
    orig_fsync = os.fsync
    try:
        def _boom(fd):
            raise OSError("simulated fsync failure")
        os.fsync = _boom
        raised = False
        try:
            cl.atomic_write_text(tmp / "never.json", "x")
        except OSError:
            raised = True
        finally:
            os.fsync = orig_fsync
    finally:
        os.fsync = orig_fsync
    check("atomic_write_text raises on write/fsync failure", raised)
    check("atomic_write_text removes orphan tmp on write failure",
          not list(tmp.glob("never.json.tmp-*")))
    check("failed atomic write leaves no target", not (tmp / "never.json").exists())

    # ---- fix I2: lock-acquisition failure is LOGGED, not silent ----------
    orig_lock = cl._lock_file
    cl._LOCK_FAIL_LOGGED = False
    try:
        cl._lock_file = lambda f: False
        cl.append_signal(proj, "sess-lock", {"kind": "static", "layer": 1,
                                             "outcome": "pass"})
    finally:
        cl._lock_file = orig_lock
    txt = errlog.read_text(encoding="utf-8")
    check("lock-acquisition failure lands in errors.log",
          "append_signal.lock" in txt)

    # ---- fix C2: GOAL.json <-> events.jsonl reconciliation ---------------
    gmem = tmp / "goalrec" / ".itd-memory"
    gmem.mkdir(parents=True)
    goal_schema = json.loads(
        (ROOT / "docs" / "templates" / "itd-memory" / "goal.schema.json")
        .read_text(encoding="utf-8"))
    unit = {}
    for f in goal_schema.get("unitRequiredFields", []):
        unit[f] = "x"
    unit.update({"id": "U-1", "status": "in_progress"})
    goal_statuses = goal_schema.get("goalStatuses", ["active"])
    goal = {"goal": "test goal", "status": ("active" if "active" in goal_statuses
                                            else goal_statuses[0]),
            "units": [unit], "currentUnitId": "U-1"}
    for f in goal_schema.get("requiredFields", []):
        goal.setdefault(f, "x")
    gpath = gmem / "GOAL.json"
    gpath.write_text(json.dumps(goal, ensure_ascii=False), encoding="utf-8")
    errors, warnings = core.validate_path(gpath)
    check("valid GOAL without events.jsonl -> no errors", errors == [])

    gevents = gmem / "events.jsonl"
    gevents.write_text(
        json.dumps({"type": "unit", "name": "U-1", "decision": "verified"}) + "\n",
        encoding="utf-8")
    errors, warnings = core.validate_path(gpath)
    check("open GOAL unit vs verified event -> reconciliation ERROR",
          any("reconciliation" in e for e in errors))

    unit["status"] = "verified"
    goal["currentUnitId"] = ""
    gpath.write_text(json.dumps(goal, ensure_ascii=False), encoding="utf-8")
    gevents.write_text(
        json.dumps({"type": "unit", "name": "U-1", "decision": "activated"}) + "\n",
        encoding="utf-8")
    errors, warnings = core.validate_path(gpath)
    check("verified GOAL unit with activated-only log -> WARNING, not error",
          errors == [] and len(warnings) == 1)

    # ---- fix I1: PreToolUse single-writer gate (behavioural deny proof) --
    gate_proj = tmp / "gate"
    (gate_proj / ".itd-memory").mkdir(parents=True)
    fakehome = tmp / "gatehome"
    parts = gate_proj.resolve().parts
    memdir2 = fakehome / ".claude" / "projects" / ("-" + "-".join(parts[1:])) / "memory"
    memdir2.mkdir(parents=True)
    genv = dict(os.environ)
    genv["HOME"] = str(fakehome)
    genv["USERPROFILE"] = str(fakehome)

    (memdir2 / ".active-session.lock").write_text(json.dumps(
        {"timestamp": time.time(), "session": "other-owner", "pid": 1,
         "branch": "b", "project": str(gate_proj), "note": "n"}), encoding="utf-8")
    gsid = f"gate-{os.getpid()}"
    gpayload = {"hook_event_name": "PreToolUse", "session_id": gsid,
                "cwd": str(gate_proj), "tool_name": "Write",
                "tool_input": {"file_path": str(gate_proj / ".itd-memory" / "STATE.json")}}

    def run_gate(pl):
        return subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                              input=json.dumps(pl), capture_output=True,
                              text=True, timeout=30, env=genv)

    res = run_gate(gpayload)
    check("ledger gate DENIES on a foreign fresh owned lock (exit 2)",
          res.returncode == 2 and "permissionDecision" in res.stdout
          and "deny" in res.stdout)
    res = run_gate(gpayload)
    check("second attempt is still denied", res.returncode == 2)
    res = run_gate(gpayload)
    check("third attempt auto-allows with a warning",
          res.returncode == 0 and "auto-allow" in (res.stdout or ""))

    (memdir2 / ".active-session.lock").write_text(json.dumps(
        {"timestamp": time.time(), "pid": 1, "branch": "b",
         "project": str(gate_proj), "note": "ownerless"}), encoding="utf-8")
    gpayload["session_id"] = f"gate2-{os.getpid()}"
    res = run_gate(gpayload)
    check("ownerless legacy lock is never gated", res.returncode == 0)

    gpayload["tool_input"]["file_path"] = str(gate_proj / "src" / "x.py")
    res = run_gate(gpayload)
    check("gate ignores non-ledger writes", res.returncode == 0)

    # v1.76.1: locator resolves the REAL Claude Code munging (every non-alnum
    # char of the resolved cwd -> '-'; underscores/non-ASCII included). The
    # pre-v1.76.1 candidate missed such layouts and the gate was a silent
    # no-op — caught by the live smoke on a real Windows install.
    uproj = tmp / "und_proj"
    (uproj / ".itd-memory").mkdir(parents=True)
    munged_name = re.sub(r"[^A-Za-z0-9]", "-", str(uproj.resolve()))
    memdir3 = fakehome / ".claude" / "projects" / munged_name / "memory"
    memdir3.mkdir(parents=True)
    (memdir3 / ".active-session.lock").write_text(json.dumps(
        {"timestamp": time.time(), "session": "other-owner", "pid": 1,
         "branch": "b", "project": str(uproj), "note": "n"}), encoding="utf-8")
    upayload = {"hook_event_name": "PreToolUse", "session_id": f"und-{os.getpid()}",
                "cwd": str(uproj), "tool_name": "Write",
                "tool_input": {"file_path": str(uproj / ".itd-memory" / "STATE.json")}}
    res = run_gate(upayload)
    check("locator resolves real munged layout (underscore path) -> gate denies",
          res.returncode == 2 and "deny" in (res.stdout or ""))

    # v1.78.0: Bash pre-write gate — ledger as WRITE TARGET is denied,
    # mere co-occurrence is not (soft revalidation still covers it).
    (memdir2 / ".active-session.lock").write_text(json.dumps(
        {"timestamp": time.time(), "session": "other-owner", "pid": 1,
         "branch": "b", "project": str(gate_proj), "note": "n"}), encoding="utf-8")
    bsid = f"bashgate-{os.getpid()}"
    bpay = {"hook_event_name": "PreToolUse", "session_id": bsid,
            "cwd": str(gate_proj), "tool_name": "Bash",
            "tool_input": {"command": 'echo "{}" > .itd-memory/STATE.json'}}
    res = run_gate(bpay)
    check("Bash redirect INTO ledger is denied pre-write (exit 2)",
          res.returncode == 2 and "deny" in (res.stdout or ""))
    bpay["tool_input"]["command"] = "sed -i s/a/b/ .itd-memory/GOAL.json"
    bpay["session_id"] = f"bashgate2-{os.getpid()}"
    res = run_gate(bpay)
    check("sed -i on ledger is denied pre-write", res.returncode == 2)
    bpay["tool_input"]["command"] = "git diff .itd-memory/STATE.json > out.txt"
    res = run_gate(bpay)
    check("co-occurrence (redirect NOT into ledger) is not gated",
          res.returncode == 0 and "deny" not in (res.stdout or ""))
    bpay["tool_input"]["command"] = "cat .itd-memory/STATE.json | jq .nextAction"
    res = run_gate(bpay)
    check("read-only pipe over ledger is not gated", res.returncode == 0)
    # review v1.78.0 (important): ledger as mv/cp SOURCE is a read — not gated
    bpay["tool_input"]["command"] = "cp .itd-memory/STATE.json backup.json"
    res = run_gate(bpay)
    check("cp with ledger as SOURCE (backup) is not gated",
          res.returncode == 0 and "deny" not in (res.stdout or ""))
    bpay["tool_input"]["command"] = "mv new-state.json .itd-memory/STATE.json"
    bpay["session_id"] = f"bashgate3-{os.getpid()}"
    res = run_gate(bpay)
    check("mv INTO ledger (destination) is denied pre-write", res.returncode == 2)

    # v1.80.0: git checkout/restore with an EXPLICIT ledger path is a
    # deliberate overwrite -> hard-gated; branch switching is not.
    bpay["session_id"] = f"gitgate-{os.getpid()}"
    bpay["tool_input"]["command"] = "git checkout -- .itd-memory/STATE.json"
    res = run_gate(bpay)
    check("git checkout of ledger path is denied pre-write",
          res.returncode == 2 and "deny" in (res.stdout or ""))
    bpay["tool_input"]["command"] = "git checkout feature-branch"
    res = run_gate(bpay)
    check("git branch switch (no ledger path) is not gated", res.returncode == 0)

    # v1.81.0 (а): deleting the ledger is deny-worthy under a foreign lock
    bpay["session_id"] = f"rmgate-{os.getpid()}"
    bpay["tool_input"]["command"] = "rm .itd-memory/STATE.json"
    res = run_gate(bpay)
    check("rm of ledger file is denied pre-write",
          res.returncode == 2 and "deny" in (res.stdout or ""))
    bpay["tool_input"]["command"] = "rm -rf .itd-memory"
    res = run_gate(bpay)
    check("rm -rf of .itd-memory dir is denied pre-write", res.returncode == 2)
    bpay["tool_input"]["command"] = "rm -rf node_modules dist"
    res = run_gate(bpay)
    check("rm of unrelated dirs is not gated", res.returncode == 0)
    # review v1.81.0 (important): flags-after-path, trailing redirect, cmd.exe
    bpay["tool_input"]["command"] = "Remove-Item .itd-memory -Recurse -Force"
    bpay["session_id"] = f"rmgate2-{os.getpid()}"
    res = run_gate(bpay)
    check("Remove-Item with flags AFTER path is denied", res.returncode == 2)
    bpay["tool_input"]["command"] = "rm -rf .itd-memory/ 2>/dev/null"
    res = run_gate(bpay)
    check("rm with trailing redirect is denied", res.returncode == 2)
    bpay["tool_input"]["command"] = "rm -rf tmp/.itd-memory-backup"
    res = run_gate(bpay)
    check("neighbour name .itd-memory-backup is NOT gated (lookahead)",
          res.returncode == 0)

    # v1.78.1: PowerShell tool is the same mutation channel
    bpay["tool_name"] = "PowerShell"
    bpay["session_id"] = f"psgate-{os.getpid()}"
    bpay["tool_input"]["command"] = 'Set-Content .itd-memory/STATE.json "x"'
    res = run_gate(bpay)
    check("PowerShell Set-Content into ledger is denied pre-write",
          res.returncode == 2 and "deny" in (res.stdout or ""))
    bpay["tool_input"]["command"] = "Get-Content .itd-memory/STATE.json"
    res = run_gate(bpay)
    check("PowerShell read of ledger is not gated", res.returncode == 0)
    bpay["tool_name"] = "Bash"

    # v1.78.1: interpreter writes are caught by the SOFT leg (PostToolUse)
    ipay = {"hook_event_name": "PostToolUse", "session_id": "interp-t",
            "cwd": str(mem.parent), "tool_name": "Bash",
            "tool_input": {"command":
                "python -c \"open('.itd-memory/STATE.json','w').write('{}')\""}}
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(ipay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("python -c write near ledger triggers soft re-validation",
          res.returncode == 0 and "FAILED" in (res.stdout or ""))
    ipay["tool_input"]["command"] = "python -m json.tool .itd-memory/STATE.json"
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(ipay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("python without -c/-e near ledger stays silent",
          res.returncode == 0 and "FAILED" not in (res.stdout or ""))

    # v1.80.0: git overwrite of a ledger — soft revalidation fires
    ipay["tool_input"]["command"] = "git restore .itd-memory/STATE.json"
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(ipay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("git restore of ledger triggers soft re-validation",
          res.returncode == 0 and "FAILED" in (res.stdout or ""))

    # important review v1.80.0: BARE git checkout/reset (no ledger path in
    # the command!) must ALSO trigger soft re-validation — the working-tree
    # rewrite rolls the ledger back without ever naming it.
    ipay["tool_input"]["command"] = "git checkout feature-branch"
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(ipay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("bare git checkout triggers soft re-validation",
          res.returncode == 0 and "FAILED" in (res.stdout or ""))
    ipay["tool_input"]["command"] = "git status && git log --oneline -3"
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(ipay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("non-rewriting git (status/log) stays silent",
          res.returncode == 0 and "FAILED" not in (res.stdout or ""))

    # v1.81.0 (а): new soft tokens + git stash + missing-ledger report
    ipay["tool_input"]["command"] = "perl -i -pe s/a/b/ .itd-memory/STATE.json"
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(ipay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("perl -i on ledger triggers soft re-validation",
          res.returncode == 0 and "FAILED" in (res.stdout or ""))
    ipay["tool_input"]["command"] = "git stash"
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(ipay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("git stash triggers unconditional soft re-validation",
          res.returncode == 0 and "FAILED" in (res.stdout or ""))
    rmmem = tmp / "rmproj" / ".itd-memory"
    rmmem.mkdir(parents=True)
    rmpay = dict(ipay); rmpay["cwd"] = str(rmmem.parent)
    rmpay["tool_input"] = {"command": "rm .itd-memory/STATE.json"}
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(rmpay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("vanished ledger after rm-class command is red-marked",
          res.returncode == 0 and "FAILED" in (res.stdout or "")
          and "STATE.json" in (res.stdout or ""))
    # review v1.81.0 (critical): BARE directory deletion — no STATE.json token
    # in the command — must still be caught by the soft leg
    rmpay["tool_input"] = {"command": "rm -rf .itd-memory"}
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(rmpay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("bare rm of .itd-memory dir (dir still present) is red-marked",
          res.returncode == 0 and "FAILED" in (res.stdout or ""))
    gonepay = dict(rmpay); gonepay["cwd"] = str(tmp / "goneproj")
    (tmp / "goneproj").mkdir()
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(gonepay), capture_output=True,
                         text=True, timeout=30, env=env)
    check("vanished .itd-memory dir after deletion command is red-marked",
          res.returncode == 0 and "FAILED" in (res.stdout or ""))

    # v1.81.0 (б): shell channel heartbeats the lock too
    hb_home = tmp / "hbhome"
    # deep=False у shell-heartbeat сканирует только ПРЯМЫЕ кандидаты —
    # раскладка строится настоящим munging'ом (каждый не-alnum -> '-')
    hbmem = hb_home / ".claude" / "projects" / re.sub(
        r"[^A-Za-z0-9]", "-", str((tmp / "rmproj").resolve())) / "memory"
    hbmem.mkdir(parents=True)
    hb_env = dict(os.environ)
    hb_env["HOME"] = str(hb_home); hb_env["USERPROFILE"] = str(hb_home)
    hbpay = {"hook_event_name": "PostToolUse", "session_id": "hb-shell",
             "cwd": str(tmp / "rmproj"), "tool_name": "Bash",
             "tool_input": {"command": "echo hi"}}
    subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                   input=json.dumps(hbpay), capture_output=True,
                   text=True, timeout=30, env=hb_env)
    hb_lock = hbmem / ".active-session.lock"
    check("bare shell activity heartbeats the session lock",
          hb_lock.is_file()
          and json.loads(hb_lock.read_text(encoding="utf-8")).get("session") == "hb-shell")

    # v1.80.0: POSIX flock is non-blocking with bounded retries (symmetric
    # to the msvcrt path) — a held lock returns False fast, never hangs.
    if os.name == "posix":
        import fcntl as _fcntl
        lockp = tmp / "posix.lock"
        holder = lockp.open("a+")
        _fcntl.flock(holder.fileno(), _fcntl.LOCK_EX)
        contender = lockp.open("a+")
        t0 = time.time()
        got = cl._lock_file(contender)
        took = time.time() - t0
        check("held POSIX lock -> _lock_file gives up (False)", got is False)
        check("POSIX lock give-up is bounded (< 4s)", took < 4)
        _fcntl.flock(holder.fileno(), _fcntl.LOCK_UN)
        holder.close(); contender.close()

    # stale foreign owned lock -> allow (through the real gate subprocess)
    (memdir2 / ".active-session.lock").write_text(json.dumps(
        {"timestamp": time.time() - 3600, "session": "other-owner", "pid": 1,
         "branch": "b", "project": str(gate_proj), "note": "stale"}),
        encoding="utf-8")
    gpayload["session_id"] = f"gate3-{os.getpid()}"
    gpayload["tool_input"]["file_path"] = str(gate_proj / ".itd-memory" / "STATE.json")
    res = run_gate(gpayload)
    check("stale foreign owned lock is not gated", res.returncode == 0)

    # no memory dir at all -> allow
    genv_nomem = dict(genv)
    genv_nomem["HOME"] = str(tmp / "gatehome-empty")
    genv_nomem["USERPROFILE"] = str(tmp / "gatehome-empty")
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(gpayload), capture_output=True,
                         text=True, timeout=30, env=genv_nomem)
    check("missing memory dir is not gated", res.returncode == 0)

    # ---- fix C3: Bash-bypass detection ------------------------------------
    bpayload = {"hook_event_name": "PostToolUse", "session_id": "bash-t",
                "cwd": str(mem.parent), "tool_name": "Bash",
                "tool_input": {"command": 'printf "{}" > .itd-memory/STATE.json'}}
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(bpayload), capture_output=True,
                         text=True, timeout=30, env=env)
    check("Bash mutation of a ledger triggers re-validation (red mark)",
          res.returncode == 0 and "FAILED" in (res.stdout or ""))

    bpayload["tool_input"]["command"] = "git status && ls .itd-memory"
    res = subprocess.run([sys.executable, str(HOOKS / "state-guard.sh")],
                         input=json.dumps(bpayload), capture_output=True,
                         text=True, timeout=30, env=env)
    check("non-mutating Bash near the ledger stays silent",
          res.returncode == 0 and "FAILED" not in (res.stdout or ""))

    # ---- fix D2: pre-flight consumes persist-error logs -------------------
    pf = load_hook_module("pre-flight-check.sh", "pre_flight_ht")
    perr_proj = tmp / "perr"
    (perr_proj / ".claude" / "completion").mkdir(parents=True)
    (perr_proj / ".claude" / "completion" / "errors.log").write_text(
        "2026-07-10T00:00:00+00:00 write_verdict: OSError: disk full\n",
        encoding="utf-8")
    ctx = pf.persist_errors_context(perr_proj)
    check("pre-flight surfaces a non-empty persist-error log",
          "Persist-failure" in ctx and "write_verdict" in ctx)
    ctx2 = pf.persist_errors_context(perr_proj)
    check("persist-error surfacing is rate-limited", ctx2 == "")

    # ---- v1.84.0 P8: memory-collision guard (session_*.md) -----------------
    memp = tmp / "memcol" / "memory"
    memp.mkdir(parents=True)
    mf = memp / "session_2026-07-11_5.md"
    mf.write_text("x", encoding="utf-8")
    sidp8 = f"tP8-{int(time.time() * 1000)}"
    mctx = sg.memory_collision_context(sidp8, str(mf))
    check("P8: Write over fresh existing session memo -> warning",
          bool(mctx) and "ПАМЯТИ" in mctx)
    check("P8: repeat warning suppressed per (session,file)",
          sg.memory_collision_context(sidp8, str(mf)) is None)
    check("P8: bash mv over fresh memo -> warning",
          bool(sg.bash_memory_collision_context(sidp8 + "b", f"mv /tmp/x {mf}")))
    old_ts = time.time() - 8 * 3600
    os.utime(mf, (old_ts, old_ts))
    check("P8: old memo -> silent",
          sg.memory_collision_context(sidp8 + "c", str(mf)) is None)
    check("P8: missing memo -> silent",
          sg.memory_collision_context(
              sidp8 + "d", str(memp / "session_2026-07-11_9.md")) is None)
    check("P8: non-memory path -> silent",
          sg.memory_collision_context(sidp8 + "e", str(tmp / "notes.md")) is None)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

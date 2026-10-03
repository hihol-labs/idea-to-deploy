#!/usr/bin/env python3
"""COMPLETION-SUPERSEDE-1: a red run of an oracle is not a red layer once the
latest runner record of the same invocation is green.

The identity and the outcome of a run come from the record the runner writes
(opt-in: ITD_RUN_RECORD=1 sh skills/_shared/itd_py.sh <script> [args]), not from
the command text:

  - the runner passes the wrapped command through unchanged (exit code, stdout,
    stderr), writes <records dir>/<id>.json {id, script, args, cwd, rc, isolated,
    python, lines} and adds one stderr line `ITD-RUN <id>`; without the variable
    nothing changes;
  - the hook attaches a record to a signal only when exactly one `ITD-RUN <id>`
    line is in the output it observed, the record exists and is well-formed, and
    EVERY observed line is character for character a line of the recorded run (no
    more often than the run printed it) or one `EXIT: N` echo equal to the recorded
    code - the output of any other command of the same call, before or after the
    run, unbinds the record; a record is consumed by the first call that shows its
    id, bound or not;
  - a red signal with a record (rc != 0) is dropped when the LATEST recorded
    signal of the same invocation (script, args, isolated mode, interpreter,
    layer) is a pass with rc 0 that ran in the project root on the current HEAD
    (the project has a HEAD and the green signal names the same one).
    Superseding only removes a red.

Everything else stays red: no record, a record that is not matched, another
script, a green outside the project root, a later red, a real failing test.

Checks run against the real runner (subprocess), in-process against
hooks/completion_lib.py and through the real hooks. `--mutations` applies each
mutant to a temp copy and requires the checks to go red (every marker must occur
exactly once). `--hooks DIR --shared DIR` points the suite at another tree
(RED-first on the pre-fix code).

Run: sh skills/_shared/itd_py.sh tests/verify_completion_supersede.py [--mutations]
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / "hooks"
SHARED = REPO / "skills" / "_shared"
PRODUCER = "itd-completion-signals"
L2_CONFIG = {"l2_evidence_patterns": [
    "itd_py\\.sh\\s+(--itd-isolated\\s+)?tests/(verify|meta)_\\S+\\.py"]}

ORACLE = "sh skills/_shared/itd_py.sh tests/verify_a.py"
RED_CMD = "cd /tmp/prefix && ITD_RUN_RECORD=1 " + ORACLE + ' 2>&1 | tail -3; echo "EXIT: ${PIPESTATUS[0]}"'
GREEN_CMD = "ITD_RUN_RECORD=1 " + ORACLE + " 2>&1 | tail -2"
RED_OUT = "FAIL check one\nFAILED: 1 failed (0 passed)\n"
GREEN_OUT = "ok   check one\nPASSED: 0 failed (1 passed)\n"

# The probe script: prints what the runner must pass through and exits with the
# code named in probe.rc (default 0).
PROBE = (
    "import os, sys\n"
    "from pathlib import Path\n"
    "rc = int((Path(__file__).parent / 'probe.rc').read_text()) "
    "if (Path(__file__).parent / 'probe.rc').exists() else 0\n"
    "print('out args=%s record=%s isolated=%d' % (sys.argv[1:], "
    "os.environ.get('ITD_RUN_RECORD'), sys.flags.isolated))\n"
    "print('err line', file=sys.stderr)\n"
    "print('FAILED: 1 failed (0 passed)' if rc else 'PASSED: 0 failed (1 passed)')\n"
    "raise SystemExit(rc)\n"
)

PASS = FAIL = 0
LOG: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        LOG.append("ok   " + name)
    else:
        FAIL += 1
        LOG.append("FAIL " + name + (("  -- " + detail) if detail else ""))


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                   timeout=30, check=True)


def load_lib(hooks: Path):
    name = "completion_lib_supersede_%d" % abs(hash(str(hooks)))
    spec = importlib.util.spec_from_file_location(name, hooks / "completion_lib.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_tree(root: Path, shared: Path, repo: bool) -> None:
    """A project (repo=True) or a scratch copy with the runner and the probe."""
    root.mkdir(parents=True, exist_ok=True)
    dst = root / "skills" / "_shared"
    dst.mkdir(parents=True)
    for name in ("itd_py.sh", "itd_run_record.py"):
        if (shared / name).exists():
            shutil.copy2(shared / name, dst / name)
    (root / "tests").mkdir()
    (root / "tests" / "verify_a.py").write_text(PROBE, encoding="utf-8")
    (root / "tests" / "verify_b.py").write_text(PROBE, encoding="utf-8")
    if not repo:
        return
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t.t")
    git(root, "config", "user.name", "t")
    (root / "app.py").write_text("X = 1\n", encoding="utf-8")
    (root / ".itd").mkdir()
    (root / ".itd" / "VERIFICATION_CONTRACT.json").write_text(json.dumps(
        {"commands": [{"id": "noop", "command": "exit 0",
                       "passFailParser": "exit_code_zero", "timeoutSeconds": 30}]}),
        encoding="utf-8")
    cfg = root / ".claude" / "completion"
    cfg.mkdir(parents=True)
    (cfg / "config.json").write_text(json.dumps(L2_CONFIG), encoding="utf-8")
    git(root, "add", "app.py", ".itd/VERIFICATION_CONTRACT.json")
    git(root, "commit", "-q", "-m", "base")
    (root / "app.py").write_text("X = 2\n", encoding="utf-8")
    git(root, "add", "app.py")


def run_runner(cwd: Path, args: list, runs: Path | None, record: bool = True,
               rc: int | None = None):
    """Run the tree's own runner; returns (rc, stdout, stderr)."""
    flag = cwd / "tests" / "probe.rc"
    if rc is None:
        flag.unlink(missing_ok=True)
    else:
        flag.write_text(str(rc), encoding="utf-8")
    env = dict(os.environ)
    env.pop("ITD_RUN_RECORD", None)
    env.pop("ITD_RUN_RECORD_DIR", None)
    if record:
        env["ITD_RUN_RECORD"] = "1"
    if runs is not None:
        env["ITD_RUN_RECORD_DIR"] = str(runs)
    proc = subprocess.run(["sh", "skills/_shared/itd_py.sh", *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=60, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def run_ids(stderr: str) -> list:
    return [ln.split(" ", 1)[1] for ln in stderr.splitlines() if ln.startswith("ITD-RUN ")]


def mk_record(runs: Path, cwd: Path, rc: int, script: str = "tests/verify_a.py",
              args=(), lines=(), **override) -> str:
    """A record in the documented format, written without the runner."""
    run_id = uuid.uuid4().hex
    rec = {"id": run_id, "script": script, "args": list(args), "cwd": str(cwd), "rc": rc,
           "isolated": False, "python": "/usr/bin/python3",
           "lines": [ln for ln in lines if ln]}
    rec.update(override)
    runs.mkdir(parents=True, exist_ok=True)
    (runs / (run_id + ".json")).write_text(json.dumps(rec), encoding="utf-8")
    return run_id


def classify(cl, root: Path, command: str, stdout: str, stderr: str, i: int) -> dict:
    sig = cl.classify_bash(command, {"stdout": stdout, "stderr": stderr, "interrupted": False},
                           cwd=root)
    if sig is None:
        return {"unclassified": command}
    sig.update(session="probe", producer=PRODUCER, ts="2026-10-02T12:%02d:00+00:00" % i)
    return sig


def red(cl, root, runs, scratch, i, rc=1, script="tests/verify_a.py", cwd=None, echo=None,
        line=True, before="", after="", body=RED_OUT, **record) -> dict:
    """A red call as the Bash tool reports it: the run's stdout, then stderr."""
    run_id = mk_record(runs, cwd or scratch, rc, script=script, lines=RED_OUT.splitlines(),
                       **record)
    out = before + body + after + (("EXIT: %d\n" % rc) if echo is None else echo)
    return classify(cl, root, RED_CMD.replace("tests/verify_a.py", script), out,
                    "ITD-RUN %s\n" % run_id if line else "", i)


def green(cl, root, runs, i, cwd=None, script="tests/verify_a.py", out=GREEN_OUT, rc=0,
          **record) -> dict:
    run_id = mk_record(runs, cwd or root, rc, script=script, lines=out.splitlines(), **record)
    return classify(cl, root, GREEN_CMD.replace("tests/verify_a.py", script), out,
                    "ITD-RUN %s\n" % run_id, i)


def layer2(cl, root: Path, rows: list) -> str:
    return str(cl.compute_verdict(root, rows)["layers"]["2"]["status"])


def run_gate(hooks: Path, root: Path, rows: list | None, strict: bool, session="probe"):
    if rows is not None:
        led = root / ".claude" / "completion" / "signals.jsonl"
        led.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    payload = {"session_id": session, "cwd": str(root), "tool_name": "Bash",
               "tool_input": {"command": "git commit -m x", "description": "commit"}}
    env = dict(os.environ)
    env.pop("ITD_COMPLETION_GATE", None)
    env["ITD_COMPLETION_POLICY"] = "strict" if strict else "calibrated"
    proc = subprocess.run([sys.executable, str(hooks / "completion-gate.sh")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          timeout=120, env=env)
    try:
        out = json.loads(proc.stdout)
    except Exception:
        out = None
    if not isinstance(out, dict) or not isinstance(out.get("hookSpecificOutput"), dict):
        return "broken", "rc=%s stdout=%r stderr=%r" % (proc.returncode, proc.stdout[:120],
                                                       proc.stderr[-200:])
    hso = out["hookSpecificOutput"]
    reason = str(hso.get("permissionDecisionReason") or hso.get("additionalContext") or "")
    if hso.get("permissionDecision") == "deny":
        return "deny", reason
    if proc.returncode != 0:
        return "broken", "rc=%s %s" % (proc.returncode, reason)
    return "allow", reason


def run_signals_hook(hooks: Path, root: Path, command: str, stdout: str, stderr: str) -> bool:
    payload = {"session_id": "probe-hook", "cwd": str(root), "tool_name": "Bash",
               "tool_input": {"command": command},
               "tool_response": {"stdout": stdout, "stderr": stderr, "interrupted": False}}
    env = dict(os.environ)
    env.pop("ITD_COMPLETION_SIGNALS", None)
    proc = subprocess.run([sys.executable, str(hooks / "completion-signals.sh")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          timeout=60, env=env)
    return proc.returncode == 0


def runner_checks(shared: Path, tmp: Path) -> None:
    root = tmp / "runner-project"
    runs = tmp / "runner-runs"
    make_tree(root, shared, repo=False)
    direct = subprocess.run([sys.executable, "tests/verify_a.py", "x", "y z"], cwd=str(root),
                            capture_output=True, text=True, timeout=60,
                            env={k: v for k, v in os.environ.items() if k != "ITD_RUN_RECORD"})

    rc, out, err = run_runner(root, ["tests/verify_a.py", "x", "y z"], runs, record=False)
    check("runner: without the variable the run is byte-identical and leaves no record",
          (rc, out, err) == (direct.returncode, direct.stdout, direct.stderr)
          and not runs.exists(), "rc=%s err=%r" % (rc, err))

    rc, out, err = run_runner(root, ["tests/verify_a.py", "x", "y z"], runs)
    ids = run_ids(err)
    rec = {}
    if len(ids) == 1 and (runs / (ids[0] + ".json")).exists():
        rec = json.loads((runs / (ids[0] + ".json")).read_text(encoding="utf-8"))
    check("runner: a recorded green run keeps the exit code and stdout",
          rc == 0 and out == direct.stdout,
          "rc=%s out=%r" % (rc, out))
    check("runner: stderr is the wrapped stderr plus one final ITD-RUN line",
          len(ids) == 1 and err == direct.stderr + "ITD-RUN %s\n" % ids[0], repr(err))
    check("runner: the record names the script, the arguments, the run directory and the code",
          rec.get("id") == (ids[0] if ids else None)
          and rec.get("script") == "tests/verify_a.py" and rec.get("args") == ["x", "y z"]
          and os.path.realpath(str(rec.get("cwd"))) == os.path.realpath(str(root))
          and rec.get("rc") == 0 and rec.get("isolated") is False
          and rec.get("python") == os.path.realpath(sys.executable), repr(rec))
    check("runner: the record keeps the lines the run printed on both streams",
          sorted(rec.get("lines") or []) == sorted(
              ln for ln in (direct.stdout + direct.stderr).splitlines() if ln),
          repr(rec.get("lines")))
    if os.name == "posix":
        check("runner: the records directory and the record are private to the owner",
              bool(ids) and (runs.stat().st_mode & 0o077) == 0
              and ((runs / (ids[0] + ".json")).stat().st_mode & 0o177) == 0,
              "dir=%o" % (runs.stat().st_mode & 0o777) if runs.exists() else "no records dir")
    check("runner: the wrapped command does not inherit the variable",
          "record=None" in out, out)

    rc, out, err = run_runner(root, ["tests/verify_a.py"], runs, rc=3)
    ids = run_ids(err)
    rec = json.loads((runs / (ids[0] + ".json")).read_text(encoding="utf-8")) \
        if len(ids) == 1 and (runs / (ids[0] + ".json")).exists() else {}
    check("runner: a recorded red run keeps its exact exit code",
          rc == 3 and rec.get("rc") == 3 and "FAILED: 1 failed" in out,
          "rc=%s rec=%r" % (rc, rec))

    rc, out, err = run_runner(root, ["--itd-isolated", "tests/verify_a.py"], runs)
    ids = run_ids(err)
    rec = json.loads((runs / (ids[0] + ".json")).read_text(encoding="utf-8")) \
        if len(ids) == 1 and (runs / (ids[0] + ".json")).exists() else {}
    check("runner: the isolated mode stays isolated and is named in the record",
          rc == 0 and "isolated=1" in out and rec.get("isolated") is True,
          "%r %r" % (out, rec))

    before = len(list(runs.glob("*.json")))
    rc, out, err = run_runner(root, ["-c", "print('inline')"], runs)
    check("runner: an inline -c run is passed through without a record",
          rc == 0 and out == "inline\n" and not run_ids(err)
          and len(list(runs.glob("*.json"))) == before, "%r %r" % (out, err))

    blocked = tmp / "not-a-dir"
    blocked.write_text("x", encoding="utf-8")
    rc, out, err = run_runner(root, ["tests/verify_a.py"], blocked, rc=3)
    check("runner: a record that cannot be written changes nothing and prints no ITD-RUN line",
          rc == 3 and "FAILED: 1 failed" in out and err == "err line\n", "rc=%s %r" % (rc, err))
    signal_check(root, tmp, runs)


def signal_check(root: Path, tmp: Path, runs: Path) -> None:
    """Terminating a recorded runner terminates the wrapped command (POSIX)."""
    if os.name != "posix":
        return
    pidfile = tmp / "sleeper.pid"
    (root / "tests" / "sleeper.py").write_text(
        "import os, sys, time\nfrom pathlib import Path\n"
        "Path(sys.argv[1]).write_text(str(os.getpid()))\ntime.sleep(60)\n", encoding="utf-8")
    env = dict(os.environ, ITD_RUN_RECORD="1", ITD_RUN_RECORD_DIR=str(runs))
    proc = subprocess.Popen(["sh", "skills/_shared/itd_py.sh", "tests/sleeper.py", str(pidfile)],
                            cwd=str(root), env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    child = 0
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text(encoding="utf-8").strip():
            child = int(pidfile.read_text(encoding="utf-8"))
            break
        time.sleep(0.1)
    proc.terminate()
    try:
        proc.wait(timeout=15)
        ended = True
    except subprocess.TimeoutExpired:
        ended = False
        proc.kill()
        proc.wait()
    gone = False
    for _ in range(50):
        try:
            os.kill(child, 0)
        except OSError:
            gone = True
            break
        time.sleep(0.1)
    if child and not gone:
        os.kill(child, 9)
    check("runner: terminating a recorded run terminates the wrapped command",
          bool(child) and ended and gone, "child=%s ended=%s gone=%s" % (child, ended, gone))


def judge_checks(hooks: Path, shared: Path, tmp: Path) -> None:
    cl = load_lib(hooks)
    root = tmp / "project"
    scratch = tmp / "prefix"
    runs = tmp / "runs"
    make_tree(root, shared, repo=True)
    make_tree(scratch, shared, repo=False)
    os.environ["ITD_RUN_RECORD_DIR"] = str(runs)

    def status(rows):
        return layer2(cl, root, rows)

    def gates(rows):
        return run_gate(hooks, root, rows, False)[0], run_gate(hooks, root, rows, True)

    # --- the baseline that must stay red -----------------------------------
    plain_red = classify(cl, root, RED_CMD, RED_OUT + "EXIT: 1\n", "", 1)
    plain_green = classify(cl, root, GREEN_CMD, GREEN_OUT, "", 2)
    check("baseline: the probe commands are layer-2 signals",
          plain_red.get("layer") == 2 and plain_red.get("outcome") == "fail"
          and plain_green.get("outcome") == "pass", repr(plain_red))
    check("a red without a runner record blocks even after a green of another command text",
          status([plain_red, plain_green]) == "fail")
    check("a real failing test recorded in the project root blocks",
          status([green(cl, root, runs, 1), red(cl, root, runs, scratch, 2, cwd=root)]) == "fail")

    # --- the supersede ------------------------------------------------------
    rows = [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2)]
    check("the hook attaches the record to the signal",
          isinstance(rows[0].get("run"), dict) and rows[0]["run"].get("rc") == 1
          and rows[0]["run"].get("script") == "tests/verify_a.py"
          and "lines" not in rows[0]["run"], repr(rows[0].get("run")))
    check("a red one-off run is superseded by a later green record of the same invocation",
          status(rows) == "pass", status(rows))
    calibrated, (strict, reason) = gates(rows)
    check("the gate allows the commit after the supersede (calibrated)", calibrated == "allow")
    check("the gate allows the commit after the supersede (strict)", strict == "allow", reason)
    check("superseding does not rewrite the red signal",
          rows[0].get("outcome") == "fail")
    rows = [green(cl, root, runs, 1), red(cl, root, runs, scratch, 2), green(cl, root, runs, 3)]
    check("a mutation run after a green is superseded by the next green run",
          status(rows) == "pass", status(rows))
    rows = [red(cl, root, runs, root, 1, cwd=root), green(cl, root, runs, 2)]
    check("a red in the project root is superseded by a later green of the same invocation",
          status(rows) == "pass", status(rows))
    # the output may be cut by `tail`/`grep` and merged by `2>&1`: still the run's own lines
    one = mk_record(runs, scratch, 1, lines=RED_OUT.splitlines())
    merged = classify(cl, root, RED_CMD,
                      "FAILED: 1 failed (0 passed)\nITD-RUN %s\nEXIT: 1\n" % one, "", 1)
    check("a cut and merged output of the run still binds the record",
          isinstance(merged.get("run"), dict) and status([merged, green(cl, root, runs, 2)]) == "pass",
          repr(merged.get("run")))

    # --- what must still block ----------------------------------------------
    def blocks(name, rows):
        calibrated, (strict, _reason) = gates(rows)
        check(name, status(rows) == "fail" and calibrated == "deny" and strict == "deny",
              "layer=%s calibrated=%s strict=%s" % (status(rows), calibrated, strict))

    blocks("a later red record of the same invocation blocks",
           [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2),
            red(cl, root, runs, scratch, 3)])
    blocks("a green record of another script does not supersede",
           [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2, script="tests/verify_b.py")])
    blocks("a green record with other arguments does not supersede",
           [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2, args=["--fast"])])
    blocks("a green record of the non-isolated mode does not supersede an isolated red",
           [red(cl, root, runs, scratch, 1, isolated=True), green(cl, root, runs, 2)])
    blocks("a green record of another interpreter does not supersede",
           [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2, python="/opt/other/python3")])
    blocks("a green record outside the project root does not supersede",
           [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2, cwd=scratch)])
    blocks("a green without a record does not supersede a recorded red",
           [red(cl, root, runs, scratch, 1), plain_green])
    blocks("a recorded green does not supersede a red without the ITD-RUN line",
           [red(cl, root, runs, scratch, 1, line=False), green(cl, root, runs, 2)])
    blocks("a recorded green whose own outcome is not a pass does not supersede",
           [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2, out="no summary line\n")])
    blocks("a record with a non-zero code does not supersede",
           [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2, rc=1)])
    blocks("a red whose record says exit 0 is not explained by the run",
           [red(cl, root, runs, scratch, 1, rc=0, echo=""), green(cl, root, runs, 2)])
    # the whole observed output must belong to the recorded run
    blocks("another command AFTER the run in the same call unbinds the record",
           [red(cl, root, runs, scratch, 1, after="3 failed\n"), green(cl, root, runs, 2)])
    blocks("another command BEFORE the run in the same call unbinds the record",
           [red(cl, root, runs, scratch, 1, before="3 failed\n"), green(cl, root, runs, 2)])
    blocks("a line repeated more often than the run printed it unbinds the record",
           [red(cl, root, runs, scratch, 1, after="FAILED: 1 failed (0 passed)\n"),
            green(cl, root, runs, 2)])
    blocks("a line that differs from the run's line only by whitespace unbinds the record",
           [red(cl, root, runs, scratch, 1, body="FAIL check one\n  FAILED: 1 failed (0 passed)\n"),
            green(cl, root, runs, 2)])
    blocks("a whitespace-only line of another command unbinds the record",
           [red(cl, root, runs, scratch, 1, after="   \n"), green(cl, root, runs, 2)])
    blocks("an exit echo that differs from the recorded code unbinds the record",
           [red(cl, root, runs, scratch, 1, echo="EXIT: 2\n"), green(cl, root, runs, 2)])
    blocks("an exit echo in another spelling unbinds the record",
           [red(cl, root, runs, scratch, 1, echo="RUN_EXIT=1\n"), green(cl, root, runs, 2)])
    long_echo = red(cl, root, runs, scratch, 1, echo="EXIT: " + "9" * 5000 + "\n")
    check("an exit echo with a very long number is rejected without an error",
          "run" not in long_echo and long_echo.get("outcome") == "fail", repr(long_echo.get("run")))
    joint = mk_record(runs, scratch, 1, lines=RED_OUT.splitlines())
    joined = classify(cl, root, RED_CMD, RED_OUT + "EXIT: 1\n", "ITD-RUN %s\n" % joint, 1)
    check("the empty line where the host joins stdout and stderr does not unbind the record",
          isinstance(joined.get("run"), dict), repr(joined.get("run")))
    blocks("a second exit echo unbinds the record",
           [red(cl, root, runs, scratch, 1, echo="EXIT: 1\nEXIT: 1\n"), green(cl, root, runs, 2)])

    # a missing record, two ids in one call, a replayed id, a malformed record
    ghost = classify(cl, root, RED_CMD, RED_OUT + "EXIT: 1\n",
                     "ITD-RUN %s\n" % uuid.uuid4().hex, 1)
    blocks("an ITD-RUN line without a record file is not a record",
           [ghost, green(cl, root, runs, 2)])
    one = mk_record(runs, scratch, 1, lines=RED_OUT.splitlines())
    two = mk_record(runs, scratch, 1, lines=RED_OUT.splitlines())
    double = classify(cl, root, RED_CMD, RED_OUT, "ITD-RUN %s\nITD-RUN %s\n" % (one, two), 1)
    blocks("two ITD-RUN lines in one call are not a record",
           [double, green(cl, root, runs, 2)])
    again = [classify(cl, root, RED_CMD, RED_OUT, "ITD-RUN %s\n" % rid, 3) for rid in (one, two)]
    check("both records shown by a two-id call are consumed and cannot be replayed",
          not (runs / (one + ".json")).exists() and not (runs / (two + ".json")).exists()
          and all("run" not in sig for sig in again), repr([sig.get("run") for sig in again]))
    first = green(cl, root, runs, 1)
    replay_id = (first.get("run") or {}).get("id", uuid.uuid4().hex)
    replay = classify(cl, root, GREEN_CMD, GREEN_OUT, "ITD-RUN %s\n" % replay_id, 3)
    check("a record is consumed by the first call that shows its id",
          isinstance(first.get("run"), dict) and "run" not in replay
          and not (runs / (replay_id + ".json")).exists(), repr(replay.get("run")))
    spoiled = mk_record(runs, scratch, 1, lines=RED_OUT.splitlines())
    noisy = classify(cl, root, RED_CMD, RED_OUT + "3 failed\n", "ITD-RUN %s\n" % spoiled, 1)
    retry = classify(cl, root, RED_CMD, RED_OUT, "ITD-RUN %s\n" % spoiled, 2)
    check("a record shown by a call with foreign output is consumed and cannot be replayed",
          "run" not in noisy and "run" not in retry
          and not (runs / (spoiled + ".json")).exists(), repr(retry.get("run")))
    blocks("a replayed ITD-RUN line does not supersede a later red",
           [first, red(cl, root, runs, scratch, 2), replay])
    for label, override in (("args that are not a list", {"args": "x"}),
                            ("a code that is not an integer", {"rc": "1"}),
                            ("a foreign id", {"id": uuid.uuid4().hex}),
                            ("an empty script", {"script": ""}),
                            ("a mode that is not a boolean", {"isolated": "no"}),
                            ("lines that are not a list", {"lines": "FAILED"}),
                            ("a run directory that is not a string", {"cwd": 7}),
                            ("an empty run directory", {"cwd": ""}),
                            ("an interpreter that is not a string", {"python": None}),
                            ("an argument that is not a string", {"args": [1]}),
                            ("a line that is not a string", {"lines": ["FAILED: 1 failed (0 passed)", 2]}),
                            ("a missing code", {"rc": None}),
                            ("a boolean code", {"rc": True})):
        bad_id = uuid.uuid4().hex
        rec = {"id": bad_id, "script": "tests/verify_a.py", "args": [], "cwd": str(scratch),
               "rc": 1, "isolated": False, "python": "/usr/bin/python3",
               "lines": RED_OUT.splitlines()}
        rec.update(override)
        (runs / (bad_id + ".json")).write_text(json.dumps(rec), encoding="utf-8")
        bad = classify(cl, root, RED_CMD, RED_OUT + "EXIT: 1\n", "ITD-RUN %s\n" % bad_id, 1)
        blocks("a malformed record (%s) is not a record" % label,
               [bad, green(cl, root, runs, 2)])
    for label, payload in (("invalid JSON", "{not json"),
                           ("truncated JSON", '{"id": "x", "script": "tests/verify_a.py"'),
                           ("a JSON list", "[]"),
                           ("an empty file", "")):
        bad_id = uuid.uuid4().hex
        (runs / (bad_id + ".json")).write_text(payload, encoding="utf-8")
        bad = classify(cl, root, RED_CMD, RED_OUT + "EXIT: 1\n", "ITD-RUN %s\n" % bad_id, 1)
        blocks("a corrupted record file (%s) is not a record" % label,
               [bad, green(cl, root, runs, 2)])
    missing_id = uuid.uuid4().hex
    rec = {"id": missing_id, "script": "tests/verify_a.py", "args": [], "cwd": str(scratch),
           "rc": 1, "isolated": False, "python": "/usr/bin/python3",
           "lines": RED_OUT.splitlines()}
    for field in ("script", "args", "cwd", "rc", "isolated", "python", "lines"):
        bad_id = uuid.uuid4().hex
        broken = dict(rec, id=bad_id)
        broken.pop(field)
        (runs / (bad_id + ".json")).write_text(json.dumps(broken), encoding="utf-8")
        bad = classify(cl, root, RED_CMD, RED_OUT + "EXIT: 1\n", "ITD-RUN %s\n" % bad_id, 1)
        blocks("a record without the field %s is not a record" % field,
               [bad, green(cl, root, runs, 2)])

    # a duplicated id inside the ledger, a green of a stale HEAD, a green of another layer
    rows = [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2)]
    dup = dict(rows[1], ts="2026-10-02T12:09:00+00:00")
    blocks("a ledger row that repeats a run id is not a second record",
           [rows[1], red(cl, root, runs, scratch, 3), dup])
    counted = getattr(cl, "counted_signals", lambda _cwd, signals: signals)
    rows = [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2)]
    rows[1]["head"] = "0" * 40
    check("a green recorded on another HEAD does not supersede",
          rows[0] in counted(root, rows), "red dropped by a stale green")
    rows = [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2)]
    rows[1].pop("head", None)
    check("a green without a HEAD does not supersede",
          rows[0] in counted(root, rows), "red dropped by a green that names no HEAD")
    plain = tmp / "not-a-repo"
    plain.mkdir()
    rows = [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2, cwd=plain)]
    rows[1].pop("head", None)
    check("a project without a HEAD supersedes nothing",
          rows[0] in counted(plain, rows), "red dropped although the project has no HEAD")
    rows = [red(cl, root, runs, scratch, 1), green(cl, root, runs, 2)]
    rows[1]["layer"] = 1
    check("a green classified as another layer does not supersede",
          rows[0] in counted(root, rows), "red dropped by a green of another layer")

    # --- end to end: the real runner and the real hooks ---------------------
    cmd_red = "cd %s && ITD_RUN_RECORD=1 %s; echo \"EXIT: $?\"" % (scratch, ORACLE)
    cmd_green = "ITD_RUN_RECORD=1 " + ORACLE

    def real_red(extra_stdout=""):
        rc, out, err = run_runner(scratch, ["tests/verify_a.py"], runs, rc=1)
        return rc == 1 and run_signals_hook(hooks, root, cmd_red,
                                            out + extra_stdout + "EXIT: 1\n", err)

    def real_green():
        rc, out, err = run_runner(root, ["tests/verify_a.py"], runs)
        return rc == 0 and run_signals_hook(hooks, root, cmd_green, out, err)

    ok = real_red() and real_green()
    verdict, reason = run_gate(hooks, root, None, False, session="probe-hook")
    check("end to end: runner records, the signals hook binds them, the gate allows",
          ok and verdict == "allow", "%s %s" % (verdict, reason[:200]))
    real_red()
    verdict, _reason = run_gate(hooks, root, None, False, session="probe-hook")
    check("end to end: a new red run of the same oracle blocks again", verdict == "deny", verdict)
    ok = real_green()
    verdict, _reason = run_gate(hooks, root, None, False, session="probe-hook")
    check("end to end: the next green run supersedes it again", ok and verdict == "allow", verdict)
    ok = real_red(extra_stdout="3 failed\n") and real_green()
    verdict, _reason = run_gate(hooks, root, None, False, session="probe-hook")
    check("end to end: a failing command after the recorded run keeps the call red",
          ok and verdict == "deny", verdict)


def suite(hooks: Path, shared: Path) -> None:
    saved = os.environ.get("ITD_RUN_RECORD_DIR")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(os.path.realpath(tmp))
            runner_checks(shared, tmp_path)
            judge_checks(hooks, shared, tmp_path)
    finally:
        if saved is None:
            os.environ.pop("ITD_RUN_RECORD_DIR", None)
        else:
            os.environ["ITD_RUN_RECORD_DIR"] = saved


# name -> (tree, file, unique marker, replacement)
MUTANTS = {
    "runner ignores the variable": (
        "shared", "itd_py.sh", '[ "${ITD_RUN_RECORD:-}" = "1" ]', '[ "${ITD_RUN_RECORD:-}" = "never" ]'),
    "recorder loses the exit code": (
        "shared", "itd_run_record.py", "    rc = proc.wait()\n", "    proc.wait()\n    rc = 0  # MUTANT\n"),
    "recorder alters the output": (
        "shared", "itd_run_record.py", "            dst.write(chunk)\n", "            dst.write(chunk.upper())\n"),
    "recorder leaks the variable": (
        "shared", "itd_run_record.py", 'env.pop("ITD_RUN_RECORD", None)', "pass  # MUTANT"),
    "recorder records inline runs": (
        "shared", "itd_run_record.py", "if not os.path.isfile(args[0]):", "if False:"),
    "recorder prints the id without a record": (
        "shared", "itd_run_record.py", "    os.replace(tmp, path)\n", "    os.unlink(tmp)  # MUTANT\n"),
    "recorder loses the mode": (
        "shared", "itd_run_record.py", '"rc": rc, "isolated": isolated,', '"rc": rc, "isolated": False,'),
    "recorder loses the lines": (
        "shared", "itd_run_record.py", "out_tail.lines() + err_tail.lines())", "[])"),
    "recorder does not forward signals": (
        "shared", "itd_run_record.py", "            proc.send_signal(signum)\n", "            pass  # MUTANT\n"),
    "two ids accepted": (
        "hooks", "completion_lib.py", "    if len(ids) != 1 or ids[0] not in shown:\n",
        "    if not ids or ids[0] not in shown:\n"),
    "foreign line accepted": (
        "hooks", "completion_lib.py", "            return None\n        echoes += 1\n",
        "            continue\n        echoes += 1\n"),
    "line count ignored": (
        "hooks", "completion_lib.py", "        if budget.get(ln, 0) > 0:\n", "        if ln in budget:\n"),
    "exit echo not compared": (
        "hooks", "completion_lib.py", "or int(m.group(1)) != rec[\"rc\"]:", "or False:"),
    "any exit echo spelling accepted": (
        "hooks", "completion_lib.py", '_RUN_EXIT_ECHO_RE = re.compile(r"^EXIT: ([0-9]{1,3})$")',
        '_RUN_EXIT_ECHO_RE = re.compile(r"^(?:[A-Z][A-Z0-9_]*_)?EXIT\\s*[:=]\\s*(\\d+)$", re.I)'),
    "unbounded exit echo": (
        "hooks", "completion_lib.py", 'r"^EXIT: ([0-9]{1,3})$"', 'r"^EXIT: ([0-9]+)$"'),
    "second exit echo accepted": (
        "hooks", "completion_lib.py", "if m is None or echoes or", "if m is None or False or"),
    "record not consumed": (
        "hooks", "completion_lib.py", "            path.unlink()\n", "            pass  # MUTANT\n"),
    "record survives a failed binding": (
        "hooks", "completion_lib.py", "    for run_id in set(ids):\n",
        "    for run_id in (set(ids) if len(ids) == 1 and len(lines) < 4 else ()):\n"),
    "lines compared after stripping": (
        "hooks", "completion_lib.py", "lines = [ln for ln in (text or \"\").splitlines() if ln]",
        "lines = [ln.strip() for ln in (text or \"\").splitlines() if ln.strip()]"),
    "record readable by others": (
        "shared", "itd_run_record.py", "os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)",
        "os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)"),
    "records directory open to others": (
        "shared", "itd_run_record.py", "    os.chmod(directory, 0o700)", "    os.chmod(directory, 0o755)"),
    "record id not checked": (
        "hooks", "completion_lib.py", "and rec[\"id\"] == run_id", "and True"),
    "ledger id repeat counted": (
        "hooks", "completion_lib.py", "or s[\"run\"][\"id\"] in seen", "or False"),
    "green outside the root supersedes": (
        "hooks", "completion_lib.py", "and _real(s[\"run\"][\"cwd\"]) == root", "and True"),
    "non-pass green supersedes": (
        "hooks", "completion_lib.py", "green = (s.get(\"outcome\") == \"pass\"", "green = (True"),
    "non-zero green supersedes": (
        "hooks", "completion_lib.py", "and s[\"run\"][\"rc\"] == 0", "and True"),
    "stale green supersedes": (
        "hooks", "completion_lib.py", "and bool(head) and s.get(\"head\") == head)", "and True)"),
    "green without a HEAD supersedes": (
        "hooks", "completion_lib.py", "and bool(head) and s.get(\"head\")", "and bool(head) and s.get(\"head\", head)"),
    "project without a HEAD supersedes": (
        "hooks", "completion_lib.py", "bool(head) and s.get(\"head\") == head)", "s.get(\"head\", \"\") == head)"),
    "latest record ignored": (
        "hooks", "completion_lib.py", "and latest[key]):", "and True):"),
    "red with rc 0 superseded": (
        "hooks", "completion_lib.py", "and s[\"run\"][\"rc\"] != 0", "and True"),
    "any key supersedes": (
        "hooks", "completion_lib.py", "return (run[\"script\"], tuple(run[\"args\"]),",
        "return (\"x\", (),"),
    "mode not in the key": (
        "hooks", "completion_lib.py", "run[\"isolated\"], ", "False, "),
    "interpreter not in the key": (
        "hooks", "completion_lib.py", " run[\"python\"],", " \"\","),
    "layer not in the key": (
        "hooks", "completion_lib.py", "            sig.get(\"layer\"))", "            None)"),
    "verdict ignores the supersede": (
        "hooks", "completion_lib.py", "    signals = counted_signals(cwd, signals)\n", ""),
    "strict path ignores the supersede": (
        "hooks", "completion-gate.sh", "runtime_evidence_status(cl.counted_signals(cwd, signals), policy)",
        "runtime_evidence_status(signals, policy)"),
}


def run_mutations() -> int:
    global PASS, FAIL, LOG
    survived = []
    for name, (tree, fname, marker, replacement) in MUTANTS.items():
        with tempfile.TemporaryDirectory() as tmp:
            hooks = Path(tmp) / "hooks"
            shared = Path(tmp) / "shared"
            shutil.copytree(HOOKS, hooks, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(SHARED, shared, ignore=shutil.ignore_patterns("__pycache__"))
            target = (hooks if tree == "hooks" else shared) / fname
            text = target.read_text(encoding="utf-8")
            count = text.count(marker)
            if count != 1:
                print("FAIL mutation %s: marker occurs %d times in %s" % (name, count, fname))
                survived.append(name)
                continue
            target.write_text(text.replace(marker, replacement), encoding="utf-8")
            PASS = FAIL = 0
            LOG = []
            try:
                suite(hooks, shared)
            except Exception as exc:  # a mutant that crashes the suite is killed
                FAIL += 1
                LOG.append("FAIL crashed: %r" % (exc,))
            if FAIL:
                print("ok   mutation %s killed (%d checks red)" % (name, FAIL))
            else:
                print("FAIL mutation %s survived" % name)
                survived.append(name)
    if survived:
        print("FAILED: %d of %d mutations survived" % (len(survived), len(MUTANTS)))
        return 1
    print("PASSED: 0 failed (%d mutations killed)" % len(MUTANTS))
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if "--mutations" in argv:
        return run_mutations()
    hooks = Path(argv[argv.index("--hooks") + 1]).resolve() if "--hooks" in argv else HOOKS
    shared = Path(argv[argv.index("--shared") + 1]).resolve() if "--shared" in argv else SHARED
    suite(hooks, shared)
    for line in LOG:
        print(line)
    if FAIL:
        print("FAILED: %d failed (%d passed)" % (FAIL, PASS))
        return 1
    print("PASSED: 0 failed (%d passed)" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())

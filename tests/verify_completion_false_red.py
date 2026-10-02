#!/usr/bin/env python3
"""COMPLETION-FALSE-RED-1: the declared exit 2 of
`scripts/itd_stop_rule.py --check-binding` is not a red test layer.

The form is one literal (owner decision after the stop rule
REDESIGN_OR_DISCARD - parsing arbitrary shell broke on every review round):

    sh skills/_shared/itd_py.sh scripts/itd_stop_rule.py --check-binding; echo "EXIT: $?"[; ...]

and the script proves it ran: exactly one `BINDING <STATE>` line precedes the
only `EXIT: N` line. Then the `EXIT: 2` line is cut before the outcome is
computed. Every other form - another code, another script, extra arguments,
another interpreter, a redirect, a prefix, `&&`/`||`, a missing script file, no
or a late BINDING line, a second EXIT line - stays red as before.

Checks run in-process against hooks/completion_lib.py and through the real hooks
(completion-gate.sh in calibrated and strict mode, completion-signals.sh).
`--mutations` applies each mutant to a temp copy of hooks/ and requires the
checks to go red (every marker must occur exactly once).

Run: sh skills/_shared/itd_py.sh tests/verify_completion_false_red.py [--mutations]
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / "hooks"
PRODUCER = "itd-completion-signals"

CB = "sh skills/_shared/itd_py.sh scripts/itd_stop_rule.py --check-binding"
ECHO = 'echo "EXIT: $?"'
AGG = "sh skills/_shared/itd_py.sh tests/verify_stop_rule.py 2>&1 | tail -1"
OUT_AGG = "RESULT: 593 passed, 0 failed"
OUT_AGG_RED = "FAILED: 3 failed (590 passed)"
BIND = "BINDING   NO_ACTIVE_UNIT\n  WHY: no active unit\n"

OK = (CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
OK_ALONE = (CB + "; " + ECHO, "BINDING   ROUTE_DEFECT\nEXIT: 2")
ZERO = (CB + "; " + ECHO + "; " + AGG, "BINDING   ALIGNED\nEXIT: 0\n" + OUT_AGG)
CODE_1 = (CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 1\n" + OUT_AGG)
NO_BINDING = (CB + "; " + ECHO + "; " + AGG,
              "STOP-RULE INPUT REJECTED: ledger is malformed\nEXIT: 2\n" + OUT_AGG)
LATE_BINDING = (CB + "; " + ECHO + "; " + AGG, "EXIT: 2\nBINDING   NO_ACTIVE_UNIT\n" + OUT_AGG)
TWO_BINDINGS = (CB + "; " + ECHO + "; " + AGG,
                "BINDING   ALIGNED\nBINDING   ROUTE_DEFECT\nEXIT: 2\n" + OUT_AGG)
TWO_EXITS = (CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 2\nTSC_EXIT=2\n" + OUT_AGG)
GLUED = (CB + "; " + ECHO + "; " + AGG, BIND + "check failed: kaboom EXIT: 2\n" + OUT_AGG)
REAL_FAIL_AFTER = (CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG_RED)
REDIRECTED = (CB + " > /dev/null 2>&1; " + ECHO + "; " + AGG, "EXIT: 2\n" + OUT_AGG)
OTHER_SCRIPT = ("sh skills/_shared/itd_py.sh scripts/itd_other.py --check-binding; " + ECHO + "; " + AGG,
                BIND + "EXIT: 2\n" + OUT_AGG)
EXTRA_ARG = (CB + " --bogus; " + ECHO + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
BASH_INTERP = ("bash skills/_shared/itd_py.sh scripts/itd_stop_rule.py --check-binding; " + ECHO
               + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
PREFIX_CD = ("cd /tmp; " + CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
PREFIX_ENV = ("PATH=/tmp/shim:$PATH " + CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
WRAPPED = ("timeout 5 " + CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
AND_ECHO = (CB + " && " + ECHO + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
OR_ECHO = (CB + " || " + ECHO + "; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
PRINTF = (CB + '; printf "EXIT: $?\\n"; ' + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
SINGLE_QUOTED = (CB + "; echo 'EXIT: $?'; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
TRAILING_EXIT = (CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 2 (suite crashed)\n" + OUT_AGG)
SECOND_RC = (CB + "; " + ECHO + "; " + AGG + '; echo "rc=$?"', BIND + "EXIT: 2\n" + OUT_AGG + "\nrc=1")
SILENT_TAIL = (CB + "; " + ECHO + "; sh skills/_shared/itd_py.sh tests/verify_x.py",
               BIND + "EXIT: 2\npython3: can't open file 'tests/verify_x.py'")
EMPTY_TAIL = (CB + "; " + ECHO + "; " + AGG, BIND + "EXIT: 2\n")
FAKE_TAIL = (CB + "; " + ECHO + "; false; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
NEWLINE_SEP = (CB + "\n" + ECHO + "\n" + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
SPACED_SEP = (CB + " ;  " + ECHO + " ; " + AGG, BIND + "EXIT: 2\n" + OUT_AGG)
FAKE_STATE = (CB + "; " + ECHO + "; " + AGG, "BINDING   ROUTE_DEFECT\nEXIT: 2\n" + OUT_AGG)
SECOND_ECHO = (CB + "; " + ECHO + "; " + AGG + "; " + ECHO, BIND + "EXIT: 2\n" + OUT_AGG + "\nEXIT: 0")

L2_CONFIG = {"l2_evidence_patterns": [
    "tests/run-all\\.sh",
    "itd_py\\.sh\\s+(--itd-isolated\\s+)?tests/(verify|meta)_\\S+\\.py"]}

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
    name = "completion_lib_probe_%d" % abs(hash(str(hooks)))
    spec = importlib.util.spec_from_file_location(name, hooks / "completion_lib.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REAL_CHECK = 'print("BINDING   NO_ACTIVE_UNIT")\nprint("  WHY: no active unit")\nraise SystemExit(2)\n'
ZERO_CHECK = 'print("BINDING   NO_ACTIVE_UNIT")\nraise SystemExit(0)\n'
ONE_CHECK = 'print("BINDING   NO_ACTIVE_UNIT")\nraise SystemExit(1)\n'


def make_repo(root: Path, with_script: bool = True, check_source: str = REAL_CHECK) -> None:
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
    if with_script:
        (root / "scripts").mkdir()
        (root / "scripts" / "itd_stop_rule.py").write_text(check_source, encoding="utf-8")
    git(root, "add", "app.py", ".itd/VERIFICATION_CONTRACT.json")
    git(root, "commit", "-q", "-m", "base")
    (root / "app.py").write_text("X = 2\n", encoding="utf-8")
    git(root, "add", "app.py")


def classify(cl, root: Path, case, i: int = 0) -> dict:
    command, output = case
    sig = cl.classify_bash(command, {"stdout": output, "stderr": "", "interrupted": False}, cwd=root)
    if sig is None:
        return {"unclassified": command}
    sig.update(session="probe", producer=PRODUCER, ts="2026-10-02T12:%02d:00+00:00" % i)
    return sig


def outcome(cl, root: Path, case) -> str:
    return str(classify(cl, root, case).get("outcome") or "unclassified")


def run_gate(hooks: Path, root: Path, rows: list, strict: bool):
    led = root / ".claude" / "completion" / "signals.jsonl"
    led.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    payload = {"session_id": "probe", "cwd": str(root), "tool_name": "Bash",
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


def run_signals_hook(hooks: Path, root: Path, command: str, output: str) -> str:
    payload = {"session_id": "probe-hook", "cwd": str(root), "tool_name": "Bash",
               "tool_input": {"command": command},
               "tool_response": {"stdout": output, "stderr": "", "interrupted": False}}
    env = dict(os.environ)
    env.pop("ITD_COMPLETION_SIGNALS", None)
    proc = subprocess.run([sys.executable, str(hooks / "completion-signals.sh")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          timeout=60, env=env)
    try:
        out = json.loads(proc.stdout)
    except Exception:
        out = None
    if proc.returncode != 0 or not isinstance(out, dict) \
            or not isinstance(out.get("hookSpecificOutput"), dict):
        return "BROKEN rc=%s %r %r" % (proc.returncode, proc.stdout[:120], proc.stderr[-200:])
    return str(out["hookSpecificOutput"].get("additionalContext") or "")


def suite(hooks: Path) -> None:
    cl = load_lib(hooks)
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bare, \
            tempfile.TemporaryDirectory() as zero_tmp, tempfile.TemporaryDirectory() as one_tmp:
        root = Path(tmp)
        make_repo(root)
        no_script = Path(bare)
        make_repo(no_script, with_script=False)
        zero = Path(zero_tmp)
        make_repo(zero, check_source=ZERO_CHECK)
        one = Path(one_tmp)
        make_repo(one, check_source=ONE_CHECK)

        ok = classify(cl, root, OK)
        check("declared-exit-2-is-not-red", ok.get("outcome") == "pass", json.dumps(ok)[:300])
        check("declared-exit-is-recorded",
              ok.get("expected_exit") == [{"script": "scripts/itd_stop_rule.py", "code": 2}],
              json.dumps(ok)[:300])
        alone = classify(cl, root, OK_ALONE)
        # Без оракула рядом команда не L2-сигнал вовсе; главное - не красный.
        check("declared-exit-2-alone-is-not-red", alone.get("outcome") != "fail",
              json.dumps(alone)[:300])
        check("exit-0-of-the-check-stays-green", outcome(cl, root, ZERO) == "pass")

        for label, case in [
            ("unexpected-code", CODE_1),
            ("no-binding-line (input rejected)", NO_BINDING),
            ("binding-line-after-exit", LATE_BINDING),
            ("two-binding-lines", TWO_BINDINGS),
            ("second-exit-line", TWO_EXITS),
            ("marker-glued-to-a-diagnostic", GLUED),
            ("redirected-check (not the literal)", REDIRECTED),
            ("another-script", OTHER_SCRIPT),
            ("extra-argument (usage error)", EXTRA_ARG),
            ("another-interpreter", BASH_INTERP),
            ("cd-before-the-check", PREFIX_CD),
            ("env-prefix", PREFIX_ENV),
            ("wrapper-prefix", WRAPPED),
            ("echo-behind-and", AND_ECHO),
            ("echo-behind-or", OR_ECHO),
            ("printf-echo", PRINTF),
            ("exit-line-with-a-tail", TRAILING_EXIT),
            ("tail-failing-without-a-marker", SILENT_TAIL),
            ("tail-printing-nothing", EMPTY_TAIL),
            ("newline-separators (not the literal)", NEWLINE_SEP),
            ("other-separator-spacing (not the literal)", SPACED_SEP),
            ("multi-statement-tail (silent failure, then pass text)", FAKE_TAIL),
            ("second-dollar-question-in-another-form", SECOND_RC),
            ("single-quoted-echo", SINGLE_QUOTED),
        ]:
            row = classify(cl, root, case)
            check("stays-red: " + label, row.get("outcome") == "fail" and not row.get("expected_exit"),
                  json.dumps(row)[:300])
        after = classify(cl, root, REAL_FAIL_AFTER)
        check("real-test-failure-after-the-check-stays-red", after.get("outcome") == "fail",
              json.dumps(after)[:300])
        second = classify(cl, root, SECOND_ECHO)
        check("second-dollar-question-echo-is-not-stripped", not second.get("expected_exit"),
              json.dumps(second)[:300])
        faked = classify(cl, root, FAKE_STATE)
        check("stays-red: printed state differs from the recomputed one (shim)",
              faked.get("outcome") == "fail" and not faked.get("expected_exit"), json.dumps(faked)[:300])
        lying = classify(cl, zero, OK)
        check("stays-red: printed exit 2 while the real check exits 0 (shim)",
              lying.get("outcome") == "fail" and not lying.get("expected_exit"), json.dumps(lying)[:300])
        coded = classify(cl, one, CODE_1)
        check("stays-red: a real undeclared code (1) confirmed by the recompute",
              coded.get("outcome") == "fail" and not coded.get("expected_exit"), json.dumps(coded)[:300])
        missing = classify(cl, no_script, OK)
        check("stays-red: missing-check-script", missing.get("outcome") == "fail"
              and not missing.get("expected_exit"), json.dumps(missing)[:300])

        # --- through the real gate (calibrated + strict) -------------------
        for label, case, want in [("declared-exit-2", OK, "allow"),
                                  ("unexpected-code", CODE_1, "deny"),
                                  ("no-binding-line", NO_BINDING, "deny"),
                                  ("real-test-failure-after", REAL_FAIL_AFTER, "deny")]:
            rows = [classify(cl, root, case)]
            for strict in (False, True):
                got, reason = run_gate(hooks, root, rows, strict)
                check("gate-%s-%s-%s" % ("strict" if strict else "calibrated", label, want),
                      got == want, reason[:300])

        # --- the signals hook ---------------------------------------------
        ctx = run_signals_hook(hooks, root, *OK)
        check("hook-no-red-mark-for-the-declared-exit",
              "COMPLETION-SIGNALS" not in ctx and not ctx.startswith("BROKEN"), ctx[:200])
        ctx = run_signals_hook(hooks, root, *NO_BINDING)
        check("hook-red-mark-without-proof-of-execution", "COMPLETION-SIGNALS" in ctx, ctx[:200])


# Each mutant: (file, marker, replacement). A marker must occur exactly once.
# The single-EXIT-line guard has no mutant: with the tail-must-pass rule a second EXIT
# line never changes the outcome (equivalent mutant); the guard stays as defence in depth.
# Same for the single-$? guard: with the one-statement tail a second $? cannot pass the other
# checks (&&/|| refused, extra statements refused).
MUTANTS = {
    "registry-empty": ("completion_lib.py",
                       '    "sh skills/_shared/itd_py.sh scripts/itd_stop_rule.py --check-binding": (\n',
                       '    "MUTANT-never-matches": (\n'),
    "any-code-accepted": ("completion_lib.py",
                          "    if not match or int(match.group(1)) not in codes:\n",
                          "    if not match:  # MUTANT\n"),
    "binding-proof-ignored": ("completion_lib.py",
                              "    if len(marks) != 1 or marks[0] > exits[0]:\n",
                              "    if False:  # MUTANT\n"),
    "late-binding-accepted": ("completion_lib.py",
                              "    if len(marks) != 1 or marks[0] > exits[0]:\n",
                              "    if len(marks) != 1:  # MUTANT\n"),
    "line-not-exact": ("completion_lib.py",
                       '_EXIT_LINE_RE = re.compile(r"^EXIT: (\\d+)$")\n',
                       '_EXIT_LINE_RE = re.compile(r"EXIT: (\\d+)")  # MUTANT\n'),
    "tail-pass-not-required": ("completion_lib.py",
                               '    if outcome_from(stripped, None) != "pass":\n',
                               "    if False:  # MUTANT\n"),
    "multi-statement-tail-accepted": ("completion_lib.py",
                                      "    if len(statements) > 3:\n",
                                      "    if False:  # MUTANT\n"),
    "literal-prefix-unchecked": ("completion_lib.py",
                                 '    if "\\n" in command or not any(\n',
                                 "    if False and not any(  # MUTANT\n"),
    "recompute-ignored": ("completion_lib.py",
                          "    if _recompute_check(Path(cwd) / script, Path(cwd)) != (code, binding):\n",
                          "    if False:  # MUTANT\n"),
    "recompute-code-ignored": ("completion_lib.py",
                               "    return (proc.returncode, marks[0]) if len(marks) == 1 else None\n",
                               "    return (2, marks[0]) if len(marks) == 1 else None  # MUTANT\n"),
    "strip-not-wired": ("completion_lib.py",
                        "    text, expected_exit = strip_expected_exit(command, text, cwd)\n",
                        "    expected_exit = []  # MUTANT\n"),
}


def run_mutations() -> int:
    survived = []
    for name, (fname, marker, replacement) in MUTANTS.items():
        with tempfile.TemporaryDirectory() as tmp:
            hooks = Path(tmp) / "hooks"
            shutil.copytree(HOOKS, hooks, ignore=shutil.ignore_patterns("__pycache__"))
            target = hooks / fname
            text = target.read_text(encoding="utf-8")
            count = text.count(marker)
            if count != 1:
                print("FAIL mutation %s: marker occurs %d times in %s" % (name, count, fname))
                survived.append(name)
                continue
            target.write_text(text.replace(marker, replacement), encoding="utf-8")
            global PASS, FAIL, LOG
            PASS = FAIL = 0
            LOG = []
            try:
                suite(hooks)
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
    if "--mutations" in sys.argv[1:]:
        return run_mutations()
    suite(HOOKS)
    for line in LOG:
        print(line)
    if FAIL:
        print("FAILED: %d failed (%d passed)" % (FAIL, PASS))
        return 1
    print("PASSED: 0 failed (%d passed)" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())

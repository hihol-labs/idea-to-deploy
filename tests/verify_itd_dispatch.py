#!/usr/bin/env python3
"""Behaviour of the Claude Code hook dispatcher (plan session 6, ADR-016): hooks/claude-dispatch.py + itd_dispatch.py.

The dispatcher runs in a temporary hooks directory next to fake hook scripts and a routing table, as a real
subprocess with the payload on stdin, the way the host runs it:
- routing: only the hooks of the payload's event whose matcher matches the tool run (matchers match the whole tool
  name; a script registered under two matching groups runs once); the event comes from hook_event_name;
- merging: the first blocking answer (exit 2, a deny or a block) passes through byte for byte; asks are joined with
  their reasons, context is concatenated, plain text is context on a prompt event and transcript-only elsewhere;
- failure: a hard gate that crashes, exits 1, raises SystemExit with a message, is missing or overruns its budget
  denies a tool call and blocks a SubagentStop; an advisory hook in the same states is silent; a missing or foreign
  table, a broken payload and an unloadable itd_dispatch module fail closed on PreToolUse and SubagentStop (never
  when the subagent already continues because of a stop hook) and stay silent elsewhere; a row naming a (script,
  event) pair outside the canonical registration makes the table unusable (the case copies of the dispatcher also
  route the fixture hooks; the shipped one does not);
- isolation: every hook reads the whole payload on its own stdin, runs as __main__ with its own __file__, and its
  output is not mixed with another's, even when a slow hook writes while the next one runs;
- bytecode: checked-hash bytecode of exactly the source on disk is used, stale bytecode is ignored, and a run
  writes no .pyc (1.109.1); scripts/itd_hook_bytecode.py compiles, prunes, inventories and is idempotent;
- routing(): the sync registration is one dispatcher command per event under the union of the matchers with a
  timeout above the longest budget, and every hook of the canonical registration lands in the table.

Usage: python3 tests/verify_itd_dispatch.py
"""
from __future__ import annotations

import importlib.util
import json
import marshal
import os
from pathlib import Path
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "hooks" / "claude-dispatch.py"
MODULE = ROOT / "hooks" / "itd_dispatch.py"
BYTECODE = ROOT / "scripts" / "itd_hook_bytecode.py"

spec = importlib.util.spec_from_file_location("itd_dispatch_under_test", MODULE)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)

passed = failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS {label}")
    else:
        failed += 1
        print(f"FAIL {label}: {detail}")


HOOK = '''#!/usr/bin/env python3
import json, os, sys, time
payload = json.load(sys.stdin)
with open(os.path.join(os.environ["ITD_TEST_LOG"], "{name}"), "w", encoding="utf-8") as log:
    json.dump({{"main": __name__ == "__main__", "file": __file__, "tool": payload.get("tool_name"),
               "bytes": len(json.dumps(payload))}}, log)
{body}
'''


# The fixture hooks stand in for the registered ones: a case copy of the dispatcher routes them under every event.
# The shipped ROUTABLE is held equal to the canonical registration below, and an unmodified copy refuses a fixture
# name and a registered hook under a foreign event (review a6).
FIXTURE_NAMES = ("a.sh", "b.sh", "bad.sh", "c.sh", "d.sh", "deny.sh", "fast.sh", "gone.sh", "noisy.sh", "ok.sh",
                 "slow.sh")
FIXTURE_ROUTES = ({(name, event) for name in FIXTURE_NAMES
                   for event in ("PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop", "SubagentStop")})


def make_hooks(base: Path, hooks: dict[str, str], routes: bool = True) -> Path:
    directory = base / "hooks"
    directory.mkdir(parents=True)
    shutil.copy2(ENTRY, directory / ENTRY.name)
    shutil.copy2(MODULE, directory / MODULE.name)
    if routes:
        with (directory / MODULE.name).open("a", encoding="utf-8") as module:
            module.write(f"\nROUTABLE = ROUTABLE | set({sorted(FIXTURE_ROUTES)!r})\n")
    for name, body in hooks.items():
        (directory / name).write_text(HOOK.format(name=name, body=body), encoding="utf-8")
    return directory


def write_table(directory: Path, entries: dict[str, list[dict]], kind: str = dispatch.TABLE_KIND) -> None:
    (directory / dispatch.TABLE_FILE).write_text(
        json.dumps({"version": 1, "kind": kind, "hooks": entries}), encoding="utf-8")


def run(directory: Path, payload: object, log: Path, timeout: float = 60) -> subprocess.CompletedProcess:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    env = dict(os.environ, ITD_TEST_LOG=str(log))
    env.pop("PYTHONDONTWRITEBYTECODE", None)  # the dispatcher itself must not write bytecode
    return subprocess.run([sys.executable, str(directory / ENTRY.name)], input=raw.encode("utf-8"),
                          capture_output=True, env=env, timeout=timeout, cwd=str(directory.parent))


def entry(script: str, matcher: str = "*", hard: bool = False, timeout: float = 5) -> dict:
    return {"matcher": matcher, "script": script, "timeout": timeout, "hardGate": hard}


def decision(stdout: bytes) -> str:
    try:
        data = json.loads(stdout or b"{}")
    except ValueError:
        return "not-json"
    specific = data.get("hookSpecificOutput") or {}
    return str(specific.get("permissionDecision") or data.get("decision") or "")


def ran(log: Path) -> set[str]:
    return {path.name for path in log.iterdir()}


def pre(tool: str = "Bash", **extra) -> dict:
    return {"hook_event_name": "PreToolUse", "session_id": "t", "tool_name": tool,
            "tool_input": {"command": "git status"}, **extra}


CONTEXT = 'print(json.dumps({{"hookSpecificOutput": {{"hookEventName": "PreToolUse", "additionalContext": "{0}"}}}}))'
ASK = ('print(json.dumps({{"hookSpecificOutput": {{"hookEventName": "PreToolUse", "permissionDecision": "ask", '
       '"permissionDecisionReason": "{0}"}}}}))')
DENY = ('print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", '
        '"permissionDecisionReason": "real deny"}})); print("deny detail", file=sys.stderr); sys.exit(2)')
FAILURES = {
    "crash": 'raise RuntimeError("boom")',
    "exit 1": "sys.exit(1)",
    "message exit": 'sys.exit("fatal message")',
    "overrun": "time.sleep(30)",  # far beyond its 1 s budget: the dispatcher must not wait for it
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-dispatch-") as tmp:
        base = Path(tmp)
        counter = iter(range(1000))

        def case(hooks: dict[str, str], entries: dict[str, list[dict]], payload: object,
                 kind: str = dispatch.TABLE_KIND, table: bool = True,
                 routes: bool = True) -> tuple[subprocess.CompletedProcess, Path]:
            root = base / f"c{next(counter)}"
            directory = make_hooks(root, hooks, routes)
            if table:
                write_table(directory, entries, kind)
            log = root / "log"
            log.mkdir()
            return run(directory, payload, log), log

        # --- routing -------------------------------------------------------------------------------------------
        hooks = {"a.sh": "", "b.sh": "", "c.sh": "", "d.sh": ""}
        table = {"PreToolUse": [entry("a.sh", "Bash"), entry("b.sh", "Write|Edit"), entry("c.sh", "*"),
                                entry("a.sh", "Bash|PowerShell")],
                 "PostToolUse": [entry("d.sh", "Bash")]}
        proc, log = case(hooks, table, pre("Bash"))
        check("routing: the matching hooks of the event run, a script under two groups once",
              proc.returncode == 0 and ran(log) == {"a.sh", "c.sh"}, f"{ran(log)} {proc.stderr[-200:]!r}")
        proc, log = case(hooks, table, pre("BashOutput"))
        check("routing: a matcher matches the whole tool name (Bash is not BashOutput)", ran(log) == {"c.sh"},
              str(ran(log)))
        proc, log = case(hooks, table, {"tool_name": "Bash", "tool_response": {}, "session_id": "t"})
        check("routing: without hook_event_name a tool_response means PostToolUse", ran(log) == {"d.sh"},
              str(ran(log)))
        proc, log = case(hooks, table, {"hook_event_name": "Stop"})
        check("routing: an event without entries runs nothing and answers nothing",
              proc.returncode == 0 and not proc.stdout and not ran(log), str(ran(log)))
        proc, log = case({"a.sh": ""}, {"PreToolUse": [entry("a.sh")]}, pre())
        record = json.loads((log / "a.sh").read_text(encoding="utf-8"))
        check("isolation: a hook runs as __main__ with its own __file__ and the whole payload on stdin",
              record["main"] and record["file"].endswith("a.sh") and record["bytes"] == len(json.dumps(pre())),
              str(record))

        # --- merging -------------------------------------------------------------------------------------------
        proc, log = case({"a.sh": CONTEXT.format("first"), "b.sh": ASK.format("why b"), "c.sh": CONTEXT.format("third"),
                          "d.sh": ASK.format("why d")},
                         {"PreToolUse": [entry(name) for name in ("a.sh", "b.sh", "c.sh", "d.sh")]}, pre())
        data = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {})
        check("merge: asks are joined with every reason and the context is concatenated",
              proc.returncode == 0 and data.get("permissionDecision") == "ask"
              and data.get("permissionDecisionReason") == "why b\nwhy d"
              and data.get("additionalContext") == "first\nthird" and data.get("hookEventName") == "PreToolUse",
              proc.stdout[-300:].decode())
        proc, log = case({"a.sh": CONTEXT.format("ctx"), "b.sh": DENY, "c.sh": ASK.format("later")},
                         {"PreToolUse": [entry("a.sh"), entry("b.sh", hard=True), entry("c.sh")]}, pre())
        hook_out = (b'{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", '
                    b'"permissionDecisionReason": "real deny"}}' + os.linesep.encode())  # print() as a process writes it
        check("merge: a blocking answer passes through byte for byte with its exit code",
              proc.returncode == 2 and proc.stdout == hook_out and proc.stderr == b"deny detail" + os.linesep.encode(),
              f"{proc.returncode} {proc.stdout!r} {proc.stderr!r}")
        proc, log = case({"a.sh": 'print("plain words")'},
                         {"UserPromptSubmit": [entry("a.sh")], "PreToolUse": [entry("a.sh")]},
                         {"hook_event_name": "UserPromptSubmit", "prompt": "x"})
        data = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {})
        check("merge: plain text of a prompt hook becomes context", data.get("additionalContext") == "plain words",
              proc.stdout.decode())
        proc, log = case({"a.sh": 'print("plain words")'}, {"PreToolUse": [entry("a.sh")]}, pre())
        check("merge: plain text of a tool hook stays out of the answer (transcript only)",
              proc.returncode == 0 and not proc.stdout and b"plain words" in proc.stderr, repr(proc.stdout))
        proc, log = case({"a.sh": 'print("why", file=sys.stderr); sys.exit(2)'},
                         {"PostToolUse": [entry("a.sh")]}, {"hook_event_name": "PostToolUse", "tool_name": "Bash"})
        check("merge: exit 2 with stderr only passes through (PostToolUse feedback)",
              proc.returncode == 2 and proc.stderr.strip() == b"why", repr(proc.stderr))

        # --- failure: hard gates fail closed, advisory hooks stay silent ---------------------------------------
        for label, body in FAILURES.items():
            timeout = 1 if label == "overrun" else 5
            for hard in (True, False):
                hooks = {"bad.sh": body, "ok.sh": CONTEXT.format("kept")}
                table = {"PreToolUse": [entry("bad.sh", hard=hard, timeout=timeout), entry("ok.sh")]}
                if label == "overrun" and hard:
                    continue  # a hard gate gets at least 30 s; its overrun is checked in process below
                started = time.monotonic()
                proc, log = case(hooks, table, pre())
                elapsed = time.monotonic() - started
                if hard:
                    check(f"failure ({label}) of a hard gate denies the tool call",
                          proc.returncode == 2 and decision(proc.stdout) == "deny"
                          and b"bad.sh" in proc.stdout and b"failed closed" in proc.stdout,
                          f"{proc.returncode} {proc.stdout[-300:]!r}")
                else:
                    context = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {}).get("additionalContext")
                    check(f"failure ({label}) of an advisory hook is silent, the others still answer",
                          proc.returncode == 0 and context == "kept" and (label != "overrun" or elapsed < 20),
                          f"{proc.returncode} {proc.stdout[-200:]!r} {elapsed:.1f}s")
        proc, log = case({"ok.sh": ""}, {"PreToolUse": [entry("gone.sh", hard=True), entry("ok.sh")]}, pre())
        check("failure: a missing hard-gate file denies", proc.returncode == 2 and decision(proc.stdout) == "deny",
              repr(proc.stdout))
        proc, log = case({"ok.sh": ""}, {"PreToolUse": [entry("gone.sh"), entry("ok.sh")]}, pre())
        check("failure: a missing advisory file is silent", proc.returncode == 0 and not proc.stdout, repr(proc.stdout))
        proc, log = case({"ok.sh": ""}, {"PreToolUse": [entry("../ok.sh", hard=True)]}, pre())
        check("failure: a table entry outside the hooks directory is not run and denies as a hard gate",
              proc.returncode == 2 and not ran(log), repr(proc.stdout))
        stop = {"hook_event_name": "SubagentStop", "session_id": "t"}
        proc, log = case({"bad.sh": FAILURES["crash"]}, {"SubagentStop": [entry("bad.sh", hard=True)]}, stop)
        check("failure: a hard SubagentStop gate that crashes blocks",
              proc.returncode == 2 and decision(proc.stdout) == "block", repr(proc.stdout))

        # in process: a hard gate that overruns its budget denies, and the dispatcher leaves at the budget
        root = base / "overrun"
        directory = make_hooks(root, {"slow.sh": "time.sleep(30)"})
        write_table(directory, {"PreToolUse": [entry("slow.sh", hard=True, timeout=1)]})
        (root / "log").mkdir()
        saved, dispatch.HARD_GATE_MIN_BUDGET_SECONDS = dispatch.HARD_GATE_MIN_BUDGET_SECONDS, 0.5
        shipped, dispatch.ROUTABLE = dispatch.ROUTABLE, dispatch.ROUTABLE | FIXTURE_ROUTES
        os.environ["ITD_TEST_LOG"] = str(root / "log")
        real_streams = sys.stdin, sys.stdout, sys.stderr
        try:
            for name in ("stdin", "stdout", "stderr"):
                setattr(sys, name, dispatch._ThreadStream(name, getattr(sys, name)))
            started = time.monotonic()
            (out, err, code), abandoned = dispatch.dispatch(json.dumps(pre()).encode(), directory.resolve())
            elapsed = time.monotonic() - started
        finally:
            sys.stdin, sys.stdout, sys.stderr = real_streams
            dispatch.HARD_GATE_MIN_BUDGET_SECONDS = saved
            dispatch.ROUTABLE = shipped
        check("failure: a hard gate that overruns its budget denies when the budget ends",
              code == 2 and decision(out) == "deny" and b"overran" in out and abandoned and elapsed < 15,
              f"{code} {out[-200:]!r} {abandoned} {elapsed:.1f}s")

        # --- the table, the payload and the module itself ------------------------------------------------------
        for label, kwargs in (("missing", {"table": False}), ("foreign kind", {"kind": "other"})):
            proc, log = case({"a.sh": ""}, {"PreToolUse": [entry("a.sh")]}, pre(), **kwargs)
            check(f"table {label}: a tool call is denied with the fix", proc.returncode == 2
                  and decision(proc.stdout) == "deny" and b"sync-to-active" in proc.stdout and not ran(log),
                  repr(proc.stdout))
            proc, log = case({"a.sh": ""}, {}, stop, **kwargs)
            check(f"table {label}: a SubagentStop is blocked", decision(proc.stdout) == "block", repr(proc.stdout))
            proc, log = case({"a.sh": ""}, {}, dict(stop, stop_hook_active=True), **kwargs)
            check(f"table {label}: a SubagentStop that already continues is never blocked again",
                  proc.returncode == 0 and not proc.stdout, repr(proc.stdout))
            proc, log = case({"a.sh": ""}, {}, {"hook_event_name": "UserPromptSubmit", "prompt": "x"}, **kwargs)
            check(f"table {label}: a prompt event stays silent", proc.returncode == 0 and not proc.stdout,
                  repr(proc.stdout))
        # review a1: a row that routing() would not write makes the table unusable (fail closed), and a policy hard
        # gate stays hard whatever its row's flag says
        malformed = {"no hardGate": {"matcher": "*", "script": "a.sh", "timeout": 5},
                     "a script path outside the hooks directory": entry("../a.sh"),
                     "a script in a subdirectory": entry("sub/a.sh"),
                     "a script that is not a hook file": entry("a.txt"),
                     "hardGate not a bool": dict(entry("a.sh"), hardGate="yes"),
                     "timeout a string": dict(entry("a.sh"), timeout="5"),
                     "timeout a bool": dict(entry("a.sh"), timeout=True),
                     "no matcher": {"script": "a.sh", "timeout": 5, "hardGate": False},
                     "an extra key": dict(entry("a.sh"), extra=1)}
        for label, row in malformed.items():
            proc, log = case({"a.sh": ""}, {"PreToolUse": [row]}, pre())
            check(f"table row with {label}: the table is unusable and a tool call is denied",
                  proc.returncode == 2 and decision(proc.stdout) == "deny" and not ran(log), repr(proc.stdout[-200:]))
        # review a6: the shipped dispatcher runs only the (script, event) pairs the canonical registration routes
        proc, log = case({"careful.sh": CONTEXT.format("registered")}, {"PreToolUse": [entry("careful.sh", "Bash")]},
                         pre(), routes=False)
        context = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {}).get("additionalContext")
        check("table row of a registered hook: the shipped dispatcher runs it",
              proc.returncode == 0 and context == "registered" and ran(log) == {"careful.sh"}, repr(proc.stdout))
        unrouted = {"a hook file the registration does not name": ({"a.sh": ""}, "PreToolUse", "a.sh", pre()),
                    "a registered hook under a foreign event": ({"graph-route.sh": ""}, "PreToolUse", "graph-route.sh",
                                                                pre()),
                    "a registered SubagentStop gate under PreToolUse": ({"verdict-contract.sh": ""}, "PreToolUse",
                                                                        "verdict-contract.sh", pre()),
                    "a hook file the registration does not name, on SubagentStop": (
                        {"a.sh": ""}, "SubagentStop", "a.sh", {"hook_event_name": "SubagentStop", "session_id": "t"})}
        for label, (hooks, event, script, payload) in unrouted.items():
            proc, log = case(hooks, {event: [entry(script)]}, payload, routes=False)
            expected = "block" if event == "SubagentStop" else "deny"
            check(f"table row naming {label}: the table is unusable, nothing runs, the event fails closed",
                  proc.returncode == 2 and decision(proc.stdout) == expected and b"malformed" in proc.stdout
                  and not ran(log), repr(proc.stdout[-200:]))
        proc, log = case({"a.sh": ""}, {"PostToolUse": [entry("a.sh")]},
                         {"hook_event_name": "PostToolUse", "tool_name": "Bash"}, routes=False)
        check("table row naming an unrouted hook on PostToolUse: nothing runs, the advisory event stays silent",
              proc.returncode == 0 and not proc.stdout and not ran(log), repr(proc.stdout[-200:]))
        # review a3: JSON admits Infinity and NaN; such a timeout is a malformed row, not a dispatcher crash
        for label, literal in (("Infinity", "Infinity"), ("NaN", "NaN")):
            proc, log = case({"a.sh": ""}, {}, pre(), table=False)
            (log.parent / "hooks" / dispatch.TABLE_FILE).write_text(
                '{"version": 1, "kind": "%s", "hooks": {"PreToolUse": [{"matcher": "*", "script": "a.sh", '
                '"timeout": %s, "hardGate": false}]}}' % (dispatch.TABLE_KIND, literal), encoding="utf-8")
            proc = run(log.parent / "hooks", pre(), log)
            check(f"table row with timeout {label}: malformed (the table is unusable), not a dispatcher crash",
                  proc.returncode == 2 and decision(proc.stdout) == "deny" and b"malformed" in proc.stdout
                  and b"crashed" not in proc.stdout and not ran(log), repr(proc.stdout[-200:]))
        proc, log = case({"a.sh": ""}, {}, pre(), table=False)
        root = log.parent
        (root / "hooks" / dispatch.TABLE_FILE).write_text(json.dumps({"version": 1, "kind": dispatch.TABLE_KIND,
                                                                       "hooks": []}), encoding="utf-8")
        proc = run(root / "hooks", pre(), log)
        check("table whose hooks are not an object: a tool call is denied", decision(proc.stdout) == "deny",
              repr(proc.stdout))
        proc, log = case({"pii-egress-guard.sh": FAILURES["crash"]},
                         {"PreToolUse": [entry("pii-egress-guard.sh", hard=False)]}, pre())
        check("a policy hard gate flagged advisory in the table still fails closed",
              proc.returncode == 2 and decision(proc.stdout) == "deny", repr(proc.stdout))
        policy = json.loads((ROOT / "docs" / "HARNESS_TRUST_POLICY.json").read_text(encoding="utf-8"))
        check("the dispatcher's built-in hard gates are exactly the trust policy pairs",
              dispatch.HARD_GATES == {(gate["script"], gate["event"]) for gate in policy["hardGates"]},
              str(dispatch.HARD_GATES ^ {(gate["script"], gate["event"]) for gate in policy["hardGates"]}))
        # review a1: a crash of the dispatcher itself keeps the no-stop-loop rule
        saved_dispatch = dispatch.dispatch

        def crash(raw: bytes, hooks_dir: Path):
            raise RuntimeError("synthetic dispatcher crash")

        dispatch.dispatch = crash
        try:
            looped = dispatch.answer(json.dumps(dict(stop, stop_hook_active=True)).encode(), base)
            fresh = dispatch.answer(json.dumps(stop).encode(), base)
            tool_call = dispatch.answer(json.dumps(pre()).encode(), base)
        finally:
            dispatch.dispatch = saved_dispatch
        check("a dispatcher crash never blocks a SubagentStop that already continues", looped[2] == 0
              and not looped[0] and b"synthetic dispatcher crash" in looped[1], repr(looped))
        # review a4: SystemExit and KeyboardInterrupt in the dispatcher itself fail closed too
        for raised in (SystemExit(0), KeyboardInterrupt()):
            def leave(raw: bytes, hooks_dir: Path, exc=raised):
                raise exc

            dispatch.dispatch = leave
            try:
                left = dispatch.answer(json.dumps(pre()).encode(), base)
            except BaseException as escaped:  # noqa: BLE001 - an escape is the failure under test, not the test's
                left = (b"", repr(escaped).encode(), "escaped")
            finally:
                dispatch.dispatch = saved_dispatch
            check(f"a {type(raised).__name__} in the dispatcher denies the tool call",
                  left[2] == 2 and decision(left[0]) == "deny" and type(raised).__name__.encode() in left[0], repr(left))
        read_end, write_end = os.pipe()
        try:
            dispatch.emit([(1, write_end)], b"answer through the saved original", b"")
        finally:
            os.close(write_end)
        with os.fdopen(read_end, "rb") as pipe:
            check("the answer is written through the saved copy of the original stdout, not the redirected fd 1",
                  pipe.read() == b"answer through the saved original")
        check("a dispatcher crash blocks a SubagentStop and denies a tool call",
              fresh[2] == 2 and decision(fresh[0]) == "block" and tool_call[2] == 2 and decision(tool_call[0]) == "deny",
              f"{fresh!r} {tool_call!r}")

        proc, log = case({"a.sh": ""}, {"PreToolUse": [entry("a.sh")]}, "{not json")
        check("payload that is not JSON: denied", proc.returncode == 2 and decision(proc.stdout) == "deny",
              repr(proc.stdout))
        root = base / "no-module"
        directory = make_hooks(root, {})
        (directory / MODULE.name).unlink()
        write_table(directory, {})
        (root / "log").mkdir()
        proc = run(directory, pre(), root / "log")
        check("an unloadable itd_dispatch module: the entry point denies a tool call",
              proc.returncode == 2 and decision(proc.stdout) == "deny" and b"not loadable" in proc.stdout,
              repr(proc.stdout))
        proc = run(directory, {"hook_event_name": "Stop"}, root / "log")
        check("an unloadable itd_dispatch module: a Stop stays silent", proc.returncode == 0 and not proc.stdout,
              repr(proc.stdout))
        proc = run(directory, stop, root / "log")
        check("an unloadable itd_dispatch module: a SubagentStop is blocked",
              proc.returncode == 2 and decision(proc.stdout) == "block", repr(proc.stdout))
        proc = run(directory, dict(stop, stop_hook_active=True), root / "log")
        check("an unloadable itd_dispatch module: a SubagentStop that already continues is not blocked again",
              proc.returncode == 0 and not proc.stdout, repr(proc.stdout))
        (directory / MODULE.name).write_text("raise SystemExit(0)\n", encoding="utf-8")
        proc = run(directory, pre(), root / "log")
        check("a dispatcher module that raises SystemExit while it loads: the entry point denies a tool call",
              proc.returncode == 2 and decision(proc.stdout) == "deny" and b"SystemExit" in proc.stdout,
              repr(proc.stdout))

        # --- a child process of a hook that does not capture its output -------------------------------------
        noisy = ('import subprocess\n'
                 'subprocess.run([sys.executable, "-c", "import sys; print(\'child noise\'); '
                 'print(\'child err\', file=sys.stderr)"])\n' + CONTEXT.format("after child"))
        proc, log = case({"noisy.sh": noisy, "deny.sh": DENY},
                         {"PreToolUse": [entry("noisy.sh")], "PostToolUse": [entry("noisy.sh"), entry("deny.sh")]},
                         pre())
        check("isolation: a child's inherited stdout and stderr stay out of the merged answer",
              proc.returncode == 0 and b"child noise" not in proc.stdout + proc.stderr
              and b"child err" not in proc.stdout + proc.stderr
              and json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"] == "after child",
              f"{proc.stdout!r} {proc.stderr!r}")
        proc, log = case({"noisy.sh": noisy, "deny.sh": DENY},
                         {"PreToolUse": [entry("noisy.sh"), entry("deny.sh")]}, pre())
        check("isolation: a deny after a noisy child is still passed through exactly",
              proc.returncode == 2 and proc.stdout == hook_out and proc.stderr.strip() == b"deny detail",
              f"{proc.stdout!r} {proc.stderr!r}")

        # --- isolation of concurrent output -------------------------------------------------------------------
        stamp = ('import threading\n'
                 'with open(os.path.join(os.environ["ITD_TEST_LOG"], "{0}.times"), "a", encoding="utf-8") as t:\n'
                 '    t.write(f"{{{1}}} {{time.time()}} {{threading.get_ident()}}\\n")\n')
        slow = (stamp.format("slow", '"start"') + 'time.sleep(0.6)\n' + stamp.format("slow", '"end"') +
                'print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", '
                '"additionalContext": "slow-" + "s" * 5000}}))')
        fast = (stamp.format("fast", '"start"') + 'for i in range(50): time.sleep(0.01)\n' +
                'print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", '
                '"additionalContext": "fast-" + "f" * 5000}}))')
        proc, log = case({"slow.sh": slow, "fast.sh": fast},
                         {"PreToolUse": [entry("slow.sh"), entry("fast.sh")]}, pre())
        context = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {}).get("additionalContext", "")
        times = {name: {row.split()[0]: row.split()[1:] for row in (log / f"{name}.times").read_text().splitlines()}
                 for name in ("slow", "fast")}
        check("isolation: a hook still running after the sequential wait overlaps the next one, in its own thread",
              float(times["fast"]["start"][0]) < float(times["slow"]["end"][0])
              and times["fast"]["start"][1] != times["slow"]["start"][1], str(times))
        check("isolation: a slow hook still writing while the next one runs keeps its output apart",
              context == "slow-" + "s" * 5000 + "\nfast-" + "f" * 5000, context[:60])

        # review a2: descriptors that cannot be isolated make the event fail closed
        saved_devnull = os.devnull
        os.devnull = str(base / "no-such-directory" / "null")
        try:
            refused = dispatch.respond(json.dumps(pre()).encode(), base)
            looping = dispatch.respond(json.dumps(dict(stop, stop_hook_active=True)).encode(), base)
        finally:
            os.devnull = saved_devnull
        check("descriptors that cannot be isolated: a tool call is denied, a continuing SubagentStop is not blocked",
              refused[2] == 2 and decision(refused[0]) == "deny" and b"isolated" in refused[0]
              and looping[2] == 0 and not looping[0], f"{refused!r} {looping!r}")

        # --- bytecode ------------------------------------------------------------------------------------------
        install = base / "install"
        directory = make_hooks(install, {"a.sh": CONTEXT.format("from source v1")})
        (directory / "helper.py").write_text("VALUE = 'helper'\n", encoding="utf-8")
        (directory / "b.sh").write_text(HOOK.format(name="b.sh", body=(
            'import helper\nprint(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", '
            '"additionalContext": helper.VALUE}}))')), encoding="utf-8")
        write_table(directory, {"PreToolUse": [entry("a.sh"), entry("b.sh")]})
        (install / "log").mkdir()
        proc = run(directory, pre(), install / "log")
        check("bytecode: a run without install bytecode writes no .pyc anywhere",
              proc.returncode == 0 and not list(install.rglob("*.pyc")) and not list(install.rglob("__pycache__")),
              str(list(install.rglob("*.pyc"))))
        out = subprocess.run([sys.executable, "-B", str(BYTECODE), str(install)], capture_output=True, text=True)
        inventory = json.loads((install / "itd-bytecode.json").read_text(encoding="utf-8"))
        sources = {row["source"] for row in inventory["files"]}
        check("bytecode: the installer compiles the python hooks and modules and lists them in the inventory",
              out.returncode == 0 and {"hooks/a.sh", "hooks/b.sh", "hooks/helper.py", "hooks/itd_dispatch.py",
                                       "hooks/claude-dispatch.py"} <= sources
              and inventory["cacheTag"] == sys.implementation.cache_tag, out.stdout + out.stderr)
        pyc = Path(importlib.util.cache_from_source(str(directory / "a.sh")))
        dispatch.trust_bytecode(install)
        code = dispatch.cached_code(directory / "a.sh", (directory / "a.sh").read_bytes())
        check("bytecode: checked-hash bytecode of exactly the source is loaded", code is not None and pyc.is_file())
        before = {path: path.stat().st_mtime_ns for path in install.rglob("*.pyc")}
        (directory / "a.sh").write_text(HOOK.format(name="a.sh", body=CONTEXT.format("from source v2")),
                                        encoding="utf-8")
        check("bytecode: bytecode of another source is ignored",
              dispatch.cached_code(directory / "a.sh", (directory / "a.sh").read_bytes()) is None)
        proc = run(directory, pre(), install / "log")
        context = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {}).get("additionalContext", "")
        after = {path: path.stat().st_mtime_ns for path in install.rglob("*.pyc")}
        check("bytecode: a changed source runs as changed and nothing rewrites the bytecode at run time",
              context == "from source v2\nhelper" and before == after, f"{context!r} {set(after) ^ set(before)}")
        check_out = subprocess.run([sys.executable, "-B", str(BYTECODE), str(install), "--check"],
                                   capture_output=True, text=True)
        check("bytecode: --check reports the stale bytecode and writes nothing",
              check_out.returncode == 1 and "hooks/a.sh" in check_out.stdout
              and {path: path.stat().st_mtime_ns for path in install.rglob("*.pyc")} == after, check_out.stdout)
        stray = pyc.parent / "stray.cpython-312.pyc"
        stray.write_bytes(b"x")
        first = subprocess.run([sys.executable, "-B", str(BYTECODE), str(install)], capture_output=True, text=True)
        dispatch.trust_bytecode(install)  # the inventory now lists the recompiled bytecode
        snapshot = {path: path.read_bytes() for path in install.rglob("*") if path.is_file()}
        second = subprocess.run([sys.executable, "-B", str(BYTECODE), str(install)], capture_output=True, text=True)
        check("bytecode: the installer recompiles stale bytecode and removes a .pyc without a source",
              first.returncode == 0 and "1 compiled, 1 removed" in first.stdout and not stray.exists()
              and dispatch.cached_code(directory / "a.sh", (directory / "a.sh").read_bytes()) is not None,
              first.stdout + first.stderr)
        check("bytecode: a repeated install changes no byte",
              second.returncode == 0 and "0 compiled, 0 removed" in second.stdout
              and snapshot == {path: path.read_bytes() for path in install.rglob("*") if path.is_file()},
              second.stdout)
        check("bytecode: --check after an install is clean",
              subprocess.run([sys.executable, "-B", str(BYTECODE), str(install), "--check"],
                             capture_output=True).returncode == 0)
        # review a2: a .pyc with the right header but another code object is not the install's bytecode
        def tamper(source_path: Path, replacement: str) -> None:
            pyc_path = Path(importlib.util.cache_from_source(str(source_path)))
            pyc_path.write_bytes(pyc_path.read_bytes()[:16] + marshal.dumps(compile(replacement, str(source_path), "exec")))

        tamper(directory / "a.sh", HOOK.format(name="a.sh", body=CONTEXT.format("tampered")))
        tamper(directory / "helper.py", "VALUE = 'tampered helper'\n")
        dispatch.trust_bytecode(install)
        check("bytecode: a .pyc whose code object the installer did not produce is refused",
              dispatch.cached_code(directory / "a.sh", (directory / "a.sh").read_bytes()) is None)
        proc = run(directory, pre(), install / "log")
        context = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {}).get("additionalContext", "")
        check("bytecode: a tampered hook or imported-module .pyc never runs, its source does",
              proc.returncode == 0 and context == "from source v2\nhelper", repr(context))
        if os.name != "nt":  # Windows meets the same through its 8.3 short temp path; here a link plays that part
            alias = base / "install-alias"
            alias.symlink_to(install, target_is_directory=True)
            proc = run(alias / "hooks", pre(), install / "log")
            context = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {}).get("additionalContext", "")
            check("bytecode: the guard holds when the install is reached through another spelling of its path",
                  proc.returncode == 0 and context == "from source v2\nhelper", repr(context))
        # review a6: the installer compares the whole .pyc, so a valid header in front of another code object is
        # reported by --check and replaced by the next install, never inventoried as the install's bytecode
        drift = subprocess.run([sys.executable, "-B", str(BYTECODE), str(install), "--check"],
                               capture_output=True, text=True)
        check("bytecode: --check reports a .pyc with a valid header and a code object that is not its source's",
              drift.returncode == 1 and "stale or missing bytecode: hooks/a.sh" in drift.stdout
              and "stale or missing bytecode: hooks/helper.py" in drift.stdout, drift.stdout)
        fixed = subprocess.run([sys.executable, "-B", str(BYTECODE), str(install)], capture_output=True, text=True)
        dispatch.trust_bytecode(install)
        proc = run(directory, pre(), install / "log")
        context = json.loads(proc.stdout or b"{}").get("hookSpecificOutput", {}).get("additionalContext", "")
        check("bytecode: the next install replaces it with its source's bytecode, which the dispatcher then loads",
              fixed.returncode == 0 and "2 compiled" in fixed.stdout
              and dispatch.cached_code(directory / "a.sh", (directory / "a.sh").read_bytes()) is not None
              and context == "from source v2\nhelper", fixed.stdout + fixed.stderr + repr(context))
        reference = base / "reference.pyc"
        py_compile.compile(str(directory / "a.sh"), cfile=str(reference), doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        check("bytecode: the installer writes the bytes py_compile writes for the source",
              reference.read_bytes() == pyc.read_bytes())
        spec_b = importlib.util.spec_from_file_location("itd_hook_bytecode_under_test", BYTECODE)
        installer = importlib.util.module_from_spec(spec_b)
        spec_b.loader.exec_module(installer)
        check("bytecode: the dispatcher reads the inventory the installer writes",
              (dispatch.INVENTORY_FILE, dispatch.INVENTORY_KIND) == (installer.INVENTORY_FILE, installer.INVENTORY_KIND))
        timestamp_pyc = base / "ts" / "hooks"
        timestamp_pyc.mkdir(parents=True)
        (timestamp_pyc / "x.py").write_text("X = 1\n", encoding="utf-8")
        source = str(timestamp_pyc / "x.py")
        py_compile.compile(source, cfile=importlib.util.cache_from_source(source),
                           invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
        check("bytecode: timestamp bytecode (no source hash) is never loaded by the dispatcher",
              dispatch.cached_code(timestamp_pyc / "x.py", (timestamp_pyc / "x.py").read_bytes()) is None)

    # --- routing(): the registration sync writes ----------------------------------------------------------------
    sync_text = (ROOT / "scripts" / "sync-to-active.sh").read_text(encoding="utf-8")
    desired = json.loads(re.search(r"DESIRED_HOOKS=\$\(cat <<'JSON'\n(.+?)\nJSON\n\)", sync_text, re.DOTALL).group(1))
    policy = json.loads((ROOT / "docs" / "HARNESS_TRUST_POLICY.json").read_text(encoding="utf-8"))
    hard = {(gate["script"], gate["event"]) for gate in policy["hardGates"]}
    table, registration = dispatch.routing(desired, hard)
    canonical = {(event, hook["command"].rsplit("/", 1)[-1]) for event, groups in desired.items()
                 for group in groups for hook in group["hooks"]}
    routed = {(event, row["script"]) for event, rows in table["hooks"].items() for row in rows}
    check("routing(): every hook of the canonical registration is in the table", routed == canonical,
          str(canonical ^ routed))
    check("routing(): the dispatcher routes exactly the (script, event) pairs of the canonical registration",
          dispatch.ROUTABLE == {(script, event) for event, script in canonical},
          str(dispatch.ROUTABLE ^ {(script, event) for event, script in canonical}))
    commands = [hook["command"] for groups in registration.values() for group in groups for hook in group["hooks"]]
    check("routing(): one dispatcher command per event", set(registration) == set(desired)
          and commands == [dispatch.DISPATCHER_COMMAND] * len(desired), str(commands))
    pre_group = registration["PreToolUse"][0]
    narrow = {"PostToolUse": [group for group in desired["PostToolUse"] if group.get("matcher") != "*"]}
    _, narrow_registration = dispatch.routing(narrow, hard)
    check("routing(): the matcher is the union of the event's matchers ('*' when one group matches all)",
          pre_group["matcher"] == "*" and registration["PostToolUse"][0]["matcher"] == "*"
          and set(narrow_registration["PostToolUse"][0]["matcher"].split("|"))
          == {alt for group in narrow["PostToolUse"] for alt in group["matcher"].split("|")}
          and "matcher" not in registration["UserPromptSubmit"][0], json.dumps(narrow_registration)[:300])
    check("routing(): the timeout covers the longest budget of the event",
          pre_group["hooks"][0]["timeout"] >= 900 + dispatch.REGISTRATION_MARGIN_SECONDS
          and registration["SubagentStop"][0]["hooks"][0]["timeout"]
          >= dispatch.HARD_GATE_MIN_BUDGET_SECONDS + dispatch.REGISTRATION_MARGIN_SECONDS,
          json.dumps(registration)[:300])
    flagged = {(event, row["script"]) for event, rows in table["hooks"].items() for row in rows if row["hardGate"]}
    check("routing(): the hard-gate flags are exactly the policy pairs that are registered",
          flagged == {(event, script) for script, event in hard} & canonical
          and ("PostToolUse", "state-guard.sh") not in flagged and ("PreToolUse", "state-guard.sh") in flagged,
          str(flagged))

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

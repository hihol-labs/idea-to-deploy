#!/usr/bin/env python3
"""Behavioural test for the v1.59.0 (ось 1 / G-004) friction fixes to
hooks/check-tool-skill.sh.

Two bugs made the skill-enforcement gate a dead-end:

  Bug 1 — a read-only Bash carrying an explicit `SKILL_BYPASS:` was swallowed
  by the read-only fast-path (it ran BEFORE the bypass check), so the natural
  `true` + `SKILL_BYPASS: …` gesture used to open a grace window did nothing:
  it neither reset the ignore counter, opened the window, nor logged the
  bypass.

  Bug 2 — Edit/Write/NotebookEdit carry no `description` field, so they cannot
  supply an in-band SKILL_BYPASS. Once the counter hit MAX, the ONLY escape
  was the grace window — but Bug 1 broke the one-off-Bash route to opening it,
  and the block message told the user to do the impossible ("add SKILL_BYPASS
  to the Edit/Write description").

This test drives the real hook and asserts:
  1. A read-only Bash + SKILL_BYPASS now RESETS the counter, OPENS the grace
     window, and LOGS the bypass (Bug 1 fixed).
  2. A read-only Bash WITHOUT a bypass is still exempt and does NOT open a
     window or log (ordering did not weaken the exemption).
  3. End-to-end: an Edit at MAX with no grace is BLOCKED (exit 2, the
     dead-end), then a one-off read-only Bash + SKILL_BYPASS opens the window,
     and the next Edit is ALLOWED (exit 0) — the escape works.
  4. The evidence-driven allowlist additions (`tsc --noEmit`, `node --test`)
     are read-only; bare `tsc` (emits) and `node app.js` are not.

Run: python3 tests/verify_bypass_friction.py
Exits non-zero if any case fails (CI-friendly).
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "check-tool-skill.sh")
SID = "bypass-friction-test-session"
TMP = tempfile.gettempdir()

IGNORE = os.path.join(TMP, "claude-skill-ignores-%s.state" % SID)
ACTIVE = os.path.join(TMP, "claude-skill-active-%s.state" % SID)
LEDGER = os.path.join(TMP, "claude-skill-ledger-%s.jsonl" % SID)
REMIND = os.path.join(TMP, "claude-skill-check-%s.state" % SID)

# load the hook as a module for the pure is_readonly_bash() checks
_loader = importlib.machinery.SourceFileLoader("chk_tool_skill", HOOK)
_spec = importlib.util.spec_from_loader("chk_tool_skill", _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)
MAX = mod.MAX_IGNORES


def clear():
    for p in (IGNORE, ACTIVE, LEDGER, REMIND):
        try:
            os.remove(p)
        except OSError:
            pass


def seed_ignore(n):
    with open(IGNORE, "w") as f:
        f.write(str(n))


def read_ignore():
    try:
        with open(IGNORE) as f:
            return int(f.read().strip() or "0")
    except OSError:
        return None


def active_fresh():
    try:
        return (time.time() - os.path.getmtime(ACTIVE)) < mod.SKILL_ACTIVE_TTL_SECONDS
    except OSError:
        return False


def run_hook(tool, tool_input):
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = SID
    return subprocess.run(["python3", HOOK], input=payload, cwd=REPO,
                          capture_output=True, text=True, env=env).returncode


def main():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        print("%s  %s" % ("PASS" if cond else "FAIL", name))
        if cond:
            passed += 1
        else:
            failed += 1

    # 1. Bug 1 — read-only Bash + SKILL_BYPASS: reset + grace + log
    clear()
    seed_ignore(MAX)
    rc = run_hook("Bash", {"command": "ls -la",
                           "description": "SKILL_BYPASS: read-only recon"})
    check("readonly+bypass -> exit 0", rc == 0)
    check("readonly+bypass RESETS ignore counter to 0", read_ignore() == 0)
    check("readonly+bypass OPENS grace window", active_fresh())
    check("readonly+bypass LOGS the bypass to the ledger", os.path.exists(LEDGER))
    clear()

    # 2. read-only Bash WITHOUT bypass — still exempt, no window, no log
    clear()
    seed_ignore(1)
    rc = run_hook("Bash", {"command": "cat some/file.txt", "description": ""})
    check("readonly (no bypass) -> exit 0 (exempt)", rc == 0)
    check("readonly (no bypass) does NOT open grace window", not active_fresh())
    check("readonly (no bypass) does NOT log a bypass", not os.path.exists(LEDGER))
    check("readonly (no bypass) leaves ignore counter untouched", read_ignore() == 1)
    clear()

    # 3. End-to-end dead-end escape for Edit
    clear()
    seed_ignore(MAX)
    rc_blocked = run_hook("Edit", {"file_path": "/x", "old_string": "a",
                                   "new_string": "b"})
    check("Edit at MAX with no grace -> BLOCKED (exit 2, the dead-end)",
          rc_blocked == 2)
    rc_open = run_hook("Bash", {"command": "true",
                                "description": "SKILL_BYPASS: open window for edits"})
    check("one-off readonly Bash + bypass -> exit 0 (opens window)", rc_open == 0)
    rc_edit = run_hook("Edit", {"file_path": "/x", "old_string": "a",
                                "new_string": "b"})
    check("next Edit is ALLOWED (exit 0, escape works)", rc_edit == 0)
    clear()

    # 4. Evidence-driven allowlist additions
    ro = mod.is_readonly_bash
    def bash(cmd):
        return {"tool_name": "Bash", "tool_input": {"command": cmd}}
    check("`tsc --noEmit` is read-only", ro(bash("tsc --noEmit")))
    check("`tsc --noEmit -p tsconfig.json` is read-only",
          ro(bash("tsc --noEmit -p tsconfig.json")))
    check("bare `tsc` is NOT read-only (it emits)", not ro(bash("tsc")))
    check("`node --test` is read-only", ro(bash("node --test")))
    check("`node --test tests/` is read-only", ro(bash("node --test tests/")))
    check("`node app.js` is NOT read-only", not ro(bash("node app.js")))
    # regex-boundary regression (review G-004): the --test* flag family must
    # NOT ride through as read-only (a `-` after --test satisfied a bare \\b).
    check("`node --test-reporter=tap x.js` is NOT read-only",
          not ro(bash("node --test-reporter=tap x.js")))
    check("`node --test-only` is NOT read-only", not ro(bash("node --test-only")))

    clear()
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

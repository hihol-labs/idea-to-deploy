#!/usr/bin/env python3
"""Behavioural proof: two-phase execution tracer with outcome (v1.89.0, GO-001,
«полнота трейса + информативность шага: исход в трейсе»).

Spawns hooks/execution-trace.sh with Pre/Post payloads and asserts the trace
file carries an outcome line for EVERY tool type, not just an intent line:

  - PreToolUse  -> {phase:"pre", tool, target}      (no outcome)
  - PostToolUse -> {phase:"post", tool, ..., outcome}
  - Bash exit 0 -> ok(+exit 0); exit 1 -> fail(+error tail)
  - Edit/Write success -> ok; is_error -> fail
  - Agent empty final -> empty; Agent with text -> ok
  - registration: execution-trace under both Pre and Post matcher "*"

Self-contained, stdlib only. Run: python3 tests/verify_execution_trace_outcome.py
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "execution-trace.sh"
SYNC = REPO / "scripts" / "sync-to-active.sh"

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def run(cwd, payload):
    subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                   capture_output=True, text=True, timeout=20)


def trace(cwd, sid="t"):
    f = Path(cwd) / ".claude" / "traces" / f"session-{sid}.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    with tempfile.TemporaryDirectory() as td:
        # Pre: intent, без outcome
        run(td, {"session_id": "t", "cwd": td, "tool_name": "Bash",
                 "hook_event_name": "PreToolUse", "tool_input": {"command": "pytest"}})
        rows = trace(td)
        check("Pre-строка: phase pre, без outcome",
              len(rows) == 1 and rows[0].get("phase") == "pre" and "outcome" not in rows[0],
              str(rows))

        # Post Bash exit 0 -> ok
        run(td, {"session_id": "t", "cwd": td, "tool_name": "Bash",
                 "hook_event_name": "PostToolUse",
                 "tool_input": {"command": "pytest"},
                 "tool_response": {"stdout": "3 passed", "exitCode": 0}})
        r = trace(td)[-1]
        check("Post Bash exit 0 -> ok", r.get("phase") == "post" and r.get("outcome") == "ok" and r.get("exit") == 0, str(r))

        # Post Bash exit 1 -> fail + error
        run(td, {"session_id": "t", "cwd": td, "tool_name": "Bash",
                 "hook_event_name": "PostToolUse",
                 "tool_input": {"command": "pytest"},
                 "tool_response": {"stdout": "boom\nAssertionError: x", "exitCode": 1}})
        r = trace(td)[-1]
        check("Post Bash exit 1 -> fail + error", r.get("outcome") == "fail" and "AssertionError" in r.get("error", ""), str(r))

    with tempfile.TemporaryDirectory() as td:
        # Edit success
        run(td, {"session_id": "t", "cwd": td, "tool_name": "Edit",
                 "hook_event_name": "PostToolUse",
                 "tool_input": {"file_path": "a.ts"},
                 "tool_response": "The file a.ts has been updated successfully."})
        r = trace(td)[-1]
        check("Post Edit success -> ok", r.get("tool") == "Edit" and r.get("outcome") == "ok", str(r))

        # Write is_error -> fail
        run(td, {"session_id": "t", "cwd": td, "tool_name": "Write",
                 "hook_event_name": "PostToolUse",
                 "tool_input": {"file_path": "b.ts"},
                 "tool_response": {"is_error": True, "error": "permission denied"}})
        r = trace(td)[-1]
        check("Post Write error -> fail", r.get("outcome") == "fail" and "permission" in r.get("error", ""), str(r))

        # Agent empty final -> empty
        run(td, {"session_id": "t", "cwd": td, "tool_name": "Agent",
                 "hook_event_name": "PostToolUse",
                 "tool_input": {"prompt": "review"},
                 "tool_response": {"result": "   "}})
        r = trace(td)[-1]
        check("Post Agent пустой финал -> empty", r.get("outcome") == "empty", str(r))

        # Agent with text -> ok
        run(td, {"session_id": "t", "cwd": td, "tool_name": "Agent",
                 "hook_event_name": "PostToolUse",
                 "tool_input": {"prompt": "review"},
                 "tool_response": {"result": "PASSED, no findings"}})
        r = trace(td)[-1]
        check("Post Agent с текстом -> ok", r.get("outcome") == "ok", str(r))

        # полнота: каждый tool-тип имеет outcome-строку
        rows = trace(td)
        posts = {x["tool"] for x in rows if x.get("phase") == "post"}
        with_outcome = {x["tool"] for x in rows if x.get("phase") == "post" and "outcome" in x}
        check("полнота: все post-события несут outcome", posts == with_outcome and posts, f"{posts} vs {with_outcome}")

    # регистрация под Pre и Post matcher "*"
    text = SYNC.read_text(encoding="utf-8")
    pre = text[text.index('"PreToolUse"'):text.index('"PostToolUse"')]
    post = text[text.index('"PostToolUse"'):text.index('"Stop"')]
    check("sync: execution-trace под PreToolUse", "execution-trace.sh" in pre)
    check("sync: execution-trace под PostToolUse matcher *",
          bool(re.search(r'"matcher":\s*"\*".*?execution-trace\.sh', post, re.S)),
          "не найден в PostToolUse")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

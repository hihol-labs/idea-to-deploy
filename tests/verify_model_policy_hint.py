#!/usr/bin/env python3
"""Behavioural test: hooks/model-policy.sh — advisory model-policy hint
(v1.83.0, retro 2026-07-11, component "Model").

Spawns the hook as a real subprocess (not doc-grep) and asserts:
  1. weaker override on a verify agent (security-reviewer opus -> sonnet)
     -> additionalContext hint, exit 0 (advisory, never a deny);
  2. no override -> silent exit 0;
  3. stronger/equal override -> silent exit 0;
  4. unknown agent type -> silent exit 0 (fail-open);
  5. garbage stdin -> silent exit 0 (never crashes);
  6. hint output is ASCII-only (Windows cp1251 pipe kills non-ASCII hooks).

Self-contained, stdlib only. Run: python3 tests/verify_model_policy_hint.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "model-policy.sh"
PY = sys.executable

PASSED, FAILED = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  -- " + detail) if detail else ""))


def run_hook(payload) -> subprocess.CompletedProcess:
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([PY, str(HOOK)], input=data, capture_output=True,
                          encoding="utf-8", errors="replace",
                          cwd=str(ROOT), timeout=30)


def main() -> int:
    r = run_hook({"tool_name": "Agent",
                  "tool_input": {"subagent_type": "security-reviewer",
                                 "model": "sonnet"}})
    ok_hint = False
    try:
        out = json.loads(r.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        ok_hint = ("MODEL POLICY" in ctx and "security-reviewer" in ctx
                   and "opus" in ctx and "sonnet" in ctx
                   and out["hookSpecificOutput"]["hookEventName"] == "PreToolUse")
    except Exception:
        pass
    check("weaker override on verify agent -> advisory hint",
          r.returncode == 0 and ok_hint, r.stdout[:300])
    check("hint is ASCII-only (cp1251-safe pipe)",
          all(ord(c) < 128 for c in r.stdout), r.stdout[:200])

    r = run_hook({"tool_name": "Agent",
                  "tool_input": {"subagent_type": "security-reviewer"}})
    check("no override -> silent", r.returncode == 0 and not r.stdout.strip(),
          r.stdout[:200])

    r = run_hook({"tool_name": "Agent",
                  "tool_input": {"subagent_type": "code-reviewer",
                                 "model": "opus"}})
    check("stronger override -> silent", r.returncode == 0
          and not r.stdout.strip(), r.stdout[:200])

    r = run_hook({"tool_name": "Task",
                  "tool_input": {"subagent_type": "no-such-agent-xyz",
                                 "model": "haiku"}})
    check("unknown agent -> silent fail-open", r.returncode == 0
          and not r.stdout.strip(), r.stdout[:200])

    r = run_hook("{not json")
    check("garbage stdin -> silent exit 0", r.returncode == 0
          and not r.stdout.strip(), r.stdout[:200])

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

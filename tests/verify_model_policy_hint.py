#!/usr/bin/env python3
"""Behavioural test: hooks/model-policy.sh — model/effort routing boundary.

Spawns the hook as a real subprocess (not doc-grep) and asserts:
  1. weaker override on a verify agent (security-reviewer opus -> sonnet)
     -> additionalContext hint, exit 0 (advisory, never a deny);
  2. no override -> silent exit 0;
  3. stronger/equal override -> silent exit 0;
  4. low effort on an already-low mechanical role -> silent exit 0;
  5. low effort on a medium role is silent only for a bounded low/medium-risk
     working_deadline slice with an explicit mechanical marker;
  6. protected roles, high/unknown risk, missing profile, or missing mechanical
     marker -> host-native ASK (no silent downgrade, no new hard gate);
  7. unknown agent type for a model-only override stays silent;
  8. garbage stdin -> silent exit 0 (never crashes);
  9. every emitted payload is ASCII-only (Windows cp1251-safe).

Self-contained, stdlib only. Run: python3 tests/verify_model_policy_hint.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
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


def run_hook(payload, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([PY, str(HOOK)], input=data, capture_output=True,
                          encoding="utf-8", errors="replace",
                          cwd=str(cwd), timeout=30)


def write_goal(root: Path, risk: str, profile: str) -> None:
    memory = root / ".itd-memory"
    memory.mkdir(parents=True, exist_ok=True)
    goal = {
        "currentUnitId": "T-001",
        "units": [{
            "id": "T-001",
            "status": "in_progress",
            "riskTier": risk,
            "deadlineState": {"profile": profile},
        }],
    }
    (memory / "GOAL.json").write_text(json.dumps(goal), encoding="utf-8")


def ask_payload(result: subprocess.CompletedProcess) -> tuple[bool, str]:
    try:
        parsed = json.loads(result.stdout)
        specific = parsed["hookSpecificOutput"]
        reason = specific["permissionDecisionReason"]
        return (result.returncode == 0
                and specific["hookEventName"] == "PreToolUse"
                and specific["permissionDecision"] == "ask", reason)
    except Exception:
        return False, ""


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

    r = run_hook({"tool_name": "Agent",
                  "tool_input": {"subagent_type": "doc-writer",
                                 "effort": "low"}})
    check("declared-low mechanical role -> silent without active profile",
          r.returncode == 0 and not r.stdout.strip(), r.stdout[:200])

    with tempfile.TemporaryDirectory(prefix="itd-model-policy-") as tmp:
        cwd = Path(tmp)
        write_goal(cwd, "medium", "working_deadline")
        allowed = run_hook({"tool_name": "Agent",
                            "tool_input": {
                                "subagent_type": "researcher",
                                "effort": "low",
                                "description": "[itd:mechanical] normalize table",
                            }}, cwd)
        check("bounded medium mechanical working_deadline -> low effort silent",
              allowed.returncode == 0 and not allowed.stdout.strip(),
              allowed.stdout[:200])

        protected = run_hook({"tool_name": "Agent",
                              "tool_input": {
                                  "subagent_type": "code-reviewer",
                                  "effort": "low",
                                  "description": "[itd:mechanical] review tiny diff",
                              }}, cwd)
        ok, reason = ask_payload(protected)
        check("review quality floor -> host ASK",
              ok and "protected quality-floor" in reason, protected.stdout[:300])

        unmarked = run_hook({"tool_name": "Agent",
                             "tool_input": {
                                 "subagent_type": "researcher",
                                 "effort": "low",
                                 "description": "summarize a bounded table",
                             }}, cwd)
        ok, reason = ask_payload(unmarked)
        check("missing mechanical marker -> host ASK",
              ok and "not marked mechanical" in reason, unmarked.stdout[:300])

        write_goal(cwd, "high", "working_deadline")
        high = run_hook({"tool_name": "Agent",
                         "tool_input": {
                             "subagent_type": "researcher",
                             "effort": "low",
                             "description": "[itd:mechanical] summarize",
                         }}, cwd)
        ok, reason = ask_payload(high)
        check("high risk -> host ASK", ok and "active risk is 'high'" in reason,
              high.stdout[:300])

        write_goal(cwd, "medium", "strict")
        unbounded = run_hook({"tool_name": "Agent",
                              "tool_input": {
                                  "subagent_type": "researcher",
                                  "effort": "low",
                                  "description": "[itd:mechanical] summarize",
                              }}, cwd)
        ok, reason = ask_payload(unbounded)
        check("working_deadline absent -> host ASK",
              ok and "working_deadline is not active" in reason,
              unbounded.stdout[:300])

        for emitted in (protected, unmarked, high, unbounded):
            check("effort policy output is ASCII-only",
                  all(ord(c) < 128 for c in emitted.stdout), emitted.stdout[:200])

    with tempfile.TemporaryDirectory(prefix="itd-model-policy-unknown-") as tmp:
        unknown = run_hook({"tool_name": "Agent",
                            "tool_input": {
                                "subagent_type": "researcher",
                                "effort": "low",
                                "description": "[itd:mechanical] summarize",
                            }}, Path(tmp))
        ok, reason = ask_payload(unknown)
        check("unknown risk -> host ASK",
              ok and "active risk is 'unknown'" in reason, unknown.stdout[:300])

    r = run_hook("{not json")
    check("garbage stdin -> silent exit 0", r.returncode == 0
          and not r.stdout.strip(), r.stdout[:200])

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

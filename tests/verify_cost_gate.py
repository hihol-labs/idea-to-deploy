#!/usr/bin/env python3
"""
verify_cost_gate.py — regression test for the two-stage budget gate in
hooks/cost-tracker.sh (v1.30.0, omnigent cost_budget port).

Asserts:
  1. HARD stage fires a STOP/ASK at/above 100% of the ceiling.
  2. HARD re-fire is suppressed within the +500k-token window.
  3. SOFT stage warns (warn-only) between 80% and 100%.
  4. Below 80% the hook is silent.
  5. Malformed stdin never crashes the hook (rc=0, silent).
  6. ITD_COST_CEILING_TOKENS env override is respected.

Run: python3 tests/verify_cost_gate.py   (exit 0 = pass, 1 = fail)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "cost-tracker.sh")


def _run(session: str, ledger_state, payload, extra_env=None) -> str:
    env = dict(os.environ, CLAUDE_SESSION_ID=session)
    if extra_env:
        env.update(extra_env)
    lf = f"/tmp/claude-cost-{session}.json"
    if ledger_state is None:
        try:
            os.remove(lf)
        except FileNotFoundError:
            pass
    else:
        with open(lf, "w") as f:
            json.dump(ledger_state, f)
    p = subprocess.run(["python3", HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, f"hook exited non-zero: {p.returncode} / {p.stderr}"
    return p.stdout.strip()


def _ctx(out: str) -> str:
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def main() -> int:
    fails: list[str] = []

    c = _ctx(_run("vcg-hard",
                  {"total_tokens": 1_999_500, "total_calls": 500, "by_tool": {},
                   "warnings_sent": 3, "hard_fired_at_tokens": 0},
                  {"tool_name": "Bash", "tool_input": {}}))
    if "HARD CEILING" not in c or "STOP" not in c:
        fails.append(f"1. HARD gate did not fire STOP/ASK: {c[:80]!r}")

    out = _run("vcg-refire",
               {"total_tokens": 2_100_000, "total_calls": 600, "by_tool": {},
                "warnings_sent": 3, "hard_fired_at_tokens": 2_099_700},
               {"tool_name": "Glob", "tool_input": {}})
    if _ctx(out):
        fails.append("2. HARD re-fire not suppressed within +500k window")

    c = _ctx(_run("vcg-soft",
                  {"total_tokens": 1_610_000, "total_calls": 400, "by_tool": {},
                   "warnings_sent": 0, "hard_fired_at_tokens": 0},
                  {"tool_name": "Read", "tool_input": {}}))
    if "approaching budget ceiling" not in c.lower() or "HARD CEILING" in c:
        fails.append(f"3. SOFT gate wrong: {c[:80]!r}")

    if _run("vcg-low", None, {"tool_name": "Glob", "tool_input": {}}):
        fails.append("4. below threshold not silent")

    p = subprocess.run(["python3", HOOK], input="not json", capture_output=True,
                       text=True, env=dict(os.environ, CLAUDE_SESSION_ID="vcg-bad"))
    if p.returncode != 0 or p.stdout.strip():
        fails.append(f"5. bad JSON not graceful: rc={p.returncode} out={p.stdout!r}")

    c = _ctx(_run("vcg-env",
                  {"total_tokens": 60_000, "total_calls": 10, "by_tool": {},
                   "warnings_sent": 3, "hard_fired_at_tokens": 0},
                  {"tool_name": "Bash", "tool_input": {}},
                  extra_env={"ITD_COST_CEILING_TOKENS": "50000"}))
    if "HARD CEILING" not in c:
        fails.append("6. ITD_COST_CEILING_TOKENS override not respected")

    # 7. ceiling=0 means "disabled" — must stay silent, not spam HARD every call
    out = _run("vcg-zero",
               {"total_tokens": 5_000, "total_calls": 5, "by_tool": {},
                "warnings_sent": 0, "hard_fired_at_tokens": 0},
               {"tool_name": "Bash", "tool_input": {}},
               extra_env={"ITD_COST_CEILING_TOKENS": "0"})
    if _ctx(out):
        fails.append(f"7. ceiling=0 not silent (disable semantics): {_ctx(out)[:60]!r}")

    if fails:
        print("verify_cost_gate: FAILED")
        for f in fails:
            print("  - " + f)
        return 1
    print("verify_cost_gate: PASSED (7/7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

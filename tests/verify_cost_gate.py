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
from pathlib import Path
import subprocess
import sys
import tempfile

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


def _decision(out: str) -> str:
    try:
        return str((json.loads(out).get("hookSpecificOutput") or {}).get(
            "permissionDecision") or "")
    except Exception:
        return ""


def _preflight(tmp: str, session: str, ledger_state: dict, tool: str,
               command: str = "", ceiling: str = "50000"):
    path = Path(tmp) / f"claude-cost-{session}.json"
    path.write_text(json.dumps(ledger_state), encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "TMPDIR": tmp,
        "TEMP": tmp,
        "TMP": tmp,
        "CLAUDE_SESSION_ID": session,
        "ITD_COST_CEILING_TOKENS": ceiling,
    })
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": session,
        "tool_name": tool,
        "tool_input": {"command": command},
    }
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    after = json.loads(path.read_text(encoding="utf-8"))
    return result, after


def _preflight_registered(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    groups = (payload.get("hooks") or payload).get("PreToolUse") or []
    for group in groups:
        matcher = set(str(group.get("matcher") or "").split("|"))
        commands = " ".join(
            str(hook.get("command") or "") + " "
            + str(hook.get("commandWindows") or "")
            for hook in group.get("hooks") or []
        )
        if {"Bash", "PowerShell", "Task", "Agent"} <= matcher \
                and "cost-tracker.sh" in commands:
            return True
    return False


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

    base_state = {
        "session_start": 0,
        "total_tokens": 40_000,
        "total_calls": 10,
        "by_tool": {},
        "warnings_sent": 0,
        "hard_fired_at_tokens": 0,
    }
    with tempfile.TemporaryDirectory(prefix="itd-cost-preflight-") as tmp:
        result, after = _preflight(tmp, "pre-agent", base_state, "Agent")
        if result.returncode != 2 or _decision(result.stdout) != "deny":
            fails.append(
                "8. next expensive Agent attempt was not denied before crossing "
                f"the ceiling: rc={result.returncode} out={result.stdout[:100]!r}"
            )
        if after != base_state:
            fails.append("8b. denied pre-attempt mutated the cost ledger")

        result, after = _preflight(
            tmp, "pre-cheap", base_state, "Bash", "git status")
        if result.returncode != 0 or result.stdout.strip():
            fails.append(
                "9. cheap low-risk inspection paid the blocking path: "
                f"rc={result.returncode} out={result.stdout[:100]!r}"
            )
        if after != base_state:
            fails.append("9b. low-risk preflight mutated the cost ledger")

        result, _ = _preflight(
            tmp, "pre-suite", base_state, "Bash", "bash tests/run-all.sh --quick",
            ceiling="40500")
        if result.returncode != 2 or _decision(result.stdout) != "deny":
            fails.append(
                "10. expensive full-suite shell attempt crossed the ceiling: "
                f"rc={result.returncode} out={result.stdout[:100]!r}"
            )

    root = Path(REPO)
    registration_paths = [
        root / "hooks" / "hooks.json",
        root / "skills" / "adopt" / "references" / "codex-project-hooks.json",
        root / "skills" / "adopt" / "references" / "project-settings-template.json",
    ]
    missing = [str(path.relative_to(root)) for path in registration_paths
               if not _preflight_registered(path)]
    sync = (root / "scripts" / "sync-to-active.sh").read_text(encoding="utf-8")
    sync_block = (
        '"matcher": "Bash|PowerShell|Task|Agent"' in sync
        and '"command": "~/.claude/hooks/cost-tracker.sh"' in sync
    )
    if missing or not sync_block:
        fails.append(
            "11. cost preflight is not registered on every host/install path: "
            f"missing={missing} sync={sync_block}"
        )

    if fails:
        print("verify_cost_gate: FAILED")
        for f in fails:
            print("  - " + f)
        return 1
    print("verify_cost_gate: PASSED (11/11; pre-attempt stop + low-risk fast path)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

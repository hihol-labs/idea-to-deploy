#!/usr/bin/env python3
"""Behavioural proof: completion-signals collects runtime signals from the
PowerShell tool on par with Bash (v1.88.0, GP-001 «пункт 1: сбор рантайм-
сигналов» — Windows-канал).

Spawns hooks/completion-signals.sh with real PostToolUse JSON on stdin and
asserts the actual ledger outcome in a temp project:

  - tool_name "PowerShell" + test runner command -> signal layer 2 / pass
  - tool_name "PowerShell" + Invoke-Pester fail  -> signal layer 2 / fail + red mark
  - tool_name "Bash" keeps working (regression)
  - tool_name "WebFetch" ignored (no ledger)
  - sync-to-active.sh registers the hook under the "PowerShell" matcher

Self-contained, stdlib only. Run: python3 tests/verify_completion_signals_powershell.py
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "completion-signals.sh"
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


def run_hook(cwd, tool_name, command, response):
    payload = {
        "session_id": "ps-probe",
        "cwd": str(cwd),
        "tool_name": tool_name,
        "tool_input": {"command": command},
        "tool_response": response,
    }
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
    )
    return p


def signals(cwd):
    f = Path(cwd) / ".claude" / "completion" / "signals.jsonl"
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    with tempfile.TemporaryDirectory() as td:
        # 1) PowerShell test runner -> L2 pass
        p = run_hook(td, "PowerShell", 'npm test; echo "EXIT: $LASTEXITCODE"',
                     {"stdout": "Tests: 5 passed\nEXIT: 0", "exitCode": 0})
        rows = signals(td)
        check("ps-npm-test записан", len(rows) == 1, f"rows={len(rows)} rc={p.returncode}")
        if rows:
            check("ps-npm-test layer 2 / pass",
                  rows[0].get("layer") == 2 and rows[0].get("outcome") == "pass",
                  json.dumps(rows[0], ensure_ascii=False))

        # 2) Invoke-Pester fail -> L2 fail + красная пометка в additionalContext
        p = run_hook(td, "PowerShell", "Invoke-Pester -Path tests",
                     {"stdout": "Tests Passed: 3, Failed: 2\nFAILED", "exitCode": 1})
        rows = signals(td)
        check("Invoke-Pester fail записан", len(rows) == 2, f"rows={len(rows)}")
        if len(rows) == 2:
            check("Invoke-Pester layer 2 / fail",
                  rows[1].get("layer") == 2 and rows[1].get("outcome") == "fail",
                  json.dumps(rows[1], ensure_ascii=False))
        try:
            out = json.loads(p.stdout)
            ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        except Exception:
            ctx = ""
        check("красная пометка на PS-провале", "COMPLETION-SIGNALS" in ctx, p.stdout[:200])

    with tempfile.TemporaryDirectory() as td:
        # 3) Bash regression: прежний канал не сломан
        run_hook(td, "Bash", "pytest -q", {"stdout": "3 passed", "exitCode": 0})
        rows = signals(td)
        check("bash-канал жив (регрессия)",
              len(rows) == 1 and rows[0].get("layer") == 2 and rows[0].get("outcome") == "pass",
              json.dumps(rows, ensure_ascii=False)[:200])

        # 4) прочие tools игнорируются
        run_hook(td, "WebFetch", "pytest -q", {"stdout": "3 passed", "exitCode": 0})
        check("WebFetch игнорируется", len(signals(td)) == 1)

    # 5) регистрация: sync-to-active ставит хук под matcher "PowerShell"
    text = SYNC.read_text(encoding="utf-8")
    post = text[text.index('"PostToolUse"'):text.index('"Stop"')]
    m = re.search(r'"matcher":\s*"PowerShell".*?\]\s*\}', post, re.S)
    block = m.group(0) if m else ""
    check("sync-to-active: completion-signals под PowerShell-matcher",
          "completion-signals.sh" in block,
          block[:200] or "matcher PowerShell не найден")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

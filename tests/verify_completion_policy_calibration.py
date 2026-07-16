#!/usr/bin/env python3
"""Calibration proof: strict high risk, advisory low risk, audited bypass."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "hooks" / "completion-gate.sh"
POLICY = ROOT / "docs" / "templates" / "itd" / "COMPLETION_POLICY.json"
passed = failed = 0


def check(name: str, condition: bool) -> None:
    global passed, failed
    print(f"{'PASS' if condition else 'FAIL'}  {name}")
    if condition:
        passed += 1
    else:
        failed += 1


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                   text=True, timeout=20)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def set_risk(repo: Path, risk: str) -> None:
    write_json(repo / ".itd-memory" / "STATE.json", {
        "currentUnit": {"id": "CAL-1", "status": "in_progress",
                        "riskTier": risk}})


def run_gate(repo: Path, description: str = ""):
    payload = {"session_id": "calibration", "cwd": str(repo),
               "tool_name": "Bash", "tool_input": {
                   "command": "git commit -m calibration",
                   "description": description}}
    result = subprocess.run([sys.executable, str(GATE)], input=json.dumps(payload),
                            capture_output=True, text=True, timeout=30)
    output = json.loads(result.stdout) if result.stdout.strip() else {}
    hook = output.get("hookSpecificOutput") or {}
    return result, hook.get("permissionDecision"), output.get("systemMessage", "")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-completion-calibration-") as td:
        repo = Path(td)
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "cal@example.test")
        git(repo, "config", "user.name", "Calibration")
        (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        git(repo, "add", "app.py")
        write_json(repo / ".itd" / "COMPLETION_POLICY.json",
                   json.loads(POLICY.read_text(encoding="utf-8")))

        set_risk(repo, "low")
        result, decision, message = run_gate(repo)
        check("low-risk no-signal source commit is advisory, not hard-blocked",
              result.returncode == 0 and decision != "deny"
              and "НЕ подтверждено" in message)

        set_risk(repo, "medium")
        result, decision, _ = run_gate(repo)
        check("calibrated medium no-signal remains advisory",
              result.returncode == 0 and decision != "deny")

        set_risk(repo, "high")
        result, decision, _ = run_gate(repo)
        check("the same no-signal commit becomes strict at high risk",
              result.returncode == 2 and decision == "deny")

        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        policy["mode"] = "strict"
        write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)
        set_risk(repo, "low")
        result, decision, _ = run_gate(repo)
        check("strict project mode overrides low unit risk",
              result.returncode == 2 and decision == "deny")

        policy["mode"] = "calibrated"
        write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)
        signals = repo / ".claude" / "completion" / "signals.jsonl"
        signals.parent.mkdir(parents=True, exist_ok=True)
        signals.write_text(json.dumps({
            "session": "calibration", "layer": 2, "kind": "test_run",
            "outcome": "fail", "command": "pytest", "evidence": "1 failed"})
            + "\n", encoding="utf-8")
        result, decision, _ = run_gate(repo)
        check("low-risk still blocks known failed runtime evidence",
              result.returncode == 2 and decision == "deny")

        signals.unlink()
        result, decision, _ = run_gate(repo, "COMPLETION_BYPASS: accepted debt")
        events = repo / ".itd-memory" / "events.jsonl"
        check("calibrated bypass remains explicit and auditable",
              result.returncode == 0 and decision != "deny" and events.is_file()
              and "accepted debt" in events.read_text(encoding="utf-8"))

        result, decision, _ = run_gate(repo, "COMPLETION_BYPASS:")
        check("empty bypass is never accepted, even at low risk",
              result.returncode == 2 and decision == "deny")

        git(repo, "reset", "-q")
        (repo / "README.md").write_text("docs only\n", encoding="utf-8")
        git(repo, "add", "README.md")
        policy["mode"] = "strict"
        write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)
        result, decision, _ = run_gate(repo)
        check("strict policy does not hard-block docs-only commit",
              result.returncode == 0 and decision != "deny")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

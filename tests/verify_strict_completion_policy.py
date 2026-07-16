#!/usr/bin/env python3
"""Strict/high-risk source-commit and explicit-close completion boundaries."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "hooks" / "completion-gate.sh"
DISPATCH = ROOT / "hooks" / "codex-dispatch.py"
SIGNALS_HOOK = ROOT / "hooks" / "completion-signals.sh"
HYGIENE = ROOT / "docs" / "templates" / "itd" / "itd_hygiene.py"
POLICY_TEMPLATE = ROOT / "docs" / "templates" / "itd" / "COMPLETION_POLICY.json"
passed = failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    print(f"{'PASS' if condition else 'FAIL'}  {name}"
          + (f" [{detail[:250]}]" if detail and not condition else ""))
    if condition:
        passed += 1
    else:
        failed += 1


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=20)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def init_source_repo(base: Path, risk: str = "high") -> Path:
    repo = base / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "strict@example.test")
    git(repo, "config", "user.name", "Strict Completion")
    (repo / ".gitignore").write_text(".verification-status\n", encoding="utf-8")
    (repo / ".verification-status").write_text("pass\n", encoding="utf-8")
    (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    write_json(repo / ".itd-memory" / "STATE.json", {
        "currentUnit": {"id": "STRICT-1", "status": "in_progress",
                        "riskTier": risk}})
    policy = json.loads(POLICY_TEMPLATE.read_text(encoding="utf-8"))
    write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)
    write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", {
        "version": 1,
        "commands": [{"id": "tests", "command": command(
            "import time; s=open('.verification-status').read().strip(); "
            "time.sleep(4 if s == 'slow' else 0); "
            "raise SystemExit(0 if s in ('pass', 'slow') else 7)"),
                      "timeoutSeconds": 30, "expectedOutput": "",
                      "passFailParser": "exit_code_zero"}],
    })
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "approved source and verification baseline")
    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    git(repo, "add", "app.py")
    return repo


def seed_signals(repo: Path, rows: list[dict], session: str = "probe") -> None:
    target = repo / ".claude" / "completion" / "signals.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = []
    for row in rows:
        item = dict(row)
        layer = int(item.get("layer", 0))
        item.setdefault("kind", "test_run" if layer == 2 else "static")
        item.setdefault("command", "pytest -q" if layer == 2 else "ruff check .")
        item.setdefault("evidence", "12 passed" if item.get("outcome") == "pass"
                        else "verification failed")
        item.update({"session": session, "ts": "2026-07-15T00:00:00Z",
                     "producer": "itd-completion-signals"})
        normalized.append(item)
    target.write_text("".join(json.dumps(row) + "\n" for row in normalized),
                      encoding="utf-8")


def run_gate(repo: Path, description: str = "", env_extra: dict[str, str] | None = None,
             session_id: str = "probe", cwd: Path | None = None,
             command_text: str = "git commit -m strict", tool_name: str = "Bash"):
    payload = {"session_id": session_id, "cwd": str(cwd or repo), "tool_name": "Bash",
               "tool_input": {"command": command_text,
                              "description": description}}
    payload["tool_name"] = tool_name
    env = dict(os.environ)
    env.update(env_extra or {})
    result = subprocess.run([sys.executable, str(GATE)], input=json.dumps(payload),
                            capture_output=True, text=True, env=env, timeout=900)
    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception:
        output = {}
    hook = output.get("hookSpecificOutput") or {}
    return result, hook.get("permissionDecision"), hook.get("permissionDecisionReason", "")


def run_dispatch_gate(repo: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    payload = {
        "session_id": "probe", "cwd": str(repo), "tool_name": "Bash",
        "hook_event_name": "PreToolUse",
        "tool_input": {"command": "git commit -m strict", "description": ""},
    }
    env = dict(os.environ)
    env["PLUGIN_ROOT"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, str(DISPATCH), "--script", "completion-gate.sh"],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
        timeout=20)
    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception:
        output = {}
    return result, output


def run_raw_gate(payload) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run([sys.executable, str(GATE)], input=json.dumps(payload),
                            capture_output=True, text=True, timeout=30)
    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception:
        output = {}
    return result, output.get("hookSpecificOutput") or {}


def command(code: str) -> str:
    return subprocess.list2cmdline([sys.executable, "-c", code])


def init_close_repo(base: Path) -> Path:
    repo = base / "close-repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "close@example.test")
    git(repo, "config", "user.name", "Strict Close")
    (repo / ".gitignore").write_text(
        ".claude/completion/\n.itd-memory/events.jsonl\n"
        ".itd-memory/.active-session.lock\n.verification-status\n", encoding="utf-8")
    (repo / ".verification-status").write_text("pass\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    write_json(repo / ".itd-memory" / "STATE.json", {
        "currentUnit": {"id": "CLOSE-1", "status": "verified",
                        "riskTier": "high"}})
    write_json(repo / ".itd-memory" / "session-artifacts.json",
               {"version": 1, "artifacts": []})
    policy = json.loads(POLICY_TEMPLATE.read_text(encoding="utf-8"))
    write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)
    write_json(repo / ".itd" / "VERIFICATION_CONTRACT.json", {
        "version": 1,
        "commands": [{"id": "tests", "command": command(
            "s=open('.verification-status').read().strip(); "
            "raise SystemExit(0 if s == 'pass' else 9)"),
                      "timeoutSeconds": 30, "expectedOutput": "",
                      "passFailParser": "exit_code_zero"}],
    })
    write_json(repo / ".itd" / "QUALITY.json", {
        "version": 1, "reviewedAt": dt.date.today().isoformat(), "maxAgeDays": 30,
        "modules": [{"id": "app", "grade": "A", "verification": "passing",
                     "agentUnderstandable": "yes", "testStability": "stable",
                     "architectureBoundaries": "compliant",
                     "codeConventions": "followed",
                     "reviewedAt": dt.date.today().isoformat(),
                     "evidence": ["src/app.py"], "priorities": []}],
    })
    write_json(repo / ".itd" / "SESSION_EXIT_CONTRACT.json", {
        "version": 1, "mode": "explicit_close",
        "verificationContract": ".itd/VERIFICATION_CONTRACT.json",
        "completionPolicy": ".itd/COMPLETION_POLICY.json",
        "requireCleanGit": True,
        "requiredStateFiles": [".itd-memory/STATE.json"],
        "startupProbeCommand": command("raise SystemExit(0)"),
        "startupTimeoutSeconds": 30,
        "cleanupManifest": ".itd-memory/session-artifacts.json",
        "qualityLedger": ".itd/QUALITY.json", "qualityMaxAgeDays": 30,
        "debugScan": {"enabled": True, "paths": ["src"], "excludeGlobs": [],
                      "patterns": [r"\bdebugger\b"]},
    })
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "strict close fixture")
    return repo


def run_close(repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["ITD_SESSION_ID"] = "close-probe"
    return subprocess.run(
        [sys.executable, str(HYGIENE), "close", "--root", str(repo),
         "--contract", ".itd/SESSION_EXIT_CONTRACT.json", *extra],
        cwd=repo, capture_output=True, text=True, env=env, timeout=60)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-strict-completion-") as td:
        repo = init_source_repo(Path(td))
        result, hook = run_raw_gate([])
        check("non-object hook payload fails closed",
              result.returncode == 2 and hook.get("permissionDecision") == "deny")
        result, hook = run_raw_gate({"tool_name": "Bash", "tool_input": []})
        check("non-object tool_input fails closed",
              result.returncode == 2 and hook.get("permissionDecision") == "deny")
        result, decision, reason = run_gate(repo)
        check("high-risk source commit without signals is denied",
              result.returncode == 2 and decision == "deny" and "missing" in reason)
        for label, command_text in (
                ("git -C", f'git -C "{repo}" commit -m strict'),
                ("git --git-dir", "git --git-dir=.git commit -m strict"),
                ("absolute git path", "/usr/bin/git commit -m strict"),
                ("command wrapper", "command git commit -m strict"),
                ("env wrapper", "env ITD_PROBE=1 git commit -m strict"),
                ("env chdir wrapper", "env -C . git commit -m strict"),
                ("env unset wrapper", "env -u HOME git commit -m strict"),
                ("sudo wrapper", "sudo git commit -m strict"),
                ("sudo user wrapper", "sudo -u root git commit -m strict"),
                ("sudo chdir wrapper", "sudo -D . git commit -m strict"),
                ("sudo preserve wrapper",
                 "sudo --preserve-env=HOME git commit -m strict"),
                ("sudo close-from wrapper",
                 "sudo --close-from=3 git commit -m strict")):
            result, decision, _ = run_gate(repo, command_text=command_text)
            check(f"{label} commit form cannot bypass strict gate",
                  result.returncode == 2 and decision == "deny")
        result, decision, _ = run_gate(repo, tool_name="PowerShell")
        check("PowerShell commit channel cannot bypass strict gate",
              result.returncode == 2 and decision == "deny")

        rename_base = Path(td) / "rename-case"
        rename_base.mkdir()
        rename_repo = init_source_repo(rename_base)
        git(rename_repo, "mv", "app.py", "app.txt")
        result, decision, _ = run_gate(rename_repo)
        check("source-to-non-source rename remains inside strict scope",
              result.returncode == 2 and decision == "deny")

        seed_signals(repo, [{"layer": 1, "outcome": "pass"}])
        result, decision, _ = run_gate(repo)
        check("L1-only evidence is insufficient in strict mode",
              result.returncode == 2 and decision == "deny")

        seed_signals(repo, [{"layer": 2, "kind": "test_run", "outcome": "unknown"}])
        result, decision, reason = run_gate(repo)
        check("ambiguous runtime outcome is denied",
              result.returncode == 2 and decision == "deny"
              and ("ambiguous" in reason or "not verified" in reason))

        seed_signals(repo, [{"layer": 2, "kind": "test_run", "outcome": "fail",
                             "command": "pytest", "evidence": "1 failed"}])
        result, decision, _ = run_gate(repo)
        check("failed runtime evidence is denied",
              result.returncode == 2 and decision == "deny")

        seed_signals(repo, [{"layer": 1, "outcome": "pass"},
                            {"layer": 2, "kind": "test_run", "outcome": "pass",
                             "command": "pytest", "evidence": "12 passed"}])
        result, decision, _ = run_gate(repo)
        check("green L2 runtime evidence permits strict commit",
              result.returncode == 0 and decision != "deny")

        verification_path = repo / ".itd" / "VERIFICATION_CONTRACT.json"
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        weakened = json.loads(json.dumps(verification))
        weakened["commands"][0]["expectedOutput"] = "agent-weakened-oracle"
        write_json(verification_path, weakened)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        result, decision, reason = run_gate(repo)
        check("staged verifier weakening cannot authorize a source commit",
              result.returncode == 2 and decision == "deny"
              and "differs from HEAD" in reason, reason)
        git(repo, "reset", "-q", "HEAD", "--", ".itd/VERIFICATION_CONTRACT.json")
        write_json(verification_path, verification)

        policy_path = repo / ".itd" / "COMPLETION_POLICY.json"
        canonical_policy = json.loads(policy_path.read_text(encoding="utf-8"))
        redirected_policy = json.loads(json.dumps(canonical_policy))
        redirected_policy["verificationContract"] = ".itd/ALTERNATE_CONTRACT.json"
        write_json(policy_path, redirected_policy)
        result, decision, reason = run_gate(repo)
        check("completion policy cannot redirect the canonical strict verifier",
              result.returncode == 2 and decision == "deny"
              and "must be the canonical" in reason, reason)
        write_json(policy_path, canonical_policy)

        (repo / ".verification-status").write_text("fail\n", encoding="utf-8")
        # This is a complete, schema-valid row with the expected producer.  It
        # is intentionally forged directly into the workspace ledger.  Strict
        # completion must bind authorization to the rerun, not this assertion.
        seed_signals(repo, [{"layer": 2, "kind": "test_run", "outcome": "pass",
                             "command": "pytest -q", "evidence": "999 passed"}])
        result, decision, reason = run_gate(repo)
        check("fully forged passing ledger cannot bypass a failing strict rerun",
              result.returncode == 2 and decision == "deny"
              and "verification command tests failed" in reason, reason)
        (repo / ".verification-status").write_text("pass\n", encoding="utf-8")

        seed_signals(repo, [{"layer": 2, "kind": "test_run", "outcome": "pass",
                             "command": "pytest -q", "evidence": "12 passed"}])
        (repo / ".verification-status").write_text("slow\n", encoding="utf-8")
        dispatched, dispatch_output = run_dispatch_gate(repo)
        dispatch_hook = dispatch_output.get("hookSpecificOutput") or {}
        check("Codex dispatcher allows a valid verifier longer than three seconds",
              dispatched.returncode == 0
              and dispatch_hook.get("permissionDecision") != "deny",
              dispatched.stderr or dispatched.stdout)
        (repo / ".verification-status").write_text("pass\n", encoding="utf-8")

        verification_path.unlink()
        result, decision, reason = run_gate(repo)
        check("missing strict verification contract fails closed",
              result.returncode == 2 and decision == "deny"
              and "verification contract is missing" in reason, reason)
        write_json(verification_path, verification)

        ledger = repo / ".claude" / "completion" / "signals.jsonl"
        ledger.write_text(json.dumps({"session": "probe", "layer": 2,
                                      "outcome": "pass"}) + "\n", encoding="utf-8")
        result, decision, _ = run_gate(repo)
        check("hand-written bare L2 pass cannot satisfy strict evidence",
              result.returncode == 2 and decision == "deny")
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}])
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write("{malformed\n")
        result, decision, _ = run_gate(repo)
        check("malformed row plus valid pass is denied",
              result.returncode == 2 and decision == "deny")
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}])
        row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
        row["producer"] = "self-authored"
        ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
        result, decision, _ = run_gate(repo)
        check("untrusted signal producer is denied",
              result.returncode == 2 and decision == "deny")
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}])
        bad_layer = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
        bad_layer["layer"] = "not-a-layer"
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(bad_layer) + "\n")
        result, decision, _ = run_gate(repo)
        check("invalid layer beside valid pass is denied",
              result.returncode == 2 and decision == "deny")
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}], "other-session")
        result, decision, _ = run_gate(repo, session_id="")
        check("missing session id cannot borrow another session's pass",
              result.returncode == 2 and decision == "deny")
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}], "stale-session")
        write_json(repo / ".itd-memory" / ".active-session.lock", {
            "session": "stale-session", "timestamp": 1})
        result, decision, _ = run_gate(repo, session_id="")
        check("stale session lock cannot authorize runtime evidence",
              result.returncode == 2 and decision == "deny")

        ledger.unlink()
        nested = repo / "src" / "nested"
        nested.mkdir(parents=True)
        result, decision, _ = run_gate(repo, cwd=nested)
        check("nested cwd still enforces root high-risk policy",
              result.returncode == 2 and decision == "deny")
        signal_payload = {
            "session_id": "probe", "cwd": str(nested), "tool_name": "Bash",
            "tool_input": {"command": "pytest -q"},
            "tool_response": {"stdout": "12 passed", "exitCode": 0},
        }
        signal_run = subprocess.run(
            [sys.executable, str(SIGNALS_HOOK)], input=json.dumps(signal_payload),
            capture_output=True, text=True, timeout=30)
        root_rows = [json.loads(line) for line in ledger.read_text(
            encoding="utf-8").splitlines() if line.strip()]
        check("nested runtime signal is rooted and producer-attributed",
              signal_run.returncode == 0 and len(root_rows) == 1
              and root_rows[0].get("producer") == "itd-completion-signals")
        result, decision, _ = run_gate(repo, cwd=nested)
        check("nested cwd accepts root-attributed green runtime evidence",
              result.returncode == 0 and decision != "deny")
        result, decision, _ = run_gate(
            repo, "COMPLETION_BYPASS: nested recovery", cwd=nested)
        check("nested cwd bypass audit is written only at canonical root",
              result.returncode == 0 and decision != "deny"
              and (repo / ".itd-memory" / "events.jsonl").is_file()
              and not (nested / ".itd-memory").exists())

        result, decision, _ = run_gate(repo, "COMPLETION_BYPASS:")
        check("empty bypass reason is denied",
              result.returncode == 2 and decision == "deny")
        result, decision, _ = run_gate(repo, "COMPLETION_BYPASS: emergency hotfix")
        events = repo / ".itd-memory" / "events.jsonl"
        check("reasoned bypass is allowed and durably audited",
              result.returncode == 0 and decision != "deny" and events.is_file()
              and "emergency hotfix" in events.read_text(encoding="utf-8"))

        policy = json.loads((repo / ".itd" / "COMPLETION_POLICY.json").read_text())
        policy["bypassAuditLedger"] = "."
        write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)
        result, decision, reason = run_gate(repo, "COMPLETION_BYPASS: cannot audit")
        check("bypass audit write failure is denied",
              result.returncode == 2 and decision == "deny" and "audit" in reason)
        policy["bypassAuditLedger"] = ".itd-memory/events.jsonl"
        write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)

        policy["strictRiskTiers"] = "high"
        write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)
        result, decision, _ = run_gate(repo)
        check("semantically invalid policy cannot disable high-risk strictness",
              result.returncode == 2 and decision == "deny")
        policy["strictRiskTiers"] = ["high"]
        write_json(repo / ".itd" / "COMPLETION_POLICY.json", policy)

        result, decision, _ = run_gate(repo, env_extra={"ITD_COMPLETION_GATE": "0"})
        check("strict kill switch without reason is denied",
              result.returncode == 2 and decision == "deny")
        result, decision, _ = run_gate(repo, env_extra={
            "ITD_COMPLETION_GATE": "0",
            "ITD_COMPLETION_BYPASS_REASON": "operator recovery"})
        check("reasoned kill switch is audited and allowed",
              result.returncode == 0 and decision != "deny"
              and "operator recovery" in events.read_text(encoding="utf-8"))

        (repo / ".itd" / "COMPLETION_POLICY.json").write_text("{broken", encoding="utf-8")
        (repo / ".itd-memory" / "STATE.json").write_text("{broken", encoding="utf-8")
        result, decision, _ = run_gate(repo)
        check("malformed policy plus risk state fails closed",
              result.returncode == 2 and decision == "deny")

    with tempfile.TemporaryDirectory(prefix="itd-strict-close-") as td:
        repo = init_close_repo(Path(td))
        close = run_close(repo)
        check("strict explicit close denies missing runtime ledger",
              close.returncode == 1 and "runtime signal ledger is missing" in close.stdout,
              close.stdout)
        ledger = repo / ".claude" / "completion" / "signals.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("{broken\n", encoding="utf-8")
        close = run_close(repo)
        check("strict explicit close denies malformed runtime evidence",
              close.returncode == 1 and "is malformed" in close.stdout,
              close.stdout)
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}], "close-probe")
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write("{malformed\n")
        close = run_close(repo)
        check("strict explicit close denies valid pass plus malformed row",
              close.returncode == 1 and "is malformed" in close.stdout,
              close.stdout)
        ledger.write_text(json.dumps({"session": "close-probe", "layer": 2,
                                      "outcome": "pass"}) + "\n", encoding="utf-8")
        close = run_close(repo)
        check("strict explicit close denies a bare hand-written pass",
              close.returncode == 1 and "missing fields" in close.stdout,
              close.stdout)
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}], "close-probe")
        bad_layer = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
        bad_layer["layer"] = "not-a-layer"
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(bad_layer) + "\n")
        close = run_close(repo)
        check("explicit close denies invalid layer beside valid pass",
              close.returncode == 1 and "layer is invalid" in close.stdout,
              close.stdout)
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}], "other-session")
        close = run_close(repo)
        check("strict explicit close cannot borrow another session's pass",
              close.returncode == 1 and "evidence is missing" in close.stdout,
              close.stdout)
        seed_signals(repo, [{"layer": 2, "outcome": "fail"}], "close-probe")
        close = run_close(repo)
        check("strict explicit close denies failed runtime evidence",
              close.returncode == 1 and "contains a failure" in close.stdout,
              close.stdout)
        seed_signals(repo, [{"layer": 2, "outcome": "pass"}], "close-probe")
        close = run_close(repo)
        check("strict explicit close accepts matching green runtime evidence",
              close.returncode == 0, close.stdout)
        verification_path = repo / ".itd" / "VERIFICATION_CONTRACT.json"
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        (repo / ".verification-status").write_text("fail\n", encoding="utf-8")
        seed_signals(repo, [{"layer": 2, "kind": "test_run", "outcome": "pass",
                             "command": "pytest -q", "evidence": "999 passed"}],
                     "close-probe")
        close = run_close(repo)
        check("fully forged passing ledger cannot bypass failing explicit-close rerun",
              close.returncode == 1 and "tests:" in close.stdout, close.stdout)

        exit_contract_path = repo / ".itd" / "SESSION_EXIT_CONTRACT.json"
        exit_contract = json.loads(exit_contract_path.read_text(encoding="utf-8"))
        late_verification_path = repo / ".itd" / "LATE_VERIFICATION_CONTRACT.json"
        late_verification = json.loads(json.dumps(verification))
        late_verification["commands"][0]["command"] = command("raise SystemExit(0)")
        write_json(late_verification_path, late_verification)
        mismatched_exit_contract = json.loads(json.dumps(exit_contract))
        mismatched_exit_contract["verificationContract"] = (
            ".itd/LATE_VERIFICATION_CONTRACT.json")
        write_json(exit_contract_path, mismatched_exit_contract)
        git(repo, "add", ".itd/SESSION_EXIT_CONTRACT.json",
            ".itd/LATE_VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "redirect explicit close verifier")
        close = run_close(repo)
        check("explicit close cannot redirect away from the policy baseline verifier",
              close.returncode == 1
              and "does not match the completion policy verifier" in close.stdout,
              close.stdout)
        write_json(exit_contract_path, exit_contract)
        late_verification_path.unlink()
        git(repo, "add", "-A", ".itd")
        git(repo, "commit", "-qm", "restore canonical explicit close verifier")

        (repo / ".verification-status").write_text("pass\n", encoding="utf-8")

        weakened = json.loads(json.dumps(verification))
        weakened["commands"][0]["expectedOutput"] = "agent-weakened-oracle"
        write_json(verification_path, weakened)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "weaken verifier after source checkpoint")
        close = run_close(repo)
        check("committed post-source verifier weakening cannot authorize close",
              close.returncode == 1
              and "changed after the last source-code checkpoint" in close.stdout,
              close.stdout)
        write_json(verification_path, verification)
        git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
        git(repo, "commit", "-qm", "restore approved verifier")

        policy_path = repo / ".itd" / "COMPLETION_POLICY.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["strictRiskTiers"] = "high"
        write_json(policy_path, policy)
        close = run_close(repo)
        check("explicit close rejects semantically invalid completion policy",
              close.returncode == 1 and "strictRiskTiers" in close.stdout,
              close.stdout)
        policy["strictRiskTiers"] = ["high"]
        write_json(policy_path, policy)
        ledger.unlink()
        close = run_close(repo, "--completion-bypass-reason", "approved recovery")
        events = repo / ".itd-memory" / "events.jsonl"
        check("strict explicit close bypass is audited and allowed",
              close.returncode == 0 and events.is_file()
              and "approved recovery" in events.read_text(encoding="utf-8"),
              close.stdout)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

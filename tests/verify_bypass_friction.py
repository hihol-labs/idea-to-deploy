#!/usr/bin/env python3
"""Operational-friction benchmark for every registered hard gate."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"
POLICY = ROOT / "docs" / "HARNESS_TRUST_POLICY.json"
CORPUS = ROOT / "benchmarks" / "operational-friction" / "BYPASS_FRICTION.json"
CORPUS_SHA = ROOT / "benchmarks" / "operational-friction" / "BYPASS_FRICTION.sha256"
sys.path.insert(0, str(ROOT / "tests"))
import verify_all_hard_gate_host_parity as parity  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def load_corpus() -> dict:
    raw = CORPUS.read_bytes()
    expected = CORPUS_SHA.read_text(encoding="utf-8").strip().split()[0]
    actual = hashlib.sha256(raw).hexdigest()
    check("friction corpus seal matches", actual == expected,
          f"expected={expected} actual={actual}")
    return json.loads(raw)


def init_repo(cwd: Path) -> None:
    cwd.mkdir(parents=True)
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "friction@example.invalid"],
        ["git", "config", "user.name", "Friction Fixture"],
    ):
        subprocess.run(args, cwd=str(cwd), check=True, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=30)


def isolated_env(root: Path, session: str) -> dict[str, str]:
    home = root / "home"
    tmp = root / "tmp"
    home.mkdir(exist_ok=True)
    tmp.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "USERPROFILE": str(home),
        "TMPDIR": str(tmp),
        "TEMP": str(tmp),
        "TMP": str(tmp),
        "PYTHONUTF8": "1",
        "CLAUDE_SESSION_ID": session,
        "PLUGIN_ROOT": str(ROOT),
    })
    return env


def invoke_payload(script: str, host: str, cwd: Path, env: dict[str, str],
                   payload: dict) -> tuple[int, str, str]:
    if host == "claude":
        command = [sys.executable, str(HOOKS / script)]
        env = dict(env, ITD_HOST="claude")
    else:
        command = [sys.executable, str(HOOKS / "codex-dispatch.py"), "--script", script]
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    decision, reason = parity.parse_decision(proc.stdout)
    return proc.returncode, decision, reason


def read_only_probe(script: str, host: str) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix=f"itd-friction-read-{host}-") as td:
        root = Path(td)
        cwd = root / "work"
        init_repo(cwd)
        session = f"friction-read-{uuid.uuid4().hex[:10]}"
        payload = {
            "hook_event_name": "PreToolUse",
            "session_id": session,
            "cwd": str(cwd),
            "tool_name": "Bash",
            "tool_input": {
                "command": "git status --short",
                "description": "read-only operational probe",
            },
        }
        return invoke_payload(script, host, cwd, isolated_env(root, session), payload)


def reasoned_bypass_probe(host: str) -> tuple[bool, bool, str]:
    with tempfile.TemporaryDirectory(prefix=f"itd-friction-bypass-{host}-") as td:
        root = Path(td)
        cwd = root / "work"
        init_repo(cwd)
        session = f"friction-bypass-{uuid.uuid4().hex[:10]}"
        env = isolated_env(root, session)
        (root / "tmp" / f"claude-skill-ignores-{session}.state").write_text("3", encoding="utf-8")
        bypass = {
            "hook_event_name": "PreToolUse",
            "session_id": session,
            "cwd": str(cwd),
            "tool_name": "Bash",
            "tool_input": {
                "command": "true",
                "description": "SKILL_BYPASS: frozen operational-friction fixture",
            },
        }
        rc, decision, reason = invoke_payload("check-tool-skill.sh", host, cwd, env, bypass)
        bypass_allowed = rc == 0 and decision not in {"deny", "block"}

        if host == "claude":
            mutation = {
                "hook_event_name": "PreToolUse",
                "session_id": session,
                "cwd": str(cwd),
                "tool_name": "Edit",
                "tool_input": {"file_path": str(cwd / "app.py"), "content": "x"},
            }
        else:
            mutation = {
                "hook_event_name": "PreToolUse",
                "session_id": session,
                "cwd": str(cwd),
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Add File: app.py\n+x\n*** End Patch"},
            }
        rc2, decision2, reason2 = invoke_payload("check-tool-skill.sh", host, cwd, env, mutation)
        mutation_allowed = rc2 == 0 and decision2 not in {"deny", "block"}
        ledger = root / "tmp" / f"claude-skill-ledger-{session}.jsonl"
        records = ([json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
                    if line.strip()] if ledger.is_file() else [])
        audited = any(row.get("reason") == "frozen operational-friction fixture"
                      for row in records)
        return bypass_allowed and audited, mutation_allowed, reason + reason2


def main() -> int:
    corpus = load_corpus()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy_gates = [row["script"] for row in policy["hardGates"]]
    check("corpus covers the exact hard-gate registry", policy_gates == corpus["hardGates"],
          f"policy={policy_gates} corpus={corpus['hardGates']}")

    required = corpus["denyContract"]["requiredMarkers"]
    deny_total = actionable = 0
    unactionable: list[str] = []
    for script in corpus["hardGates"]:
        for host in corpus["denyContract"]["hosts"]:
            rc, decision, reason = parity.invoke(script, host)
            expected_decision = next(row["decision"] for row in policy["hardGates"]
                                     if row["script"] == script)
            expected_rc = 0 if expected_decision == "block" else 2
            fired = rc == expected_rc and decision == expected_decision
            check(f"deny fixture fires: {host}/{script}", fired,
                  f"rc={rc} decision={decision!r} reason={reason[-240:]!r}")
            deny_total += 1
            is_actionable = fired and all(marker in reason for marker in required)
            if is_actionable:
                actionable += 1
            else:
                unactionable.append(f"{host}/{script}")
            check(f"deny has WHY/FIX: {host}/{script}", is_actionable, reason[-400:])

    pretool = [row["script"] for row in policy["hardGates"] if row["event"] == "PreToolUse"]
    false_blocks: list[str] = []
    for script in pretool:
        for host in corpus["denyContract"]["hosts"]:
            rc, decision, reason = read_only_probe(script, host)
            allowed = decision not in {"deny", "block"} and rc in (0, 2)
            # Some non-applicable hooks use exit 2 as a fail-open transport
            # detail, but a blocking decision is the authoritative boundary.
            if not allowed:
                false_blocks.append(f"{host}/{script}")
            check(f"read-only path stays open: {host}/{script}", allowed,
                  f"rc={rc} decision={decision!r} reason={reason[-240:]!r}")

    dead_ends: list[str] = []
    for host in corpus["denyContract"]["hosts"]:
        bypass_ok, mutation_ok, detail = reasoned_bypass_probe(host)
        check(f"reasoned bypass is allowed and audited: {host}", bypass_ok, detail[-300:])
        check(f"grace window admits next authorized mutation: {host}", mutation_ok, detail[-300:])
        if not (bypass_ok and mutation_ok):
            dead_ends.append(host)

    coverage = actionable / max(1, deny_total)
    thresholds = corpus["thresholds"]
    check("actionable denial coverage is 100%",
          coverage >= corpus["denyContract"]["requiredCoverage"],
          f"{actionable}/{deny_total}; missing={unactionable}")
    check("read-only false-block threshold",
          len(false_blocks) <= thresholds["maxFalseBlocks"], str(false_blocks))
    check("authorized bypass dead-end threshold",
          len(dead_ends) <= thresholds["maxDeadEnds"], str(dead_ends))
    check("unactionable denial threshold",
          len(unactionable) <= thresholds["maxUnactionableDenials"], str(unactionable))
    print("METRICS " + json.dumps({
        "denyFixtures": deny_total,
        "actionableDenials": actionable,
        "actionableCoverage": coverage,
        "falseBlocks": len(false_blocks),
        "deadEnds": len(dead_ends),
    }, sort_keys=True))
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS — hard-gate friction contract satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

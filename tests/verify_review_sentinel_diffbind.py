#!/usr/bin/env python3
"""Behavioural commit-gate tests for the exact-context review cache."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "check-review-before-commit.sh"
CACHE = ROOT / "skills" / "review" / "scripts" / "itd_review_cache.py"
SKILL = ROOT / "skills" / "review" / "SKILL.md"
RECORDER = ROOT / "hooks" / "record-agent-skill.sh"
SID = "exact-review-gate"
PY = sys.executable


def run(args: list[str], cwd: Path, *, stdin: str | None = None,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), input=stdin, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          env=env, timeout=30)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repo: Path, *args: str) -> None:
    proc = run(["git", *args], repo)
    if proc.returncode:
        raise RuntimeError(proc.stderr)


def make_repo(staged: int = 3) -> Path:
    repo = Path(tempfile.mkdtemp(prefix="exact-review-gate-"))
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "gate@example.test")
    git(repo, "config", "user.name", "Gate Test")
    write(repo / "base.txt", "base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-qm", "base")
    for index in range(staged):
        write(repo / f"change-{index}.txt", f"change {index}\n")
        git(repo, "add", f"change-{index}.txt")
    write(repo / ".itd" / "SCOPE_LOCK.md", "# scope v1\n")
    write(repo / ".itd" / "ACCEPTANCE_CONTRACT.json",
          json.dumps({"criterion": "v1"}))
    write(repo / ".itd-memory" / "GOAL.json", json.dumps({
        "version": 1, "goal": "fixture", "status": "active",
        "currentUnitId": "R-1", "units": [{
            "id": "R-1", "status": "in_progress", "riskTier": "medium",
            "criterion": "exact cache", "verificationCommand": "true",
        }],
    }))
    return repo


def gate(repo: Path) -> subprocess.CompletedProcess:
    payload = json.dumps({
        "tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
    })
    env = dict(os.environ, CLAUDE_SESSION_ID=SID)
    return run([PY, str(HOOK)], repo, stdin=payload, env=env)


def record(repo: Path, verdict: str, *extra: str) -> subprocess.CompletedProcess:
    return run([PY, str(CACHE), "record", "--root", str(repo),
                "--kind", "general", "--verdict", verdict,
                "--session", SID, *extra], ROOT)


def legacy_marker(content: str) -> Path:
    path = Path(tempfile.gettempdir()) / f"claude-review-done-{SID}"
    path.write_text(content, encoding="utf-8")
    return path


def main() -> int:
    passed = failed = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        print(("PASS" if condition else "FAIL") + "  " + name
              + ((" — " + detail[:240]) if detail and not condition else ""))
        if condition:
            passed += 1
        else:
            failed += 1

    marker: Path | None = None
    repo = make_repo()
    try:
        denied = gate(repo)
        check("three staged files without cache are denied", denied.returncode == 2,
              denied.stdout + denied.stderr)

        marker = legacy_marker(str(int(time.time())))
        check("legacy timestamp marker cannot unlock", gate(repo).returncode == 2)
        marker.write_text("tree:" + "a" * 40, encoding="utf-8")
        check("legacy tree marker cannot unlock", gate(repo).returncode == 2)

        clean = record(repo, "PASSED")
        check("PASSED exact-context record succeeds", clean.returncode == 0,
              clean.stdout + clean.stderr)
        check("unchanged exact-context cache unlocks", gate(repo).returncode == 0)

        write(repo / "change-2.txt", "changed after review\n")
        git(repo, "add", "change-2.txt")
        check("staged diff change invalidates", gate(repo).returncode == 2)
        record(repo, "PASSED")

        write(repo / ".itd" / "SCOPE_LOCK.md", "# scope v2\n")
        check("scope contract change invalidates", gate(repo).returncode == 2)
        record(repo, "PASSED")

        write(repo / ".itd" / "ACCEPTANCE_CONTRACT.json",
              json.dumps({"criterion": "v2"}))
        check("acceptance contract change invalidates", gate(repo).returncode == 2)
        record(repo, "PASSED")

        goal_path = repo / ".itd-memory" / "GOAL.json"
        goal = json.loads(goal_path.read_text(encoding="utf-8"))
        goal["units"][0]["riskTier"] = "high"
        write(goal_path, json.dumps(goal))
        check("risk-tier change invalidates", gate(repo).returncode == 2)

        blocked = record(repo, "BLOCKED")
        check("BLOCKED record is rejected", blocked.returncode != 0)
        check("BLOCKED cannot unlock", gate(repo).returncode == 2)
        unverified = record(repo, "UNVERIFIED")
        check("UNVERIFIED record is rejected", unverified.returncode != 0)
        check("UNVERIFIED cannot unlock", gate(repo).returncode == 2)
        warningless = record(repo, "PASSED_WITH_WARNINGS")
        check("warning verdict without durable warnings is rejected",
              warningless.returncode != 0 and gate(repo).returncode == 2)
        warned = record(repo, "PASSED_WITH_WARNINGS",
                        "--warning", "change-0.txt: durable warning")
        check("durable warning verdict is accepted",
              warned.returncode == 0 and gate(repo).returncode == 0,
              warned.stdout + warned.stderr)

        payload = json.dumps({"tool_name": "Agent",
                              "tool_input": {"subagent_type": "code-reviewer"}})
        record(repo, "BLOCKED")
        env = dict(os.environ, CLAUDE_SESSION_ID=SID)
        run([PY, str(RECORDER)], repo, stdin=payload, env=env)
        check("agent type alone cannot mint a review pass", gate(repo).returncode == 2)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        if marker is not None:
            try:
                marker.unlink()
            except FileNotFoundError:
                pass

    repo2 = make_repo(staged=2)
    try:
        check("two staged files remain below the review threshold",
              gate(repo2).returncode == 0)
    finally:
        shutil.rmtree(repo2, ignore_errors=True)

    hook_source = HOOK.read_text(encoding="utf-8")
    skill_source = SKILL.read_text(encoding="utf-8")
    check("commit hook delegates to exact cache",
          "itd_review_cache.py" in hook_source and "cache_allows" in hook_source)
    check("review skill records the exact verdict producer",
          "itd_review_cache.py" in skill_source and "--verdict PASSED" in skill_source)

    print(f"\nRESULT: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

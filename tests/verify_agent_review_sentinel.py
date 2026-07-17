#!/usr/bin/env python3
"""Agent-type completion must not manufacture review/security success."""
from __future__ import annotations

import json
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORDER = ROOT / "hooks" / "record-agent-skill.sh"
REVIEW_GATE = ROOT / "hooks" / "check-review-before-commit.sh"
DOD_GATE = ROOT / "hooks" / "check-dod-before-commit.sh"
SID = "agent-verdict-bound"
PY = sys.executable


def marker(skill: str) -> Path:
    return Path(tempfile.gettempdir()) / f"claude-{skill}-done-{SID}"


def clear() -> None:
    for directory in {Path("/tmp"), Path(tempfile.gettempdir())}:
        for skill in ("review", "test", "security-audit"):
            for candidate in glob.glob(str(directory / f"claude-{skill}-done-*")):
                try:
                    Path(candidate).unlink()
                except FileNotFoundError:
                    pass


def run_hook(hook: Path, payload: dict, cwd: Path | None = None) -> int:
    env = dict(os.environ, CLAUDE_SESSION_ID=SID)
    proc = subprocess.run([PY, str(hook)], input=json.dumps(payload),
                          cwd=str(cwd or ROOT), capture_output=True, text=True,
                          env=env, timeout=30)
    return proc.returncode


def record(agent: str, tool: str = "Agent", cwd: Path | None = None) -> int:
    return run_hook(RECORDER, {"tool_name": tool,
                              "tool_input": {"subagent_type": agent}}, cwd)


def git(repo: Path, *args: str) -> None:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, timeout=20)
    if proc.returncode:
        raise RuntimeError(proc.stderr)


def make_repo(payment: bool = False) -> Path:
    repo = Path(tempfile.mkdtemp(prefix="agent-verdict-"))
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "agent@example.test")
    git(repo, "config", "user.name", "Agent Test")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-qm", "base")
    if payment:
        path = repo / "src" / "payments" / "config.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("x\n", encoding="utf-8")
        git(repo, "add", "src/payments/config.yaml")
    else:
        for index in range(3):
            path = repo / f"f{index}.txt"
            path.write_text("x\n", encoding="utf-8")
            git(repo, "add", path.name)
    return repo


def commit_gate(hook: Path, repo: Path) -> int:
    return run_hook(hook, {"tool_name": "Bash",
                           "tool_input": {"command": "git commit -m x"}}, repo)


def main() -> int:
    passed = failed = 0

    def check(name: str, condition: bool) -> None:
        nonlocal passed, failed
        print(("PASS" if condition else "FAIL") + "  " + name)
        if condition:
            passed += 1
        else:
            failed += 1

    clear()
    check("code-reviewer agent writes no review sentinel",
          record("code-reviewer") == 0 and not marker("review").exists())
    clear()
    check("code-reviewer Task writes no review sentinel",
          record("code-reviewer", "Task") == 0 and not marker("review").exists())
    clear()
    check("security-reviewer writes no security sentinel",
          record("security-reviewer") == 0
          and not marker("security-audit").exists())
    clear()
    check("test-generator still writes its completion sentinel",
          record("test-generator") == 0 and marker("test").exists())
    clear()
    check("unmapped agent writes no gate sentinel",
          record("architect") == 0
          and not any(marker(name).exists()
                      for name in ("review", "test", "security-audit")))

    repo = make_repo()
    try:
        before = commit_gate(REVIEW_GATE, repo)
        record("code-reviewer", cwd=repo)
        after = commit_gate(REVIEW_GATE, repo)
        check("review gate denies before verdict", before == 2)
        check("code-reviewer completion alone leaves review gate denied", after == 2)
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    clear()
    repo = make_repo(payment=True)
    try:
        before = commit_gate(DOD_GATE, repo)
        record("security-reviewer", cwd=repo)
        after = commit_gate(DOD_GATE, repo)
        check("security DoD gate denies before verdict", before == 2)
        check("security-reviewer completion alone leaves DoD gate denied", after == 2)
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    clear()
    print(f"\nRESULT: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

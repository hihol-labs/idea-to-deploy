#!/usr/bin/env python3
"""Regression tests for verdict-aware, bucket-specific risk paydown."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from verification_loop_fixture import make_review_receipt


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "risk-score.sh"
CACHE = ROOT / "skills" / "review" / "scripts" / "itd_review_cache.py"
PY = sys.executable


def state_path(session: str) -> Path:
    return Path(tempfile.gettempdir()) / f"claude-risk-{session}.json"


def clean(session: str) -> None:
    try:
        state_path(session).unlink()
    except FileNotFoundError:
        pass


def call(session: str, payload: dict, extra_env: dict[str, str] | None = None) -> str:
    env = dict(os.environ, CLAUDE_SESSION_ID=session)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run([PY, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=20)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return proc.stdout.strip()


def context(output: str) -> str:
    if not output:
        return ""
    return json.loads(output)["hookSpecificOutput"]["additionalContext"]


def edit(path: str = "src/util.py") -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": path}}


def run_git(repo: Path, *args: str) -> None:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, timeout=20)
    if proc.returncode:
        raise RuntimeError(proc.stderr)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="risk-verdict-"))
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "risk@example.test")
    run_git(repo, "config", "user.name", "Risk Test")
    write(repo / ".gitignore", ".itd-memory/\n")
    write(repo / "base.txt", "base\n")
    run_git(repo, "add", "base.txt", ".gitignore")
    run_git(repo, "commit", "-qm", "base")
    write(repo / "change.txt", "candidate\n")
    run_git(repo, "add", "change.txt")
    write(repo / ".itd" / "SCOPE_LOCK.md", "# risk scope\n")
    write(repo / ".itd" / "ACCEPTANCE_CONTRACT.json", "{}\n")
    run_git(repo, "add", ".itd")
    write(repo / ".itd-memory" / "GOAL.json", json.dumps({
        "version": 1, "goal": "risk fixture", "status": "active",
        "currentUnitId": "R-1", "units": [{
            "id": "R-1", "status": "in_progress", "riskTier": "medium",
            "criterion": "risk", "verificationCommand": "true",
        }],
    }))
    return repo


def verdict(repo: Path, session: str, value: str, kind: str) -> int:
    receipt_args: list[str] = []
    if value in {"PASSED", "PASSED_WITH_WARNINGS"}:
        # Each scenario models a separate completed change/review. Give it an
        # exact candidate of its own so independent scenarios do not consume
        # one claim's deliberate three-attempt repair budget.
        write(repo / "change.txt", f"candidate for {session} {kind}\n")
        run_git(repo, "add", "change.txt")
        receipt = make_review_receipt(
            repo, unit_id="R-1", risk_tier="medium", kind=kind)
        receipt_args = ["--verification-receipt", str(receipt)]
    proc = subprocess.run(
        [PY, str(CACHE), "record", "--root", str(repo), "--session", session,
         "--kind", kind, "--verdict", value, *receipt_args],
        cwd=str(ROOT), capture_output=True, text=True, timeout=30,
    )
    return proc.returncode


def read_state(session: str) -> dict:
    return json.loads(state_path(session).read_text(encoding="utf-8"))


def accumulate(session: str, count: int, path: str = "src/util.py") -> str:
    message = ""
    for _ in range(count):
        message = context(call(session, edit(path))) or message
    return message


def main() -> int:
    failures: list[str] = []
    sessions: list[str] = []
    repo = make_repo()

    def use(name: str) -> str:
        sessions.append(name)
        clean(name)
        return name

    try:
        session = use("risk-plain")
        if context(call(session, edit())):
            failures.append("plain edit escalated before threshold")
        if not all(not context(call(session, edit())) for _ in range(10)):
            failures.append("plain edits escalated before edit 12")
        msg = context(call(session, edit()))
        if "successful bound /review verdict" not in msg:
            failures.append("plain edit 12 did not escalate to bound /review")

        session = use("risk-security")
        msg = accumulate(session, 3, "app/auth/login.py")
        if "successful bound /security-audit verdict" not in msg:
            failures.append("three sensitive edits did not escalate to security audit")

        session = use("risk-marker")
        accumulate(session, 11)
        marker = Path(tempfile.gettempdir()) / f"claude-review-done-{session}"
        marker.write_text("tree:" + "a" * 40, encoding="utf-8")
        try:
            if not context(call(session, edit())):
                failures.append("legacy review marker incorrectly reset risk")
        finally:
            marker.unlink(missing_ok=True)

        session = use("risk-blocked")
        accumulate(session, 7)
        before = read_state(session)
        if verdict(repo, session, "BLOCKED", "general") == 0:
            failures.append("BLOCKED CLI verdict unexpectedly succeeded")
        after = read_state(session)
        if after["general_score"] != before["general_score"]:
            failures.append("BLOCKED verdict reset general risk")
        if verdict(repo, session, "UNVERIFIED", "security") == 0:
            failures.append("UNVERIFIED CLI verdict unexpectedly succeeded")
        if read_state(session)["general_score"] != before["general_score"]:
            failures.append("UNVERIFIED verdict reset risk")

        session = use("risk-general-bucket")
        accumulate(session, 4)
        accumulate(session, 2, "app/auth/login.py")  # general=4, security=8
        if verdict(repo, session, "PASSED", "general") != 0:
            failures.append("accepted general verdict failed")
        state = read_state(session)
        if (state["general_score"], state["security_score"], state["risk_score"]) \
                != (0.0, 8.0, 8.0):
            failures.append(f"general verdict changed wrong bucket: {state}")

        session = use("risk-security-bucket")
        accumulate(session, 4)
        accumulate(session, 2, "app/auth/login.py")
        if verdict(repo, session, "PASSED", "security") != 0:
            failures.append("accepted security verdict failed")
        state = read_state(session)
        if (state["general_score"], state["security_score"], state["risk_score"]) \
                != (4.0, 0.0, 4.0):
            failures.append(f"security verdict changed wrong bucket: {state}")

        session = use("risk-post-gate")
        accumulate(session, 12)
        if verdict(repo, session, "PASSED", "general") != 0:
            failures.append("post-gate fixture review failed")
        early = accumulate(session, 11)
        final = context(call(session, edit()))
        if early or "successful bound /review verdict" not in final:
            failures.append("post-gate delta did not restart at exactly 12 edits")

        session = use("risk-lagging-baseline")
        state_path(session).write_text(json.dumps({
            "risk_score": 25.0, "general_score": 15.0,
            "security_score": 10.0, "last_escalation_score": 12.0,
            "escalations": 1,
        }), encoding="utf-8")
        if verdict(repo, session, "PASSED", "general") != 0:
            failures.append("lagging-baseline fixture review failed")
        early = accumulate(session, 11)
        final = context(call(session, edit()))
        if early or "successful bound /review verdict" not in final:
            failures.append("lagging baseline reused pre-gate risk as new delta")

        session = use("risk-read")
        for _ in range(40):
            if context(call(session, {"tool_name": "Read",
                                      "tool_input": {"file_path": "x.py"}})):
                failures.append("read-only operations accrued risk")
                break

        bad = subprocess.run([PY, str(HOOK)], input="not json", capture_output=True,
                             text=True, env=dict(os.environ,
                             CLAUDE_SESSION_ID=use("risk-bad")), timeout=20)
        if bad.returncode or bad.stdout.strip():
            failures.append("malformed input was not a quiet no-op")

        session = use("risk-env")
        call(session, edit(), {"ITD_RISK_THRESHOLD": "2"})
        if not context(call(session, edit(), {"ITD_RISK_THRESHOLD": "2"})):
            failures.append("ITD_RISK_THRESHOLD=2 was not respected")
        session = use("risk-disabled")
        if any(context(call(session, edit(), {"ITD_RISK_THRESHOLD": "0"}))
               for _ in range(20)):
            failures.append("ITD_RISK_THRESHOLD=0 did not disable escalation")

        session_b = use("risk-cross-b")
        session_a = use("risk-cross-a")
        accumulate(session_b, 11)
        accumulate(session_a, 5)
        verdict(repo, session_a, "PASSED", "general")
        if not context(call(session_b, edit())):
            failures.append("session A verdict paid down session B")
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        for session in sessions:
            clean(session)

    if failures:
        print("verify_risk_score: FAILED")
        for failure in failures:
            print("  - " + failure)
        return 1
    print("verify_risk_score: PASSED (13 scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

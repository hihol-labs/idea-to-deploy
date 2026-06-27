#!/usr/bin/env python3
"""Behavioural test for hooks/record-agent-skill.sh and its effect on the
review/DoD gates (continuation of bug #2).

A review/test/security pass is often delegated to a SUBAGENT (Agent/Task
tool, e.g. the read-only `code-reviewer` agent) instead of the matching
skill. The agent cannot write its own completion sentinel (read-only
tools), and the Skill tool emits no hook events -- but the Task/Agent tool
DOES. record-agent-skill.sh (PostToolUse) writes the sentinel on the
agent behalf so the gates count the work.

Asserts:
  1. A finished `code-reviewer` subagent writes the /review sentinel.
  2. test-generator -> /test, security-reviewer -> /security-audit.
  3. Unmapped agents (architect) and non-subagent tools (Bash) write nothing.
  4. END-TO-END through both real gates: after the code-reviewer agent
     runs, the review gate (check-review-before-commit.sh) ALLOWS a
     >2-file commit (exit 0) where without it it denies (exit 2); and
     after the security-reviewer agent runs, the DoD gate
     (check-dod-before-commit.sh) ALLOWS a payments-path commit likewise.

Run: python3 tests/verify_agent_review_sentinel.py
Exits non-zero if any case fails (CI-friendly).
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# `.sh` extension is the methodology convention; the files are Python 3 and
# are launched via `python3 <file.sh>` (see hooks/README.md).
REC_HOOK = os.path.join(REPO, "hooks", "record-agent-skill.sh")
REVIEW_HOOK = os.path.join(REPO, "hooks", "check-review-before-commit.sh")
DOD_HOOK = os.path.join(REPO, "hooks", "check-dod-before-commit.sh")
SID = "agentrev-test-session"

SENTINEL_DIRS = []
for _d in ("/tmp", tempfile.gettempdir()):
    if _d and _d not in SENTINEL_DIRS:
        SENTINEL_DIRS.append(_d)


def sentinel_paths(skill):
    return [os.path.join(d, "claude-%s-done-%s" % (skill, SID)) for d in SENTINEL_DIRS]


def clear_sentinels():
    for skill in ("review", "test", "security-audit"):
        for d in SENTINEL_DIRS:
            for p in glob.glob(os.path.join(d, "claude-%s-done-*" % skill)):
                try:
                    os.remove(p)
                except OSError:
                    pass


def sentinel_exists(skill):
    return any(os.path.exists(p) for p in sentinel_paths(skill))


def run_record(tool_name, subagent_type=None):
    ti = {}
    if subagent_type is not None:
        ti["subagent_type"] = subagent_type
    payload = json.dumps({"tool_name": tool_name, "tool_input": ti})
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = SID
    return subprocess.run(
        ["python3", REC_HOOK], input=payload,
        capture_output=True, text=True, env=env,
    ).returncode


def _sh(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def make_repo_with_n_staged(n):
    d = tempfile.mkdtemp(prefix="agentrev-")
    _sh(["git", "init", "-q"], d)
    _sh(["git", "config", "user.email", "t@t"], d)
    _sh(["git", "config", "user.name", "t"], d)
    for i in range(n):
        p = os.path.join(d, "f%d.txt" % i)
        with open(p, "w") as f:
            f.write("x\n")
        _sh(["git", "add", "f%d.txt" % i], d)
    return d


def run_gate(hook, repo):
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
    )
    env = dict(os.environ)
    env["CLAUDE_SESSION_ID"] = SID
    return subprocess.run(
        ["python3", hook], input=payload, cwd=repo,
        capture_output=True, text=True, env=env,
    ).returncode


def make_repo_with_payment_file():
    """A single staged file on a payments path — trips the DoD gate's
    security-audit requirement (and only that: .yaml is not a source ext,
    and one file stays under the review gate's >2 threshold)."""
    d = tempfile.mkdtemp(prefix="agentrev-dod-")
    _sh(["git", "init", "-q"], d)
    _sh(["git", "config", "user.email", "t@t"], d)
    _sh(["git", "config", "user.name", "t"], d)
    sub = os.path.join(d, "src", "payments")
    os.makedirs(sub)
    p = os.path.join(sub, "config.yaml")
    with open(p, "w") as f:
        f.write("x\n")
    _sh(["git", "add", "src/payments/config.yaml"], d)
    return d


def main():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        print("%s  %s" % ("PASS" if cond else "FAIL", name))
        if cond:
            passed += 1
        else:
            failed += 1

    # 1. code-reviewer -> review sentinel (Agent tool name)
    clear_sentinels()
    run_record("Agent", "code-reviewer")
    check("code-reviewer (Agent) writes /review sentinel", sentinel_exists("review"))

    # 1b. same via Task tool name
    clear_sentinels()
    run_record("Task", "code-reviewer")
    check("code-reviewer (Task) writes /review sentinel", sentinel_exists("review"))

    # 2. test-generator -> test ; security-reviewer -> security-audit
    clear_sentinels()
    run_record("Agent", "test-generator")
    check("test-generator writes /test sentinel", sentinel_exists("test"))

    clear_sentinels()
    run_record("Agent", "security-reviewer")
    check("security-reviewer writes /security-audit sentinel",
          sentinel_exists("security-audit"))

    # 3a. unmapped agent -> nothing
    clear_sentinels()
    run_record("Agent", "architect")
    check("architect (unmapped) writes no sentinel",
          not (sentinel_exists("review") or sentinel_exists("test")
               or sentinel_exists("security-audit")))

    # 3b. non-subagent tool -> nothing
    clear_sentinels()
    run_record("Bash", None)
    check("Bash tool writes no sentinel",
          not (sentinel_exists("review") or sentinel_exists("test")
               or sentinel_exists("security-audit")))

    # 4. END-TO-END through the real review gate (>2 files -> /review)
    clear_sentinels()
    repo = make_repo_with_n_staged(3)
    try:
        before = run_gate(REVIEW_HOOK, repo)
        run_record("Agent", "code-reviewer")
        after = run_gate(REVIEW_HOOK, repo)
        check("review gate DENIES >2 files before agent (exit 2)", before == 2)
        check("review gate ALLOWS >2 files after code-reviewer agent (exit 0)",
              after == 0)
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    # 5. END-TO-END through the real DoD gate (payments path -> /security-audit)
    clear_sentinels()
    repo = make_repo_with_payment_file()
    try:
        before = run_gate(DOD_HOOK, repo)
        run_record("Agent", "security-reviewer")
        after = run_gate(DOD_HOOK, repo)
        check("DoD gate DENIES payments path before agent (exit 2)", before == 2)
        check("DoD gate ALLOWS payments path after security-reviewer agent (exit 0)",
              after == 0)
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    clear_sentinels()
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

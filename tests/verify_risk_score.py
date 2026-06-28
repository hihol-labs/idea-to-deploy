#!/usr/bin/env python3
"""
verify_risk_score.py — regression test for hooks/risk-score.sh
(v1.30.0, omnigent risk_score_policy port).

Asserts:
  1. Plain edits accumulate; escalation fires at threshold and points to /review.
  2. Security-sensitive edits bias escalation toward /security-audit.
  3. Running /review (marker) pays the budget down -> subsequent calls silent.
  4. Reads/searches accrue no change-risk (stay silent).
  5. Malformed stdin never crashes (rc=0, silent).
  6. ITD_RISK_THRESHOLD override is respected.

Run: python3 tests/verify_risk_score.py   (exit 0 = pass, 1 = fail)
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "risk-score.sh")


def _clean(session: str) -> None:
    for p in [f"/tmp/claude-risk-{session}.json",
              f"/tmp/claude-review-done-{session}",
              f"/tmp/claude-security-audit-done-{session}"]:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


def _call(session: str, payload: dict, extra_env=None) -> str:
    env = dict(os.environ, CLAUDE_SESSION_ID=session)
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(["python3", HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, f"hook exited {p.returncode}: {p.stderr}"
    return p.stdout.strip()


def _ctx(out: str) -> str:
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def _edit(path="src/util.py"):
    return {"tool_name": "Edit", "tool_input": {"file_path": path}}


def main() -> int:
    fails: list[str] = []

    # 1. Plain edits below threshold (12): 11 plain edits -> silent, 12th -> escalate /review
    s = "vrs-plain"
    _clean(s)
    fired = None
    for i in range(13):
        out = _call(s, _edit())
        if _ctx(out) and fired is None:
            fired = i + 1
    if fired is None:
        fails.append("1a. plain edits never escalated")
    elif fired < 12:
        fails.append(f"1b. escalated too early at edit {fired} (threshold 12)")
    else:
        last = _ctx(_call(s, _edit()))  # already escalated; should be quiet until +threshold
        # verify the escalation we saw recommended /review
        # (re-run a fresh accumulation to capture the message)
    # capture the escalation message content
    s2 = "vrs-plain-msg"
    _clean(s2)
    msg = ""
    for _ in range(12):
        msg = _ctx(_call(s2, _edit())) or msg
    if "running /review on" not in msg:
        fails.append(f"1c. plain escalation should point to /review: {msg[:120]!r}")

    # 2. Security-sensitive edits -> /security-audit (4 pts each, 3 edits = 12)
    s = "vrs-sec"
    _clean(s)
    msg = ""
    for _ in range(3):
        msg = _ctx(_call(s, _edit("app/auth/login.py"))) or msg
    if "running /security-audit on" not in msg:
        fails.append(f"2. security-heavy escalation should point to /security-audit: {msg[:120]!r}")

    # 3. Pay-down via /review marker resets the budget
    s = "vrs-paydown"
    _clean(s)
    for _ in range(12):
        _call(s, _edit())  # accumulate to/over threshold
    # write a review-done marker dated in the future so it is newer than paid_down_at
    marker = f"/tmp/claude-review-done-{s}"
    with open(marker, "w") as f:
        f.write(str(int(time.time())))
    future = time.time() + 100
    os.utime(marker, (future, future))
    # next call should reset and be silent (score back to ~1)
    out = _call(s, _edit())
    if _ctx(out):
        fails.append("3. /review marker did not pay down the risk budget")

    # 4. Reads/searches accrue nothing
    s = "vrs-read"
    _clean(s)
    silent = True
    for _ in range(40):
        if _ctx(_call(s, {"tool_name": "Read", "tool_input": {"file_path": "x.py"}})):
            silent = False
    for _ in range(40):
        if _ctx(_call(s, {"tool_name": "Grep", "tool_input": {"pattern": "x"}})):
            silent = False
    if not silent:
        fails.append("4. reads/searches should never escalate")

    # 5. Bad JSON -> graceful
    p = subprocess.run(["python3", HOOK], input="not json", capture_output=True,
                       text=True, env=dict(os.environ, CLAUDE_SESSION_ID="vrs-bad"))
    if p.returncode != 0 or p.stdout.strip():
        fails.append(f"5. bad JSON not graceful: rc={p.returncode} out={p.stdout!r}")

    # 6. Threshold override: lower to 2 -> escalate after 2 plain edits
    s = "vrs-env"
    _clean(s)
    fired = None
    for i in range(3):
        if _ctx(_call(s, _edit(), extra_env={"ITD_RISK_THRESHOLD": "2"})) and fired is None:
            fired = i + 1
    if fired is None or fired > 2:
        fails.append(f"6. ITD_RISK_THRESHOLD=2 override not respected (fired={fired})")

    # 7. ITD_RISK_THRESHOLD=0 disables the gate -> never escalates
    s = "vrs-disabled"
    _clean(s)
    silent = True
    for _ in range(40):
        if _ctx(_call(s, _edit(), extra_env={"ITD_RISK_THRESHOLD": "0"})):
            silent = False
    if not silent:
        fails.append("7. ITD_RISK_THRESHOLD=0 should disable the gate")

    # 8. MultiEdit on a sensitive path accrues 4.0 pts (3 -> escalate /security-audit)
    s = "vrs-multiedit"
    _clean(s)
    msg = ""
    for _ in range(3):
        payload = {"tool_name": "MultiEdit",
                   "tool_input": {"edits": [{"file_path": "app/auth/login.py"}]}}
        msg = _ctx(_call(s, payload)) or msg
    if "running /security-audit on" not in msg:
        fails.append(f"8. MultiEdit sensitive path not scored as sensitive: {msg[:120]!r}")

    # 9. Cross-session isolation: session A's /review must NOT pay down session B
    s_b, s_a = "vrs-xsession-b", "vrs-xsession-a"
    _clean(s_b)
    _clean(s_a)
    for _ in range(11):
        _call(s_b, _edit())  # 11 pts, still silent (threshold 12)
    mk = f"/tmp/claude-review-done-{s_a}"
    with open(mk, "w") as f:
        f.write("x")
    far = time.time() + 100
    os.utime(mk, (far, far))
    if not _ctx(_call(s_b, _edit())):  # 12th -> must escalate (A's review is irrelevant)
        fails.append("9. cross-session: session A /review wrongly paid down session B")

    # cleanup
    for s in ["vrs-plain", "vrs-plain-msg", "vrs-sec", "vrs-paydown", "vrs-read",
              "vrs-bad", "vrs-env", "vrs-disabled", "vrs-multiedit",
              "vrs-xsession-a", "vrs-xsession-b"]:
        _clean(s)

    if fails:
        print("verify_risk_score: FAILED")
        for f in fails:
            print("  - " + f)
        return 1
    print("verify_risk_score: PASSED (9/9)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

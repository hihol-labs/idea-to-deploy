#!/usr/bin/env python3
"""
PostToolUse hook — cumulative risk-score escalation (omnigent risk_score_policy port).

idea-to-deploy's commit gates are binary and stateless: a single change either
trips a gate (migration / payments / >2 files without /review) or it does not.
That misses "death by a thousand edits" — many individually-OK changes that add
up to a risky session with no single tripwire.

This hook ports the OUTCOME of omnigent's risk_score_policy: a cumulative
"safety budget". Every mutating tool call adds risk points (scaled by how
sensitive the target is). When the running score crosses a threshold the hook
ESCALATES — it injects an instruction to pay the risk down with /review (or
/security-audit when the accumulated risk is mostly security-relevant) before
continuing. Running either skill resets the budget (detected via the markers
those skills already write).

It is NOT omnigent's server-side policy engine and it never blocks — a
PostToolUse hook cannot pause the loop, so escalation is a high-priority ASK
injected via hookSpecificOutput.additionalContext. Judgment stays with the user.

State: /tmp/claude-risk-<session>.json. Fail-open: any error → exit 0, silent.

Tunables (env): ITD_RISK_THRESHOLD (int, default 12).

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}}
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

RISK_THRESHOLD = 12  # accumulate this many points before escalating
try:
    RISK_THRESHOLD = int(os.environ.get("ITD_RISK_THRESHOLD", RISK_THRESHOLD))
except Exception:
    pass

# Paths/commands that make a change security- or data-sensitive. A change here is
# worth more risk points and biases escalation toward /security-audit.
SENSITIVE = re.compile(
    r"auth|login|password|passwd|secret|token|api[_-]?key|credential|payment|"
    r"billing|invoice|checkout|migration|schema|\.env|security|crypto|session|"
    r"permission|\bacl\b|oauth|jwt|webhook|stripe|sql",
    re.IGNORECASE,
)

# Risky Bash commands (destructive / production / egress / schema).
RISKY_BASH = re.compile(
    r"\brm\s+-[a-z]*[rf]|\bDROP\s+(TABLE|DATABASE|SCHEMA)|\bALTER\s+TABLE|"
    r"\bTRUNCATE\b|\bDELETE\s+FROM\b|git\s+push|--force|reset\s+--hard|"
    r"\bmigrate\b|\bdeploy\b|\bprod\b|chmod\s+777|\b(curl|wget)\b|docker\s+(rm|prune)",
    re.IGNORECASE,
)


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def state_file() -> str:
    return os.path.join(tempfile.gettempdir(), f"claude-risk-{session_id()}.json")


def read_state() -> dict:
    try:
        with open(state_file()) as f:
            return json.load(f)
    except Exception:
        return {
            "risk_score": 0.0,
            "security_score": 0.0,
            "last_escalation_score": 0.0,
            "paid_down_at": 0.0,
            "escalations": 0,
        }


def write_state(state: dict) -> None:
    try:
        with open(state_file(), "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def latest_paydown_marker() -> float:
    """Newest mtime among THIS session's /review and /security-audit markers.

    Deliberately session-scoped: the risk budget is a per-session counter, so a
    parallel session's /review (Agent Teams, two windows) must NOT pay this
    session's risk down. Only when our own session_id falls back to "default" do
    we also honor the "default" markers.
    """
    newest = 0.0
    sid = session_id()
    names = [f"claude-review-done-{sid}", f"claude-security-audit-done-{sid}"]
    if sid != "default":
        names += ["claude-review-done-default", "claude-security-audit-done-default"]
    dirs = []
    for d in (tempfile.gettempdir(), "/tmp"):
        if d and d not in dirs:
            dirs.append(d)
    for d in dirs:
        for name in names:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(d, name)))
            except Exception:
                continue
    # NOTE: deliberately NO cross-session glob fallback here. risk-score's
    # contract (verify_risk_score case 9) is stricter than the review/DoD
    # gates: a sentinel from session A must not pay down session B's risk.
    # Restart tolerance is provided by the gates that own the decision.
    return newest


def risk_delta(tool: str, tool_input: dict) -> tuple[float, float]:
    """Return (risk_points, security_points) for one tool call."""
    if tool == "MultiEdit":
        # MultiEdit nests per-edit file paths under "edits", no top-level file_path.
        path = " ".join(
            str(e.get("file_path") or "") for e in (tool_input.get("edits") or [])
        ) or str(tool_input.get("file_path") or "")
        return (4.0, 4.0) if SENSITIVE.search(path) else (1.0, 0.0)
    if tool in ("Write", "Edit", "NotebookEdit"):
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if SENSITIVE.search(path):
            return 4.0, 4.0
        return 1.0, 0.0
    if tool == "Bash":
        cmd = str(tool_input.get("command") or "")
        if RISKY_BASH.search(cmd):
            sec = 3.0 if SENSITIVE.search(cmd) else 0.0
            return 3.0, sec
        return 0.5, 0.0
    # Reads / searches / planning tools do not accrue change-risk.
    return 0.0, 0.0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or ""
    tool_input = (payload or {}).get("tool_input") or {}

    # Threshold of 0 (or negative) disables the risk gate entirely.
    if RISK_THRESHOLD <= 0:
        return 0

    state = read_state()

    # Pay down: if a /review or /security-audit ran after our last paydown, reset.
    marker = latest_paydown_marker()
    if marker > state.get("paid_down_at", 0.0):
        state["risk_score"] = 0.0
        state["security_score"] = 0.0
        state["last_escalation_score"] = 0.0
        state["paid_down_at"] = marker

    dr, ds = risk_delta(tool, tool_input)
    state["risk_score"] = round(state.get("risk_score", 0.0) + dr, 2)
    state["security_score"] = round(state.get("security_score", 0.0) + ds, 2)

    score = state["risk_score"]
    since_last = score - state.get("last_escalation_score", 0.0)

    # Escalate once per THRESHOLD worth of accumulation.
    if score >= RISK_THRESHOLD and since_last >= RISK_THRESHOLD:
        state["last_escalation_score"] = score
        state["escalations"] = state.get("escalations", 0) + 1
        write_state(state)

        security_heavy = state["security_score"] >= score * 0.5
        target = "/security-audit" if security_heavy else "/review"
        why = (
            "most of it touched security- or data-sensitive surfaces"
            if security_heavy
            else "spread across many changes"
        )
        context = (
            f"[RISK BUDGET — escalation]\n"
            f"⚖️ Accumulated change-risk score {score:.0f} "
            f"(threshold {RISK_THRESHOLD}); {why}.\n\n"
            f"Many individually-OK changes add up — idea-to-deploy's binary gates "
            f"do not catch this drift. Before continuing or committing, pay the "
            f"risk down by running {target} on what changed so far. Running "
            f"/review or /security-audit resets this budget.\n\n"
            f"State: `cat {state_file()}`"
        )
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0

    write_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())

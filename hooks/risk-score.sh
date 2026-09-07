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
continuing. Only a successful exact-context verdict resets a bucket: /review
resets general risk, /security-audit resets security risk, and rejected
verdicts reset neither.

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
import shlex
import sys
import tempfile

# Hook output is a JSON transport contract. Native Windows may select cp1251
# for redirected stdout, which cannot encode the diagnostic's Unicode marker.
# Emit the same UTF-8 JSON bytes on every host instead of dropping escalation.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")

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

# A Bash request is normally a shell program, even when it looks harmless.
# Only this small argv-shaped grammar is read-only.  In particular, a WSL
# transport is accepted only when it reaches `git` directly; `wsl ... bash
# -lc ...` remains an unknown shell program and keeps its conservative score.
SHELL_SYNTAX = re.compile(r"(?:\$\(|`|&&|\|\||[;|<>]|[\r\n])")
WSL_NAMES = {"wsl", "wsl.exe"}


def read_only_git(argv: list[str]) -> bool:
    """Closed argv grammar; Git transport helpers can execute arbitrary code."""
    if len(argv) < 4 or argv[:2] != ["git", "--no-pager"]:
        return False
    subcommand, arguments = argv[2], argv[3:]
    # Zero-risk is reserved for closed plumbing that cannot invoke repository
    # diff, pager, filter, fsmonitor, or transport helpers. Porcelain and
    # diff-producing commands remain conservative even when read-only.
    permitted = {
        "rev-parse": (("--git-dir",), ("--is-inside-work-tree",)),
    }
    return tuple(arguments) in permitted.get(subcommand, ())


def read_only_bash(command: str) -> bool:
    """Recognize a closed set of direct, read-only Git inspections."""
    if not command or SHELL_SYNTAX.search(command) or "'" in command or '"' in command:
        return False
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return False
    if not argv:
        return False
    if argv[0].casefold() in WSL_NAMES:
        index = 1
        while index < len(argv) and argv[index] != "--":
            item = argv[index]
            if item in {"-d", "--distribution", "--cd"}:
                if (index + 1 >= len(argv) or argv[index + 1] == "--"
                        or argv[index + 1].startswith("-")):
                    return False
                index += 2
            else:
                # WSL management and unknown switches are never a read-only
                # transport. The grammar accepts only explicit selectors.
                return False
        if index >= len(argv) - 1 or argv[index] != "--":
            return False
        argv = argv[index + 1:]
    return read_only_git(argv)


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
            state = json.load(f)
    except Exception:
        state = {}
    security = float(state.get("security_score", 0.0) or 0.0)
    total = float(state.get("risk_score", 0.0) or 0.0)
    general = float(state.get("general_score", max(0.0, total - security)) or 0.0)
    state.update({
        "general_score": round(max(0.0, general), 2),
        "security_score": round(max(0.0, security), 2),
        "risk_score": round(max(0.0, general) + max(0.0, security), 2),
        "last_escalation_score": round(
            float(state.get("last_escalation_score", 0.0) or 0.0), 2),
        "paid_down_at": float(state.get("paid_down_at", 0.0) or 0.0),
        "escalations": int(state.get("escalations", 0) or 0),
    })
    return state


def write_state(state: dict) -> None:
    try:
        with open(state_file(), "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def risk_delta(tool: str, tool_input: dict) -> tuple[float, float]:
    """Return disjoint (general_points, security_points) for one tool call."""
    if tool == "MultiEdit":
        # MultiEdit nests per-edit file paths under "edits", no top-level file_path.
        path = " ".join(
            str(e.get("file_path") or "") for e in (tool_input.get("edits") or [])
        ) or str(tool_input.get("file_path") or "")
        return (0.0, 4.0) if SENSITIVE.search(path) else (1.0, 0.0)
    if tool in ("Write", "Edit", "NotebookEdit"):
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if SENSITIVE.search(path):
            return 0.0, 4.0
        return 1.0, 0.0
    if tool == "Bash":
        cmd = str(tool_input.get("command") or "")
        if read_only_bash(cmd):
            return 0.0, 0.0
        if RISKY_BASH.search(cmd):
            return (0.0, 3.0) if SENSITIVE.search(cmd) else (3.0, 0.0)
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

    dg, ds = risk_delta(tool, tool_input)
    state["general_score"] = round(state.get("general_score", 0.0) + dg, 2)
    state["security_score"] = round(state.get("security_score", 0.0) + ds, 2)
    state["risk_score"] = round(state["general_score"] + state["security_score"], 2)

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
            f"You may repair the current BLOCKED candidate and run its tests; "
            f"this advisory does not authorize publication, commit, or security "
            f"acceptance. Pay the matching bucket down only with a current bound "
            f"{target} verdict.\n\n"
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

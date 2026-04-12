#!/usr/bin/env python3
"""
PreToolUse hook — /careful safety guardrail (inspired by gstack).

Fires before Bash tool calls. Detects destructive commands
(rm -rf, DROP TABLE, git push --force, git reset --hard, etc.)
and injects a warning into Claude's context asking for explicit
user confirmation before proceeding.

Does NOT block (exit 0, permissionDecision: allow) — it's a
soft guardrail that adds friction, not a hard gate. The user
can disable it by removing the hook from settings.json.

Activation: set CAREFUL_MODE=1 env var, or the user says /careful
in the session. The hook checks for a state file to persist
activation across tool calls within a session.

When NOT active: silent no-op (exit 0, no output).

Reads JSON on stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}}
"""
from __future__ import annotations

import json
import os
import re
import sys

# Patterns that match destructive commands
DESTRUCTIVE_PATTERNS = [
    # File deletion
    (r"\brm\s+(-[a-zA-Z]*[rf]|--recursive|--force)", "rm with -rf (recursive/force delete)"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r", "rm -rf (recursive force delete)"),
    # Database destruction
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b", "DROP TABLE/DATABASE (irreversible data loss)"),
    (r"\bTRUNCATE\s+TABLE\b", "TRUNCATE TABLE (deletes all rows)"),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", "DELETE FROM without WHERE (deletes all rows)"),
    # Git destructive operations
    (r"\bgit\s+push\s+[^|]*--force\b", "git push --force (overwrites remote history)"),
    (r"\bgit\s+push\s+[^|]*-f\b", "git push -f (overwrites remote history)"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard (discards uncommitted changes)"),
    (r"\bgit\s+clean\s+[^|]*-f", "git clean -f (deletes untracked files)"),
    (r"\bgit\s+checkout\s+--\s+\.", "git checkout -- . (discards all changes)"),
    (r"\bgit\s+branch\s+-D\b", "git branch -D (force-deletes branch)"),
    # Docker destruction
    (r"\bdocker\s+(system\s+prune|volume\s+rm|rmi\s+-f)", "docker destructive command"),
    # Process killing
    (r"\bkill\s+-9\b|\bkillall\b|\bpkill\b", "process kill signal"),
    # System-level danger
    (r"\bchmod\s+777\b", "chmod 777 (world-writable permissions)"),
    (r"\b(curl|wget)\s+[^|]*\|\s*(sudo\s+)?bash", "pipe to bash (remote code execution risk)"),
]


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def is_active() -> bool:
    """Check if /careful mode is active for this session."""
    # Check env var
    if os.environ.get("CAREFUL_MODE") == "1":
        return True
    # Check session state file (set when user says /careful)
    state_file = f"/tmp/claude-careful-{session_id()}.state"
    try:
        with open(state_file) as f:
            return f.read().strip() == "active"
    except Exception:
        return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or ""
    if tool != "Bash":
        return 0

    if not is_active():
        return 0

    command = ((payload or {}).get("tool_input") or {}).get("command") or ""
    if not command:
        return 0

    # Check all patterns
    warnings = []
    for pattern, description in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            warnings.append(description)

    if not warnings:
        return 0

    warning_list = "\n".join(f"  - {w}" for w in warnings)
    context = (
        f"[/careful SAFETY WARNING] Destructive command detected:\n"
        f"{warning_list}\n\n"
        f"Command: `{command[:200]}{'...' if len(command) > 200 else ''}`\n\n"
        f"BEFORE executing this command, you MUST:\n"
        f"1. Explain to the user WHAT this command does and WHY it's dangerous\n"
        f"2. Ask for EXPLICIT confirmation: 'Эта команда {warnings[0]}. Продолжить?'\n"
        f"3. Only proceed if the user confirms\n\n"
        f"If the user has already confirmed this specific action in this conversation, proceed."
    )

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

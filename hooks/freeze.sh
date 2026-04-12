#!/usr/bin/env python3
"""
PreToolUse hook — /freeze scope guardrail (inspired by gstack).

When active, restricts file modifications (Edit/Write/NotebookEdit) to
a specific directory scope. Any attempt to modify files outside the
frozen scope triggers a warning asking Claude to confirm with the user.

Activation: user says "/freeze src/auth" → creates a state file with
the allowed scope. Deactivated with "/unfreeze".

State: /tmp/claude-freeze-{session}.state contains the allowed path
prefix (e.g., "src/auth"). If empty or missing, freeze is inactive.

Does NOT block (exit 0, permissionDecision: allow) — soft guardrail.
Adds friction by requiring explicit acknowledgment for out-of-scope edits.

Reads JSON on stdin: {"tool_name": "Edit", "tool_input": {"file_path": "..."}}
"""
from __future__ import annotations

import json
import os
import sys


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def get_frozen_scope() -> str | None:
    """Return the frozen scope path, or None if not active."""
    state_file = f"/tmp/claude-freeze-{session_id()}.state"
    try:
        with open(state_file) as f:
            scope = f.read().strip()
            return scope if scope else None
    except Exception:
        return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or ""
    if tool not in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return 0

    scope = get_frozen_scope()
    if scope is None:
        return 0

    tool_input = (payload or {}).get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    # Normalize paths for comparison
    abs_scope = os.path.abspath(scope)
    abs_file = os.path.abspath(file_path)

    # Check if the file is within the frozen scope
    if abs_file.startswith(abs_scope + os.sep) or abs_file == abs_scope:
        return 0  # Within scope, no warning

    context = (
        f"[/freeze SCOPE WARNING] File modification outside frozen scope!\n\n"
        f"Frozen scope: `{scope}`\n"
        f"Target file:  `{file_path}`\n\n"
        f"The user has activated /freeze to restrict edits to `{scope}`. "
        f"This file is OUTSIDE that scope.\n\n"
        f"BEFORE modifying this file, you MUST:\n"
        f"1. Tell the user: 'Этот файл за пределами замороженного scope ({scope}). "
        f"Вы уверены, что хотите его изменить?'\n"
        f"2. Only proceed if the user confirms\n"
        f"3. If the user wants to expand the scope, suggest: '/unfreeze' then '/freeze new/path'\n\n"
        f"If the user has already confirmed out-of-scope edits in this conversation, proceed."
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

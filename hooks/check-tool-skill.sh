#!/usr/bin/env python3
"""
PreToolUse hook — fires before Bash/Edit/Write/NotebookEdit. Gently
reminds Claude to verify a skill from Idea-to-Deploy doesn't fit before
raw tool calls. Does NOT block: always exits 0 with permission allow.

v1.5.0 change: **rate limited**. This hook used to fire on every single
tool call, which trained the model to respond with a formal "скиллы не
матчатся" brush-off before every Bash/Edit. That defeats the point —
the reminder should be a prompt to think, not a recurring checkpoint.

New behavior:
  - Only emits the reminder if no reminder has been shown in the last
    60 seconds (per Claude session, tracked via /tmp/claude-skill-
    check-<session>.state).
  - Softer language: "подумай" instead of "STOP". The hard rule to
    evaluate skills task-level is in ~/projects/.claude/CLAUDE.md; this
    hook is a nudge, not an enforcement point.
  - First tool call of a session always emits the reminder regardless
    of the window (fresh session = fresh thinking).

Session id: derived from CLAUDE_SESSION_ID env var if present, else
from the parent process id. If neither is available, use "default".

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}}
"""
from __future__ import annotations

import json
import os
import sys
import time

REMIND_WINDOW_SECONDS = 60


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    # Fall back to parent pid — stable within a single Claude Code session
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def should_remind() -> bool:
    """Return True if we should emit the reminder (no recent emit)."""
    state_file = f"/tmp/claude-skill-check-{session_id()}.state"
    now = time.time()

    try:
        with open(state_file) as f:
            last = float(f.read().strip() or "0")
    except Exception:
        last = 0

    if now - last < REMIND_WINDOW_SECONDS:
        return False

    try:
        with open(state_file, "w") as f:
            f.write(str(now))
    except Exception:
        pass  # best effort — if we can't write state, still emit
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or "?"

    if not should_remind():
        return 0  # silent no-op when recently reminded

    context = (
        f"[SKILL CHECK — периодическое напоминание] Сейчас вызов {tool}. "
        "Если это первое действие по новой задаче — оцени её task-level: "
        "подходит ли /bugfix, /test, /refactor, /doc, /review, /explain, "
        "/perf, /project, /task, /blueprint, /guide, /session-save? Если "
        "скилл подходит, вызови его ПЕРВЫМ, не руками. Если уже работаешь "
        "внутри задачи (выбор сделан) — продолжай, это напоминание "
        "следующее увидишь не раньше чем через минуту. Подробности: "
        "~/projects/.claude/CLAUDE.md раздел «ЖЁСТКОЕ ПРАВИЛО»."
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

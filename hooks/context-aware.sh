#!/usr/bin/env python3
"""
UserPromptSubmit hook — context-aware session management (inspired by GSD).

Detects long sessions (many tool calls / large context) and recommends
fresh context strategies:
  1. After N significant tool calls → suggest /session-save + fresh start
  2. Inject tiered prompt for subagents (minimal context for the task)
  3. Track session depth and warn about context rot

The key insight from GSD: spawn fresh subagents with clean 200K windows
for each unit of work, pre-loaded with only the dispatch prompt (plan +
summary), not the full conversation history.

v1.18.0: Adaptation from GSD context management.
"""
from __future__ import annotations

import json
import os
import sys
import time

# Session tool call counter file
COUNTER_DIR = "/tmp"
TOOL_CALL_THRESHOLD = 40  # Suggest fresh context after this many calls
WARNING_INTERVAL_SEC = 300  # Don't warn more than once per 5 min


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def counter_file() -> str:
    return os.path.join(COUNTER_DIR, f"claude-context-{session_id()}.json")


def read_state() -> dict:
    try:
        with open(counter_file()) as f:
            return json.load(f)
    except Exception:
        return {"count": 0, "last_warning": 0, "session_start": time.time()}


def write_state(state: dict) -> None:
    try:
        with open(counter_file(), "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def main() -> int:
    try:
        json.load(sys.stdin)  # consume stdin
    except Exception:
        pass

    state = read_state()
    state["count"] = state.get("count", 0) + 1
    now = time.time()

    # Check if we should warn
    count = state["count"]
    last_warning = state.get("last_warning", 0)
    session_start = state.get("session_start", now)
    session_minutes = int((now - session_start) / 60)

    should_warn = (
        count >= TOOL_CALL_THRESHOLD
        and (now - last_warning) > WARNING_INTERVAL_SEC
    )

    if should_warn:
        state["last_warning"] = now
        write_state(state)

        context = (
            f"[CONTEXT MANAGEMENT — GSD-inspired]\n"
            f"📊 Session stats: {count} tool calls, {session_minutes} min elapsed.\n\n"
            f"⚠️ Long session detected — risk of context rot (quality degradation "
            f"as context window fills up).\n\n"
            f"**Recommended actions:**\n"
            f"1. Run `/session-save` to persist current progress\n"
            f"2. For complex remaining work — suggest user start a fresh session\n"
            f"3. When spawning subagents (Agent tool), use **tiered prompt injection**:\n"
            f"   - Include ONLY the plan/spec relevant to the subtask\n"
            f"   - Do NOT dump full conversation history\n"
            f"   - Let the subagent read files directly instead of passing content\n\n"
            f"**Tiered injection pattern** (from GSD):\n"
            f"- Level 1 (always): task description + acceptance criteria\n"
            f"- Level 2 (if needed): relevant file paths + key decisions\n"
            f"- Level 3 (rarely): full context dump (avoid — causes rot)\n"
        )

        out = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0

    write_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())

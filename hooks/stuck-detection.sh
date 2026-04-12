#!/usr/bin/env python3
"""
PostToolUse hook — stuck detection (inspired by GSD v2).

Uses a sliding window to detect when Claude is repeating the same
actions without making progress. Typical stuck patterns:
  - Same file edited 3+ times in a row
  - Same Bash command retried 3+ times
  - Same Grep/Glob pattern searched 3+ times

When a stuck pattern is detected, injects diagnostic advice:
  - "You appear to be stuck — try a different approach"
  - Suggests specific alternatives based on the pattern

v1.18.0: Adaptation from GSD v2 stuck detection.

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}}
"""
from __future__ import annotations

import json
import os
import sys
import time

WINDOW_SIZE = 8  # Track last N tool calls
REPEAT_THRESHOLD = 3  # Alert after N identical actions
COOLDOWN_SEC = 120  # Don't warn more than once per 2 min


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def state_file() -> str:
    return f"/tmp/claude-stuck-{session_id()}.json"


def read_state() -> dict:
    try:
        with open(state_file()) as f:
            return json.load(f)
    except Exception:
        return {"window": [], "last_warning": 0}


def write_state(state: dict) -> None:
    try:
        with open(state_file(), "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def fingerprint(tool: str, tool_input: dict) -> str:
    """Create a short fingerprint for dedup detection."""
    if tool == "Bash":
        cmd = tool_input.get("command", "")
        # Normalize: strip whitespace, take first 80 chars
        return f"Bash:{cmd.strip()[:80]}"
    elif tool in ("Edit", "Write"):
        path = tool_input.get("file_path", "")
        return f"{tool}:{path}"
    elif tool == "Read":
        path = tool_input.get("file_path", "")
        return f"Read:{path}"
    elif tool in ("Grep", "Glob"):
        pattern = tool_input.get("pattern", "")
        return f"{tool}:{pattern[:60]}"
    else:
        return f"{tool}:other"


def detect_stuck(window: list[str]) -> str | None:
    """Check if the sliding window shows a stuck pattern."""
    if len(window) < REPEAT_THRESHOLD:
        return None

    # Check last N entries for identical fingerprints
    last = window[-1]
    count = 0
    for entry in reversed(window):
        if entry == last:
            count += 1
        else:
            break

    if count >= REPEAT_THRESHOLD:
        return last

    # Check for edit-read-edit-read cycle on same file
    if len(window) >= 4:
        pairs = set()
        for i in range(len(window) - 1):
            pair = (window[i], window[i + 1])
            pairs.add(pair)
        # If we see the same pair repeated, it's a cycle
        for pair in pairs:
            pair_count = sum(
                1
                for i in range(len(window) - 1)
                if (window[i], window[i + 1]) == pair
            )
            if pair_count >= REPEAT_THRESHOLD:
                return f"cycle:{pair[0]}→{pair[1]}"

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or ""
    tool_input = (payload or {}).get("tool_input") or {}

    state = read_state()
    window = state.get("window", [])

    fp = fingerprint(tool, tool_input)
    window.append(fp)
    if len(window) > WINDOW_SIZE:
        window = window[-WINDOW_SIZE:]
    state["window"] = window

    now = time.time()
    last_warning = state.get("last_warning", 0)

    stuck_pattern = detect_stuck(window)

    if stuck_pattern and (now - last_warning) > COOLDOWN_SEC:
        state["last_warning"] = now
        write_state(state)

        # Determine advice based on pattern
        if stuck_pattern.startswith("Bash:"):
            advice = (
                "**The same Bash command is being retried.** Try:\n"
                "- Read the error message carefully\n"
                "- Check if a file/dependency is missing\n"
                "- Try a completely different approach\n"
                "- Ask the user for guidance"
            )
        elif stuck_pattern.startswith(("Edit:", "Write:")):
            advice = (
                "**The same file is being edited repeatedly.** Try:\n"
                "- Read the file to verify current state\n"
                "- Check if your edit pattern matches correctly\n"
                "- Consider rewriting the entire section instead of patching"
            )
        elif stuck_pattern.startswith("cycle:"):
            advice = (
                "**A read-edit cycle detected on the same file.** Try:\n"
                "- Step back and re-read the requirements\n"
                "- The approach may be fundamentally wrong\n"
                "- Ask the user if the direction is correct"
            )
        else:
            advice = (
                "**Repeated identical actions detected.** Try:\n"
                "- Take a different approach entirely\n"
                "- Ask the user for clarification\n"
                "- Run /session-save and suggest a fresh session"
            )

        context = (
            f"[STUCK DETECTION — GSD-inspired]\n"
            f"🔄 Pattern: `{stuck_pattern[:80]}`\n"
            f"Repeated {REPEAT_THRESHOLD}+ times in last {WINDOW_SIZE} tool calls.\n\n"
            f"{advice}\n\n"
            f"⚡ Continuing the same approach wastes tokens without progress."
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

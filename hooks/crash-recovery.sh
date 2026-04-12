#!/usr/bin/env python3
"""
PostToolUse hook — crash recovery checkpoint (inspired by GSD v2).

Auto-saves a lightweight checkpoint after every N significant tool calls
(Write, Edit, Bash with git commit). If Claude crashes mid-session,
the checkpoint file lets the next session reconstruct what was done.

GSD v2 uses lock-files + PID liveness + forensics synthesis from
surviving tool calls. We adapt the core idea: periodic auto-checkpoints
that survive crashes.

The checkpoint is a JSON file with:
  - Last N tool calls (tool name + key input summary)
  - Current branch + last commit
  - Timestamp
  - Session goal (if detectable from first prompt)

On next session start, pre-flight-check.sh reads this file and
injects it as context if the session ended abnormally (no /session-save).

v1.18.0: Adaptation from GSD v2 crash recovery.

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

CHECKPOINT_INTERVAL = 10  # Save checkpoint every N tool calls
MAX_TOOL_HISTORY = 20  # Keep last N tool calls in checkpoint
SIGNIFICANT_TOOLS = {"Write", "Edit", "Bash", "Agent", "Skill"}


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def checkpoint_file() -> str:
    return f"/tmp/claude-checkpoint-{session_id()}.json"


def git_info() -> dict:
    """Get current branch and last commit."""
    info = {}
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            info["last_commit"] = result.stdout.strip()
    except Exception:
        pass
    return info


def read_checkpoint() -> dict:
    try:
        with open(checkpoint_file()) as f:
            return json.load(f)
    except Exception:
        return {
            "session_id": session_id(),
            "session_start": time.time(),
            "tool_history": [],
            "call_count": 0,
            "last_checkpoint": 0,
            "clean_exit": False,
        }


def write_checkpoint(cp: dict) -> None:
    try:
        with open(checkpoint_file(), "w") as f:
            json.dump(cp, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def summarize_tool_input(tool: str, tool_input: dict) -> str:
    """Create a short summary of what the tool call did."""
    if tool == "Bash":
        cmd = tool_input.get("command", "")
        return cmd[:120]
    elif tool in ("Write", "Edit"):
        path = tool_input.get("file_path", "")
        return path
    elif tool == "Agent":
        desc = tool_input.get("description", "")
        return desc[:80]
    elif tool == "Skill":
        return tool_input.get("skill", "")
    else:
        return tool[:30]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or ""

    # Only track significant tool calls
    if tool not in SIGNIFICANT_TOOLS:
        return 0

    tool_input = (payload or {}).get("tool_input") or {}

    cp = read_checkpoint()
    cp["call_count"] = cp.get("call_count", 0) + 1

    # Add to tool history
    history = cp.get("tool_history", [])
    history.append({
        "tool": tool,
        "summary": summarize_tool_input(tool, tool_input),
        "time": time.time(),
    })
    # Keep only last N
    if len(history) > MAX_TOOL_HISTORY:
        history = history[-MAX_TOOL_HISTORY:]
    cp["tool_history"] = history

    # Periodic checkpoint with git info
    count = cp["call_count"]
    if count % CHECKPOINT_INTERVAL == 0:
        cp["git"] = git_info()
        cp["last_checkpoint"] = time.time()
        cp["clean_exit"] = False

    write_checkpoint(cp)

    # Silent hook — no output to Claude context.
    # M-C10 marker: "hookEventName": "PostToolUse"
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
PreToolUse hook — live execution tracer (v1.21, observability).

Closes the live-execution-trace gap noted in docs/DESIGN_SPACE.md (K15) and
docs/HARNESS_ENGINEERING_MAP.md (H5). Appends one JSON line per tool call to
`.claude/traces/session-<id>.jsonl` in the current project, giving a live,
replayable record of "which tool ran against what" during a session — useful
for debugging the methodology itself and for user oversight.

Opt-in, like cost-tracker.sh: active only when registered in settings.json
(register with matcher "*" to trace every tool). Never blocks (exit 0, no
permission verdict) and injects NOTHING into the model context — pure
side-effect telemetry, so it costs zero context budget. Writes are
best-effort; any failure is swallowed so it never breaks a session.
`.claude/` is gitignored, so traces never pollute the repo.

Reads JSON on stdin:
  {"session_id": "...", "cwd": "...", "tool_name": "...", "tool_input": {...}}
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Per-tool: the input field that best identifies the target of the call.
TARGET_FIELDS = ("file_path", "command", "path", "pattern", "url", "notebook_path", "prompt")
MAX_TARGET = 300


def summarize_target(tool_input: dict) -> str:
    if not isinstance(tool_input, dict):
        return ""
    for field in TARGET_FIELDS:
        val = tool_input.get(field)
        if isinstance(val, str) and val:
            return val[:MAX_TARGET] + ("…" if len(val) > MAX_TARGET else "")
    return ""


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0  # bad/empty payload — stay silent, never break the session

    try:
        tool = payload.get("tool_name", "")
        if not tool:
            return 0
        session_id = str(payload.get("session_id") or "unknown")
        # Sanitize the session id for safe use in a filename.
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64] or "unknown"
        cwd = payload.get("cwd") or "."
        trace_dir = Path(cwd) / ".claude" / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": tool,
            "target": summarize_target(payload.get("tool_input") or {}),
        }
        with (trace_dir / f"session-{safe_id}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return 0  # telemetry failure must never break the session

    # Minimal valid PreToolUse response: declares the event name (required by
    # the M-C10 schema check), injects no context, makes no permission verdict.
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

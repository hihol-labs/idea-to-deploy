#!/usr/bin/env python3
"""
PreToolUse hook — context-budget reminder (v1.21, PFO plugin-native port item 16).

Fires before Bash tool calls. Detects commands likely to dump a large UNBOUNDED
output into the context window (raw HTTP/API bodies, `cat` of big files, wide
`grep`/`find`/`rg` with no result cap, tailing logs without a limit). Long tasks
degrade when raw dumps flood context — spend it like a budget.
See skills/_shared/helpers.md §7.

Does NOT block (exit 0, soft reminder only) — it injects a note via
hookSpecificOutput.additionalContext asking the model to bound or summarize the
output. Judgment stays with the skill. The user can disable it by removing the
hook from settings.json.

Reads JSON on stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}}
"""
from __future__ import annotations

import json
import re
import sys

# Bounding/limiting constructs that make a large output acceptable.
BOUNDED = re.compile(
    r"\bhead\b|\btail\b|--max-count|[ =]-m\b|[ =]-n\b|\bwc\b|\|\s*less|--silent|\bjq\b",
    re.IGNORECASE,
)

# (risk regex, label). Each fires only when no BOUNDED construct is present.
RISKY = [
    (re.compile(r"\b(curl|wget|https?)\b", re.IGNORECASE), "raw HTTP/API body"),
    (re.compile(r"(^|[;&|])\s*cat\s", re.IGNORECASE), "full file dump (cat)"),
    (re.compile(r"\b(find|grep\s+-r|rg)\b", re.IGNORECASE), "wide search with no result cap"),
]


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0  # bad/empty payload — stay silent, never break the session

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or BOUNDED.search(command):
        return 0

    for pattern, label in RISKY:
        if pattern.search(command):
            context = (
                f"[context-budget] This command may dump a large unbounded output "
                f"({label}).\n"
                f"Command: `{command[:200]}{'...' if len(command) > 200 else ''}`\n\n"
                f"Prefer to: summarize the signal (counts / the few relevant lines), "
                f"bound at the source (`| head -50`, `rg -m 20`, `--max-count`, Read "
                f"offset/limit), or write the full output to a file and reference the "
                f"path — instead of pasting it all into context. Soft reminder, not blocking."
            )
            out = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": context,
                }
            }
            sys.stdout.write(json.dumps(out, ensure_ascii=False))
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
PreToolUse hook — fires before Bash/Edit/Write/NotebookEdit. Reminds Claude
to verify a skill from Idea-to-Deploy doesn't fit before raw tool calls.
Does NOT block: always exits 0 with permission allow.

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}}
"""
import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or "?"

    context = (
        f"[SKILL CHECK] Сейчас вызов {tool}. Прежде чем продолжить — убедись, "
        "что не подходит ни один скилл из Idea-to-Deploy "
        "(см. ~/projects/.claude/CLAUDE.md). Если подходит /debug, /test, "
        "/refactor, /doc, /review, /explain, /perf, /project, /blueprint, "
        "/guide — STOP, вызови Skill сначала. Если не подходит — продолжай."
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

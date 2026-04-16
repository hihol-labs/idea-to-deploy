#!/usr/bin/env python3
"""
PreToolUse hook on Bash — fires before every Bash invocation.
If the command is `git commit` and more than 2 files are staged,
checks if /review was called in this session.

Tracking: when the Skill tool is called with skill="review",
the PostToolUse hook (or this hook on Skill calls) writes a marker
file. This hook reads the marker before allowing commit.

Marker file: /tmp/claude-review-done-{session_id}

If /review was NOT called and >2 files staged → BLOCK with deny.

This enforces the CLAUDE.md rule:
"Коммитить более 2 файлов без предварительного /review запрещено"
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


GIT_COMMIT_RE = re.compile(r"(^|\s|;|&&|\|\|)git\s+commit(\s|$)")
MAX_FILES_WITHOUT_REVIEW = 2


def get_session_id() -> str:
    return os.environ.get("CLAUDE_SESSION_ID") or str(os.getppid())


def review_marker_path() -> Path:
    return Path(f"/tmp/claude-review-done-{get_session_id()}")


def review_was_done() -> bool:
    return review_marker_path().exists()


def mark_review_done() -> None:
    review_marker_path().write_text(str(os.getpid()))


def staged_file_count() -> int:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return 0
        return len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        return 0


def emit_deny(count: int) -> None:
    msg = (
        f"[REVIEW GATE] Коммит заблокирован: {count} файлов в staging, "
        f"но /review не был вызван в этой сессии.\n\n"
        f"Правило: коммитить >2 файлов без /review запрещено (CLAUDE.md).\n\n"
        f"Действия:\n"
        f"  1. Запусти /review для проверки изменений\n"
        f"  2. После /review повтори git commit\n"
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stderr.write(msg)
    sys.exit(2)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or ""
    tool_input = (payload or {}).get("tool_input") or {}

    # Only check Bash commands. The /review marker file
    # /tmp/claude-review-done-{session} is written by the /review skill
    # itself at Step 5 — NOT by this hook. The Skill tool is an internal
    # harness construct and does not route through PreToolUse hooks, so
    # we cannot detect `/review` invocations from here.
    if tool != "Bash":
        return 0

    cmd = tool_input.get("command") or ""
    if not GIT_COMMIT_RE.search(cmd):
        return 0

    # Check staged file count
    count = staged_file_count()
    if count <= MAX_FILES_WITHOUT_REVIEW:
        return 0  # small commit, no review needed

    # Check if /review was done
    if review_was_done():
        return 0  # review was called, allow commit

    # Block!
    emit_deny(count)
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())

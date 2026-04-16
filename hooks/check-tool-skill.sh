#!/usr/bin/env python3
"""
PreToolUse hook — fires before Bash/Edit/Write/NotebookEdit.
Reminds Claude to verify a skill from Idea-to-Deploy doesn't fit before
raw tool calls.

v1.19.0 change: **enforcement mode** (Gap #4 from ROADMAP_v1.19.md).

Previous behavior (v1.5.0–v1.18.1):
  - Rate-limited reminder every 60s, always exit 0, never blocks.
  - Claude could (and did) ignore reminders indefinitely.

New behavior (v1.19.0):
  - Still rate-limited to 60s between reminders.
  - Tracks consecutive ignored reminders in a state file.
  - After MAX_IGNORES (3) consecutive reminders without a Skill call,
    the hook BLOCKS the next tool call (returns decision: "block")
    with a message requiring Claude to either:
      a) Call a Skill first, OR
      b) Justify the bypass by including "SKILL_BYPASS: <reason>"
         in the model's response text before retrying.
  - Skill tool calls reset the ignore counter to 0.
  - The ignore counter also resets when Claude provides a bypass
    justification (detected by checking tool_input for SKILL_BYPASS marker).

State files (per-session):
  /tmp/claude-skill-check-{session}.state    — last reminder timestamp
  /tmp/claude-skill-ignores-{session}.state  — ignore count (int)

Session id: CLAUDE_SESSION_ID env var → parent pid → "default".

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}}
"""
from __future__ import annotations

import json
import os
import sys
import time

REMIND_WINDOW_SECONDS = 60
MAX_IGNORES = 3  # block after this many consecutive ignored reminders


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def state_paths() -> tuple[str, str]:
    """Return (reminder_state_path, ignore_count_path)."""
    sid = session_id()
    return (
        f"/tmp/claude-skill-check-{sid}.state",
        f"/tmp/claude-skill-ignores-{sid}.state",
    )


def read_ignore_count(path: str) -> int:
    try:
        with open(path) as f:
            return int(f.read().strip() or "0")
    except Exception:
        return 0


def write_ignore_count(path: str, count: int) -> None:
    try:
        with open(path, "w") as f:
            f.write(str(count))
    except Exception:
        pass


def should_remind(reminder_path: str) -> bool:
    """Return True if enough time passed since last reminder."""
    now = time.time()
    try:
        with open(reminder_path) as f:
            last = float(f.read().strip() or "0")
    except Exception:
        last = 0

    if now - last < REMIND_WINDOW_SECONDS:
        return False

    try:
        with open(reminder_path, "w") as f:
            f.write(str(now))
    except Exception:
        pass
    return True


def has_bypass_marker(payload: dict) -> bool:
    """Check if the tool input contains a SKILL_BYPASS justification.

    Only checks the 'description' field (human-visible Bash description)
    to prevent accidental bypass via crafted command strings or file paths.
    See Anthropic compliance audit I-3.
    """
    tool_input = payload.get("tool_input") or {}
    val = tool_input.get("description", "")
    return isinstance(val, str) and "SKILL_BYPASS:" in val


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = (payload or {}).get("tool_name") or "?"
    reminder_path, ignore_path = state_paths()

    # --- Skill call detected → reset ignore counter, allow silently ---
    if tool == "Skill":
        write_ignore_count(ignore_path, 0)
        return 0

    # --- Bypass marker in tool input → reset counter, allow ---
    if has_bypass_marker(payload):
        write_ignore_count(ignore_path, 0)
        return 0

    # --- Check if we should enforce (block) ---
    ignore_count = read_ignore_count(ignore_path)

    if ignore_count >= MAX_IGNORES:
        # BLOCK: too many consecutive ignores
        block_msg = (
            f"[SKILL ENFORCEMENT — БЛОКИРОВКА] ⛔ Подряд {ignore_count} "
            "напоминаний о скиллах были проигнорированы. Tool call ЗАБЛОКИРОВАН.\n\n"
            "Чтобы продолжить, выбери ОДНО из двух:\n"
            "1. Вызови подходящий скилл через инструмент Skill "
            "(/bugfix, /test, /refactor, /doc, /review, /explain, /perf, "
            "/project, /task, /blueprint, /guide, /session-save, "
            "/security-audit, /deps-audit, /migrate, /harden, /infra)\n"
            "2. Обоснуй обход — добавь в description Bash/Edit/Write текст "
            "'SKILL_BYPASS: <причина почему ни один скилл не подходит>'\n\n"
            "Подробности: ROADMAP_v1.19.md Gap #4, "
            "~/projects/.claude/CLAUDE.md раздел «ЖЁСТКОЕ ПРАВИЛО»."
        )
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": block_msg,
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stderr.write(block_msg)
        sys.exit(2)

    # --- Rate-limited reminder ---
    if not should_remind(reminder_path):
        return 0  # silent no-op when recently reminded

    # Increment ignore counter (will be reset if Skill is called next)
    write_ignore_count(ignore_path, ignore_count + 1)

    context = (
        f"[SKILL CHECK — периодическое напоминание] Сейчас вызов {tool}. "
        "Если это первое действие по новой задаче — оцени её task-level: "
        "подходит ли /bugfix, /test, /refactor, /doc, /review, /explain, "
        "/perf, /project, /task, /blueprint, /guide, /session-save? Если "
        "скилл подходит, вызови его ПЕРВЫМ, не руками. Если уже работаешь "
        "внутри задачи (выбор сделан) — продолжай, это напоминание "
        "следующее увидишь не раньше чем через минуту. Подробности: "
        "~/projects/.claude/CLAUDE.md раздел «ЖЁСТКОЕ ПРАВИЛО».\n\n"
        f"⚠️ Счётчик игнорирований: {ignore_count + 1}/{MAX_IGNORES}. "
        f"После {MAX_IGNORES} подряд — tool calls будут ЗАБЛОКИРОВАНЫ."
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

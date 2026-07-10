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

The checkpoint lives at /tmp/claude-checkpoint-{session_id}.json.

v1.18.0: Adaptation from GSD v2 crash recovery.
v1.19.2: Docstring clarified — no automatic consumer yet.
v1.67.0: Automatic consumer CLOSED (init-audit gap #5):
  - the checkpoint now records `cwd`, so a later session can match it to
    the project;
  - the same script is also registered on the Stop event: a turn that ends
    normally marks `clean_exit: true`, and every significant tool call
    flips it back to false — so `clean_exit: false` at session death means
    "died mid-work";
  - `pre-flight-check.sh` (crash_checkpoint_context) reads crashed
    checkpoints for the current cwd on session start, injects the last
    tool calls into context, and marks them consumed.

Reads JSON on stdin (PostToolUse): {"tool_name": "...", "tool_input": {...}}
                     (Stop):       {"hook_event_name": "Stop", ...}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _cwd() -> str:
    """Нормализованный cwd: Path.resolve() разворачивает 8.3-short-paths
    Windows (RUNNER~1 -> длинное имя), иначе consumer в pre-flight не сматчит
    чекпоинт по cwd (v1.68.1)."""
    try:
        return str(Path.cwd().resolve())
    except Exception:
        return os.getcwd()

CHECKPOINT_INTERVAL = 10  # Save checkpoint every N tool calls
MAX_TOOL_HISTORY = 20  # Keep last N tool calls in checkpoint
SIGNIFICANT_TOOLS = {"Write", "Edit", "Bash", "Agent", "Skill"}


def session_id(payload: dict | None = None) -> str:
    # v1.69.1: payload первым — Claude Code кладёт session_id в stdin-JSON
    # КАЖДОГО хук-события. env CLAUDE_SESSION_ID на Windows-хуках пуст, а
    # fallback pid{getppid()} НЕСТАБИЛЕН между вызовами: tool-коллы и
    # Stop/SubagentStop писали в РАЗНЫЕ файлы (наблюдалось 369 фрагментов),
    # clean-маркер бил мимо — фантомные «Crash recovery» возвращались.
    sid = (payload or {}).get("session_id") or os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return str(sid)
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def checkpoint_file(sid: str | None = None, payload: dict | None = None) -> str:
    return os.path.join(tempfile.gettempdir(),
                        f"claude-checkpoint-{sid or session_id(payload)}.json")


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


def read_checkpoint(sid: str) -> dict:
    try:
        with open(checkpoint_file(sid), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "session_id": sid,
            "session_start": time.time(),
            "tool_history": [],
            "call_count": 0,
            "last_checkpoint": 0,
            "clean_exit": False,
        }


def write_checkpoint(cp: dict, sid: str) -> None:
    # v1.75.0 (ACID-audit fixes #1+#3): atomic tmp+os.replace — a session that
    # dies mid-write can no longer leave a truncated checkpoint (the consumer
    # in pre-flight would silently skip it); a failed persist is logged to a
    # bounded error file instead of being swallowed.
    target = checkpoint_file(sid)
    tmp = f"{target}.tmp-{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cp, f, indent=2, ensure_ascii=False)
        os.replace(tmp, target)
    except Exception as exc:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass
        _log_persist_error("write_checkpoint", exc)


def _log_persist_error(where: str, exc: BaseException) -> None:
    """Persist failures must be observable (audit fix #3). Best-effort."""
    try:
        p = os.path.join(tempfile.gettempdir(), "claude-checkpoint-errors.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {where}: "
                    f"{type(exc).__name__}: {exc}\n")
        if os.path.getsize(p) > 64 * 1024:
            with open(p, encoding="utf-8", errors="replace") as f:
                tail = f.read()[-32 * 1024:]
            tmp = f"{p}.tmp-{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(tail)
            os.replace(tmp, p)
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

    payload = payload or {}
    tool = payload.get("tool_name") or ""
    sid = session_id(payload)  # v1.69.1: payload-first, стабилен для всех событий агента

    # v1.67.0: on Stop (turn ended normally) mark the checkpoint clean.
    # v1.69.0: SubagentStop тоже — субагенты пишут чекпоинты (PostToolUse
    # фаерится в их контексте со своим session_id), но завершаются через
    # SubagentStop; без этой ветки их чекпоинты вечно clean_exit=false и
    # всплывали фантомными «Crash recovery» в главной сессии. Умерший
    # мид-флайт субагент по-прежнему всплывает (сюда не доходит).
    event = (payload.get("hook_event_name") or "").lower()
    if event in ("stop", "subagentstop") or ("stop_hook_active" in payload and not tool):
        cp = read_checkpoint(sid)
        cp["clean_exit"] = True
        cp["cwd"] = _cwd()
        write_checkpoint(cp, sid)
        return 0

    # Only track significant tool calls
    if tool not in SIGNIFICANT_TOOLS:
        return 0

    tool_input = payload.get("tool_input") or {}

    cp = read_checkpoint(sid)
    cp["call_count"] = cp.get("call_count", 0) + 1
    cp["cwd"] = _cwd()
    cp["clean_exit"] = False  # work in flight — a death from here on is a crash

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

    write_checkpoint(cp, sid)

    # Silent hook — no output to Claude context.
    # M-C10 marker: "hookEventName": "PostToolUse"
    return 0


if __name__ == "__main__":
    sys.exit(main())

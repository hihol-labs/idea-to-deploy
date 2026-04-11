#!/usr/bin/env python3
"""
UserPromptSubmit hook — fires on every user prompt. Injects recent git
activity, active-session lockfiles, and memory-index state into the
model's context BEFORE it starts picking tools.

Why: Claude sessions are isolated. Two sessions working on the same
repo cannot see each other's commits, task state, or lockfiles. Without
this hook, a session often starts work that was already completed by a
parallel session (see NeuroExpert 2026-04-11 incident: same kong.yml
tech debt fixed twice in parallel).

What it does:
  1. `git log --oneline -10` + `git status --short` in $PWD (if it's a
     git repo) → so the model sees recent commits and dirty files on
     entry.
  2. Looks at the Claude project memory dir for this project
     (`~/.claude/projects/<hash>/memory/`), reads MEMORY.md index if
     present, and reads `.active-session.lock` if fresher than 10
     minutes — warns that a parallel session is (likely) active.
  3. Emits everything as `hookSpecificOutput.additionalContext`.

Does NOT block: always exits 0 with permission allow. Timeout-safe:
every external call has a 2-second deadline; the hook as a whole must
complete within the 5-second budget configured in settings.json.

Reads JSON on stdin: {"user_prompt": "..."}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

GIT_TIMEOUT_SEC = 2
LOCK_FRESH_SECONDS = 600  # 10 minutes
MEMORY_INDEX_MAX_LINES = 30


def run(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a command with a tight timeout. Return stdout on success, '' on failure."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SEC,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def git_context(cwd: Path) -> str:
    """Return a compact git status + log block, or empty string if not a repo."""
    # Cheap check first: is this a git repo?
    top = run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if not top:
        return ""

    branch = run(["git", "branch", "--show-current"], cwd=cwd) or "(detached)"
    log = run(["git", "log", "--oneline", "-10"], cwd=cwd)
    status = run(["git", "status", "--short"], cwd=cwd)

    lines = [f"**Git context** (branch: `{branch}`, repo: `{top}`)"]
    if log:
        lines.append("")
        lines.append("Recent commits:")
        lines.append("```")
        lines.append(log)
        lines.append("```")
    if status:
        lines.append("")
        lines.append("Uncommitted changes:")
        lines.append("```")
        lines.append(status[:800])  # cap to avoid blowing context
        lines.append("```")
    return "\n".join(lines)


def find_project_memory_dir(cwd: Path) -> Path | None:
    """Find the Claude project memory dir for the current cwd.

    Claude Code stores per-project memory at:
      ~/.claude/projects/-home-USER-path-to-project/memory/
    where the dir name is the cwd with `/` replaced by `-` and a leading `-`.
    We resolve it heuristically.
    """
    home = Path.home()
    projects_root = home / ".claude" / "projects"
    if not projects_root.is_dir():
        return None

    # Compute the expected dir name for cwd
    cwd_resolved = cwd.resolve()
    expected = "-" + str(cwd_resolved).lstrip("/").replace("/", "-")
    candidate = projects_root / expected / "memory"
    if candidate.is_dir():
        return candidate

    # Fallback: find any project dir whose name ends with the cwd suffix.
    # We cannot reverse-reconstruct the path from the dir name because `-`
    # is a lossy separator (works for `/home/user/projects/myapp` but fails
    # on `/home/user/projects/my-app` — the reverse `replace("-", "/")`
    # produces `my/app`). Instead, try every suffix of cwd.parts and check
    # if the corresponding expected-dir-name exists, with root="" handled.
    parts = cwd_resolved.parts  # ('/', 'home', 'user', 'projects', 'my-app')
    for i in range(1, len(parts)):
        suffix_parts = parts[i:]
        suffix = "-".join(suffix_parts)
        for entry in projects_root.iterdir():
            if not entry.is_dir() or not entry.name.startswith("-"):
                continue
            # Dir name ends with our suffix → plausible match
            if entry.name.endswith("-" + suffix) or entry.name == "-" + suffix:
                mem = entry / "memory"
                if mem.is_dir():
                    return mem
    return None


def memory_index_context(mem_dir: Path) -> str:
    """Read MEMORY.md index and return a condensed version."""
    index = mem_dir / "MEMORY.md"
    if not index.is_file():
        return ""
    try:
        content = index.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines = [l for l in content.splitlines() if l.strip()]
    if len(lines) > MEMORY_INDEX_MAX_LINES:
        lines = lines[:MEMORY_INDEX_MAX_LINES] + ["(…truncated)"]
    return "**Project memory index** (`MEMORY.md`):\n\n" + "\n".join(lines)


def session_lock_context(mem_dir: Path) -> str:
    """If .active-session.lock is fresh, emit a warning about a parallel session."""
    lock = mem_dir / ".active-session.lock"
    if not lock.is_file():
        return ""
    try:
        raw = lock.read_text(encoding="utf-8", errors="replace").strip()
        data = json.loads(raw)
    except Exception:
        return ""

    ts = data.get("timestamp", 0)
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        return ""

    age = time.time() - ts
    if age > LOCK_FRESH_SECONDS:
        return ""  # stale lock, ignore

    pid = data.get("pid", "?")
    branch = data.get("branch", "?")
    note = data.get("note", "")
    minutes_ago = int(age // 60)
    return (
        "⚠️ **Parallel session warning**: another Claude session touched "
        f"this project {minutes_ago} min ago (pid {pid}, branch `{branch}`)."
        + (f" Note: {note}" if note else "")
        + "\n\nRun `git log --oneline -10` and check the latest `session_*.md` "
        "in memory BEFORE starting work — the task you're about to do may "
        "already be committed."
    )


def main() -> int:
    try:
        json.load(sys.stdin)  # consume, we don't need the content
    except Exception:
        pass  # OK if missing

    cwd = Path(os.getcwd())
    sections: list[str] = []

    git = git_context(cwd)
    if git:
        sections.append(git)

    mem_dir = find_project_memory_dir(cwd)
    if mem_dir:
        lock = session_lock_context(mem_dir)
        if lock:
            sections.append(lock)
        idx = memory_index_context(mem_dir)
        if idx:
            sections.append(idx)

    if not sections:
        return 0  # nothing to report, stay silent

    context = "[PRE-FLIGHT CHECK]\n\n" + "\n\n---\n\n".join(sections)

    out = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

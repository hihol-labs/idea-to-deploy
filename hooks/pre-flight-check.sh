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
CWD_HISTORY_MAX = 10
CWD_SWITCH_WARN_THRESHOLD = 5  # warn about /session-save after this many switches in 30 min


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


def memory_staleness_check(cwd: Path, mem_dir: Path | None) -> str:
    """Check if memory mentions a version that doesn't match current plugin.json.

    This catches the v1.13.1→v1.18.1 drift problem from the 2026-04-15 session
    where Claude used a stale version from memory instead of the actual one.
    """
    if not mem_dir:
        return ""

    # Read current version from plugin.json
    plugin_json = cwd / ".claude-plugin" / "plugin.json"
    if not plugin_json.is_file():
        return ""

    try:
        current_version = json.loads(
            plugin_json.read_text(encoding="utf-8", errors="replace")
        ).get("version", "")
    except Exception:
        return ""

    if not current_version:
        return ""

    # Read latest session file and check for version mentions
    candidates = sorted(
        mem_dir.glob("session_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return ""

    import re

    try:
        content = candidates[0].read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

    # Find version mentions like "v1.13.1" or "version 1.18.0"
    version_pattern = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")
    mentioned_versions = set(version_pattern.findall(content))

    if not mentioned_versions:
        return ""

    # Check if any mentioned version differs from current AND looks like
    # a project version (not a random semver like Python 3.12.0)
    stale_versions = []
    for v in mentioned_versions:
        # Skip versions that look like language/tool versions (major >= 3)
        major = int(v.split(".")[0])
        if major >= 3:
            continue
        if v != current_version:
            stale_versions.append(v)

    if not stale_versions:
        return ""

    return (
        f"⚠️ **Memory staleness**: последняя сессия (`{candidates[0].name}`) "
        f"упоминает версию {', '.join('v' + v for v in stale_versions)}, "
        f"но актуальная версия — **v{current_version}** "
        f"(из `.claude-plugin/plugin.json`). Используй актуальную."
    )


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def context_switch_detect(cwd: Path) -> str:
    """Detect cwd changes between prompts. Returns warning or empty string.

    Tracks last N cwd entries with timestamps in a state file. When a switch
    is detected, warns the user. If switches exceed threshold in 30 min,
    suggests /session-save to prevent context loss.
    """
    state_file = f"/tmp/claude-cwd-history-{session_id()}.json"
    now = time.time()
    cwd_str = str(cwd.resolve())

    # Read existing history
    history: list[dict] = []
    try:
        with open(state_file) as f:
            history = json.loads(f.read() or "[]")
    except Exception:
        history = []

    # Get previous cwd
    prev_cwd = history[-1]["cwd"] if history else None

    # Append current
    history.append({"cwd": cwd_str, "ts": now})

    # Trim to max
    if len(history) > CWD_HISTORY_MAX:
        history = history[-CWD_HISTORY_MAX:]

    # Write back
    try:
        with open(state_file, "w") as f:
            f.write(json.dumps(history))
    except Exception:
        pass

    # No switch? Return empty
    if prev_cwd is None or prev_cwd == cwd_str:
        return ""

    # Switch detected
    prev_name = Path(prev_cwd).name
    curr_name = cwd.name

    # Count recent switches (last 30 min)
    cutoff = now - 1800
    recent_cwds = [h["cwd"] for h in history if h["ts"] >= cutoff]
    unique_recent = len(set(recent_cwds))
    switch_count = sum(
        1 for i in range(1, len(recent_cwds))
        if recent_cwds[i] != recent_cwds[i - 1]
    )

    warning = (
        f"🔄 **Context switch**: `{prev_name}` → `{curr_name}`. "
        "Сессия мульти-проектная. Задача task-level прежняя или начинаем новую?"
    )

    if switch_count >= CWD_SWITCH_WARN_THRESHOLD:
        warning += (
            f"\n\n⚠️ {switch_count} переключений за последние 30 мин "
            f"между {unique_recent} проектами. Рекомендуется `/session-save` "
            "чтобы не потерять контекст."
        )

    return warning


def main() -> int:
    try:
        json.load(sys.stdin)  # consume, we don't need the content
    except Exception:
        pass  # OK if missing

    cwd = Path(os.getcwd())
    sections: list[str] = []

    # Context switch detection (Gap #5)
    ctx_switch = context_switch_detect(cwd)
    if ctx_switch:
        sections.append(ctx_switch)

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

    # Memory staleness detection (Gap #7)
    staleness = memory_staleness_check(cwd, mem_dir)
    if staleness:
        sections.append(staleness)

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

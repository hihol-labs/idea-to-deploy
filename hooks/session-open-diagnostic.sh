#!/usr/bin/env python3
"""
UserPromptSubmit hook — Session-open diagnostic (Gap #6 from ROADMAP_v1.19.md).

Fires ONCE per session (on the first UserPromptSubmit). Reads project context
and injects a diagnostic summary so Claude starts with full awareness of:
  1. What the last session accomplished
  2. What the next planned steps are (from session memory or LAUNCH_PLAN.md)
  3. Active BACKLOG items (if any)

This prevents the "reactive mode" problem where Claude just responds to the
first message without consulting prior context.

After firing once, writes a sentinel file so subsequent prompts in the same
session skip this hook silently.

Session id: CLAUDE_SESSION_ID → parent pid → "default". Continuity is read
from the repository-local `.itd-memory/`; Claude-private memory is a legacy
fallback only.

Reads JSON on stdin: {"prompt": "..."}
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

# Max lines to include from each source to avoid blowing context
MAX_SESSION_LINES = 40
MAX_PLAN_LINES = 30
MAX_BACKLOG_LINES = 20


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def sentinel_path() -> str:
    return os.path.join(tempfile.gettempdir(), f"claude-session-diag-{session_id()}.done")


def already_fired() -> bool:
    """Check if diagnostic already ran this session."""
    return os.path.exists(sentinel_path())


def mark_fired() -> None:
    """Write sentinel so we don't fire again."""
    try:
        with open(sentinel_path(), "w") as f:
            f.write("1")
    except Exception:
        pass


def find_local_project_memory_dir(cwd: Path) -> Path | None:
    """Nearest canonical project-local continuity directory."""
    cwd_resolved = cwd.resolve()
    current = cwd_resolved
    while True:
        local = current / ".itd-memory"
        if local.is_dir():
            return local
        if current.parent == current:
            break
        current = current.parent
    return None


def find_legacy_project_memory_dir(cwd: Path) -> Path | None:
    """Optional Claude-private narrative-memory fallback for old projects."""
    cwd_resolved = cwd.resolve()

    home = Path.home()
    projects_root = home / ".claude" / "projects"
    if not projects_root.is_dir():
        return None

    munged = re.sub(r"[^A-Za-z0-9]", "-", str(cwd_resolved))
    legacy = "-" + str(cwd_resolved).lstrip("/").replace("/", "-")
    for name in (munged, legacy):
        candidate = projects_root / name / "memory"
        if candidate.is_dir():
            return candidate

    # Fallback: suffix match
    parts = cwd_resolved.parts
    for i in range(1, len(parts)):
        raw = "-".join(parts[i:])
        suffixes = {raw, re.sub(r"[^A-Za-z0-9]", "-", raw)}
        for entry in projects_root.iterdir():
            if not entry.is_dir():
                continue
            for suffix in suffixes:
                if entry.name.endswith("-" + suffix) or entry.name == "-" + suffix:
                    mem = entry / "memory"
                    if mem.is_dir():
                        return mem
    return None


def find_project_memory_dir(cwd: Path) -> Path | None:
    """Compatibility resolver: canonical local first, then legacy narrative."""
    return (find_local_project_memory_dir(cwd)
            or find_legacy_project_memory_dir(cwd))


def find_latest_session_file(mem_dir: Path) -> Path | None:
    """Find the most recent session_*.md file by modification time."""
    candidates = sorted(
        mem_dir.glob("session_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def read_truncated(path: Path, max_lines: int) -> str:
    """Read a file, truncating to max_lines."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines = content.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n(…truncated, {len(lines) - max_lines} more lines)"
    return content


def find_project_file(cwd: Path, name: str) -> Path | None:
    """Look for a file in cwd or common subdirectories."""
    for candidate in [cwd / name, cwd / "docs" / name]:
        if candidate.is_file():
            return candidate
    return None


def build_diagnostic(cwd: Path) -> str | None:
    """Build the diagnostic context string. Returns None if nothing useful found."""
    sections: list[str] = []

    local_mem = find_local_project_memory_dir(cwd)
    legacy_mem = find_legacy_project_memory_dir(
        local_mem.parent if local_mem is not None else cwd)
    mem_dir = local_mem or legacy_mem

    # --- 1. Last session summary ---
    if mem_dir:
        latest = find_latest_session_file(mem_dir)
        used_legacy_session = legacy_mem is not None and mem_dir == legacy_mem
        if latest is None and local_mem is not None and legacy_mem is not None:
            latest = find_latest_session_file(legacy_mem)
            used_legacy_session = latest is not None
        if latest:
            content = read_truncated(latest, MAX_SESSION_LINES)
            if content:
                sections.append(
                    f"**Последняя сессия{' (legacy host-memory fallback)' if used_legacy_session else ''}** "
                    f"(`{latest.name}`):\n\n{content}"
                )

        # --- Check NEXT SESSION PLAN in MEMORY.md ---
        index_dir = mem_dir
        if (not (index_dir / "MEMORY.md").is_file()
                and local_mem is not None and legacy_mem is not None):
            index_dir = legacy_mem
        memory_index = index_dir / "MEMORY.md"
        if memory_index.is_file():
            try:
                idx_text = memory_index.read_text(encoding="utf-8", errors="replace")
                # Look for lines with NEXT SESSION PLAN or next_session
                for line in idx_text.splitlines():
                    if re.search(r"(next.session|следующ)", line, re.IGNORECASE):
                        # Try to read the referenced file
                        match = re.search(r"\(([^)]+\.md)\)", line)
                        if match:
                            ref_file = index_dir / match.group(1)
                            if ref_file.is_file():
                                plan_content = read_truncated(ref_file, MAX_PLAN_LINES)
                                if plan_content:
                                    sections.append(
                                        f"**План следующей сессии** (`{ref_file.name}`):\n\n{plan_content}"
                                    )
                        break
            except Exception:
                pass

    # --- 2. LAUNCH_PLAN.md ---
    launch_plan = find_project_file(cwd, "LAUNCH_PLAN.md")
    if launch_plan:
        content = read_truncated(launch_plan, MAX_PLAN_LINES)
        if content:
            sections.append(
                f"**LAUNCH_PLAN.md** (текущий план проекта):\n\n{content}"
            )

    # --- 3. BACKLOG.md ---
    backlog = find_project_file(cwd, "BACKLOG.md")
    if backlog:
        content = read_truncated(backlog, MAX_BACKLOG_LINES)
        if content:
            sections.append(
                f"**BACKLOG.md** (активные задачи):\n\n{content}"
            )

    # --- 4. ROADMAP (current version) ---
    # Look for ROADMAP_v*.md files, pick latest
    roadmaps = sorted(cwd.glob("ROADMAP_v*.md"), reverse=True)
    if roadmaps:
        rm = roadmaps[0]
        content = read_truncated(rm, MAX_PLAN_LINES)
        if content:
            sections.append(
                f"**Текущий ROADMAP** (`{rm.name}`):\n\n{content}"
            )

    if not sections:
        return None

    header = (
        "[SESSION DIAGNOSTIC — старт сессии]\n\n"
        "Перед началом работы изучи контекст предыдущей сессии и текущие планы. "
        "Определи: какой следующий шаг по плану? Какой скилл запускаешь?\n\n"
        "---\n\n"
    )

    return header + "\n\n---\n\n".join(sections)


def main() -> int:
    try:
        json.load(sys.stdin)  # consume
    except Exception:
        pass

    # Only fire once per session
    if already_fired():
        return 0

    mark_fired()

    cwd = Path(os.getcwd())
    diagnostic = build_diagnostic(cwd)

    if not diagnostic:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": diagnostic,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

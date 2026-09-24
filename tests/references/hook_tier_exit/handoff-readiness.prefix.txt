#!/usr/bin/env python3
"""
Stop hook — Handoff-readiness detector (v1.40.0, Anthropic long-running-agents port).

The Anthropic research on effective harnesses for long-running agents requires
every session to END handoff-ready: clean checkpoint + fresh progress artifact,
so a fresh agent can pick the project up from repo contents alone. The methodology
already recovers context at session START (pre-flight-check, session-open-diagnostic,
crash-recovery) — this hook closes the other half: it detects, at turn end, that
the session is drifting toward a dirty death (uncommitted work + stale/absent
project-local session memory) and softly reminds the user to run /session-save
or /handoff.

Design (HARNESS_ENGINEERING_MAP.md §8.3): the detect is purely computational
(git state + file mtimes), but "is the user done for the day?" is semantic —
so this MUST stay a soft hint, never a deny. It emits a systemMessage only.

Fires on the Stop event (end of each assistant turn). Noise control:
  - hints only when BOTH signals hold: dirty git tree AND no fresh session_*.md
    in `.itd-memory/` (fresher than ITD_HANDOFF_FRESH_MIN, default 120 min);
  - rate-limited via a sentinel file: at most one hint per ITD_HANDOFF_RATE_MIN
    (default 45 min) per session;
  - disabled entirely with ITD_HANDOFF_READINESS=0;
  - never blocks, never emits a decision, fail-safe exit 0 on any error.

Reads JSON on stdin: {"session_id": "...", "stop_hook_active": bool, ...}
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FRESH_MIN_DEFAULT = 120   # session_*.md younger than this => handoff-ready enough
RATE_MIN_DEFAULT = 45     # min minutes between two hints in one session


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except Exception:
        return default


def session_id(payload: dict) -> str:
    sid = payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return str(sid)
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


def sentinel_path(sid: str, cwd: Path) -> Path:
    # cwd hash keeps two parallel sessions in different projects from sharing
    # one sentinel when both fall back to the same pid-based session id.
    cwd_tag = hashlib.md5(str(cwd).encode("utf-8", "replace")).hexdigest()[:8]
    return Path(tempfile.gettempdir()) / f"claude-handoff-ready-{sid}-{cwd_tag}"


def rate_limited(sid: str, cwd: Path, rate_min: int) -> bool:
    p = sentinel_path(sid, cwd)
    try:
        last = float(p.read_text().strip())
        return (time.time() - last) < rate_min * 60
    except Exception:
        return False


def mark_hinted(sid: str, cwd: Path) -> None:
    try:
        sentinel_path(sid, cwd).write_text(str(time.time()))
    except Exception:
        pass


def git_dirty_count(cwd: Path) -> int:
    """Number of dirty paths (staged/unstaged/untracked). -1 => not a git repo."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd), capture_output=True, text=True, timeout=4,
        )
        if out.returncode != 0:
            return -1
        return len([ln for ln in out.stdout.splitlines() if ln.strip()])
    except Exception:
        return -1


def find_project_memory_dir(cwd: Path) -> Path | None:
    """Find local canonical continuity, then an optional Claude legacy mirror."""
    cwd_resolved = cwd.resolve()
    current = cwd_resolved
    while True:
        local = current / ".itd-memory"
        if local.is_dir():
            return local
        if current.parent == current:
            break
        current = current.parent

    home = Path.home()
    projects_root = home / ".claude" / "projects"
    if not projects_root.is_dir():
        return None

    import re
    munged = re.sub(r"[^A-Za-z0-9]", "-", str(cwd_resolved))
    legacy = "-" + str(cwd_resolved).lstrip("/").replace("/", "-")
    for name in (munged, legacy):
        candidate = projects_root / name / "memory"
        if candidate.is_dir():
            return candidate

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


def find_local_project_memory_dir(cwd: Path) -> Path | None:
    """Nearest canonical store; private mirrors never satisfy readiness."""
    current = cwd.resolve()
    while True:
        local = current / ".itd-memory"
        if local.is_dir():
            return local
        if current.parent == current:
            return None
        current = current.parent


def latest_session_age_min(mem_dir: Path | None) -> float | None:
    """Minutes since the freshest session_*.md; None if no memory / no file."""
    if mem_dir is None:
        return None
    try:
        candidates = sorted(
            mem_dir.glob("session_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        return (time.time() - candidates[0].stat().st_mtime) / 60.0
    except Exception:
        return None


def main() -> int:
    if os.environ.get("ITD_HANDOFF_READINESS", "1") == "0":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    # Safety: if a Stop hook is already steering the turn, stay silent.
    if payload.get("stop_hook_active"):
        return 0

    sid = session_id(payload)
    cwd = Path(payload.get("cwd") or os.getcwd())
    rate_min = env_int("ITD_HANDOFF_RATE_MIN", RATE_MIN_DEFAULT)
    if rate_limited(sid, cwd, rate_min):
        return 0

    dirty = git_dirty_count(cwd)
    if dirty <= 0:
        # clean tree or not a git repo => nothing to hand off / not our scope
        return 0

    fresh_min = env_int("ITD_HANDOFF_FRESH_MIN", FRESH_MIN_DEFAULT)
    age = latest_session_age_min(find_local_project_memory_dir(cwd))
    if age is not None and age < fresh_min:
        # a recent /session-save (or /handoff sentinel session file) exists
        return 0

    if age is None:
        memory_note = "свежего session_*.md в памяти проекта нет"
    else:
        memory_note = f"последний session-save был ~{int(age // 60)}ч {int(age % 60)}м назад"

    mark_hinted(sid, cwd)
    msg = (
        f"[HANDOFF-READINESS] Состояние не handoff-ready: {dirty} несохранённых "
        f"путей в git, {memory_note}. Если заканчиваешь блок работы — сделай "
        f"/session-save (веха) или /handoff (пакет передачи) и оставь чистый "
        f"чекпоинт: сессия может умереть в любой момент (crash/компакция), "
        f"следующая должна подхватить проект из содержимого репо. "
        f"(soft hint, раз в {rate_min} мин; отключить: ITD_HANDOFF_READINESS=0)"
    )
    out = {
        "hookSpecificOutput": {"hookEventName": "Stop"},
        "systemMessage": msg,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

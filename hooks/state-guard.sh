#!/usr/bin/env python3
"""
PostToolUse hook на Write|Edit|MultiEdit|NotebookEdit — state-guard (v1.75.0).

ACID-audit fix #4 — две обязанности:

1. **Немедленная валидация state-леджеров.** Если правился
   `.itd-memory/STATE.json` или `.itd-memory/GOAL*.json` — сразу прогоняется
   validate_state_core (те же инварианты, что у CLI scripts/validate_state.py:
   fail-closed поля, WIP=1 сквозь оба леджера, реконсиляция с events.jsonl).
   До этого фикса невалидный STATE мог жить всю сессию и всплывать только на
   следующем boot'е — consistency сдвигается из «на старте сессии» в «после
   каждой мутации». PostToolUse не может отменить уже сделанную запись,
   поэтому нарушение возвращается модели красной пометкой (additionalContext,
   FAILED/WHY/FIX) — самокоррекция в тот же ход, не вето (§8.3: вето здесь
   невозможно физически, а не по мягкости).

2. **Heartbeat `.active-session.lock`.** Лок обновлялся только при
   /session-save — сессия без save 30+ минут выглядела мёртвой для
   parallel-session warning'а других сессий (инцидент NeuroExpert 2026-04-11:
   один долг пофиксен дважды параллельно). Теперь каждый Write/Edit (реальный
   признак живой работы) освежает лок. ЧУЖОЙ свежий лок не перетирается —
   иначе heartbeat маскировал бы именно ту параллельную сессию, о которой
   должен предупреждать pre-flight.

Чистая телеметрия + подсказка: НИКОГДА не блокирует, любая ошибка
проглатывается (exit 0). Отключение: ITD_STATE_GUARD=0.

Читает JSON на stdin (PostToolUse):
  {"session_id","cwd","tool_name":"Write|Edit|...","tool_input":{"file_path":...}}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LOCK_FRESH_SECONDS = 600      # тот же порог, что у pre-flight-check.sh
HEARTBEAT_MIN_INTERVAL = 60   # не переписывать свой лок чаще раза в минуту
GUARD_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def pass_through(context: str | None = None) -> int:
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse"}}
    if context:
        out["hookSpecificOutput"]["additionalContext"] = context
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


def find_project_memory_dir(cwd: Path) -> Path | None:
    """Локатор memory-dir проекта. Копия pre-flight-check.sh
    find_project_memory_dir (тот же lossy-suffix фолбэк) — хуки самодостаточны
    by design; при изменении раскладки ~/.claude/projects править ОБА места."""
    home = Path.home()
    projects_root = home / ".claude" / "projects"
    if not projects_root.is_dir():
        return None
    cwd_resolved = cwd.resolve()
    expected = "-" + str(cwd_resolved).lstrip("/").replace("/", "-")
    candidate = projects_root / expected / "memory"
    if candidate.is_dir():
        return candidate
    parts = cwd_resolved.parts
    for i in range(1, len(parts)):
        suffix = "-".join(parts[i:])
        for entry in projects_root.iterdir():
            if not entry.is_dir() or not entry.name.startswith("-"):
                continue
            if entry.name.endswith("-" + suffix) or entry.name == "-" + suffix:
                mem = entry / "memory"
                if mem.is_dir():
                    return mem
    return None


def _current_branch(cwd: Path) -> str:
    try:
        res = subprocess.run(["git", "branch", "--show-current"],
                             cwd=str(cwd), capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


def heartbeat_lock(cwd: Path, sid: str) -> None:
    """Освежить .active-session.lock, НЕ трогая чужой свежий лок."""
    try:
        mem_dir = find_project_memory_dir(cwd)
        if mem_dir is None:
            return
        lock = mem_dir / ".active-session.lock"
        now = time.time()
        data: dict = {}
        if lock.is_file():
            try:
                data = json.loads(lock.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                data = {}
            try:
                age = now - float(data.get("timestamp", 0))
            except (TypeError, ValueError):
                age = LOCK_FRESH_SECONDS + 1
            owner = str(data.get("session", "") or "")
            if age <= LOCK_FRESH_SECONDS and owner and owner != sid:
                return  # свежий лок ДРУГОЙ сессии — parallel-warning важнее heartbeat'а
            if age <= HEARTBEAT_MIN_INTERVAL and (not owner or owner == sid):
                return  # свой и совсем свежий — не жечь IO на каждый Edit
        payload = {
            "timestamp": now,
            "pid": os.getppid(),
            "session": sid,
            "branch": data.get("branch") or _current_branch(cwd),
            "project": str(cwd),
            "note": data.get("note", "heartbeat: state-guard (Write/Edit activity)"),
        }
        tmp = lock.with_name(lock.name + f".tmp-{os.getpid()}")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, lock)
    except Exception:
        pass


def is_state_ledger(file_path: str) -> bool:
    if not file_path:
        return False
    p = file_path.replace("\\", "/")
    if "/.itd-memory/" not in p and not p.startswith(".itd-memory/"):
        return False
    name = p.rsplit("/", 1)[-1]
    return name == "STATE.json" or (name.startswith("GOAL") and name.endswith(".json"))


def validate_ledger(file_path: str) -> str | None:
    try:
        from validate_state_core import validate_path
    except Exception:
        return None
    try:
        errors, warnings = validate_path(Path(file_path))
    except Exception:
        return None
    if not errors and not warnings:
        return None
    parts = []
    if errors:
        head = errors[0]
        rest = [f"  - {e}" for e in errors[1:3]]
        parts.append(
            "FAILED: state-ledger валидация после записи | WHY: " + head
            + (("\n" + "\n".join(rest)) if rest else "")
            + "\n| FIX: поправь файл сейчас же — невалидный леджер ломает resume "
              "следующей сессии (тот же контракт, что scripts/validate_state.py)."
        )
    for w in warnings[:2]:
        parts.append(f"WARNING: {w}")
    return "\n".join(parts)


def main() -> int:
    if os.environ.get("ITD_STATE_GUARD", "1") == "0":
        return pass_through()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return pass_through()
    payload = payload or {}
    tool = payload.get("tool_name") or ""
    if tool not in GUARD_TOOLS:
        return pass_through()

    cwd = Path(payload.get("cwd") or os.getcwd())
    sid = str(payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown")

    # 4b: heartbeat на каждом срабатывании (Write/Edit = живая работа).
    heartbeat_lock(cwd, sid)

    # 4a: немедленная валидация, только если правился state-леджер.
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    context = None
    if is_state_ledger(file_path):
        context = validate_ledger(file_path)
    return pass_through(context)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

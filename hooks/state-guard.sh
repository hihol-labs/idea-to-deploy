#!/usr/bin/env python3
"""
state-guard (v1.76.0) — страж state-леджеров `.itd-memory/`.

Регистрируется на ТРИ события (одно тело, ветвление по hook_event_name):

1. **PreToolUse Write|Edit|MultiEdit|NotebookEdit — гейт единственного писателя
   (v1.76.0, HARD).** Если правится леджер (`.itd-memory/STATE.json` /
   `GOAL*.json`), а `.active-session.lock` проекта СВЕЖИЙ и принадлежит ДРУГОЙ
   сессии (поле `session` заполнено и != наш session_id) — запись
   ОТКЛОНЯЕТСЯ (`permissionDecision: "deny"`, exit 2): две сессии на одном
   леджере = last-writer-wins, ровно инцидент NeuroExpert 2026-04-11.
   ≤2 deny на сессию (sentinel в tempdir), третья попытка проходит с warning —
   escape-hatch для ложных срабатываний, как у narration-final. Ownerless-локи
   (легаси /session-save без поля session) НЕ гейтятся — атрибуция невозможна,
   false-deny хуже. Отключение: ITD_STATE_GUARD=0.

2. **PostToolUse Write|Edit|MultiEdit|NotebookEdit (v1.75.0, soft).**
   (а) правка леджера валидируется НЕМЕДЛЕННО через validate_state_core (тот же
   контракт, что CLI scripts/validate_state.py) — нарушение возвращается
   красной пометкой FAILED/WHY/FIX (additionalContext);
   (б) heartbeat `.active-session.lock` — лок не протухает между
   /session-save; ЧУЖОЙ свежий лок не перетирается.

3. **PostToolUse Bash (v1.76.0, soft).** Мутация леджера в обход Write/Edit
   (редиректы `>`, `sed -i`, `tee`, `jq`, `mv/cp`, PowerShell Set-Content …)
   детектится по команде → леджеры проекта перевалидируются, нарушение —
   та же красная пометка. Закрывает Bash-bypass из ACID-аудита.

Любая внутренняя ошибка проглатывается (exit 0 / pass-through) — хук не имеет
права ронять сессию. Живой контракт: тесты tests/verify_state_hardening.py.

Читает JSON на stdin: {"hook_event_name","session_id","cwd","tool_name",
"tool_input":{"file_path"|"notebook_path"|"command"}}
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LOCK_FRESH_SECONDS = 600      # тот же порог, что у pre-flight-check.sh
HEARTBEAT_MIN_INTERVAL = 60   # не переписывать свой лок чаще раза в минуту
MAX_DENIES = 2                # PreToolUse-гейт: не больше 2 отказов на сессию
GUARD_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Bash-мутация леджера: путь на .itd-memory-леджер + пишущий токен.
LEDGER_PATH_RE = re.compile(r"\.itd-memory[/\\]+(STATE\.json|GOAL[\w.-]*\.json)")
BASH_MUTATION_RE = re.compile(
    r"(>>?|\btee\b|\bsed\s+(-[a-zA-Z]*\s+)*-i\b|\bmv\b|\bcp\b|\bjq\b|"
    r"\btruncate\b|\bdd\b|Set-Content|Out-File|Add-Content)")


def emit(event: str, context: str | None = None) -> int:
    out = {"hookSpecificOutput": {"hookEventName": event}}
    if context:
        out["hookSpecificOutput"]["additionalContext"] = context
    # ensure_ascii=True: на Windows-инсталле без -X utf8 пайп хука может быть
    # cp1251 — эмодзи в контексте рушили бы вывод, хук молча гас (exit 0).
    sys.stdout.write(json.dumps(out, ensure_ascii=True))
    return 0


def deny(reason: str) -> int:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=True))
    try:
        sys.stderr.write(reason)
    except Exception:
        pass  # cp1251-пайп не должен превращать deny в молчаливый exit
    return 2


def find_project_memory_dir(cwd: Path) -> Path | None:
    """Локатор memory-dir проекта. Копия pre-flight-check.sh
    find_project_memory_dir (та же логика) — хуки самодостаточны by design;
    при изменении раскладки ~/.claude/projects править ОБА места.

    v1.76.1: реальный munging Claude Code — КАЖДЫЙ не-alnum символ пути → '-'
    (Windows 'C:\\Users\\Дмитрий\\AI\\OneOfS_tmp' → 'C--Users---------AI-OneOfS-tmp';
    подчёркивания и не-ASCII тоже заменяются). Прежний кандидат (только '/'→'-')
    промахивался на таких путях, и heartbeat/гейт молча превращались в no-op —
    live-смоук v1.76.0 это и поймал.
    """
    home = Path.home()
    projects_root = home / ".claude" / "projects"
    if not projects_root.is_dir():
        return None
    cwd_resolved = cwd.resolve()
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


def _read_lock(mem_dir: Path) -> dict:
    lock = mem_dir / ".active-session.lock"
    if not lock.is_file():
        return {}
    try:
        data = json.loads(lock.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _lock_age(data: dict) -> float:
    try:
        return time.time() - float(data.get("timestamp", 0))
    except (TypeError, ValueError):
        return LOCK_FRESH_SECONDS + 1


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
        data = _read_lock(mem_dir)
        if data:
            age = _lock_age(data)
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


# ---------------------------------------------------------------------------
# PreToolUse — гейт единственного писателя леджера (v1.76.0)
# ---------------------------------------------------------------------------

def _deny_sentinel(sid: str, cwd: Path) -> Path:
    # ключ = (сессия, проект): бюджет отказов одного проекта не должен
    # утекать в другой проект той же сессии (ревью v1.76.0, finding 4)
    proj = re.sub(r"[^A-Za-z0-9]+", "-", str(cwd))[-60:]
    return Path(tempfile.gettempdir()) / f"claude-ledgerguard-{sid}-{proj}"


def _deny_count(sid: str, cwd: Path) -> int:
    try:
        return int(_deny_sentinel(sid, cwd).read_text(encoding="utf-8").strip() or 0)
    except Exception:
        return 0


def _bump_deny(sid: str, cwd: Path) -> None:
    try:
        _deny_sentinel(sid, cwd).write_text(str(_deny_count(sid, cwd) + 1),
                                            encoding="utf-8")
    except Exception:
        pass


def ledger_gate_decision(cwd: Path, sid: str, file_path: str) -> tuple[str, str]:
    """('allow'|'warn'|'deny', reason). Deny только при ЧУЖОМ свежем ВЛАДЕЕМОМ
    локе (session заполнен и != наш) и не более MAX_DENIES раз на сессию."""
    if not is_state_ledger(file_path):
        return "allow", ""
    mem_dir = find_project_memory_dir(cwd)
    if mem_dir is None:
        return "allow", ""
    data = _read_lock(mem_dir)
    if not data:
        return "allow", ""
    owner = str(data.get("session", "") or "")
    if not owner or owner == sid or _lock_age(data) > LOCK_FRESH_SECONDS:
        return "allow", ""
    branch = data.get("branch", "?")
    if _deny_count(sid, cwd) >= MAX_DENIES:
        return "warn", (
            "⚠️ LEDGER-GUARD (auto-allow после 2 отказов): параллельная сессия "
            f"(session {owner[:8]}…, branch `{branch}`) всё ещё активна, а ты "
            "пишешь в тот же state-леджер. Запись пропущена как осознанная — "
            "сверь потом события в events.jsonl (реконсиляция это поймает)."
        )
    _bump_deny(sid, cwd)
    return "deny", (
        "FAILED: запись state-леджера заблокирована | WHY: свежий "
        f".active-session.lock другой сессии (session {owner[:8]}…, branch "
        f"`{branch}`, возраст {int(_lock_age(data))}s) — две сессии на одном "
        "леджере = last-writer-wins и потерянные юниты (инцидент NeuroExpert "
        "2026-04-11) | FIX: дай параллельной сессии закончить/сделать "
        "/session-save, или осознанно повтори запись (после "
        f"{MAX_DENIES} отказов пройдёт с warning). Отключение: ITD_STATE_GUARD=0."
    )


# ---------------------------------------------------------------------------
# PostToolUse Bash — детект мутации леджера в обход Write/Edit (v1.76.0)
# ---------------------------------------------------------------------------

def bash_ledger_context(cwd: Path, command: str) -> str | None:
    if not command:
        return None
    if not LEDGER_PATH_RE.search(command) or not BASH_MUTATION_RE.search(command):
        return None
    mem = cwd / ".itd-memory"
    contexts = []
    try:
        candidates = [mem / "STATE.json"] + sorted(mem.glob("GOAL*.json"))
    except Exception:
        candidates = [mem / "STATE.json"]
    for ledger in candidates:
        if ledger.is_file():
            ctx = validate_ledger(str(ledger))
            if ctx:
                contexts.append(ctx)
    if not contexts:
        return None
    return ("Bash-мутация state-леджера детектирована — перевалидация:\n"
            + "\n".join(contexts))


def main() -> int:
    if os.environ.get("ITD_STATE_GUARD", "1") == "0":
        return 0  # тихий pass: событие неизвестно без чтения stdin
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    payload = payload or {}
    tool = payload.get("tool_name") or ""
    event = (payload.get("hook_event_name") or "").strip() or "PostToolUse"
    cwd = Path(payload.get("cwd") or os.getcwd())
    sid = str(payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown")
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")

    if event.lower() == "pretooluse":
        if tool not in GUARD_TOOLS:
            return emit("PreToolUse")
        action, reason = ledger_gate_decision(cwd, sid, file_path)
        if action == "deny":
            return deny(reason)
        return emit("PreToolUse", reason if action == "warn" else None)

    # --- PostToolUse ---
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        return emit("PostToolUse", bash_ledger_context(cwd, command))

    if tool not in GUARD_TOOLS:
        return emit("PostToolUse")

    heartbeat_lock(cwd, sid)
    context = None
    if is_state_ledger(file_path):
        context = validate_ledger(file_path)
    return emit("PostToolUse", context)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)

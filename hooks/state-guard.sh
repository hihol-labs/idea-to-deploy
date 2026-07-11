#!/usr/bin/env python3
"""
state-guard (v1.80.0) — страж state-леджеров `.itd-memory/`.

ШЕСТЬ регистраций (одно тело, ветвление по hook_event_name/tool; PowerShell —
отдельные matcher-блоки в sync-to-active/adopt-шаблоне):

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

3. **PostToolUse Bash|PowerShell (v1.76.0, soft; v1.78.1 + PowerShell-tool
   и интерпретаторные записи python -c/py -c/node -e).** Мутация леджера в обход Write/Edit
   (редиректы `>`, `sed -i`, `tee`, `jq`, `mv/cp`, PowerShell Set-Content …)
   детектится по команде → леджеры проекта перевалидируются, нарушение —
   та же красная пометка. Закрывает Bash-bypass из ACID-аудита.

4. **PreToolUse Bash|PowerShell (v1.78.0, HARD; v1.78.1 + PowerShell-tool).** Тот же single-writer гейт, что и в
   п.1, для Bash-канала: команда, где леджер — ЦЕЛЬ записи (target-anchored:
   редирект/`tee`/`sed -i`/`mv`/`cp`/`truncate`/`dd of=`/`Set-Content` прямо
   в `.itd-memory/STATE.json|GOAL*.json`), при чужом свежем owned-локе
   отклоняется. Общий deny-бюджет с п.1. Со-вхождение (например
   `git diff .itd-memory/STATE.json > out.txt`) НЕ гейтится — false-deny
   дороже, для таких случаев остаётся soft-ревалидация п.3.

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
SHELL_TOOLS = {"Bash", "PowerShell"}  # v1.78.1: PowerShell-tool = тот же канал мутаций

# Bash-мутация леджера: путь на .itd-memory-леджер + пишущий токен.
# Широкое СО-ВХОЖДЕНИЕ — только для SOFT-ревалидации после Bash (цена FP ~0:
# молчит, если леджер на диске валиден).
LEDGER_PATH_RE = re.compile(r"\.itd-memory[/\\]+(STATE\.json|GOAL[\w.-]*\.json)")
BASH_MUTATION_RE = re.compile(
    r"(>>?|\btee\b|\bsed\s+(-[a-zA-Z]*\s+)*-i\b|\bmv\b|\bcp\b|\bjq\b|"
    r"\btruncate\b|\bdd\b|Set-Content|Out-File|Add-Content|"
    # v1.78.1: интерпретаторные записи (python -c / py -c / node -e) — soft-
    # детект; co-occurrence с путём леджера уже требуется, цена FP ~0
    r"\bpython[\w.]*\s[^|;&\n]*-c\b|\bpy\s[^|;&\n]*-c\b|\bnode\s[^|;&\n]*-e\b|"
    # v1.81.0 (финальная пересдача, кандидат (а)): дыры soft-детекта с FP~0 —
    # perl -i, sponge, install, rsync, PowerShell Copy-Item/New-Item, запуск
    # скрипта (python x.py — не только -c), rm/del/Remove-Item (после удаления
    # леджера перевалидация репортит отсутствие)
    r"\bperl\s+[^|;&\n]*-i\b|\bsponge\b|\binstall\b|\brsync\b|"
    r"Copy-Item|New-Item|\brm\b|\bdel\b|Remove-Item|"
    r"\bpython[\w.]*\s+\S+\.py\b|\bpy\s+\S+\.py\b|\bnode\s+\S+\.js\b)")

# v1.80.0: git-перезапись рабочего дерева (checkout/restore/reset) может
# откатить леджер БЕЗ упоминания его пути в команде (`git checkout ветка`,
# `git reset --hard`) — поэтому триггер БЕЗУСЛОВНЫЙ, вне co-occurrence-гейта
# (important ревью v1.80.0: AND-условие делало эту ногу мёртвой для голого
# checkout). После отката леджер валиден по схеме, но ПРОТУХ относительно
# events.jsonl — ловит реконсиляция в перевалидации. Цена FP ~0: валидация
# гоняется только если леджеры проекта существуют, и молчит на валидных.
# v1.81.0: + stash/clean (перезаписывают/удаляют рабочее дерево так же неявно)
GIT_REWRITE_RE = re.compile(
    r"\bgit\b[^|;&\n]*\b(?:checkout|restore|reset|stash|clean)\b")

# v1.81.0 (critical ревью): удаление КАТАЛОГА .itd-memory не содержит токена
# STATE.json — co-occurrence-гейт его не видел, «vanished»-репорт был мёртв.
# Отдельный безусловный триггер: глагол удаления + упоминание .itd-memory.
# (?![\w-]) отсекает .itd-memory-backup и подобные соседние имена.
DELETION_VERB_RE = re.compile(r"\b(?:rm|del|rd|rmdir|Remove-Item)\b")
ITD_MEMORY_MENTION_RE = re.compile(r"\.itd-memory(?![\w-])")

# v1.78.0 — pre-write HARD-гейт для Bash-канала: леджер должен быть ЦЕЛЬЮ
# записи, а не просто упомянут (иначе `git diff .itd-memory/STATE.json >
# out.txt` ловил бы false-deny). Ленивая цена FP у deny выше, чем у soft —
# поэтому регэксп target-anchored: редирект/tee/Out-File прямо В леджер,
# sed -i / mv / cp / truncate / dd of= с леджером среди аргументов команды.
_L = r"\S*\.itd-memory[/\\]+(?:STATE\.json|GOAL[\w.-]*\.json)"
LEDGER_WRITE_TARGET_RE = re.compile(
    r"(?:"
    r">>?\s*['\"]?" + _L +                                   # > ledger / >> ledger
    r"|\btee\b(?:\s+-\w+)*\s+['\"]?" + _L +                  # tee [-a] ledger
    r"|\bsed\b[^|;&\n]*\s-i[^|;&\n]*" + _L +                 # sed -i ... ledger
    # mv/cp: леджер только в позиции НАЗНАЧЕНИЯ (конец клаузы) — иначе
    # `cp .itd-memory/STATE.json backup.json` (леджер-ИСТОЧНИК, чтение)
    # ловил false-deny (ревью v1.78.0, important). Леджер-источник у mv
    # покрывает soft-ревалидация PostToolUse-ноги.
    r"|\b(?:mv|cp)\b[^|;&\n]*\s['\"]?" + _L + r"['\"]?\s*(?:[|;&\n]|$)"
    r"|\btruncate\b[^|;&\n]*" + _L +                         # truncate -s0 ledger
    r"|\bdd\b[^|;&\n]*\bof=['\"]?" + _L +                    # dd of=ledger
    r"|(?:Set-Content|Out-File|Add-Content)[^|;&\n]*" + _L + # PowerShell в леджер
    # v1.80.0: git checkout/restore с ЯВНЫМ путём леджера = намеренная
    # перезапись файла старой версией → hard-гейт при чужом свежем локе.
    # git reset --hard / checkout <ветка> БЕЗ пути леджера НЕ гейтятся
    # (обычное переключение веток — false-deny дороже); их протухание ловит
    # soft-ревалидация + реконсиляция с events.jsonl.
    r"|\bgit\b[^|;&\n]*\b(?:checkout|restore)\b[^|;&\n]*\s['\"]?" + _L +
    # v1.81.0 (топ-пробел финальной пересдачи): УДАЛЕНИЕ леджера/каталога —
    # та же deny-достойная операция под чужим локом. Без end-anchor'а
    # (important ревью: анкер резал flags-after-path `Remove-Item .itd-memory
    # -Recurse` и хвостовые редиректы `2>/dev/null`; у удаления нет
    # src/dst-неоднозначности mv/cp, анкер не нужен). (?![\w-]) отсекает
    # соседние имена вида .itd-memory-backup. + rd/rmdir (cmd.exe-формы).
    r"|\b(?:rm|del|rd|rmdir|Remove-Item)\b[^|;&\n]*\s['\"]?\S*\.itd-memory(?![\w-])"
    r")")


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


def find_project_memory_dir(cwd: Path, deep: bool = True) -> Path | None:
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
    if not deep:
        # v1.81.0 (important ревью): heartbeat на shell-канале зовётся на
        # КАЖДЫЙ Bash/PowerShell — suffix-скан ~/.claude/projects там слишком
        # дорог и best-effort не нужен (прямые кандидаты покрывают onboarded)
        return None
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


def heartbeat_lock(cwd: Path, sid: str, deep: bool = True) -> None:
    """Освежить .active-session.lock, НЕ трогая чужой свежий лок."""
    try:
        mem_dir = find_project_memory_dir(cwd, deep=deep)
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


# --- v1.84.0 (retro 2026-07-11 P8): коллизии файлов памяти сессий ------------
# Live-инцидент: mv поверх существующего session_*.md параллельной сессии затёр
# её хронику (восстанавливали из JSONL-транскрипта). Прямые записи в memory-дир
# обходят lockfile-дисциплину /session-save. Soft-guard (warn, не deny —
# ownership файла памяти неатрибутируем): перезапись СУЩЕСТВУЮЩЕГО и СВЕЖЕГО
# session-файла подсвечивается один раз per (session, file).
SESSION_MEM_FILE_RE = re.compile(
    r"[\\/]memory[\\/]session_\d{4}-\d{2}-\d{2}[^\\/]*\.md$", re.I)
SESSION_MEM_TOKEN_RE = re.compile(
    r"((?:[A-Za-z]:)?[^\s'\"|;&<>]*[\\/]memory[\\/]"
    r"session_\d{4}-\d{2}-\d{2}[^\s'\"|;&<>]*\.md)", re.I)
BASH_MEM_WRITE_VERB_RE = re.compile(
    r"\b(mv|cp|tee|dd)\b|>{1,2}|Set-Content|Copy-Item|Move-Item", re.I)
MEM_FRESH_SECONDS = 6 * 3600


def memory_collision_context(sid: str, file_path: str) -> str | None:
    m = SESSION_MEM_FILE_RE.search(file_path or "")
    if not m:
        return None
    p = Path(file_path)
    try:
        if not p.is_file():
            return None
        age = time.time() - p.stat().st_mtime
    except OSError:
        return None
    if age > MEM_FRESH_SECONDS:
        return None
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in p.name)[:60]
    sentinel = Path(tempfile.gettempdir()) / f"claude-memcol-{sid[:40]}-{safe}.state"
    if sentinel.exists():
        return None
    try:
        sentinel.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass
    return (
        f"ПРЕДУПРЕЖДЕНИЕ О КОЛЛИЗИИ ПАМЯТИ: '{p.name}' уже существует и свежий "
        f"(<6 ч) — его могла записать ПАРАЛЛЕЛЬНАЯ сессия; перезапись затрёт "
        f"чужую хронику (live-инцидент 2026-07-11: mv затёр session-файл "
        f"соседней сессии, восстанавливали из JSONL-транскрипта). Если файл не "
        f"твой — возьми следующий свободный суффикс (_N+1) или дозаписывай "
        f"Edit'ом, а не перезаписывай."
    )


def bash_memory_collision_context(sid: str, command: str) -> str | None:
    if not command or not BASH_MEM_WRITE_VERB_RE.search(command):
        return None
    tok = SESSION_MEM_TOKEN_RE.search(command)
    if not tok:
        return None
    return memory_collision_context(sid, tok.group(1))


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
    co_occurrence = bool(LEDGER_PATH_RE.search(command)
                         and BASH_MUTATION_RE.search(command))
    # git-перезапись — безусловно (леджер откатывается и без упоминания
    # его пути в команде; см. GIT_REWRITE_RE, important ревью v1.80.0);
    # v1.81.0 (critical ревью): удаление каталога .itd-memory — тоже
    # безусловно (токена STATE.json в команде нет, co-occurrence слеп)
    deletionish = bool(DELETION_VERB_RE.search(command)
                       and ITD_MEMORY_MENTION_RE.search(command))
    if not co_occurrence and not deletionish \
            and not GIT_REWRITE_RE.search(command):
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
        elif (ledger.name == "STATE.json" and mem.is_dir()
              and re.search(r"\brm\b|\bdel\b|\brd\b|\brmdir\b|Remove-Item|"
                            r"\bmv\b|\bgit\b", command)):
            # v1.81.0: леджер ИСЧЕЗ после команды класса удаления/переноса —
            # раньше отсутствующий файл молча пропускался. Guard по классу
            # команды: проект без STATE.json не должен получать FAILED на
            # каждый git stash
            contexts.append(
                "FAILED: state-леджер отсутствует после мутационной команды "
                "| WHY: .itd-memory/ существует, а STATE.json в нём нет — "
                "команда могла удалить/переместить леджер | FIX: восстанови "
                "из git (git checkout -- .itd-memory/STATE.json) или из "
                "события session-save, resume следующей сессии сломан.")
    if not contexts and deletionish and not mem.is_dir():
        # v1.81.0: снесён САМ каталог .itd-memory (rm -rf .itd-memory) —
        # ветка выше требует mem.is_dir() и здесь молчала бы
        contexts.append(
            "FAILED: каталог .itd-memory исчез после команды удаления "
            "| WHY: команда явно удаляла .itd-memory, каталога больше нет — "
            "потеряны STATE/GOAL/events | FIX: восстанови из git или из "
            "памяти сессии (~/.claude/projects/<проект>/memory), resume "
            "следующей сессии сломан.")
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
        if tool in SHELL_TOOLS:
            # v1.78.0: Bash-канал гейтится PRE-write — тем же решением
            # (чужой свежий owned-лок, общий deny-бюджет), но только когда
            # леджер — ЦЕЛЬ записи (target-anchored regex, не со-вхождение).
            command = str(tool_input.get("command") or "")
            m = LEDGER_WRITE_TARGET_RE.search(command)
            if not m:
                # v1.84.0 P8: мутация файла памяти сессии (mv/cp/redirect в
                # memory/session_*.md) — soft-предупреждение о коллизии
                return emit("PreToolUse", bash_memory_collision_context(sid, command))
            lm = LEDGER_PATH_RE.search(m.group(0))
            pseudo = ".itd-memory/" + (lm.group(1) if lm else "STATE.json")
            action, reason = ledger_gate_decision(cwd, sid, pseudo)
            if action == "deny":
                return deny(reason)
            return emit("PreToolUse", reason if action == "warn" else None)
        if tool not in GUARD_TOOLS:
            return emit("PreToolUse")
        action, reason = ledger_gate_decision(cwd, sid, file_path)
        if action == "deny":
            return deny(reason)
        ctx = reason if action == "warn" else None
        if tool == "Write":
            # v1.84.0 P8: Write поверх свежего чужого session_*.md (Edit не
            # гейтится — он требует предварительного Read того же содержимого)
            mem_ctx = memory_collision_context(sid, file_path)
            if mem_ctx:
                ctx = (ctx + "\n" + mem_ctx) if ctx else mem_ctx
        return emit("PreToolUse", ctx)

    # --- PostToolUse ---
    if tool in SHELL_TOOLS:
        # v1.81.0 (кандидат (б)): heartbeat и на shell-каналах — чисто
        # Bash/PowerShell-сессия раньше протухала свой лок за 10 мин, и
        # вторая сессия легитимно забирала single-writer посреди работы.
        # Внутренний rate-limit (HEARTBEAT_MIN_INTERVAL) держит IO ~нулевым;
        # deep=False — без suffix-скана ~/.claude/projects (цена на каждый Bash).
        heartbeat_lock(cwd, sid, deep=False)
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

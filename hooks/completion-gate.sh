#!/usr/bin/env python3
"""
PreToolUse hook на Bash — коммит-гейт «Врата завершения» (v1.51.0, пункты 1 и 2).

ЭКСТЕРНАЛИЗАЦИЯ СУЖДЕНИЯ О ЗАВЕРШЕНИИ (пункт 1). Перед каждым `git commit`,
затрагивающим исходный код, гейт выносит суждение НЕ из уверенности агента, а из
объективного леджера runtime-сигналов (.claude/completion/signals.jsonl, который
пишет completion-signals). Трёхслойный вердикт (пункт 2, L1→L2→L3 с блокировкой
перехода) считает completion_lib.compute_verdict. Итог:

  • слой в FAIL / тесты есть, но не прогнаны  -> ВЕТО: deny + exit 2 (коммит стоп)
  • нет ни одного runtime-сигнала за сессию    -> ДЕГРАДАЦИЯ: advisory, коммит идёт
  • сигналы есть, слои не красные               -> пропуск (краткое подтверждение)

BEST-EFFORT INVARIANT. Контракт — это JSON-леджер в репо + текст в CLAUDE.md;
хук лишь ПРИМЕНЯЕТ его как транспорт. Когда данных для суждения нет, гейт НЕ
зеленит и НЕ ложно-блокирует — он деградирует в мягкое напоминание. Так вето
реально, но не ломает тривиальные/безтестовые коммиты.

Область (против шума): срабатывает ТОЛЬКО когда в staged-диффе есть файлы
исходного кода. Чистые docs/config/миграции без кода гейт не трогает.

Осознанный обход: 'COMPLETION_BYPASS: <причина>' (или 'SKILL_BYPASS: <причина>')
в поле description Bash-вызова коммита. Отключение целиком: ITD_COMPLETION_GATE=0.

Читает JSON на stdin:
  {"session_id","cwd","tool_name":"Bash","tool_input":{"command","description"}}
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GIT_COMMIT_RE = re.compile(r"(^|\s|;|&&|\|\|)git\s+commit(\s|$)")
SOURCE_EXT_RE = re.compile(
    r"\.(py|js|jsx|ts|tsx|go|rb|java|rs|php|c|cc|cpp|cs|kt|kts|swift|scala|ex|exs|"
    r"vue|svelte|sql)$",
    re.I,
)
BYPASS_RE = re.compile(r"(COMPLETION_BYPASS|SKILL_BYPASS)\s*:", re.I)


def allow(context: str | None = None) -> int:
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if context:
        out["systemMessage"] = context
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


def deny(reason: str) -> int:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stderr.write(reason)
    return 2


def staged_source(cwd: Path) -> list:
    """Пути файлов исходного кода в staged-диффе (git diff --cached), с cwd."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(cwd), capture_output=True, text=True, timeout=5,
        )
        if res.returncode != 0:
            return []
        return [ln.strip() for ln in res.stdout.splitlines()
                if ln.strip() and SOURCE_EXT_RE.search(ln.strip())]
    except Exception:
        return []


def main() -> int:
    if os.environ.get("ITD_COMPLETION_GATE", "1") == "0":
        return allow()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return allow()
    if (payload or {}).get("tool_name") != "Bash":
        return allow()

    tool_input = payload.get("tool_input") or {}
    cmd = tool_input.get("command") or ""
    if not GIT_COMMIT_RE.search(cmd):
        return allow()
    # Осознанный обход — только через видимое человеку поле description.
    if BYPASS_RE.search(tool_input.get("description") or ""):
        return allow()

    try:
        import completion_lib as cl
    except Exception:
        return allow()  # библиотека недоступна -> деградация в «не мешать»

    try:
        cwd = Path(payload.get("cwd") or os.getcwd())
        session_id = str(payload.get("session_id") or "")

        # Область: только коммиты, где есть исходный код.
        if not staged_source(cwd):
            return allow()

        signals = cl.read_signals(cwd, session_id)
        verdict = cl.compute_verdict(cwd, signals)
        cl.write_verdict(cwd, verdict)

        if verdict.get("blocked"):
            reason = (
                "[COMPLETION-GATE] Коммит заблокирован: завершение не подтверждено "
                "runtime-сигналами.\n\n" + verdict.get("reason", "") + "\n\n"
                "Слои завершения (дёшево→дорого): L1 статика → L2 тесты → L3 e2e/smoke. "
                "Переход к следующему слою — только после зелёного предыдущего.\n"
                "Суждение вынес независимый гейт из леджера .claude/completion/, а не "
                "оценка агента: «код написан» ≠ «работает».\n\n"
                "Действия:\n"
                "  1. Устрани причину, прогони проверку заново (она попадёт в леджер).\n"
                "  2. Осознанный обход: добавь 'COMPLETION_BYPASS: <причина>' в поле "
                "description Bash-вызова коммита.\n"
                "  (Отключить гейт целиком: ITD_COMPLETION_GATE=0.)"
            )
            return deny(reason)

        if verdict.get("degraded"):
            msg = (
                "[COMPLETION-GATE] Коммит пропущен, но завершение НЕ подтверждено "
                "объективно: за сессию нет ни одного runtime-сигнала (сборка/тесты/"
                "smoke). Если это не тривиальное изменение — прогони проверки перед "
                "тем как считать сделанным. (best-effort деградация; вето появится, "
                "как только будут сигналы провала.)"
            )
            return allow(msg)

        # Зелёный путь.
        L = verdict.get("layers", {})
        summ = " · ".join(f"L{k}:{L[k]['status']}" for k in ("1", "2", "3") if k in L)
        return allow(f"[COMPLETION-GATE] Слои подтверждены сигналами ({summ}). Коммит разрешён.")
    except Exception:
        return allow()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

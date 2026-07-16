#!/usr/bin/env python3
"""
PostToolUse hook на Bash|PowerShell — сборщик runtime-сигналов (v1.51.0,
пункты 4 и 3; v1.88.0 + PowerShell-tool: на Windows-машинах тесты/сборки
гоняются и через PowerShell-tool — без него слой был слеп на целый канал).

Каждый вызов Bash/PowerShell классифицируется в один runtime-сигнал и дописывается в
вендор-нейтральный леджер .claude/completion/signals.jsonl текущего проекта:

  layer 1  static      — сборка / типы / линт   (синтаксис и статический анализ)
  layer 2  test_run    — прогон тестов            (доказательство поведения)
  layer 3  app_start   — запуск/health/e2e        (системное подтверждение)
  layer 0  side_effect — миграции/записи в БД
  layer 0  cleanup     — удаление временных ресурсов

Это тот самый «сбор runtime-сигналов как входных данных для суждения о
завершении» — леджер потом читает completion-gate (вето) и completion-stop
(напоминание). Хук ничего не решает сам, только фиксирует факты.

Пункт 3 (красные пометки в момент сбоя): если только что упал тест или сборка,
хук ВОЗВРАЩАЕТ модели немедленную «красную пометку учителя» через
additionalContext — не просто «упало», а WHY + конкретный FIX. Это даёт
самокоррекцию без ожидания коммит-гейта.

Чистая телеметрия + подсказка: НИКОГДА не блокирует (PostToolUse и не может),
любая ошибка проглатывается (exit 0). Отключение: ITD_COMPLETION_SIGNALS=0.

Читает JSON на stdin:
  {"session_id","cwd","tool_name":"Bash"|"PowerShell","tool_input":{"command":...},
   "tool_response": {...} | "..."}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def pass_through(context: str | None = None) -> int:
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse"}}
    if context:
        out["hookSpecificOutput"]["additionalContext"] = context
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


def project_root(cwd: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(cwd),
            capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except Exception:
        pass
    return cwd.resolve()


def main() -> int:
    if os.environ.get("ITD_COMPLETION_SIGNALS", "1") == "0":
        return pass_through()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return pass_through()

    # v1.88.0: PowerShell — тот же канал runtime-доказательств, что и Bash
    # (симметрия со state-guard SHELL_TOOLS, v1.78.1).
    if (payload or {}).get("tool_name") not in ("Bash", "PowerShell"):
        return pass_through()

    try:
        import completion_lib as cl
    except Exception:
        return pass_through()

    try:
        tool_input = payload.get("tool_input") or {}
        command = tool_input.get("command") or ""
        cwd = project_root(Path(payload.get("cwd") or os.getcwd()))
        session_id = str(payload.get("session_id") or "unknown")
        response = payload.get("tool_response")
        if response is None:
            response = payload.get("tool_result")

        sig = cl.classify_bash(command, response, cwd=cwd)
        if not sig:
            return pass_through()

        sig["producer"] = "itd-completion-signals"
        cl.append_signal(cwd, session_id, sig)

        # Красная пометка ровно в момент сбоя проверяемого слоя (1 или 2).
        if sig.get("outcome") == "fail" and sig.get("layer") in (1, 2):
            ev = sig.get("evidence", "")
            what = "Тесты не прошли" if sig["layer"] == 2 else "Статика/сборка не прошла"
            mark = cl.red_mark(what, ev or "проверка вернула ошибку", cl.fix_for(ev))
            ctx = (
                "[COMPLETION-SIGNALS] " + mark + "\n"
                "Это runtime-сигнал провала слоя — устрани корневую причину и "
                "перезапусти проверку. Слой завершения не будет засчитан, пока не "
                "станет зелёным (см. коммит-гейт «Врата завершения»)."
            )
            return pass_through(ctx)
    except Exception:
        return pass_through()

    return pass_through()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

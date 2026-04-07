#!/usr/bin/env python3
"""
UserPromptSubmit hook — analyzes user prompt for triggers and reminds Claude
to check whether a skill from the Idea-to-Deploy methodology fits.

Reads JSON on stdin: {"prompt": "...", ...}
Outputs JSON on stdout with hookSpecificOutput.additionalContext (injected
back into the model context for the current turn).

Silent (exit 0, no output) if no triggers match — keeps normal turns clean.
"""
import json
import sys


# Each tuple: (regex pattern, hint text). All patterns are matched
# case-insensitively against the lowercased prompt.
TRIGGERS = [
    (
        r"(новый\s+проект|создай\s+проект|хочу\s+проект|стартуем\s+проект|"
        r"начнём\s+проект|приложен|с\s+нуля|новый\s+сайт|новое\s+приложение)",
        "🔔 Триггер 'проект/приложение' → используй скилл /project (роутер: "
        "/kickstart полный цикл, /blueprint только планирование, /guide промпты "
        "по готовой документации). Вызови через инструмент Skill ПЕРВЫМ.",
    ),
    (
        r"(\bбаг\b|ошибк|не\s+работает|почини|сломал|крашит|падает|"
        r"\bкраш\b|exception|stack\s*trace|стектрейс|стек\s*трейс)",
        "🔔 Триггер 'баг/ошибка' → используй скилл /debug "
        "(системная отладка через стек/логи/git). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(напиши\s+тест|покрой\s+тест|покрой\s+unit|добавь\s+тест|"
        r"генери\s+тест|unit\s*test|integration\s*test)",
        "🔔 Триггер 'тесты' → используй скилл /test или субагента test-generator.",
    ),
    (
        r"(тормозит|медлен|оптимиз|производительност|\bperf\b|bottleneck|"
        r"узкое\s+место)",
        "🔔 Триггер 'производительность' → используй /perf или perf-analyzer.",
    ),
    (
        r"(отрефактор|рефактор|упрост\w*\s+код|refactor|переписать|"
        r"улучш\w+\s+код)",
        "🔔 Триггер 'рефакторинг' → используй скилл /refactor.",
    ),
    (
        r"(объясни\s+(код|как|что)|как\s+работает|что\s+делает|разбер\w+\s+как)",
        "🔔 Триггер 'объясни' → используй /explain (диаграммы + пошаговый разбор).",
    ),
    (
        r"(напиши\s+документ|создай\s+readme|задокумент|api\s+docs?|"
        r"инлайн\s+комментар|сгенери\s+doc)",
        "🔔 Триггер 'документация' → используй /doc или субагента doc-writer.",
    ),
    (
        r"(проверь\s+(код|документ|архитект)|валидац|\breview\b|ревью|"
        r"чек\s+архитектур)",
        "🔔 Триггер 'review' → используй /review или субагента code-reviewer.",
    ),
    (
        r"(спланируй|архитект|blueprint|подготовь\s+документац|спроектируй)",
        "🔔 Триггер 'планирование/архитектура' → используй /blueprint или architect.",
    ),
    (
        r"(сгенери\s+гайд|сгенерируй\s+промпт|claude\s+code\s+guide|"
        r"пошаговые\s+промпты)",
        "🔔 Триггер 'guide' → используй /guide (генерирует CLAUDE_CODE_GUIDE.md).",
    ),
    (
        r"(\bauth\b|аутентифик|авториз|платеж|оплат\w+\s+(сист|инт|api)|"
        r"\bjwt\b|\bcsrf\b|\bxss\b|sql\s*injection)",
        "🔔 Триггер 'security' → подключи плагин security-guidance перед изменениями.",
    ),
    (
        r"(\bui\b|интерфейс|frontend|дизайн\s+компонент|верстк|\bux\b)",
        "🔔 Триггер 'UI/frontend' → подключи плагин frontend-design.",
    ),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    prompt = (payload or {}).get("prompt") or ""
    if not prompt:
        return 0

    import re

    lp = prompt.lower()
    hints = []
    seen = set()
    for pattern, hint in TRIGGERS:
        if re.search(pattern, lp) and hint not in seen:
            hints.append(hint)
            seen.add(hint)

    if not hints:
        return 0

    context = (
        "[SKILL HINT — Idea-to-Deploy methodology]\n"
        + "\n".join(hints)
        + "\n\nВАЖНО: проверь, подходит ли хоть один скилл. Если да — вызови "
        "его через инструмент Skill ДО Read/Edit/Bash/Write. Если не подходит "
        "— продолжай как обычно. См. ~/projects/.claude/CLAUDE.md раздел "
        "«Автоматическое использование скиллов»."
    )

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

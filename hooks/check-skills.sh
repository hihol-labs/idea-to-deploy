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
        r"начнём\s+проект|запили\s+проект|сделай\s+проект\s+целиком|"
        r"от\s+идеи\s+до\s+деплоя|полный\s+цикл|"
        r"приложен|с\s+нуля|новый\s+сайт|новое\s+приложение|"
        r"сделай\s+сайт|сделай\s+сервис|новый\s+mvp|хочу\s+запустить|"
        r"start\s+a?\s*project|build\s+(it\s+|a\s+)?(from\s+scratch|project)|"
        r"end-to-end|kickstart|new\s+(app|service))",
        "🔔 Триггер 'проект/приложение' → используй скилл /project (роутер: "
        "/kickstart полный цикл, /blueprint только планирование, /guide промпты "
        "по готовой документации). Вызови через инструмент Skill ПЕРВЫМ.",
    ),
    (
        r"(\bбаг\b|ошибк|не\s+работает|почини|сломал|крашит|падает|"
        r"\bкраш\b|exception|stack\s*trace|стектрейс|стек\s*трейс|"
        r"\btraceback\b|\bpanic\b|странное\s+поведени|"
        r"log\s+fragment|любая\s+вставка\s+error|"
        r"debug\s+(this|that|it|error|bug|issue|problem)|"
        r"fix\s+(this\s+)?(error|bug)|\btroubleshoot)",
        "🔔 Триггер 'баг/ошибка' → используй скилл /bugfix "
        "(системная отладка через стек/логи/git). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(напиши\s+тест|покрой\s+тест|покрой\s+unit|добавь\s+тест|добавь\s+покрыт|"
        r"нет\s+тестов|юнит-?тест|интеграционн\w+\s+тест|регрессионн\w+\s+тест|"
        r"генери\s+тест|unit\s*test|integration\s*test|\bcoverage\b|"
        r"\bpytest\b|\bvitest\b|\bjest\b|go\s+test|\brspec\b|"
        r"add\s+tests?|write\s+tests?|test\s+this|generate\s+tests?)",
        "🔔 Триггер 'тесты' → используй скилл /test или субагента test-generator.",
    ),
    (
        r"(тормозит|медлен|оптимиз|производительност|\bperf\b|bottleneck|"
        r"узкое\s+место|лагает|n\+1|утечк\w+\s+памят|memory\s+leak|"
        r"высокая\s+нагрузк|\blatency\b|\bthroughput\b|slow\s+page\s+load|"
        r"\boptimize\b|make\s+it\s+faster|"
        r"optimize\s+(performance|this|speed)|slow\s+(down|query|endpoint))",
        "🔔 Триггер 'производительность' → используй /perf или perf-analyzer.",
    ),
    (
        r"(отрефактор|рефактор|упрост\w*\s+код|refactor|переписать|перепиши\s+понятнее|"
        r"улучш\w+\s+(код|читаемост)|вынеси\s+в\s+функци|убери\s+дублирован|"
        r"длинн\w+\s+функци|глубок\w+\s+вложенност|слишком\s+сложн\w+\s+код|"
        r"code\s+smell|clean\s+up|poor\s+naming|magic\s+number|god\s+class)",
        "🔔 Триггер 'рефакторинг' → используй скилл /refactor.",
    ),
    (
        r"(объясни\s+(код|как|что)|как\s+(это\s+)?работает|как\s+устроен|что\s+делает|"
        r"что\s+здесь\s+происходит|разбер\w+\s+(как|код|этот|файл|модуль)|"
        r"расскажи\s+про|explain\s+(this|that|how|what|code)|"
        r"how\s+does\s+this\s+work|walk\s+me\s+through|\bwalkthrough\b|"
        r"what\s+does\s+(this\s+|the\s+)?(\w+\s+)?(do|mean|return)|"
        r"can\s+you\s+explain|"
        r"tell\s+me\s+(about|how)\s+(this|the|that)\s+"
        r"(code|function|module|class|file|method|component|handler|endpoint))",
        "🔔 Триггер 'объясни' → используй /explain (диаграммы + пошаговый разбор).",
    ),
    (
        r"(напиши\s+документ|создай\s+readme|обнови\s+readme|опиши\s+api|"
        r"задокумент|api\s+docs?|добавь\s+комментар|(инлайн|inline)\s+комментар|"
        r"\bjsdoc\b|\bdocstrings?\b|\bchangelog(\.md)?\b|"
        r"сгенери(руй)?\s+(документ|doc|readme)|"
        r"generate\s+(readme|docs?|documentation)|write\s+docs?|add\s+docstrings?)",
        "🔔 Триггер 'документация' → используй /doc или субагента doc-writer.",
    ),
    (
        r"(проверь\s+(код|документ|архитект|pr\b)|валидац|\breview\b|ревью|"
        r"чек\s+архитектур|найди\s+косяк|найди\s+баги\s+в\s+код|"
        r"оцени\s+качество|check\s+quality|\bvalidate\b|\baudit\b)",
        "🔔 Триггер 'review' → используй /review или субагента code-reviewer.",
    ),
    (
        r"(спланируй|архитект|blueprint|подготовь\s+документац|спроектируй|"
        r"создай\s+документацию\s+для\s+проекта|техническое\s+задание|"
        r"\bprd\b|design\s+the\s+system|system\s+design)",
        "🔔 Триггер 'планирование/архитектура' → используй /blueprint или architect.",
    ),
    (
        r"(сгенери(руй)?\s+(гайд|guide)|создай\s+гайд|сделай\s+cookbook|"
        r"сгенерируй\s+промпт|промпты\s+для\s+claude|claude\s+code\s+guide|"
        r"пошаговая?\s+инструкция\s+для\s+claude|пошаговые\s+промпты|"
        r"generate\s+(a\s+)?guide|step-by-step\s+prompts?|guide\s+for\s+project|"
        r"\bcookbook\b|prompt\s+sequence)",
        "🔔 Триггер 'guide' → используй /guide (генерирует CLAUDE_CODE_GUIDE.md).",
    ),
    (
        r"(проверь\s+безопасност|security\s*(audit|review|headers)|найди\s+уязвимост|"
        r"проверь\s+(auth|секрет|токен|pr\s+на\s+безопасност)|"
        r"secrets?\s+check|exposed\s+credentials|утечк\w+\s+ключ|"
        r"cors\s+check|csp\s+check|"
        r"\bowasp\b|vulnerability\s+scan\b(?!\s+dependencies)|"
        r"перед\s+продакшен\w*\s+проверить)",
        "🔔 Триггер 'security audit' → используй /security-audit (read-only OWASP-style проверка). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(накати\s+миграц|применить\s+миграц|обнови\s+схему\s+бд|schema\s+change|"
        r"\bmigrate\b|apply\s+migration|run\s+migration|rollback\s+migration|"
        r"alter\s+table|add\s+column|drop\s+table|create\s+index|"
        r"alembic\s+upgrade|prisma\s+migrate|knex\s+migrate|dbmate\s+up|"
        r"перед\s+(any\s+)?ddl|нужно\s+изменить\s+схему)",
        "🔔 Триггер 'миграция БД' → используй /migrate (с backup и rollback path). Вызови Skill ПЕРВЫМ — особенно если речь о production.",
    ),
    (
        r"(аутентифик|авториз|платеж|оплат\w+\s+(сист|инт|api)|"
        r"\bjwt\b|\bcsrf\b|\bxss\b|sql\s*injection)",
        "🔔 Триггер 'auth/payments' → подключи плагин security-guidance ИЛИ используй /security-audit для read-only проверки.",
    ),
    (
        r"(\bui\b|интерфейс|frontend|дизайн\s+компонент|верстк|\bux\b)",
        "🔔 Триггер 'UI/frontend' → подключи плагин frontend-design.",
    ),
    (
        r"(проверь\s+зависимост|проверь\s+пакет|audit\s+deps|"
        r"dependency\s+audit|dep\s+audit|check\s+dependencies|"
        r"найди\s+уязвимые\s+пакет|найди\s+cve\s+в\s+зависимост|"
        r"проверь\s+лицензи|license\s+(check|audit)|"
        r"lockfile\s+audit|package-lock\.json\s+audit|requirements\.txt\s+audit|"
        r"supply\s+chain\s+audit|проверка\s+цепочки\s+поставок|"
        r"abandoned\s+packages|заброшенные\s+пакет|устаревшие\s+зависимост|"
        r"vulnerability\s+scan\s+dependencies|"
        r"\bosv\b|\bghsa\b|github\s+advisory)",
        "🔔 Триггер 'dependency audit' → используй /deps-audit (read-only проверка CVE/лицензий/заброшенных пакетов, тот же enum статусов что у /review). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(подготовь\s+к\s+продакшен|готов\s+ли\s+прод|production\s+readiness|"
        r"\bharden\b|hardening|production\s+hardening|"
        r"sre\s+checklist|\brunbook\b|generate\s+runbook|"
        r"нужен\s+мониторинг|настрой\s+prometheus|настрой\s+grafana|"
        r"rate\s+limit|ограничен\w+\s+запрос|throttling|"
        r"graceful\s+shutdown|плавное\s+выключен|"
        r"load\s+test|нагрузочн\w+\s+тест|\bk6\b|"
        r"health\s*check|/healthz|liveness|readiness|"
        r"structured\s+log|structured\s+logs|logs?\s+to\s+json|"
        r"secrets?\s+management|\bvault\b|\bdoppler\b|"
        r"backup\s+strateg|стратеги\w+\s+бэкап)",
        "🔔 Триггер 'production hardening' → используй /harden (рубрика health/logs/metrics/backups/load-test/runbook, генерация артефактов с согласия пользователя). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(настрой\s+инфраструктур|provision\s+infrastructure|infra\s+as\s+code|"
        r"\bterraform\b|terraform\s+module|сгенери\w+\s+terraform|"
        r"\bhelm\b|helm\s+chart|k8s\s+manifests?|kubernetes\s+manifests?|"
        r"настрой\s+vault|настрой\s+doppler|secrets?\s+manager|"
        r"provision\s+(servers?|droplet|ec2|instance)|create\s+(droplet|ec2|instance)|"
        r"\btfstate\b|terraform\s+state|backend\s+s3|"
        r"\biac\b|infrastructure\s+as\s+code|инфраструктура\s+как\s+код|"
        r"deploy\s+to\s+(digitalocean|aws|hetzner)|"
        r"managed\s+kubernetes|\bdoks\b|\beks\b|\bgke\b)",
        "🔔 Триггер 'infrastructure-as-code' → используй /infra (Terraform/Helm/secrets для DO/AWS/Hetzner/K8s, remote tfstate с локами для prod). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(сохрани\s+контекст|сохрани\s+сессию|запомни\s+что\s+делали|"
        r"итоги\s+сессии|конец\s+сессии|закончили\s+работу|"
        r"на\s+сегодня\s+всё|заканчиваем\s+работу|"
        r"save\s+session|save\s+context|end\s+of\s+session|"
        r"wrap\s+up\s+session|session\s+summary)",
        "🔔 Триггер 'session save' → используй /session-save "
        "(сохранение контекста сессии в память проекта). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(закрой\s+tech\s*debt|закрой\s+техдолг|убери\s+техдолг|"
        r"поправь\s+в\s+проекте|почини\s+в\s+проекте|надо\s+поправить|"
        r"есть\s+задача\s+в\s+проекте|работа\s+в\s+существующем|"
        r"инкрементальн\w+\s+изменен|надо\s+что-то\s+сделать\s+в\s+проекте|"
        r"tech\s*debt\s+cleanup|work\s+on\s+existing|existing\s+project|"
        r"maintenance\s+task|housekeeping|\bchore\b|"
        r"поработать\s+над\s+(проектом|кодом)|"
        r"накопилось\s+(мелоч|задач)|куча\s+мелочей)",
        "🔔 Триггер 'существующий код / tech debt' → используй /task "
        "(роутер daily-work: /bugfix / /refactor / /doc / /test / /perf / "
        "/security-audit / /deps-audit / /migrate / /harden / /infra / "
        "/explain / /review). Вызови Skill ПЕРВЫМ — если тип задачи сразу "
        "ясен, /task делегирует без доп. вопросов.",
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

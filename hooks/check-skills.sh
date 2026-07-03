#!/usr/bin/env python3
"""
UserPromptSubmit hook — analyzes user prompt for triggers and reminds Claude
to check whether a skill from the Idea-to-Deploy methodology fits.

Reads JSON on stdin: {"prompt": "...", ...}
Outputs JSON on stdout with hookSpecificOutput.additionalContext (injected
back into the model context for the current turn).

Silent (exit 0, no output) if no triggers match — keeps normal turns clean.

v1.24.0: when a trigger matches, this hook also stamps the per-session
"skill-active" sentinel that check-tool-skill.sh reads to grant a grace
window. Because PreToolUse/PostToolUse hooks do NOT fire for the Skill tool,
this UserPromptSubmit hook is the reliable place to record that the current
task is methodology/skill work, so a legitimate Edit/Bash flow is not falsely
blocked by the enforcement gate. The session-id derivation below MUST stay
identical to check-tool-skill.sh or the sentinel paths will not match.
"""
import json
import os
import sys
import tempfile
import time


# NOTE: this function MUST stay byte-for-byte behaviourally identical to the
# copy in hooks/check-tool-skill.sh — both derive the per-session sentinel path,
# and any divergence silently breaks the skill-active grace window. The
# drift-guard in tests/verify_skill_enforcement.py asserts the two bodies match.
def session_id() -> str:
    """Identical to check-tool-skill.sh: env var → per-day anchor → default."""
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        anchor = os.path.join(tempfile.gettempdir(), "claude-skill-session-anchor")
        try:
            with open(anchor) as f:
                tok = f.read().strip()
            if tok:
                return tok
        except Exception:
            pass
        tok = time.strftime("day%Y%m%d")
        with open(anchor, "w") as f:
            f.write(tok)
        return tok
    except Exception:
        return "default"


def mark_skill_active() -> None:
    """Stamp the skill-active sentinel read by check-tool-skill.sh. Best-effort."""
    try:
        path = os.path.join(
            tempfile.gettempdir(), "claude-skill-active-%s.state" % session_id()
        )
        with open(path, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


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
        r"(отрефактор|рефактор|упрост\w*\s+код|refactor|"
        r"переписать\s+(код|модул|функци|класс|метод|компонент)|"
        r"перепиши\s+(код|модул|функци|класс|метод|понятнее)|"
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
        r"generate\s+(a\s+)?(step-by-step\s+)?guide|step-by-step\s+prompts?|guide\s+for\s+(the\s+)?project|"
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
        r"\bmigrate\b|apply\s+(a\s+)?migration|run\s+migration|rollback\s+migration|"
        r"alter\s+table|add\s+(a\s+)?column|drop\s+table|create\s+index|"
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
        r"(задеплой|деплой\b|deploy\b|выкат\w*\s+на\s+прод|обнови\s+прод|"
        r"обнови\s+сервер|update\s+(production|server)|"
        r"залей\s+на\s+сервер|push\s+to\s+prod|"
        r"перезапусти\s+прод|перезапусти\s+контейнер|"
        r"rsync\s+на\s+сервер|синхронизируй\s+с\s+сервером)",
        "🔔 Триггер 'deploy' → используй /deploy "
        "(деплой на прод: sync, build, migrations, healthcheck). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(сохрани\s+контекст|сохрани\s+сессию|запомни\s+что\s+делали|"
        r"итоги\s+сессии|конец\s+сессии|закончили\s+работу|"
        r"на\s+сегодня\s+всё|заканчиваем\s+работу|"
        r"save\s+session|save\s+context|end\s+of\s+session|"
        r"wrap\s+up\s+(the\s+)?session|session\s+summary)",
        "🔔 Триггер 'session save' → используй /session-save "
        "(сохранение контекста сессии в память проекта). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(исследуй\s+рынок|анализ\s+рынк|market\s+analysis|market\s+research|"
        r"целевая\s+аудитори|кто\s+пользовател|user\s+personas?|target\s+audience|"
        r"\bконкуренты\b|конкурентн\w+\s+анализ|competitor\s+analysis|competitive\s+research|"
        r"приоритизаци\w+\s+фич|какие\s+фичи\s+важнее|feature\s+prioritization|"
        r"product\s+discovery|discovery\s+phase|discovery\s+фаз|"
        r"что\s+строить|что\s+делать\s+первым|what\s+to\s+build\s+first|"
        r"\btam\b.*\bsam\b.*\bsom\b|value\s+proposition|ценностное\s+предложени|"
        r"проверь\s+идею|валидаци\w+\s+идеи|validate\s+idea|idea\s+validation)",
        "🔔 Триггер 'product discovery' → используй /discover (анализ рынка, "
        "персоны, конкуренты, MoSCoW/RICE приоритизация). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(автопилот|запусти\s+всё|сделай\s+от\s+начала\s+до\s+конца|"
        r"полный\s+автопилот|автоматический\s+режим|"
        r"от\s+идеи\s+до\s+деплоя\s+автоматическ|hands-?free|"
        r"\bautopilot\b|auto\s+mode|run\s+everything|full\s+auto|"
        r"запусти\s+pipeline\s+целиком|весь\s+конвейер)",
        "🔔 Триггер 'автопилот' → используй /autopilot "
        "(авто-pipeline: /discover → /blueprint → /kickstart → /review → /test). "
        "Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(пересмотри\s+стратеги|обнови\s+стратеги|стратегическ\w+\s+пересмотр|"
        r"обнови\s+launch\s*plan|пересмотри\s+план\s+запуска|переоценк\w+\s+проект|"
        r"проект\s+не\s+работает\s+как\s+планировали|нужен\s+pivot|"
        r"что\s+изменить\s+в\s+проекте|куда\s+двигаться\s+дальше|"
        r"обнови\s+roadmap\s+проекта|пересмотри\s+roadmap|"
        r"kpi\s+gap|не\s+достигаем\s+целей|метрики\s+не\s+растут|"
        r"strategic\s+review|replan\s+project|update\s+launch\s*plan|"
        r"pivot\s+decision|project\s+reassessment|strategic\s+pivot|"
        r"что\s+делать\s+с\s+проектом|проект\s+буксует)",
        "🔔 Триггер 'стратегический пересмотр' → используй /strategy "
        "(анализ текущего состояния, gap analysis, ADR для pivot decisions, "
        "обновление LAUNCH_PLAN.md). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(мигрируй\s+серв|перенеси\s+серв|перенос\s+prod|миграци\w+\s+prod|"
        r"перенос\s+сайт\w*\s+на\s+другой|переезд\s+серв|переезд\s+vds|"
        r"с\s+одного\s+серв\w+\s+на\s+другой|переезд\s+на\s+новый\s+серв|"
        r"migrate\s+prod|migrate\s+server|server\s+migration|"
        r"move\s+to\s+new\s+(server|host|vds|vps)|"
        r"перенос\s+инфраструктур|infrastructure\s+migration|"
        r"dual[\s-]?run|cut[\s-]?over\s+dns)",
        "🔔 Триггер 'миграция prod-сервисов' → используй /migrate-prod "
        "(inventory → setup target → data migration → dual-run → cut-over → "
        "rollback plan → decommission). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(посоветуй|дай\s+совет|стратегическ\w+\s+совет|"
        r"консалтинг|консультац|что\s+ты\s+думаешь\s+о\s+стратеги|"
        r"оцени\s+идею|сравни\s+варианты|какой\s+вариант\s+лучше|"
        r"анализ\s+без\s+кода|только\s+анализ|без\s+изменений\s+в\s+код|"
        r"advisor\s+mode|give\s+advice|strategic\s+advice|"
        r"consult\w*\s+mode|just\s+analyze|analysis\s+only|"
        r"compare\s+options|which\s+option\s+is\s+better|"
        r"помоги\s+выбрать\s+направлени|какую\s+нишу\s+выбрать)",
        "🔔 Триггер 'советник/консалтинг' → используй /advisor "
        "(анализ без кода, Agent subagents business-analyst + devils-advocate, "
        "output: рекомендации с pros/cons). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(закрой\s+tech\s*debt|закрой\s+техдолг|убери\s+техдолг|"
        r"поправь\s+в\s+проекте|почини\s+в\s+проекте|надо\s+поправить|"
        r"есть\s+задача\s+в\s+проекте|работа\s+в\s+существующем|"
        r"инкрементальн\w+\s+изменен|надо\s+что-то\s+сделать\s+в\s+проекте|"
        r"tech\s*debt\s+cleanup|work\s+on\s+existing|existing\s+project|"
        r"maintenance\s+task|housekeeping|\bchore\b|"
        r"поработать\s+над\s+(проектом|кодом)|"
        r"накопилось\s+(мелоч|задач)|куча\s+мелочей|"
        r"реализуй\s+фичу|добавь\s+функциональн|новая\s+фича\s+в|"
        r"implement\s+(a\s+)?feature|add\s+a\s+feature|feature\s+in\s+existing)",
        "🔔 Триггер 'существующий код / tech debt / фича' → используй /task "
        "(роутер daily-work: /bugfix / /refactor / /doc / /test / /perf / "
        "/security-audit / /deps-audit / /migrate / /harden / /infra / "
        "/explain / /review; новая фича в существующем проекте → "
        "feature-конвейер /task Step 3f). Вызови Skill ПЕРВЫМ — если тип "
        "задачи сразу ясен, /task делегирует без доп. вопросов.",
    ),
    (
        r"(адоптир\w*|адоптируй\s+проект|подключи\s+методолог\w*|"
        r"подключи\s+idea[- ]to[- ]deploy|подключи\s+к\s+idea[- ]to[- ]deploy|"
        r"включи\s+методолог\w*|примени\s+методолог\w*|"
        r"bootstrap\s+methodolog\w*|добавь\s+claude\.md|"
        r"добавь\s+хуки\s+(в\s+)?проект|настрой\s+(этот\s+)?проект\s+под\s+методолог\w*|"
        r"этот\s+проект\s+без\s+методолог\w*|в\s+проекте\s+нет\s+claude\.md|"
        r"нет\s+claude\.md|legacy\s+project|legacy\s+adoption|adopt\s+legacy|"
        r"onboard\s+(this\s+|an\s+|the\s+)?(existing\s+)?project|"
        r"adopt\s+(this\s+|the\s+)?(existing\s+|legacy\s+)?project|"
        r"adopt\s+methodolog\w*|enable\s+methodolog\w*)",
        "🔔 Триггер 'адоптация методологии' → используй /adopt "
        "(минимальный bootstrap: CLAUDE.md + .claude/settings.json project-level + "
        "memory dir, затем voice-chain в /strategy или /blueprint). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(хендофф|сделай\s+хендофф|передай\s+контекст|"
        r"передача\s+сесси|контекст\s+для\s+передач|пакет\s+контекст|"
        r"контекст\s+(для\s+)?следующ\w+\s+сесси|перед\s+компакц|"
        r"\bhandoff\b|make\s+a\s+handoff|hand\s+off|"
        r"transfer\s+context|session\s+handoff|context\s+packet|"
        r"delegate\s+to\s+(another\s+)?(agent|session))",
        "🔔 Триггер 'передача контекста' → используй /handoff "
        "(компактный пакет HANDOFF.md для передачи следующей сессии/агенту перед "
        "компакцией, делегированием, AFK или восстановлением; ≠ /session-save, "
        "которая сохраняет веху для будущего «я»). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(проверь\s+мой\s+план|устрой\s+(мне\s+)?допрос|"
        r"погоняй\s+(меня\s+)?по\s+план|"
        r"стресс-?тест\w*\s+(решени|план|иде|архитектур|стратеги|миграци)|"
        r"разнеси\s+(мой\s+)?план|задай\w*\s+неудобные\s+вопрос|"
        r"grill\s+me|stress[- ]?test\s+my\s+plan|challenge\s+my\s+(design|plan)|"
        r"poke\s+holes|interrogate\s+the\s+plan|pressure[- ]?test)",
        "🔔 Триггер 'стресс-тест решения' → используй /grill-me "
        "(интерактивный read-only допрос плана/дизайна/архитектуры по одному "
        "вопросу с рекомендуемым ответом; запускай ДО /review, чтобы поднять "
        "качество решения). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(скан\s+рынка|сканир\w+\s+рынок|свеж\w+\s+сигнал\w+\s+рынка|"
        r"что\s+говорят\s+о\s+(продукт|нише|рынке)|проверь\s+нишу|"
        r"рыночн\w+\s+сигнал|сигнал\w+\s+сообществ|сигнал\w+\s+рынка|"
        r"market\s+scan|scan\s+the\s+market|fresh\s+market\s+signal|"
        r"market\s+signals|community\s+signals|validate\s+(my\s+)?idea|"
        r"competitor\s+chatter|competitor\s+signals)",
        "🔔 Триггер 'скан рынка' → используй /market-scan "
        "(свежие публичные рыночные/комьюнити-сигналы за ~30 дней через last30days, "
        "нормализация в MARKET_BRIEF.md; ≠ /discover, который делает полную "
        "discovery-фазу с TAM/SAM/SOM и персонами). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(актуальн\w+\s+документац|проверь\s+доки|свеж\w+\s+доки|"
        r"документац\w+\s+(по\s+)?библиотек|актуальн\w+\s+api|"
        r"\bcontext7\b|посмотри\s+доки\s+библиотек|"
        r"mcp\s+docs|check\s+the\s+docs|library\s+documentation|"
        r"current\s+api\s+docs|look\s+up\s+docs|fetch\s+documentation|"
        r"latest\s+(library\s+)?docs)",
        "🔔 Триггер 'актуальная документация' → используй /mcp-docs "
        "(подтягивание свежих доков библиотек/фреймворков через MCP-провайдеров, "
        "в первую очередь Context7; read-only, перед добавлением зависимостей или "
        "интеграцией против SDK). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(созда\w+\s+issue|откр\w+\s+pull\s+request|оформ\w+\s+pr\b|"
        r"github\s+issue|github\s+actions?\s+упал|gh\s+workflow|"
        r"релиз\s+ноут|саммари\s+pr|комментар\w+\s+ревью\s+на\s+github|"
        r"create\s+(a\s+)?github\s+issue|open\s+(a\s+)?pull\s+request|"
        r"ci\s+is\s+failing|failing\s+(github\s+)?actions?|"
        r"release\s+notes|pr\s+summary|review\s+comments)",
        "🔔 Триггер 'GitHub workflow' → вызови /github-workflow ЯВНО "
        "(issues/PR/CI/релизы; external-write, explicit-invocation — никаких "
        "push/merge/close/release без явного намерения). Вызови Skill.",
    ),
    (
        r"(синхронизируй\s+с\s+notion|синк\s+в\s+linear|экспорт\s+в\s+obsidian|"
        r"синк\s+с\s+google\s+drive|синхрон\w+\s+с\s+внешн|"
        r"синхрон\w+\s+с\s+(notion|linear|obsidian|google)|"
        r"экспорт\w*\s+(\S+\s+){0,3}в\s+(notion|linear|google)|"
        r"tool\s+sync|sync\s+to\s+notion|sync\s+with\s+linear|export\s+to\s+obsidian|"
        r"mirror\s+to\s+google\s+drive|sync\s+(\S+\s+){0,2}roadmap|sync\s+project\s+state)",
        "🔔 Триггер 'синк с внешними инструментами' → вызови /tool-sync ЯВНО "
        "(зеркалирование артефактов в GitHub/Linear/Notion/Google Drive/Obsidian; "
        "external-write, explicit-invocation — спрашивай перед записью в live-системы). "
        "Вызови Skill.",
    ),
    (
        r"(obsidian\s+vault|граф\s+знаний|связанн\w+\s+заметк|"
        r"выгруз\w+\s+в\s+обсидиан|экспорт\s+в\s+obsidian|vault-?заметк|"
        r"obsidian\s+export|knowledge\s+graph|linked\s+notes|"
        r"export\s+to\s+vault|project\s+vault|obsidian\s+notes|"
        r"в\s+обсидиан|в\s+vault\b)",
        "🔔 Триггер 'Obsidian / граф знаний' → используй /obsidian-export "
        "(производный перегенерируемый Obsidian-слой в .itd-integrations/obsidian/ "
        "из канонических артефактов; канон не трогается). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(проверь\s+в\s+браузере|открой\s+в\s+браузере|проверь\s+верстку|"
        r"проверь\s+вёрстку|проверь\s+страниц|отрендер\w+\s+страниц|"
        r"смоук[- ]?тест\s+ui|проверь\s+ui\b|"
        r"browser\s+check|smoke\s+test\s+ui|check\s+in\s+browser|"
        r"test\s+the\s+ui|visual\s+check|playwright\s+check|browser\s+smoke)",
        "🔔 Триггер 'проверка в браузере' → используй /browser-check "
        "(локальный browser smoke-тест через Playwright-харнесс; первый рендер + "
        "критический путь; BLOCKED при поломке до деплоя). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(подготов\w*\s+к\s+встреч|подготов\w*\s+вопрос|состав\w*\s+вопрос|"
        r"сформулир\w*\s+вопрос|вопрос\w*\s+(для|к)\s+(встреч|интервью|заказчик|клиент|финмен)|"
        r"к\s+интервью|провести\s+интервью|подготов\w*\s+к\s+интервью|"
        r"что\s+(нужно\s+)?(выяснить|спросить|узнать)\s+(у|на\s+встреч|в\s+ходе|перед)|"
        r"prepare\s+(for\s+)?(a\s+)?(meeting|interview)|meeting\s+prep|"
        r"questions?\s+(for|to\s+ask)|interview\s+questions?|discovery\s+interview)",
        "🔔 Триггер 'подготовка встречи/вопросов' → используй /advisor "
        "(многоперспективный разбор), /grill-me (стресс-тест) или /discover "
        "(если это product discovery). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(caveman|режим\s+caveman|talk\s+like\s+caveman|use\s+caveman|"
        r"меньше\s+токен|сжима\w*\s+ответ|короче\s+отвеча|короткие\s+ответы|"
        r"less\s+tokens|be\s+brief|terse\s+repl|token\s+efficiency|compress\s+output)",
        "🔔 Триггер 'caveman / меньше токенов' → используй /caveman "
        "(token-efficiency режим: терсе-ответы lite/full/ultra/wenyan без потери "
        "статуса гейтов, блокеров и verification-evidence). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(context\s*-?\s*mode|режим\s+контекста|ctx\s+mode|"
        r"экономия\s+контекст|сжать\s+контекст|забива\w*\s+контекст|контекстное\s+окно\s+забива|"
        r"большой\s+вывод\s+инструмент|огромн\w*\s+вывод|sandbox\s+вывод|песочниц\w*\s+для\s+вывод|"
        r"save\s+context\s+window|context\s+window\s+optim|sandbox\s+tool\s+output|huge\s+tool\s+output|too\s+much\s+context)",
        "🔔 Триггер 'context mode / экономия контекстного окна' → используй /context-mode-setup "
        "(интеграция upstream Context Mode: песочница большого вывода инструментов в FTS5-стор "
        "вместо дампа в контекст; детект install + lifecycle-fit, гейты методологии не трогает). "
        "Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(\bseo\b|\bсео|поисков\w*\s+оптимиз|"
        r"schema\s+markup|schema\.org|разметк\w*\s+schema|микроразметк|json-?ld|structured\s+data|"
        r"core\s+web\s+vitals|web\s+vitals|"
        r"\bsitemap|карт\w*\s+сайта|"
        r"e-?e-?a-?t|eeat|"
        r"ai\s+overview|geo\s+optimiz|generative\s+engine|ai\s+search\s+visib|"
        r"technical\s+seo|техническ\w*\s+seo|on-?page\s+seo|"
        r"search\s+ranking|поисков\w*\s+выдач|ранжирован\w*\s+сайт|"
        r"backlink|обратн\w*\s+ссылк|ссылочн\w*\s+профил|"
        r"keyword\s+research|ключев\w*\s+слов|semantic\s+cluster|кластеризац\w*\s+ключ)",
        "🔔 Триггер 'SEO / поисковая оптимизация / schema / Core Web Vitals / GEO' → используй /seo-setup "
        "(интеграция upstream Claude SEO plugin AgriciDaniel/claude-seo, MIT: 25 скиллов + 18 агентов "
        "для technical SEO, E-E-A-T, schema, sitemap, CWV, local, backlinks, AI/GEO, hreflang, Google APIs; "
        "детект install + маппинг на жизненный цикл discover/blueprint/kickstart/harden/deploy, гейты не трогает). "
        "Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(security[\s-]?guidance|плагин\s+security|секьюрити[\s-]?гайденс|"
        r"shift[\s-]?left\s+security|сдвиг\w*\s+безопасност\w*\s+влево|"
        r"real[\s-]?time\s+security|безопасност\w*\s+на\s+лету|безопасност\w*\s+в\s+реальном\s+времени|"
        r"security\s+review\s+(as|when|while|on\s+commit)|review\s+code\s+as\s+(it|i)\b|"
        r"безопасност\w*\s+при\s+написании|ревью\s+безопасност\w*\s+при\s+коммит|commit\s+security\s+review|"
        r"автоматическ\w*\s+security|авто[\s-]?ревью\s+безопасност|automatic\s+security\s+review|"
        r"лов\w*\s+уязвимост|catch\s+vulnerabilit\w*\s+as\s+you|vulnerabilit\w*\s+as\s+you\s+(code|write)|"
        r"official\s+security\s+plugin|официальн\w*\s+security[\s-]?плагин)",
        "🔔 Триггер 'security-guidance / shift-left security / ревью безопасности на лету' → используй /security-guidance-setup "
        "(интеграция официального Anthropic-плагина security-guidance: 3 слоя — pattern-warnings на каждом Edit/Write, "
        "LLM diff-ревью на Stop, агентский commit/push-ревью кросс-файловых уязвимостей; ships default-on, free. "
        "Детект install + маппинг на жизненный цикл; КОМПЛЕМЕНТ к /security-audit, не замена; гейты не трогает). "
        "Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(cross[\s-]?review|cross[\s-]?vendor\s+review|кросс[\s-]?ревью|"
        r"перекр[её]стн\w*\s+ревью|"
        r"review\s+by\s+another\s+(model|llm)|независимое\s+ревью\s+другой|"
        r"ревью\s+другой\s+модель\w*|кросс[\s-]?вендор\w*\s+ревью|"
        r"second\s+opinion\s+on\s+the\s+code|второе\s+мнение\s+по\s+коду|"
        r"codex\s+review|ревью\s+через\s+codex|gemini\s+review|ревью\s+через\s+gemini)",
        "🔔 Триггер 'cross-review / второе мнение другой моделью' → используй /cross-review "
        "(независимое второе мнение по диффу от внешней модели — OpenAI Codex CLI или Gemini CLI; "
        "PII-scrub перед отправкой; fail-open цепочка codex→gemini→нативный red-team review Claude; "
        "АДДИТИВНО к /review, не заменяет и не является гейтом). Вызови Skill ПЕРВЫМ.",
    ),
    (
        # (?<![а-яё]) отсекает «сопоставь/составь/приставлю…» — триггер только
        # на реальные формы постановки цели (поставь/поставим/ставлю/ставим).
        r"(долг\w*\s+цель|режим\s+цели|(?<![а-яё])(?:постав\w*|став(?:лю|им))\s+цель|"
        r"декомпозир\w*\s+цель|цель\s+на\s+несколько\s+сесси|"
        r"продолж\w*\s+цель|верн\w*\s+к\s+цели|работаем\s+к\s+цели|"
        r"goal\s+mode|long-?running\s+goal|multi-?session\s+goal|"
        r"decompose\s+the\s+goal|goal\s+ledger|"
        r"\bgoal\.json\b)",
        "🔔 Триггер 'долгая цель / goal mode' → используй /goal "
        "(режим долгой цели: декомпозиция в проверяемые юниты в .itd-memory/GOAL.json "
        "с одобрением пользователя, ведение по одному юниту через штатный конвейер "
        "/task при WIP=1, resume между сессиями с первого не-verified юнита; "
        "НЕ гейт — /review и DoD не обходит). Вызови Skill ПЕРВЫМ.",
    ),
    (
        r"(ретроспектив\w*\s+методологи\w*|методологическ\w+\s+ретро|"
        r"ретро\s+методологи\w*|что\s+улучшить\s+в\s+методологи\w*|"
        r"предлож\w+\s+улучшени\w+\s+методологи\w*|"
        r"(?:methodology|itd)\s+retro|(?:methodology|itd)\s+improvement\s+retro|"
        r"self[\s-]?improvement\s+(?:cycle|loop))",
        "🔔 Триггер 'ретро методологии / self-improvement' → используй /retro "
        "(самопредлагающий цикл улучшений: факты собирает скрипт itd_retro_scan.py "
        "— VCR, регрессии, bypass-леджер, активные цели, cost; модель формирует "
        "ранжированные предложения ТОЛЬКО с evidence; merge остаётся за человеком "
        "через обычный релизный конвейер; НЕ гейт, самомержа нет). Вызови Skill ПЕРВЫМ.",
    ),
]


def project_profile(cwd: str) -> str:
    """Resolve the methodology profile for the project at `cwd` (v1.36.0).

    Precedence:
      1. An explicit marker in the project's CLAUDE.md wins in EITHER direction
         (case-insensitive, first 8 KB):
             itd-profile: brownfield  /  <!-- itd:brownfield -->  -> 'brownfield'
             itd-profile: greenfield  /  <!-- itd:greenfield -->  -> 'greenfield'
      2. Otherwise AUTO-DETECT by repo maturity: an established git history
         (>= ITD_BROWNFIELD_MIN_COMMITS commits, default 25) is 'brownfield';
         a fresh/empty project (few or no commits, or no git repo) is
         'greenfield' — the safe default that keeps the greenfield pipeline.

    Returns 'brownfield' or 'greenfield'. Only 'brownfield' suppresses the
    greenfield-pipeline hints in the caller. A mature repo that still wants the
    pipeline (e.g. a big new feature) sets `itd-profile: greenfield` to opt back.
    """
    import re
    # 1. Explicit marker (either direction) — check both CLAUDE.md locations.
    try:
        for name in ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md")):
            p = os.path.join(cwd, name)
            if os.path.isfile(p):
                with open(p, encoding="utf-8", errors="ignore") as f:
                    head = f.read(8192).lower()
                if re.search(r"itd-profile:\s*greenfield|itd:greenfield", head):
                    return "greenfield"
                if re.search(r"itd-profile:\s*brownfield|itd:brownfield", head):
                    return "brownfield"
    except Exception:
        pass
    # 2. Auto-detect by git maturity.
    try:
        threshold = int(os.environ.get("ITD_BROWNFIELD_MIN_COMMITS", "25"))
    except Exception:
        threshold = 25
    try:
        import subprocess
        out = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            commits = int((out.stdout or "0").strip() or "0")
            return "brownfield" if commits >= threshold else "greenfield"
    except Exception:
        pass
    return "greenfield"


# Hints whose skill belongs to the greenfield "idea → deploy" pipeline. In a
# project that declared itd-profile: brownfield these are suppressed, because
# the work is feature/maintenance on an existing codebase, not a new build.
_GREENFIELD_SKILLS = ("/project", "/blueprint", "/discover", "/kickstart",
                      "/guide", "/strategy", "/market-scan", "/autopilot")


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
    # (v1.35.0) Neutralise the methodology's own name so a casual mention like
    # "методология idea to deploy" can't self-trigger generic keyword hints
    # (the word "deploy" inside "idea to deploy" used to fire /deploy). The
    # /adopt trigger legitimately keys on the name, so it matches the raw prompt.
    lp_clean = re.sub(r"idea[\s\-]?to[\s\-]?deploy", "  ", lp)
    hints = []
    seen = set()
    for pattern, hint in TRIGGERS:
        target = lp if "/adopt" in hint else lp_clean
        if re.search(pattern, target) and hint not in seen:
            hints.append(hint)
            seen.add(hint)

    # (v1.36.0) Brownfield profile: suppress greenfield-pipeline hints on a
    # mature/existing codebase. Auto-detected by repo maturity, overridable by an
    # explicit marker (see project_profile). Match a hint by its OWN (primary)
    # skill — the first "/skill" token, i.e. the one after "используй" — never by
    # a greenfield skill merely mentioned in the prose (e.g. the /adopt hint
    # references /blueprint). Resolve only when a greenfield hint actually fired,
    # to avoid the git call on ordinary prompts.
    def _primary_skill(h):
        m = re.search(r"/([a-z][a-z-]+)", h)
        return "/" + m.group(1) if m else ""

    if any(_primary_skill(h) in _GREENFIELD_SKILLS for h in hints):
        cwd = (payload or {}).get("cwd") or os.getcwd()
        if project_profile(cwd) == "brownfield":
            hints = [h for h in hints
                     if _primary_skill(h) not in _GREENFIELD_SKILLS]

    if not hints:
        return 0

    # A skill trigger matched → methodology context is established for this
    # task. Open a grace window so the enforcement gate (check-tool-skill.sh)
    # does not falsely block the resulting skill-driven Edit/Bash flow.
    mark_skill_active()

    context = (
        "[SKILL HINT — Idea-to-Deploy methodology]\n"
        + "\n".join(hints)
        + "\n\nВАЖНО: вынеси решение видимой ПЕРВОЙ строкой ответа — "
        "«Скилл: /X» (вызови его через инструмент Skill ДО Read/Edit/Bash/"
        "Write) либо «Скилл: не нужен — <причина>». Молча игнорировать "
        "нельзя. См. ~/.claude/CLAUDE.md раздел "
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

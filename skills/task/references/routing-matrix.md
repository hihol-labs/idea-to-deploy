# /task — Routing Matrix

Полная таблица соответствий «сигнал от пользователя → целевой daily-work скилл». Используется `/task` на Step 3 (routing decision).

## Матрица

| № | User signal (RU / EN) | Target skill | Примечания |
|---|---|---|---|
| 1 | Стек трейс, "не работает", crash, `AttributeError`, `TypeError`, "падает", "exception", "traceback" | **`/bugfix`** | Требует стек/логи/ошибку. Если симптомов нет — не вызывать. |
| 2 | "Отрефактори", "упрости код", "вынеси в функцию", "убери дублирование", "длинная функция", "code smell", "clean up", "God class" | **`/refactor`** | Поведение сохраняется, структура улучшается. Всегда запускать тесты после. |
| 3 | "Тормозит", "медленно", "bottleneck", N+1, "утечка памяти", "high latency", "slow query", "optimize this" | **`/perf`** | Требует metric/profile — если их нет, сначала собрать. |
| 4 | "Обнови README", "напиши docs", "задокументируй API", "inline comments", "JSDoc", "docstrings", "changelog" | **`/doc`** | Проверяет существующий стиль проекта, не навязывает свой. |
| 5 | "Добавь тесты", "покрой тестами", "нет покрытия", "regression test", "unit test", "integration test" | **`/test`** | Детектирует фреймворк по `package.json`/`requirements.txt`. |
| 6 | "Проверь безопасность", "security audit", "OWASP", "проверь auth", "secrets check", "exposed credentials" | **`/security-audit`** | **Read-only** — не применяет фиксы, только report. |
| 7 | "Проверь зависимости", "dependency audit", "CVE", "устаревшие пакеты", "lockfile audit", "supply chain" | **`/deps-audit`** | Read-only, same status enum as `/review`. |
| 8 | "Накати миграцию", "schema change", "ALTER TABLE", "add column", "Alembic upgrade", "Prisma migrate" | **`/migrate`** | Обязательно backup + rollback path. Осторожно в prod. |
| 9 | "Готов ли прод", "production hardening", "rate limit", "graceful shutdown", "health check", "runbook", "structured logs", "backup strategy" | **`/harden`** | Чек-лист SRE (health/logs/metrics/backups/load-test/runbook). |
| 10 | "Настрой Terraform", "Helm chart", "K8s manifests", "provision droplet", "tfstate", "IaC", "secrets manager", "deploy to DigitalOcean" | **`/infra`** | Генерация IaC (Terraform/Helm), **не** shell-скрипты деплоя. |
| 11 | "Объясни код", "как это работает", "walk me through", "разбери модуль" | **`/explain`** | Диаграммы + пошаговый разбор. |
| 12 | "Проверь PR", "review", "оцени качество", "check quality", "validate architecture" | **`/review`** | Code-level + architecture-level проверка. |
| 13 | "Сохрани контекст", "итоги сессии", "заканчиваем работу", "save session" | **`/session-save`** | Пишет `session_YYYY-MM-DD.md` + `.active-session.lock`. |

## Неявные маппинги

Эти случаи модель должна распознавать по контексту:

| Косвенный сигнал | Вероятный target |
|---|---|
| `git status` показывает staged changes, user говорит «проверь» | `/review` |
| `git log` показывает 10 commits без тестов, user говорит «что с качеством» | `/test` затем `/review` |
| `.env.example` содержит plaintext secrets, user говорит «всё нормально?» | `/security-audit` |
| User говорит «надо выкатить в прод», `/harden` ещё не запускался | `/harden` |
| `deploy.sh` содержит inline `envsubst`/`sed`/`cat <<EOF`, user говорит «почисти скрипт» | `/refactor` (extract-method) |
| `package.json` 2 года не обновлялся, user говорит «есть уязвимости?» | `/deps-audit` |

## Приоритет при множественных совпадениях

Если несколько сигналов срабатывают одновременно, приоритет от наиболее специфичного к наиболее общему:

1. `/bugfix` (есть стек/ошибка — конкретный симптом)
2. `/security-audit`, `/deps-audit` (read-only, не меняют код)
3. `/migrate` (требует осторожности в prod)
4. `/perf`, `/refactor`, `/test`, `/doc` (обычная работа)
5. `/harden`, `/infra` (infrastructure-level)
6. `/review` (валидация после работы)
7. `/session-save` (всегда последний в цепочке)

## Что НЕ роутится через `/task`

- **Создание нового проекта** — всегда `/project` (варианты А/Б/В). `/task` для существующего кода.
- **Долгие планирующие сессии без кода** — это `/blueprint` (план на 6 документов без кода), не `/task`.
- **Генерация гайда по готовым документам** — это `/guide`, не `/task`.
- **Однострочные фиксы (typo, rename)** — делай напрямую без роутера.
- **Конкретные запросы сразу под target skill** — хук `check-skills.sh` поднимает целевой скилл напрямую, `/task` не нужен.

## Пример: сегодняшний инцидент (2026-04-11)

Задача: «закрой tech debt с deploy.sh» (NeuroExpert).

Анализ:
- «tech debt» — нет явного trigger под /bugfix/refactor/etc.
- Контекст: `memory/feedback_deploy_kong_yml.md` объясняет root cause (rsync --delete сносит kong.yml)
- Root cause уже известен → не `/bugfix`
- Фикс: вынести inline envsubst в отдельный shell-скрипт → **classic extract-method refactoring**
- **Target: `/refactor`**

До v1.5.0 методология не имела явного entry point для этого — модель лезла руками. С `/task` теперь: пользователь говорит «закрой tech debt» → хук поднимает `/task` → `/task` распознаёт «rsync сносит» + «inline envsubst» → `/refactor`.

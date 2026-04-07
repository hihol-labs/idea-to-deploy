# Fixture 03: CLI tool — log analyzer

## User says

> Хочу CLI-утилиту на Python, которая читает JSON-логи nginx/Caddy/Traefik из stdin или из файла, агрегирует по статус-кодам / IP / эндпоинтам, и печатает отчёт в табличном виде. Опционально — выгрузка в CSV. Локально, без сервера, без БД, без интернета. Один бинарь, один человек запускает руками.

## Why this fixture exists

Tests **edge case**: CLI tool with no database, no API, no auth, no deployment. Verifies that:
- The rubric's C2 check ("at least one database table OR explicit 'no database' justification") passes via the justification path
- The rubric's C4 check ("at least one API endpoint OR explicit 'no API' justification") passes via justification
- IMPLEMENTATION_PLAN handles "no scaffolding for web stack" correctly
- /review doesn't fail Critical when there's legitimately no DB/API

## Expected complexity

- 0 tables (CLI is stateless)
- 0 endpoints (no HTTP)
- 4–5 implementation steps: arg parser → log parser → aggregator → formatter → tests
- Single Python file or small package

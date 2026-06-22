# Browser Check — Checklist

Чеклист для локального browser smoke-теста фронтенда/фуллстека/визуальных флоу
через Playwright (или Browser Use / in-app browser при недоступности Playwright).

> Дефолт — локальный Playwright-харнесс в `playwright/`. `$SKILL_DIR` = директория
> с `SKILL.md`. Запуск: `node $SKILL_DIR/playwright/run.js <script>` или
> `node $SKILL_DIR/playwright/run.js --detect`.

## Preconditions

- Определи локальный URL или file URL.
- Подними dev-сервер, если проект его требует.
- Подтверди критичный флоу из `PRD.md`, `.itd/GOLDEN_FLOWS.md`, `TEST_PLAN.md`
  или текущей задачи.
- Для localhost — сначала задетектируй запущенные dev-серверы.

## Процедура

1. Резолвни цель:
   - URL дан → используй его.
   - localhost без URL → `node $SKILL_DIR/playwright/run.js --detect`.
   - Несколько серверов → спроси, какой проверять.
2. Напиши task-specific Playwright-проверку во временный скрипт ВНЕ проекта,
   например `/tmp/itd-browser-check-<flow>.js`.
3. Выполни через `node $SKILL_DIR/playwright/run.js /tmp/itd-browser-check-<flow>.js`.
4. Проверь первый рендер: пустой экран, поломанная вёрстка, наезжающий текст,
   отсутствующие ассеты, ошибки в консоли.
5. Прогони критический путь: навигация, формы, auth-заглушки, loading/error
   состояния, основные CTA.
6. Сделай скриншоты desktop и mobile, когда визуальное доказательство полезно.
7. Зафиксируй: проверка блокирует релиз или advisory.

## Форма вывода

```text
BROWSER TARGET:
ENGINE: Playwright | Browser Use | in-app browser | manual
FLOW CHECKED:
RESULT: PASSED | PASSED_WITH_WARNINGS | BLOCKED
EVIDENCE:
SCREENSHOTS:
CONSOLE OR NETWORK ISSUES:
ISSUES:
NEXT ACTION:
```

## Правила

- Предпочитай реальное взаимодействие статической инспекции для user-facing изменений.
- Поломанный первый рендер / пустой app shell / неработающая навигация /
  недоступный основной флоу = `BLOCKED` до деплоя.
- Не полагайся только на скриншоты, когда формы/навигацию можно кликнуть.
- Не коммить временные Playwright-скрипты, созданные только для smoke-проверки.
- Параметризуй target URL в генерируемых скриптах.
- Предпочитай стабильные role/text/test-id локаторы хрупким CSS-селекторам.
- Headless — только по запросу или когда требует CI.
- Если зависимость харнесса отсутствует — `npm run setup` из
  `$SKILL_DIR/playwright` после одобрения пользователя (нужен сетевой доступ).
- Не делай production-impacting изменений из browser-check; фиксы — через
  `/bugfix` или активный узел работы.
- Сохраняй browser-доказательства в финальном отчёте или в `.rubric-status`
  (гейт `/review`), когда в scope deploy-readiness.

## Self-validation (перед выводом)

- [ ] Цель резолвнута (URL или `--detect`); dev-сервер поднят, если нужен.
- [ ] Критический флоу проверен реальным взаимодействием, не только скриншотом.
- [ ] Первый рендер и консоль проверены на ошибки.
- [ ] RESULT выставлен (PASSED/PASSED_WITH_WARNINGS/BLOCKED) честно.
- [ ] Временные скрипты не закоммичены; URL параметризованы.
- [ ] Фиксы маршрутизированы через `/bugfix`, не сделаны прямо из проверки.

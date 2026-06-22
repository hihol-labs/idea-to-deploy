# Fixture 25 — /browser-check

Локальный browser smoke-тест критичного флоу после фронтенд-изменения.

## Context

После изменения формы логина на фронтенде нужно проверить реальное поведение в
браузере (Playwright-харнесс), а не только статически. Проверяется local-browser
режим: детект dev-сервера, написание временного скрипта ВНЕ проекта, прогон через
харнесс, проверка первого рендера и критического пути, честный RESULT.

## Input prompt

Проверь в браузере: после правок не сломалась ли форма логина и навигация.
Смоук тест ui на localhost.

## Expected behavior

- Резолвится цель: URL дан → используется; localhost без URL →
  `node $SKILL_DIR/playwright/run.js --detect`; несколько серверов → вопрос.
- Временный Playwright-скрипт пишется ВНЕ проекта (`/tmp/itd-browser-check-*.js`),
  не коммитится.
- Прогон через `node $SKILL_DIR/playwright/run.js <script>`.
- Проверяется первый рендер (пустой экран/вёрстка/консоль) и критический путь
  (навигация, форма логина, loading/error состояния).
- Поломанный первый рендер/недоступный основной флоу → RESULT `BLOCKED` до деплоя.
- Фиксы маршрутизируются через `/bugfix`, не делаются прямо из проверки.
- Вывод по форме: BROWSER TARGET / ENGINE / FLOW CHECKED / RESULT / EVIDENCE /
  SCREENSHOTS / CONSOLE OR NETWORK ISSUES / ISSUES / NEXT ACTION.

## Fixture status

`pending` — snapshot-стаб (тот же бакет, что fixture-15-advisor): зависит от
запущенного dev-сервера, Playwright-харнесса и stdout. Полная автоматизация — Phase 2.

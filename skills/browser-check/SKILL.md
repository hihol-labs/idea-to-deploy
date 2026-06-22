---
name: browser-check
description: 'Local browser smoke testing for frontend, full-stack, and visual workflows using the bundled Playwright harness (or Browser Use / in-app browser as fallback). Use when a UI, route, form, dashboard, landing page, generated app, or frontend regression needs interactive verification.'
argument-hint: local URL, app path, route, user flow, or visual check target
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(node:*) Bash(npm:*) Bash(npx:*)
context: fork
metadata:
  effort: medium
  side_effect: local-browser
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.21.0
  category: quality-assurance
  tags: [browser, frontend, smoke-test, ux, playwright]
---

# Browser Check

## Trigger phrases

- проверь в браузере, открой в браузере, проверь верстку
- смоук тест ui, проверь страницу, отрендерь страницу
- browser check, smoke test ui, check in browser
- test the ui, visual check, playwright check

## Recommended model

**Sonnet** — написание task-specific Playwright-скрипта и интерпретация
результата структурны. Opus оправдан для тонкого визуального/UX-суждения по
сложной верстке.

## Instructions

Проверяй user-facing поведение в браузере после фронтенд/фуллстек-изменений.
Подробный чеклист — в `references/browser-check-checklist.md`.

По умолчанию используй локальный Playwright-харнесс в `playwright/`. Используй
in-app browser или Browser Use, когда Playwright недоступен, нужно
визуальное/ручное суждение, или пользователь явно просит интерактивную инспекцию.

> При запуске команд резолвь `$SKILL_DIR` в директорию, содержащую этот
> `SKILL.md`. Харнесс: `node $SKILL_DIR/playwright/run.js`.

### Preconditions

- Определи локальный URL или file URL.
- Подними dev-сервер, если проект его требует.
- Подтверди критичный флоу из `PRD.md`, `.itd/GOLDEN_FLOWS.md`, `TEST_PLAN.md`
  или текущей задачи.
- Для localhost — сначала задетектируй запущенные dev-серверы.

### Procedure

1. Резолвни цель:
   - URL дан → используй его.
   - localhost без URL → `node $SKILL_DIR/playwright/run.js --detect`.
   - Несколько серверов → спроси, какой проверять.
2. Напиши task-specific Playwright-проверку во временный скрипт ВНЕ проекта
   (`/tmp/itd-browser-check-<flow>.js`).
3. Выполни через `node $SKILL_DIR/playwright/run.js /tmp/itd-browser-check-<flow>.js`.
4. Проверь первый рендер: пустой экран, поломанная вёрстка, наезжающий текст,
   отсутствующие ассеты, ошибки в консоли.
5. Прогони критический путь: навигация, формы, auth-заглушки, loading/error
   состояния, основные CTA.
6. Сделай скриншоты desktop и mobile, когда визуальное доказательство полезно.
7. Зафиксируй: проверка блокирует релиз или advisory.

### Output

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

## Examples

### Example 1: Смоук-тест формы логина на localhost
User: «Проверь в браузере форму логина после правок. Смоук тест ui.»

Actions:
1. `node $SKILL_DIR/playwright/run.js --detect` — находит dev-сервер.
2. Пишет `/tmp/itd-browser-check-login.js`, прогоняет через харнесс.
3. Проверяет первый рендер + клик по форме логина + навигацию.
4. RESULT honest; поломка основного флоу → BLOCKED. Временный скрипт не коммитит.

### Example 2: Визуальная проверка лендинга (desktop + mobile)
User: «Проверь вёрстку лендинга на десктопе и мобиле.»

Actions:
1. Резолвит URL, пишет скрипт со скриншотами для двух viewport'ов.
2. Смотрит наезжающий текст, поломанную сетку, отсутствующие ассеты.
3. Не полагается только на скриншоты, если есть кликабельные элементы.

### Example 3: Playwright недоступен (fallback)
User: «Проверь страницу», но харнесс не установлен.

Actions:
1. Предлагает `npm run setup` из `$SKILL_DIR/playwright` (после одобрения, нужен сетевой доступ).
2. Или fallback на in-app browser / Browser Use / manual с указанием engine.
3. Не выдумывает результат проверки.

## Self-validation

Перед выводом убедись:
- [ ] Цель резолвнута (URL или `--detect`); dev-сервер поднят, если нужен.
- [ ] Критический путь проверен реальным взаимодействием, не только скриншотом.
- [ ] Первый рендер и консоль проверены на ошибки.
- [ ] RESULT выставлен честно (PASSED/PASSED_WITH_WARNINGS/BLOCKED).
- [ ] Временные скрипты не закоммичены; URL параметризованы.
- [ ] Фиксы маршрутизированы через `/bugfix`, не сделаны прямо из проверки.

## Troubleshooting

### Зависимость харнесса отсутствует
`npm run setup` из `$SKILL_DIR/playwright` после одобрения пользователя (нужен
сетевой доступ). Или fallback на in-app browser / Browser Use / manual.

### Несколько dev-серверов
`--detect` вернул несколько — спроси, какой target проверять, не угадывай.

### Поломанный первый рендер
Пустой app shell / неработающая навигация / недоступный основной флоу = `BLOCKED`
до деплоя. Опиши проблему, маршрутизируй фикс через `/bugfix`.

### Хочется поправить код прямо из проверки
Запрещено: browser-check не делает production-impacting изменений. Фиксы — через
`/bugfix` или активный узел работы.

## Rules

- Предпочитай реальное взаимодействие статической инспекции для user-facing изменений.
- Поломанный первый рендер/недоступный основной флоу = `BLOCKED` до деплоя.
- Не полагайся только на скриншоты, когда формы/навигацию можно кликнуть.
- Не коммить временные Playwright-скрипты smoke-проверок.
- Параметризуй target URL; предпочитай role/text/test-id локаторы хрупким CSS.
- Headless — только по запросу или когда требует CI.
- Не делай production-impacting изменений; фиксы — через `/bugfix`.
- Сохраняй browser-доказательства в отчёте или `.rubric-status`, когда в scope deploy-readiness.
- **Match the user's language** для всего вывода.

# Fixture 27 — /context-mode-setup

Оптимизация контекстного окна: настройка и интеграция upstream Context Mode
(FTS5-песочница большого вывода инструментов) без вендоринга ELv2-кода и без
потери гейтов.

## Context

Пользователь упирается в контекстное окно из-за большого вывода инструментов
(логи сборки, grep, стек-трейсы) в долгой сессии. Проверяется read-only
оркестратор/интеграция: скилл детектит установлен ли upstream-плагин
(`claude plugin list`, `claude plugin details`, `node --version`), запускает/печатает
проверенные команды install, маппит компоненты плагина на жизненный цикл и НЕ
трогает гейты методологии. Файлы проекта не меняются, ELv2-код upstream не
копируется.

## Input prompt

Контекст забивается от логов сборки в этой сессии — что делать, как включить
context mode?

## Expected behavior

- Распознаёт давление на контекстное окно от большого вывода инструментов → /context-mode-setup.
- Детект (read-only): `claude --version` (≥1.0.33), `node --version` (≥22.5),
  `claude plugin list | grep context-mode`, `claude plugin details context-mode`.
  Если не установлен — говорит об этом, НЕ заявляет что активен.
- Запускает/печатает проверенный CLI-путь install: `claude plugin marketplace add
  mksglu/context-mode`, `claude plugin install context-mode@context-mode`; после
  рестарта — скилл `ctx-doctor` для проверки.
- Механизм описывается по факту установленной 1.0.168: 8 скиллов (`context-mode` +
  `ctx-*`) + 6 harness-only хуков + bundled-движок (MCP servers = 0), ~631 ток
  always-on. НЕ выдуманные `ctx_*` MCP-инструменты.
- Атрибуция к @mksglu, лицензия ELv2 указана; код upstream НЕ вендорится в репо.
- Lifecycle-fit: где помогает (длинные `/kickstart`-сборки, долгие `/task`/`/bugfix`),
  где НЕ нужен (короткие однократные задачи — оверхед ~631 ток).
- Coexistence: 17 хуков idea-to-deploy + 6 хуков Context Mode (в settings рядом,
  без перезатирания); `ctx-doctor` на дубли; гейты (`/review`, `/test`, DoD) и
  строка-решение остаются явными.
- Файлы не создаются и не меняются.

## Fixture status

`pending` — snapshot-стаб (тот же бакет, что fixture-15-advisor,
fixture-21-mcp-docs, fixture-26-caveman): read-only, detect/advise stdout-вывод.
Полная автоматизация — Phase 2.

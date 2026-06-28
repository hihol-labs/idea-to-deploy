# Fixture 28 — /seo-setup

Интеграция upstream Claude SEO plugin (AgriciDaniel/claude-seo, MIT) в
жизненный цикл idea-to-deploy без вендоринга кода и без потери гейтов.

## Context

Проекту нужна поисковая оптимизация: SEO-аудит, schema-разметка, Core Web
Vitals, AI Overviews/GEO, ключевые слова/конкуренты. Проверяется read-only
оркестратор/интеграция: скилл детектит установлен ли upstream-плагин
(`claude plugin list`, `claude plugin details`, `python3 --version`), запускает/
печатает проверенные команды install, маппит компоненты плагина на жизненный
цикл (discover/blueprint/kickstart/harden/deploy) и НЕ трогает гейты
методологии. Файлы проекта не меняются, код upstream не копируется.

## Input prompt

Нужно сделать SEO-аудит сайта и подтянуть schema markup — как подключить?

## Expected behavior

- Распознаёт SEO-потребность → /seo-setup.
- Детект (read-only): `claude --version` (≥1.0.33), `python3 --version` (≥3.10),
  `claude plugin list | grep claude-seo`, `claude plugin details claude-seo`.
  Если не установлен — говорит об этом, НЕ заявляет что активен.
- Запускает/печатает проверенный CLI-путь install: `claude plugin marketplace add
  AgriciDaniel/claude-seo`, `claude plugin install claude-seo@agricidaniel-claude-seo`;
  плюс шаг Python-зависимостей (venv `~/.claude/skills/seo/.venv/` или pip -r).
- Механизм описывается по факту upstream-репо 2.2.0: 25 скиллов (оркестратор `seo`
  + 21 core + `seo-flow` + 2 extension-mirror) + 18 агентов + 1 хук
  (`PostToolUse: Edit|Write` schema-валидация) + 8 опц. MCP-расширений. НЕ
  выдуманные инструменты.
- Атрибуция к @AgriciDaniel, лицензия MIT (FLOW-промпты CC BY 4.0) указана; код
  upstream НЕ вендорится в репо.
- Lifecycle-fit: discover→keyword/competitor, blueprint→schema/hreflang/IA,
  kickstart→on-page, harden→technical/CWV/GEO, deploy→drift baseline+Google APIs.
  Где НЕ нужен — проекты без публичной веб-поверхности (internal tool, library, CLI).
- Coexistence: хуки idea-to-deploy + 1 хук Claude SEO (schema-валидация на
  каждом Edit/Write; нужен node+Python-деп); гейты (`/review`, `/test`, DoD) и
  строка-решение остаются явными.
- Файлы не создаются и не меняются.

## Fixture status

`pending` — snapshot-стаб (тот же бакет, что fixture-15-advisor,
fixture-21-mcp-docs, fixture-26-caveman, fixture-27-context-mode-setup):
read-only, detect/advise stdout-вывод. Полная автоматизация — Phase 2.

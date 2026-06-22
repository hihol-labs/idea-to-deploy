# Fixture 24 — /obsidian-export

Генерация Obsidian-слоя знаний из канонических артефактов проекта.

## Context

Пользователь ведёт планирование в idea-to-deploy (`LAUNCH_PLAN.md`, `BACKLOG.md`,
`STATE.json`, `HANDOFF.md`) и хочет локальный Obsidian-граф знаний для работы в
vault. Проверяется local-export-write режим: канон остаётся в source-документах,
генерируется производный набор заметок в `.itd-integrations/obsidian/`, секреты
не попадают в экспорт.

## Input prompt

Сделай экспорт в obsidian: собери граф знаний проекта из плановых документов и
памяти. Канон не трогай — это должна быть перегенерируемая выгрузка.

## Expected behavior

- Подтверждается адаптация (`CLAUDE.md`, memory-dir со `STATE.json`).
- Генерируется набор в `.itd-integrations/obsidian/`: `PROJECT_INDEX.md`,
  `KNOWLEDGE_GRAPH.md`, `STATE.md`, `DECISIONS.md`, `GATES.md` + копии плановых/память.
- Wikilinks `[[...]]`, embed `![[KNOWLEDGE_GRAPH]]`, callouts, frontmatter-теги `itd/*`.
- Канонические документы НЕ изменяются (правки — в source, потом перегенерация).
- Секреты/креды/приватные данные НЕ попадают в экспорт.
- Вывод по форме: OBSIDIAN EXPORT / ENTRYPOINT / NOTES / SOURCE ARTIFACTS /
  REGENERATE COMMAND / NEXT ACTION.

## Fixture status

`pending` — snapshot-стаб (тот же бакет, что fixture-15-advisor): генерируемый
вывод в `.itd-integrations/obsidian/` + stdout. Полная автоматизация — Phase 2.

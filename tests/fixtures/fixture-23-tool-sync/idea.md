# Fixture 23 — /tool-sync

Синхронизация плана проекта во внешний инструмент (Notion) с export-fallback.

## Context

Команда ведёт планирование в idea-to-deploy (`LAUNCH_PLAN.md`, `BACKLOG.md`,
`STATE.json`), и нужно зеркалировать статус в Notion для стейкхолдеров.
Проверяется explicit-invocation режим (external-write): connector-native чтение
до записи (не затирать внешние правки вслепую), при отсутствии/неодобрении
live-доступа — export-only в `.itd-integrations/`, секреты не уходят наружу.

## Input prompt

/tool-sync: синхронизируй с notion текущий план и статус из LAUNCH_PLAN.md и
BACKLOG.md. Не затирай правки, которые там уже сделала команда.

## Expected behavior

- Определяются source-артефакты (`LAUNCH_PLAN.md`, `BACKLOG.md`, `STATE.json`).
- Connector-native чтение Notion ДО записи — внешние правки сохраняются (reconcile,
  не overwrite вслепую).
- Если live-доступ недоступен/не одобрен — export-only в
  `.itd-integrations/notion.json` с явной пометкой режима.
- Секреты/приватные данные/креды НЕ синкаются.
- Результат синка фиксируется в `STATE.json`/отчёте, если влияет на статус.
- Вывод по форме: SYNC TARGET / SOURCE ARTIFACTS / MODE / CHANGES /
  UNSYNCED ITEMS / NEXT ACTION.

## Fixture status

`pending` — snapshot-стаб (тот же бакет, что fixture-15-advisor): зависит от
внешнего коннектора и stdout. Полная автоматизация — Phase 2.

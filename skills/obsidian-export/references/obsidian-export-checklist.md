# Obsidian Export — Checklist

Чеклист для генерации опционального Obsidian-слоя знаний из канонических
артефактов idea-to-deploy. Слой — **производный, локальный, безопасно
перегенерируемый**.

> Канонические артефакты остаются в корне проекта и в memory-dir. Obsidian-слой
> в `.itd-integrations/obsidian/` — это сгенерированный вывод; ручные правки
> делаются в source-документах, потом экспорт перегенерируется.

## Source-артефакты

- Плановые: `DISCOVERY.md`, `PRD.md`, `LAUNCH_PLAN.md`, `BACKLOG.md`,
  `ARCHITECTURE.md`, `STRATEGIC_PLAN.md`, `MARKET_BRIEF.md` и связанные.
- Память: `MEMORY.md`, `session_YYYY-MM-DD.md`, `STATE.json` (memory-dir).
- Контракты: `.itd/SCOPE_LOCK.md`, `.itd/GOLDEN_FLOWS.md`, `.itd/PROJECT_CONTRACT.md`.
- Передача: `HANDOFF.md`.

## Процедура

1. Подтверди адаптацию idea-to-deploy: `CLAUDE.md`, memory-dir со `STATE.json`,
   плановые документы.
2. Сгенерируй vault-ready набор заметок в `.itd-integrations/obsidian/`.
3. Точка входа — `.itd-integrations/obsidian/PROJECT_INDEX.md`.
4. Проверь, что экспорт содержит:
   - `PROJECT_INDEX.md`
   - `KNOWLEDGE_GRAPH.md`
   - `STATE.md`
   - `DECISIONS.md`
   - `GATES.md`
   - скопированные плановые/память заметки для существующих source-артефактов
5. Канонические правки — в source-документах idea-to-deploy, затем перегенерация.

## Obsidian Markdown — правила

- `[[wikilinks]]` для ссылок между сгенерированными заметками.
- `![[KNOWLEDGE_GRAPH]]` для встраивания графа в `PROJECT_INDEX.md`.
- Callouts для next action, блокеров, рисков, source-заметок.
- Frontmatter-теги: `itd/project`, `itd/planning`, `itd/memory`, `itd/graph`.
- **Не синкать** секреты, креды, приватные данные клиентов, production-дампы.

## Форма вывода

```text
OBSIDIAN EXPORT:
ENTRYPOINT:
NOTES:
SOURCE ARTIFACTS:
REGENERATE COMMAND:
NEXT ACTION:
```

## Правила

- `.itd-integrations/obsidian/` — сгенерированный вывод.
- Не делать Obsidian-синтаксис обязательным для канонических документов idea-to-deploy.
- Сохранять правки пользователя в канонических доках; перегенерировать экспорт,
  а не править сгенерированные заметки руками.
- Если пользователь даёт путь к реальному vault — спросить перед записью вне проекта.

## Self-validation (перед выводом)

- [ ] Адаптация idea-to-deploy подтверждена (`CLAUDE.md`, `STATE.json`).
- [ ] Экспорт содержит PROJECT_INDEX/KNOWLEDGE_GRAPH/STATE/DECISIONS/GATES + заметки.
- [ ] Wikilinks/embeds/callouts/frontmatter-теги проставлены.
- [ ] Секреты/приватные данные не попали в экспорт.
- [ ] Канон не тронут; экспорт перегенерируем.

---
name: obsidian-export
description: 'Export idea-to-deploy planning docs, handoff, memory, state, decisions, and gates into an Obsidian-compatible local knowledge graph. Derived, regenerable output under .itd-integrations/obsidian/ — canonical docs stay the source of truth. Use when the user mentions Obsidian, vault, wikilinks, knowledge graph, or linked notes.'
argument-hint: project path, Obsidian vault/export request, knowledge graph, linked notes
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash
context: fork
metadata:
  effort: medium
  side_effect: local-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.21.0
  category: integration
  tags: [obsidian, markdown, knowledge-graph, memory, export]
---

# Obsidian Export

## Trigger phrases

- obsidian vault, граф знаний, связанные заметки
- выгрузи в обсидиан, экспорт в obsidian, vault-заметки
- obsidian export, knowledge graph, linked notes
- export to vault, project vault, obsidian notes

## Recommended model

**Sonnet** — производная генерация заметок из существующих артефактов
(копирование + проставление wikilinks/тегов) механична. Opus избыточен.

## Instructions

Создай опциональный Obsidian-слой знаний из канонических артефактов
idea-to-deploy. Подробный чеклист — в `references/obsidian-export-checklist.md`.

> Канон остаётся в source-документах (корень проекта + memory-dir). Слой в
> `.itd-integrations/obsidian/` — **производный, локальный, перегенерируемый**.
> Ручные правки делаются в source, потом экспорт перегенерируется — не правь
> сгенерированные заметки руками.

### Source-артефакты

- Плановые: `DISCOVERY.md`, `PRD.md`, `LAUNCH_PLAN.md`, `BACKLOG.md`,
  `ARCHITECTURE.md`, `STRATEGIC_PLAN.md`, `MARKET_BRIEF.md`.
- Память: `MEMORY.md`, `session_YYYY-MM-DD.md`, `STATE.json`.
- Контракты: `.itd/SCOPE_LOCK.md`, `.itd/GOLDEN_FLOWS.md`, `.itd/PROJECT_CONTRACT.md`.
- Передача: `HANDOFF.md`.

### Procedure

1. Подтверди адаптацию idea-to-deploy: `CLAUDE.md`, memory-dir со `STATE.json`,
   плановые документы.
2. Сгенерируй vault-ready набор в `.itd-integrations/obsidian/`.
3. Точка входа — `.itd-integrations/obsidian/PROJECT_INDEX.md`.
4. Проверь, что экспорт содержит: `PROJECT_INDEX.md`, `KNOWLEDGE_GRAPH.md`,
   `STATE.md`, `DECISIONS.md`, `GATES.md` + копии плановых/память заметок.
5. Канонические правки — в source-документах, затем перегенерация.

### Obsidian Markdown — правила

- `[[wikilinks]]` для ссылок между сгенерированными заметками.
- `![[KNOWLEDGE_GRAPH]]` для встраивания графа в `PROJECT_INDEX.md`.
- Callouts для next action, блокеров, рисков, source-заметок.
- Frontmatter-теги: `itd/project`, `itd/planning`, `itd/memory`, `itd/graph`.
- Не синкать секреты, креды, приватные данные клиентов, production-дампы.

### Output

```text
OBSIDIAN EXPORT:
ENTRYPOINT:
NOTES:
SOURCE ARTIFACTS:
REGENERATE COMMAND:
NEXT ACTION:
```

## Examples

### Example 1: Граф знаний из плановых документов
User: «Сделай экспорт в obsidian: собери граф знаний из плана и памяти.»

Actions:
1. Подтверждает адаптацию (`CLAUDE.md`, `STATE.json`).
2. Генерирует `.itd-integrations/obsidian/` с `PROJECT_INDEX.md`,
   `KNOWLEDGE_GRAPH.md`, `STATE.md`, `DECISIONS.md`, `GATES.md` + копии.
3. Проставляет wikilinks/embeds/callouts/`itd/*` теги. Канон не трогает.

### Example 2: Перегенерация после правки канона
User: «Обновил LAUNCH_PLAN.md, перегенери obsidian.»

Actions:
1. Перечитывает обновлённый source.
2. Перегенерирует экспорт (не правит сгенерированные заметки руками).
3. Заметки отражают изменение канона.

### Example 3: Реальный vault-путь
User: «Выгрузи в obsidian в мой vault `~/vaults/work`.»

Actions:
1. Спрашивает подтверждение перед записью ВНЕ проекта.
2. После согласия пишет туда; иначе — в `.itd-integrations/obsidian/`.
3. Не кладёт секреты в экспорт.

## Self-validation

Перед выводом убедись:
- [ ] Адаптация подтверждена (`CLAUDE.md`, `STATE.json`).
- [ ] Экспорт содержит PROJECT_INDEX/KNOWLEDGE_GRAPH/STATE/DECISIONS/GATES + заметки.
- [ ] Wikilinks/embeds/callouts/`itd/*` теги проставлены.
- [ ] Секреты/приватные данные не попали в экспорт.
- [ ] Канон не изменён; экспорт перегенерируем.
- [ ] При реальном vault-пути — спрошено подтверждение записи вне проекта.

## Troubleshooting

### Проект не адаптирован под idea-to-deploy
Нет `CLAUDE.md`/`STATE.json` — предложи сначала `/adopt`, затем экспорт. Не
выдумывай артефакты, которых нет.

### Пользователь правит сгенерированные заметки
Объясни: `.itd-integrations/obsidian/` — генерируемый вывод. Правки делаются в
source-документах, экспорт перегенерируется.

### Реальный внешний vault
Спроси перед записью вне проекта. По умолчанию пиши в `.itd-integrations/obsidian/`.

### Риск утечки секретов
Не клади секреты/креды/приватные данные/prod-дампы в экспорт.

## Rules

- `.itd-integrations/obsidian/` — генерируемый вывод.
- Obsidian-синтаксис не обязателен для канонических документов idea-to-deploy.
- Сохраняй правки пользователя в каноне; перегенерируй экспорт, а не правь заметки руками.
- Реальный vault-путь → спроси перед записью вне проекта.
- Не синкать секреты/приватные данные.
- **Match the user's language** для всего вывода.

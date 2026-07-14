---
name: tool-sync
description: 'Synchronize idea-to-deploy state with external planning and documentation tools — GitHub, Linear, Notion, Google Drive (Docs/Sheets/Slides), and local Obsidian vaults. Connector-native reads before writes, export-only fallback to .itd-integrations/. Explicit-invocation, external-write.'
argument-hint: target tool, project path, roadmap, plan, backlog, or status sync
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash
disable-model-invocation: false
metadata:
  effort: medium
  side_effect: external-write
  explicit_invocation: true
  author: HiH-DimaN
  version: 1.21.0
  category: integration
  tags: [linear, notion, google-drive, obsidian, sync, integration]
---

# Tool Sync

## Trigger phrases

- синхронизируй с notion, синк в linear, экспорт в obsidian
- синк с google drive, синхронизация с внешним, tool sync
- sync to notion, sync with linear, export to obsidian
- mirror to google drive, sync roadmap, sync project state

## Recommended model

**Sonnet** — маппинг артефактов на внешние схемы и reconcile-логика
структурированы; глубокое рассуждение не требуется. Haiku допустим для простого
export-only payload.

## Instructions

Используй этот скилл, когда артефакты idea-to-deploy нужно синхронизировать с
внешним инструментом планирования/документации. Подробный чеклист — в
`references/tool-sync-checklist.md`.

> **Explicit-invocation** (`metadata.explicit_invocation: true`; Codex policy
> `allow_implicit_invocation: false`). Вызывается явно
> через `/tool-sync`. Несёт `external-write` — изменения live-систем выполняются
> **только по явной просьбе** пользователя; иначе export-only.

### Targets

- **GitHub:** issues, labels, milestones, контекст PR (см. также `/github-workflow`).
- **Linear:** проекты, issues, workflow-состояния, блокеры.
- **Notion:** страницы проектов, базы задач, decision logs.
- **Google Drive:** Docs, Sheets, Slides, project briefs, summary для стейкхолдеров.
- **Obsidian:** локальные vault-ready Markdown-заметки (предпочитай `/obsidian-export`).

### Procedure

1. Определи source-артефакты: `STATE.json`, `MEMORY.md`, `session_YYYY-MM-DD.md`,
   `HANDOFF.md`, `LAUNCH_PLAN.md`, `BACKLOG.md`, `PRD.md`, плановые документы.
2. Определи target-коннектор и доступен ли live write-доступ.
3. Сначала connector-native чтение, потом запись — чтобы не затереть внешнее состояние вслепую.
4. Если live-синк недоступен/не одобрен — экспортируй payload в
   `.itd-integrations/<target>.json` (или `.itd-integrations/obsidian/` для vault).
5. Зафиксируй результат синка в `STATE.json`/финальном отчёте, когда он влияет на статус.

### Output

```text
SYNC TARGET:
SOURCE ARTIFACTS:
MODE: live | export-only | read-only
CHANGES:
UNSYNCED ITEMS:
NEXT ACTION:
```

## Examples

### Example 1: Зеркалирование плана в Notion (reconcile)
User: «/tool-sync: синхронизируй с notion план из LAUNCH_PLAN.md, не затирай правки команды.»

Actions:
1. Читает `LAUNCH_PLAN.md`/`BACKLOG.md`/`STATE.json`.
2. Connector-native чтение Notion ДО записи — сохраняет внешние правки (reconcile).
3. Пишет только дельту (по явной просьбе); фиксирует результат в `STATE.json`.

### Example 2: Live-доступ недоступен (export-only)
User: «/tool-sync: синк в linear», но коннектор Linear недоступен.

Actions:
1. MODE = export-only.
2. Пишет `.itd-integrations/linear.json`.
3. Явно сообщает, что live-синк не выполнялся, и что нужно для live.

### Example 3: Экспорт в Obsidian
User: «/tool-sync: экспорт в obsidian текущий статус.»

Actions:
1. Предпочитает `/obsidian-export` для самого экспорта в vault.
2. Трактует `.itd-integrations/obsidian/` как сгенерированный вывод (канон — в
   source-документах idea-to-deploy).

## Self-validation

Перед выводом убедись:
- [ ] Source-артефакты определены; target-коннектор и доступ оценены.
- [ ] Connector-native чтение сделано до записи (внешнее не затёрто вслепую).
- [ ] Live-изменения — только по явной просьбе; иначе export-only в `.itd-integrations/`.
- [ ] Секреты/приватные данные не ушли во внешний инструмент.
- [ ] `LAUNCH_PLAN.md`/`BACKLOG.md` остались каноном (если пользователь не сделал инструмент авторитетным).
- [ ] Результат синка зафиксирован в `STATE.json`/отчёте, если влияет на статус.

## Troubleshooting

### Коннектор недоступен / не одобрен
Переходи в export-only: payload в `.itd-integrations/<target>.json`, явная
пометка MODE. Не делай вид, что синк выполнен.

### Во внешнем инструменте есть правки команды
Reconcile, а не overwrite вслепую: сначала прочитай внешнее состояние, потом
сливай дельту. Конфликты выводи в UNSYNCED ITEMS.

### Пользователь хочет сделать внешний инструмент авторитетным
Это допустимо только по явному указанию. По умолчанию канон — `LAUNCH_PLAN.md`/`BACKLOG.md`.

### Риск утечки секретов
Никогда не синкай секреты/креды/приватные данные клиентов в планировочные
инструменты. Обезличь перед синком.

## Rules

- **Explicit-invocation** — вызывается явно; не авто-роутится.
- **Спрашивай перед изменением live-систем**, если не было явной просьбы.
- **Reconcile, не overwrite** — сохраняй внешние правки пользователя.
- **Не синкать секреты/приватные данные/креды.**
- **Export под `.itd-integrations/`**; `obsidian/` — генерируемый вывод.
- **Канон — `LAUNCH_PLAN.md`/`BACKLOG.md`**, если не сказано иначе.
- **Match the user's language** для всего вывода.

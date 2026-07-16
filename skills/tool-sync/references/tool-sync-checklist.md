# Tool Sync — Checklist

Чеклист для синхронизации артефактов idea-to-deploy с внешними инструментами
планирования и документации: GitHub, Linear, Notion, Google Drive
(Docs/Sheets/Slides), локальный Obsidian-vault.

> **Explicit-invocation скилл** (`metadata.explicit_invocation: true`). Вызывается
> явно через `/tool-sync`, не авто-роутится — несёт `external-write` (запись во
> внешние системы). Изменения live-систем — только по явной просьбе пользователя.

## Цели синка

- **GitHub:** issues, labels, milestones, контекст PR (см. также `/github-workflow`).
- **Linear:** проекты, issues, workflow-состояния, блокеры.
- **Notion:** страницы проектов, базы задач, decision logs.
- **Google Drive:** Docs, Sheets, Slides, project briefs, summary для стейкхолдеров.
- **Obsidian:** локальные vault-ready Markdown-заметки, вики-ссылки, callouts,
  граф знаний проекта (предпочитай `/obsidian-export` для самого экспорта).

## Процедура

1. **Определи source-артефакты:** `STATE.json`, `MEMORY.md`,
   `session_YYYY-MM-DD.md`, `HANDOFF.md`, `LAUNCH_PLAN.md`, `BACKLOG.md`,
   `PRD.md`, плановые документы.
2. **Определи target-коннектор** и доступен ли live write-доступ.
3. **Сначала connector-native чтение**, потом запись — чтобы не затереть вслепую
   существующее внешнее состояние.
4. **Если live-синк недоступен или не одобрен** — экспортируй payload в
   `.itd-integrations/<target>.json` (или `.itd-integrations/obsidian/` для vault).
5. **Зафиксируй результат** синка в `STATE.json` или финальном отчёте, когда синк
   влияет на статус проекта.

## Форма вывода

```text
SYNC TARGET:
SOURCE ARTIFACTS:
MODE: live | export-only | read-only
CHANGES:
UNSYNCED ITEMS:
NEXT ACTION:
```

## Правила

- **Спрашивай перед изменением live-систем**, если пользователь явно не попросил.
- **Сохраняй внешние правки пользователя** — reconcile, а не overwrite вслепую.
- **Не синкать секреты**, приватные данные клиентов или креды в планировочные инструменты.
- Держи экспортированные payload'ы под `.itd-integrations/`.
- `.itd-integrations/obsidian/` — это **сгенерированный вывод**; канонические
  правки живут в source-документах idea-to-deploy.
- `LAUNCH_PLAN.md` / `BACKLOG.md` — канонический источник плана, если пользователь
  явно не сделал внешний инструмент авторитетным.

## Self-validation (перед выводом)

- [ ] Source-артефакты определены; target-коннектор и доступ оценены.
- [ ] Connector-native чтение сделано до записи (внешнее не затёрто вслепую).
- [ ] Live-изменения — только по явной просьбе; иначе export-only в `.itd-integrations/`.
- [ ] Секреты/приватные данные не ушли во внешний инструмент.
- [ ] Результат синка зафиксирован в `STATE.json`/отчёте, если влияет на статус.
